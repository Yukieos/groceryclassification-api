import argparse
import csv

from db import get_connection, normalize, record_price_observation
from gemini_embed import embed_text
from size_parse import parse_pack_size


def import_csv(path: str, embed: bool = True):
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
            pack_qty, pack_unit = parse_pack_size(full_name)

            embedding = None
            if embed:
                try:
                    embedding = embed_text(full_name, task_type="RETRIEVAL_DOCUMENT")
                except Exception as e:
                    print(f"  embedding failed for {full_name!r}: {e}")

            cur.execute(
                """
                INSERT INTO products (source, vendor, full_name, normalized_name, category, unit_price, pack_qty, pack_unit, embedding)
                VALUES ('manual', %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (vendor, full_name, normalized, row.get("category"), price, pack_qty, pack_unit, embedding),
            )
            record_price_observation(cur, normalized, vendor, "manual", price)
            count += 1
            if count % 50 == 0:
                print(f"  ...{count} rows imported")

    conn.commit()
    cur.close()
    conn.close()
    print(f"Imported {count} rows from {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import manually-collected prices (e.g. cleaned_price.csv)")
    parser.add_argument("csv_path")
    parser.add_argument("--no-embed", action="store_true", help="Skip embedding generation (faster, lexical-only search)")
    args = parser.parse_args()
    import_csv(args.csv_path, embed=not args.no_embed)
