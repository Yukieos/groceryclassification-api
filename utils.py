import re
from difflib import SequenceMatcher

def normalize(text):
    return ''.join(c for c in text.lower() if c.isalnum())

def compute_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()
