import re

# Converts a recognized pack size into one of two base units so prices become
# comparable within a query's results: fluid ounces (volume) or ounces
# (weight). "count" packs (eggs, etc.) are tracked separately since you can't
# meaningfully compare $/oz to $/egg.
_VOLUME_TO_FL_OZ = {
    "fl oz": 1, "fl. oz": 1, "floz": 1, "fluid ounce": 1, "fluid ounces": 1,
    "gallon": 128, "gal": 128,
    "quart": 32, "qt": 32,
    "pint": 16, "pt": 16,
    "liter": 33.814, "l": 33.814,
    "ml": 0.033814,
}
_WEIGHT_TO_OZ = {
    "oz": 1, "ounce": 1, "ounces": 1,
    "lb": 16, "lbs": 16, "pound": 16, "pounds": 16,
    "g": 0.035274, "gram": 0.035274, "grams": 0.035274,
    "kg": 35.274,
}
_COUNT_UNITS = {"count", "ct", "pack", "pk"}

_NUMBER = r"(\d+(?:\.\d+)?)"

_UNIT_PATTERN = re.compile(
    r"{num}\s*(fl\.?\s?oz|fluid\s?ounces?|floz|gallon|gal|quart|qt|pint|pt|liters?|l|ml"
    r"|ounces?|oz|pounds?|lbs?|lb|grams?|g|kg"
    r"|count|ct|pack|pk)\b".format(num=_NUMBER),
    re.IGNORECASE,
)


def parse_pack_size(text: str):
    """Best-effort extraction of (base_qty, base_unit) from a product name or
    size string, e.g. "Organic Grade A Milk Reduced Fat 1 gallon 365 by Whole
    Foods Market" -> (128.0, "fl_oz"). Returns (None, None) if nothing
    recognizable is found - callers should treat that as "can't normalize"."""
    if not text:
        return None, None

    match = _UNIT_PATTERN.search(text)
    if not match:
        return None, None

    qty = float(match.group(1))
    unit = match.group(2).lower().replace(".", "").replace(" ", "")

    if unit in _VOLUME_TO_FL_OZ:
        return qty * _VOLUME_TO_FL_OZ[unit], "fl_oz"
    if unit in ("fl oz",):
        return qty * _VOLUME_TO_FL_OZ["fl oz"], "fl_oz"
    if unit in _WEIGHT_TO_OZ:
        return qty * _WEIGHT_TO_OZ[unit], "oz"
    if unit in _COUNT_UNITS:
        return qty, "count"
    return None, None


_UNIT_LABEL = {"fl_oz": "fl oz", "oz": "oz", "count": "ct"}


def unit_price_info(price: float, pack_qty, pack_unit):
    """Returns (price_per_unit, label) or (None, None) when the pack size is
    unknown, so callers can show a per-unit price alongside the total."""
    if not pack_qty or not pack_unit or pack_qty <= 0:
        return None, None
    per_unit = round(price / pack_qty, 4)
    return per_unit, f"${per_unit:.2f}/{_UNIT_LABEL.get(pack_unit, pack_unit)}"
