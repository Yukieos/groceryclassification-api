from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import os
from utils import normalize

app = FastAPI(
    title="Grocery Price Search API",
    description="Search for grocery prices by name."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/search_price")
def search_price(q: str = Query(..., description="请输入商品名称")):
    norm_q = normalize(q)

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
        {
            "product_name": row[0],
            "vendor": row[1],
            "price": row[2],
            "similarity": round(row[3], 2)
        }
        for row in rows
    ]