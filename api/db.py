import os
import psycopg2


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
            SELECT full_name, vendor, unit_price,
                   strict_word_similarity(%s, lower(full_name)) AS sim
            FROM products
            WHERE %s <<%% lower(full_name)
            ORDER BY sim DESC, unit_price ASC
            LIMIT %s
            """,
            (term_lower, term_lower, limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "product_name": row[0],
            "vendor": row[1],
            "price": float(row[2]),
            "similarity": round(row[3], 2),
        }
        for row in rows
    ]
