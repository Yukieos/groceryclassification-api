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

def normalize(text):
    return ''.join(c for c in text.lower() if c.isalnum())

@app.get("/search_price")
def search_price(q: str = Query(...)):
    norm_q = normalize(q)
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db-foodprice.cs76a4esi9a9.us-east-1.rds.amazonaws.com"),
        dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ.get("DB_USER", "yukieos"),
        password=os.environ.get("DB_PASSWORD", "drinkmoretea1"),
        port=5432,
        sslmode="require"
    )
    cur = conn.cursor()
    cur.execute(
        """
        SELECT full_name, vendor, unit_price,
               similarity(normalized_name, %s) AS sim
        FROM products
        WHERE normalized_name %% %s
        ORDER BY sim DESC, unit_price ASC
        LIMIT 5
        """,
        (norm_q, norm_q)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"product_name": r[0], "vendor": r[1], "price": r[2], "similarity": round(r[3], 2)}
        for r in rows
    ]
