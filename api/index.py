from typing import List, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import kroger_client
from db import search_price

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


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
                for kroger_match in kroger_client.search_products(term, payload.kroger_location_id, limit=3):
                    matches.append({
                        "product_name": kroger_match["product_name"],
                        "vendor": "Kroger",
                        "price": kroger_match["price"],
                        "similarity": None,
                    })
            except Exception:
                pass

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
