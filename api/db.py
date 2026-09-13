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


def record_price_observation(cur, normalized_name: str, vendor: str, source: str, price: float):
    """Logs one (product, vendor, day) price point, keeping the latest price
    seen that day if called more than once. Called both from batch imports
    and from live search traffic, so history builds up from real usage
    without needing a separate scraping/cron job."""
    cur.execute(
        """
        INSERT INTO price_history (normalized_name, vendor, source, price)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (normalized_name, vendor, observed_date)
        DO UPDATE SET price = EXCLUDED.price
        """,
        (normalized_name, vendor, source, price),
    )


def thirty_day_low(cur, normalized_name: str, vendor: str):
    cur.execute(
        """
        SELECT MIN(price) FROM price_history
        WHERE normalized_name = %s AND vendor = %s
          AND observed_date >= CURRENT_DATE - INTERVAL '30 days'
        """,
        (normalized_name, vendor),
    )
    row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else None


def search_price(term: str, limit: int = 5):
    term_lower = term.lower().strip()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT full_name, vendor, unit_price, pack_qty, pack_unit, normalized_name, source,
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

        results = []
        for full_name, vendor, price, pack_qty, pack_unit, normalized_name, source, sim in rows:
            price = float(price)
            pack_qty = float(pack_qty) if pack_qty is not None else None
            per_unit_price, per_unit_label = unit_price_info(price, pack_qty, pack_unit)

            record_price_observation(cur, normalized_name, vendor, source, price)
            low_30d = thirty_day_low(cur, normalized_name, vendor)

            results.append({
                "product_name": full_name,
                "vendor": vendor,
                "price": price,
                "similarity": round(sim, 2),
                "price_per_unit": per_unit_price,
                "price_per_unit_label": per_unit_label,
                "thirty_day_low": low_30d,
                "is_thirty_day_low": low_30d is not None and price <= low_30d,
            })
        conn.commit()
    finally:
        conn.close()
    return results
