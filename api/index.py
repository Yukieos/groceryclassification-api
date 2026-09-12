from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/search_price")
def search_price(q: str = Query(...)):
    try:
        q_lower = q.lower().strip()
        conn = psycopg2.connect(
            host=os.environ["DB_HOST"],
            dbname=os.environ.get("DB_NAME", "postgres"),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            port=os.environ.get("DB_PORT", 5432),
            sslmode="require"
        )
        cur = conn.cursor()
        cur.execute(
            """
            SELECT full_name, vendor, unit_price,
                   strict_word_similarity(%s, lower(full_name)) AS sim
            FROM products
            WHERE %s <<%%  lower(full_name)
            ORDER BY sim DESC, unit_price ASC
            LIMIT 5
            """,
            (q_lower, q_lower)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {"product_name": r[0], "vendor": r[1], "price": r[2], "similarity": round(r[3], 2)}
            for r in rows
        ]
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}
