import os
import psycopg2

from size_parse import unit_price_info


def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        port=os.environ.get("DB_PORT", 5432),
        sslmode="require",
    )


def normalize(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


def search_price(term: str, limit: int = 5):
    term_lower = term.lower().strip()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT full_name, vendor, unit_price, pack_qty, pack_unit,
                   strict_word_similarity(%s, lower(full_name)) AS sim
            FROM products
            WHERE %s <<%% lower(full_name)
            ORDER BY
                (lower(category) = %s) DESC,
                sim DESC,
                length(full_name) ASC,
                unit_price ASC
            LIMIT %s
            """,
            (term_lower, term_lower, term_lower, limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    results = []
    for full_name, vendor, price, pack_qty, pack_unit, sim in rows:
        price = float(price)
        pack_qty = float(pack_qty) if pack_qty is not None else None
        per_unit_price, per_unit_label = unit_price_info(price, pack_qty, pack_unit)
        results.append({
            "product_name": full_name,
            "vendor": vendor,
            "price": price,
            "similarity": round(sim, 2),
            "price_per_unit": per_unit_price,
            "price_per_unit_label": per_unit_label,
        })
    return results
