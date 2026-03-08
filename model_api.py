from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from model import infer_category

app = FastAPI(
    title="Grocery Classification API",
    description="Upload a photo, get back a predicted category or OCR text."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
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