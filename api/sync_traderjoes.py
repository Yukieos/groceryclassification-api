import argparse

from db import get_connection, normalize
from traderjoes_client import fetch_store_catalog


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
        cur.execute(
            """
            INSERT INTO products (source, vendor, store_code, full_name, normalized_name, unit_price)
            VALUES ('trader_joes', %s, %s, %s, %s, %s)
            """,
            (vendor_label, store_code, title, normalize(title), float(price)),
        )
        inserted += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Synced {inserted} in-stock items for Trader Joe's store {store_code}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync one Trader Joe's store's catalog into Postgres")
    parser.add_argument("store_code", help="Trader Joe's store code, e.g. 701")
    parser.add_argument("--vendor-label", default="Trader Joe's")
    args = parser.parse_args()
    sync(args.store_code, args.vendor_label)
