import os
import psycopg2
from pgvector.psycopg2 import register_vector

from gemini_embed import embed_text
from size_parse import unit_price_info

VECTOR_MIN_SIMILARITY = 0.55


def get_connection():
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        port=os.environ.get("DB_PORT", 5432),
        sslmode="require",
    )
    register_vector(conn)
    return conn


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


_ROW_FIELDS = "id, full_name, vendor, unit_price, pack_qty, pack_unit, normalized_name, source, category"


def search_price(term: str, limit: int = 5):
    term_lower = term.lower().strip()
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Lexical pass: trigram/word similarity - catches typos and
        # substring matches, and is what the category-exact-match boost
        # below relies on.
        cur.execute(
            f"""
            SELECT {_ROW_FIELDS}, strict_word_similarity(%s, lower(full_name)) AS sim
            FROM products
            WHERE %s <<%% lower(full_name)
            """,
            (term_lower, term_lower),
        )
        lexical_rows = {row[0]: {"row": row[1:-1], "sim": row[-1], "vec_sim": 0.0} for row in cur.fetchall()}

        # Semantic pass: catches synonyms/abbreviations trigram similarity
        # can't ("OJ" -> "orange juice") that share no characters at all.
        try:
            query_vec = embed_text(term, task_type="RETRIEVAL_QUERY")
            cur.execute(
                f"""
                SELECT {_ROW_FIELDS}, 1 - (embedding <=> %s::vector) AS vec_sim
                FROM products
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_vec, query_vec, limit * 4),
            )
            for row in cur.fetchall():
                pid, vec_sim = row[0], row[-1]
                if vec_sim < VECTOR_MIN_SIMILARITY:
                    continue
                if pid in lexical_rows:
                    lexical_rows[pid]["vec_sim"] = max(lexical_rows[pid]["vec_sim"], vec_sim)
                else:
                    lexical_rows[pid] = {"row": row[1:-1], "sim": 0.0, "vec_sim": vec_sim}
        except Exception:
            conn.rollback()  # don't let a failed vector query poison the rest of this transaction
            cur = conn.cursor()  # bonus signal only - lexical search alone still works fine

        candidates = list(lexical_rows.values())
        candidates.sort(
            key=lambda c: (
                (c["row"][7] or "").lower() != term_lower,  # category exact match first
                -max(c["sim"], c["vec_sim"]),
                len(c["row"][0]),
                c["row"][2],
            )
        )
        candidates = candidates[:limit]

        results = []
        for c in candidates:
            full_name, vendor, price, pack_qty, pack_unit, normalized_name, source, category = c["row"]
            price = float(price)
            pack_qty = float(pack_qty) if pack_qty is not None else None
            per_unit_price, per_unit_label = unit_price_info(price, pack_qty, pack_unit)

            record_price_observation(cur, normalized_name, vendor, source, price)
            low_30d = thirty_day_low(cur, normalized_name, vendor)

            results.append({
                "product_name": full_name,
                "vendor": vendor,
                "price": price,
                "similarity": round(max(c["sim"], c["vec_sim"]), 2),
                "price_per_unit": per_unit_price,
                "price_per_unit_label": per_unit_label,
                "thirty_day_low": low_30d,
                "is_thirty_day_low": low_30d is not None and price <= low_30d,
            })
        conn.commit()
    finally:
        conn.close()
    return results
