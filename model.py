import os
from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

CONFIDENCE_THRESHOLD = 0.6

PROMPT = (
    "You are looking at a photo of a single grocery item. Identify the specific "
    "product using the most specific name a shopper would search for when "
    "comparing prices (e.g. 'Honeycrisp Apple', 'Organic Whole Milk', "
    "'Lay's Classic Potato Chips'), covering produce, dairy, packaged and "
    "branded goods alike. Also transcribe any legible brand or label text "
    "visible in the image, if any. If you cannot confidently identify a "
    "grocery product in the image, set confidence to 0 and category to an "
    "empty string."
)


class ProductIdentification(BaseModel):
    category: str
    raw_text: Optional[str] = None
    confidence: float


def infer_category(img_bytes: bytes, mime_type: str = "image/jpeg"):
    """
    输入:图片二进制
    输出:{"category": str|None, "raw_text": str|None, "method": "gemini"/"manual"}
    """
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            PROMPT,
            types.Part.from_bytes(data=img_bytes, mime_type=mime_type),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=ProductIdentification.model_json_schema(),
        ),
    )
    result = ProductIdentification.model_validate_json(response.text)

    if result.confidence < CONFIDENCE_THRESHOLD or not result.category:
        return {
            "category": None,
            "raw_text": result.raw_text or None,
            "method": "manual",
        }

    return {
        "category": result.category,
        "raw_text": result.raw_text or None,
        "method": "gemini",
    }
