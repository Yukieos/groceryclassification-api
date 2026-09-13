from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import kroger_client
from db import get_connection, normalize, record_price_observation, search_price, thirty_day_low
from gemini_client import infer_category
from rate_limit import check_and_increment
from size_parse import unit_price_info

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

INFER_RATE_LIMIT = 20  # per client per hour - Gemini calls cost money


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


@app.post("/infer")
async def infer(request: Request, photo: UploadFile = File(...)):
    if photo.content_type.split("/")[0] != "image":
        raise HTTPException(400, "Only image uploads are supported.")

    try:
        allowed = check_and_increment(_client_key(request), limit=INFER_RATE_LIMIT, window_minutes=60)
    except Exception:
        allowed = True  # don't block real requests if the rate-limit table itself has a problem
    if not allowed:
        raise HTTPException(429, f"Rate limit exceeded ({INFER_RATE_LIMIT} photo lookups/hour). Try again later.")

    img_bytes = await photo.read()
    try:
        return infer_category(img_bytes, mime_type=photo.content_type)
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


@app.get("/search_price")
def search_price_endpoint(q: str = Query(...)):
    try:
        return search_price(q)
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


@app.get("/nearby_stores")
def nearby_stores(lat: float, lon: float):
    """Finds nearby Kroger-family stores for a given browser/device location.

    Trader Joe's has no public geo-search API, so its store is configured
    once (by store code) rather than looked up automatically here.
    """
    try:
        kroger = kroger_client.nearby_locations(lat, lon)
    except Exception as e:
        kroger = {"error": str(e), "type": type(e).__name__}
    return {"kroger": kroger}


class ShoppingListRequest(BaseModel):
    items: List[str]
    kroger_location_id: Optional[str] = None


@app.post("/shopping_list")
def shopping_list(payload: ShoppingListRequest):
    per_item_matches = {}
    all_vendors = set()

    for term in payload.items:
        matches = search_price(term, limit=10)

        if payload.kroger_location_id:
            try:
                kroger_matches = kroger_client.search_products(term, payload.kroger_location_id, limit=3)
            except Exception:
                kroger_matches = []

            if kroger_matches:
                conn = get_connection()
                try:
                    cur = conn.cursor()
                    for kroger_match in kroger_matches:
                        per_unit_price, per_unit_label = unit_price_info(
                            kroger_match["price"], kroger_match.get("pack_qty"), kroger_match.get("pack_unit")
                        )
                        normalized = normalize(kroger_match["product_name"])
                        record_price_observation(cur, normalized, "Kroger", "kroger", kroger_match["price"])
                        low_30d = thirty_day_low(cur, normalized, "Kroger")
                        matches.append({
                            "product_name": kroger_match["product_name"],
                            "vendor": "Kroger",
                            "price": kroger_match["price"],
                            "similarity": None,
                            "price_per_unit": per_unit_price,
                            "price_per_unit_label": per_unit_label,
                            "thirty_day_low": low_30d,
                            "is_thirty_day_low": low_30d is not None and kroger_match["price"] <= low_30d,
                        })
                    conn.commit()
                finally:
                    conn.close()

        matches.sort(key=lambda m: m["price"])
        per_item_matches[term] = matches
        all_vendors.update(m["vendor"] for m in matches)

    per_item_best = {
        term: (matches[0] if matches else None)
        for term, matches in per_item_matches.items()
    }

    vendor_totals = {
        vendor: {"subtotal": 0.0, "covered_items": [], "missing_items": []}
        for vendor in all_vendors
    }
    for term, matches in per_item_matches.items():
        cheapest_by_vendor = {}
        for m in matches:
            if m["vendor"] not in cheapest_by_vendor or m["price"] < cheapest_by_vendor[m["vendor"]]:
                cheapest_by_vendor[m["vendor"]] = m["price"]
        for vendor in all_vendors:
            if vendor in cheapest_by_vendor:
                vendor_totals[vendor]["subtotal"] += cheapest_by_vendor[vendor]
                vendor_totals[vendor]["covered_items"].append(term)
            else:
                vendor_totals[vendor]["missing_items"].append(term)

    one_stop_ranking = sorted(
        (
            {
                "vendor": vendor,
                "subtotal": round(totals["subtotal"], 2),
                "covers_all_items": len(totals["missing_items"]) == 0,
                "covered_items": totals["covered_items"],
                "missing_items": totals["missing_items"],
            }
            for vendor, totals in vendor_totals.items()
        ),
        key=lambda v: (not v["covers_all_items"], v["subtotal"]),
    )

    return {
        "per_item_best": per_item_best,
        "per_item_options": per_item_matches,
        "one_stop_ranking": one_stop_ranking,
    }
