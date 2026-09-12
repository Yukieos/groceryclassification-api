import argparse
import csv

from db import get_connection, normalize


def import_csv(path: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE source = 'manual'")

    count = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            full_name = (row.get("full_name") or "").strip()
            vendor = (row.get("vendor") or "").strip()
            price_raw = (row.get("unit_price") or "").strip()
            if not full_name or not vendor or not price_raw:
                continue
            try:
                price = float(price_raw)
            except ValueError:
                continue

            normalized = (row.get("normalized_name") or "").strip() or normalize(full_name)
            cur.execute(
                """
                INSERT INTO products (source, vendor, full_name, normalized_name, category, unit_price)
                VALUES ('manual', %s, %s, %s, %s, %s)
                """,
                (vendor, full_name, normalized, row.get("category"), price),
            )
            count += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Imported {count} rows from {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import manually-collected prices (e.g. cleaned_price.csv)")
    parser.add_argument("csv_path")
    args = parser.parse_args()
    import_csv(args.csv_path)
