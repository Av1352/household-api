"""
core.py — the brain.

Pure functions only: no database, no web framework, no network. Everything here
works on plain dictionaries, which makes it trivial to test and means both the
API (app.py) and the daily WhatsApp job (send_daily.py) share one source of
truth for "what does she need to buy / pay" and "how have prices moved".
"""

import calendar
from datetime import date, datetime
from typing import List, Optional


# --------------------------------------------------------------------------
# Date and unit helpers
# --------------------------------------------------------------------------
def parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", ""))
    except ValueError:
        return None


def days_since(last_restocked: Optional[str]) -> Optional[int]:
    dt = parse_dt(last_restocked)
    if dt is None:
        return None
    return (date.today() - dt.date()).days


def days_until(due_date: Optional[str]) -> int:
    dt = parse_dt(due_date)
    if dt is None:
        return 9999
    return (dt.date() - date.today()).days


def factor(unit: str) -> float:
    return 1000.0 if (unit or "").lower() in ("kg", "l") else 1.0


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


# --------------------------------------------------------------------------
# Compute: to-buy
# --------------------------------------------------------------------------
def is_needed(item: dict) -> bool:
    restock_days = item.get("restock_days") or 0
    since = days_since(item.get("last_restocked"))
    due_by_time = restock_days > 0 and since is not None and since >= restock_days

    threshold = item.get("low_stock_threshold") or 0
    quantity = item.get("quantity") or 0
    bought_today = since is not None and since <= 0
    low_by_qty = threshold > 0 and quantity <= threshold and not bought_today

    return bool(due_by_time or low_by_qty)


def compute_to_buy(items: List[dict]) -> List[dict]:
    needed = [i for i in items if is_needed(i)]
    needed.sort(key=lambda i: (days_since(i.get("last_restocked")) or 0), reverse=True)
    return needed


# --------------------------------------------------------------------------
# Compute: to-pay
# --------------------------------------------------------------------------
def compute_to_pay(bills: List[dict]) -> List[dict]:
    out = []
    for b in bills:
        d = days_until(b.get("due_date"))
        if d <= (b.get("reminder_days") or 3):
            entry = dict(b)
            entry["days_until"] = d
            out.append(entry)
    out.sort(key=lambda b: b["days_until"])
    return out


# --------------------------------------------------------------------------
# Compute: price report
# --------------------------------------------------------------------------
def compute_report(items: List[dict]) -> dict:
    changes = []
    not_comparable = 0
    for it in items:
        hist = it.get("price_history") or []
        if len(hist) < 2 or hist[-2] <= 0:
            not_comparable += 1
            continue
        latest, prev = hist[-1], hist[-2]
        f = factor(it.get("unit", ""))
        changes.append(
            {
                "name": it.get("name", ""),
                "category": it.get("category", "Others"),
                "unit": it.get("unit", ""),
                "prev_per_unit": round(prev * f, 2),
                "latest_per_unit": round(latest * f, 2),
                "percent": round((latest - prev) / prev * 100, 1),
            }
        )
    changes.sort(key=lambda r: abs(r["percent"]), reverse=True)
    return {"changes": changes, "not_comparable": not_comparable}


# --------------------------------------------------------------------------
# Staples (South Indian vegetarian household)
# --------------------------------------------------------------------------
STAPLES = [
    {"name": "Ghee", "category": "Dairy", "quantity": 500, "unit": "g", "restock_days": 45},
    {"name": "Tomatoes", "category": "Vegetables", "quantity": 1, "unit": "kg", "restock_days": 5},
    {"name": "Potatoes", "category": "Vegetables", "quantity": 1, "unit": "kg", "restock_days": 10},
    {"name": "Green chillies", "category": "Vegetables", "quantity": 100, "unit": "g", "restock_days": 7},
    {"name": "Ginger", "category": "Vegetables", "quantity": 100, "unit": "g", "restock_days": 10},
    {"name": "Curry leaves", "category": "Vegetables", "quantity": 1, "unit": "", "restock_days": 7},
    {"name": "Coriander leaves", "category": "Vegetables", "quantity": 1, "unit": "", "restock_days": 4},
    {"name": "Coconut", "category": "Vegetables", "quantity": 1, "unit": "", "restock_days": 5},
    {"name": "Bananas", "category": "Fruits", "quantity": 6, "unit": "", "restock_days": 4},
    {"name": "Rice", "category": "Provisions", "quantity": 5, "unit": "kg", "restock_days": 30},
    {"name": "Toor dal", "category": "Provisions", "quantity": 1, "unit": "kg", "restock_days": 30},
    {"name": "Urad dal", "category": "Provisions", "quantity": 500, "unit": "g", "restock_days": 30},
    {"name": "Wheat flour", "category": "Provisions", "quantity": 5, "unit": "kg", "restock_days": 30},
    {"name": "Cooking oil", "category": "Provisions", "quantity": 1, "unit": "L", "restock_days": 20},
    {"name": "Salt", "category": "Provisions", "quantity": 1, "unit": "kg", "restock_days": 60},
    {"name": "Sugar", "category": "Provisions", "quantity": 1, "unit": "kg", "restock_days": 45},
    {"name": "Mustard seeds", "category": "Spices", "quantity": 100, "unit": "g", "restock_days": 60},
    {"name": "Cumin seeds", "category": "Spices", "quantity": 100, "unit": "g", "restock_days": 60},
    {"name": "Turmeric powder", "category": "Spices", "quantity": 100, "unit": "g", "restock_days": 90},
    {"name": "Chilli powder", "category": "Spices", "quantity": 100, "unit": "g", "restock_days": 60},
]
