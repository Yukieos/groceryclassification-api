from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from model import infer_category
from utils import normalize
import psycopg2
import uvicorn

app = FastAPI(
    title="Grocery Photo Search API",
    description="Upload a photo, get back a predicted category or OCR text."
)

# （根据前端域名设置）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST","GET","OPTIONS"],
    allow_headers=["*"],
)

@app.post("/infer")
async def infer(photo: UploadFile = File(...)):
    """
    接收 multipart/form-data 的图片文件
    返回 JSON:{"category":..., "raw_text":..., "method":...}
    """
    if photo.content_type.split('/')[0] != 'image':
        raise HTTPException(400, "Only image uploads are supported.")
    img_bytes = await photo.read()
    result = infer_category(img_bytes)
    return result

@app.get("/search_price")
def search_price(q: str = Query(..., description="Name of the item")):
    norm_q = normalize(q)

    conn = psycopg2.connect(
        host="db-foodprice.cs76a4esi9a9.us-east-1.rds.amazonaws.com",
        dbname="postgres",
        user="yukieos",
        password="drinkmoretea1",
        port=5432
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
