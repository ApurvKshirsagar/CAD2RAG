def safe_float(value, default: float = 0.0) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return default

def safe_str(value, default: str = "") -> str:
    try:
        return str(value).strip()
    except Exception:
        return default