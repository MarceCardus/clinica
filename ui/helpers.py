# ui/helpers.py
def gs(n):
    try:
        return f"Gs {float(n):,.0f}".replace(",", ".")
    except Exception:
        return ""