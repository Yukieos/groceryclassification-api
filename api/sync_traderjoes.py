import argparse

from db import get_connection, normalize, record_price_observation
from size_parse import parse_pack_size
from traderjoes_client import fetch_store_catalog

# User's NYC stores (from traderjoes.com store locator), so a plain
# `python sync_traderjoes.py --nyc` syncs all of them with readable vendor
# labels instead of bare store codes.
NYC_STORES = {
    "542": "Trader Joe's - 72nd & Broadway",
    "543": "Trader Joe's - Chelsea",
    "546": "Trader Joe's - East Village",
    "538": "Trader Joe's - Essex Crossing",
    "576": "Trader Joe's - Harlem",
    "544": "Trader Joe's - Murray Hill",
    "539": "Trader Joe's - SoHo",
    "540": "Trader Joe's - Union Square",
    "571": "Trader Joe's - Upper East Side",
    "545": "Trader Joe's - Upper West Side",
}


def sync(store_code: str, vendor_label: str = "Trader Joe's"):
    items = fetch_store_catalog(store_code)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM products WHERE source = 'trader_joes' AND store_code = %s",
        (store_code,),
    )

    inserted = 0
    for item in items:
        if not item.get("availability"):
            continue
        title = item.get("item_title")
        price = item.get("retail_price")
        if not title or not price:
            continue
        size_text = " ".join(filter(None, [item.get("sales_size"), item.get("sales_uom_description")]))
        pack_qty, pack_unit = parse_pack_size(size_text) if size_text else (None, None)
        if pack_qty is None:
            pack_qty, pack_unit = parse_pack_size(title)
        cur.execute(
            """
            INSERT INTO products (source, vendor, store_code, full_name, normalized_name, unit_price, pack_qty, pack_unit)
            VALUES ('trader_joes', %s, %s, %s, %s, %s, %s, %s)
            """,
            (vendor_label, store_code, title, normalize(title), float(price), pack_qty, pack_unit),
        )
        record_price_observation(cur, normalize(title), vendor_label, "trader_joes", float(price))
        inserted += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Synced {inserted} in-stock items for {vendor_label} (store {store_code})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync one or more Trader Joe's stores' catalogs into Postgres")
    parser.add_argument("store_codes", nargs="*", help="Trader Joe's store code(s), e.g. 701 706")
    parser.add_argument("--vendor-label", default=None, help="Only used with a single store_code")
    parser.add_argument("--nyc", action="store_true", help="Sync all of the user's configured NYC stores")
    args = parser.parse_args()

    if args.nyc:
        for code, label in NYC_STORES.items():
            sync(code, label)
    elif args.store_codes:
        for code in args.store_codes:
            label = args.vendor_label or NYC_STORES.get(code, "Trader Joe's")
            sync(code, label)
    else:
        parser.error("Provide store_codes, or use --nyc")
