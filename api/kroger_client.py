import os
import time

import requests

TOKEN_URL = "https://api.kroger.com/v1/connect/oauth2/token"
API_BASE = "https://api.kroger.com/v1"

_token_cache = {"access_token": None, "expires_at": 0}


def _get_token() -> str:
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 30:
        return _token_cache["access_token"]

    resp = requests.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials", "scope": "product.compact"},
        auth=(os.environ["KROGER_CLIENT_ID"], os.environ["KROGER_CLIENT_SECRET"]),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = now + data["expires_in"]
    return _token_cache["access_token"]


def _headers():
    return {"Accept": "application/json", "Authorization": f"Bearer {_get_token()}"}


def search_products(term: str, location_id: str, limit: int = 3):
    """Live product+price lookup for a specific Kroger-family store location."""
    resp = requests.get(
        f"{API_BASE}/products",
        params={
            "filter.term": term,
            "filter.locationId": location_id,
            "filter.limit": limit,
        },
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()

    results = []
    for product in resp.json().get("data", []):
        items = product.get("items") or []
        price = None
        for item in items:
            price_info = item.get("price") or {}
            price = price_info.get("promo") or price_info.get("regular")
            if price:
                break
        if not price:
            continue
        results.append({"product_name": product.get("description"), "price": float(price)})
    return results


def nearby_locations(lat: float, lon: float, radius_miles: int = 10, limit: int = 5):
    resp = requests.get(
        f"{API_BASE}/locations",
        params={
            "filter.lat.near": lat,
            "filter.lon.near": lon,
            "filter.radiusInMiles": radius_miles,
            "filter.limit": limit,
        },
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()

    results = []
    for loc in resp.json().get("data", []):
        address = loc.get("address") or {}
        results.append({
            "location_id": loc.get("locationId"),
            "chain": loc.get("chain"),
            "name": loc.get("name"),
            "address": ", ".join(
                filter(None, [address.get("addressLine1"), address.get("city"), address.get("state")])
            ),
        })
    return results
