import os

from google import genai
from google.genai import types

EMBED_MODEL = os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = 768

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def embed_text(text: str, task_type: str = "RETRIEVAL_DOCUMENT"):
    """Embeds one string into a 768-dim vector. task_type should be
    RETRIEVAL_DOCUMENT for product names going into the index and
    RETRIEVAL_QUERY for a shopper's search term - asymmetric task types are
    what make retrieval-quality embeddings actually retrieval-quality."""
    result = _get_client().models.embed_content(
        model=EMBED_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=EMBED_DIM,
            task_type=task_type,
        ),
    )
    return list(result.embeddings[0].values)
