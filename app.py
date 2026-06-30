"""
app.py — the web layer.

Thin FastAPI routes. Each one validates input, calls db.py for storage or
core.py for logic, and returns the result. No business logic lives here.
"""

import hmac
from datetime import date
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import core
import db
import scan
import send_daily
from config import APP_TOKEN

db.init_db()

app = FastAPI(title="Household Manager API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- auth ----------
def require_token(x_api_token: Optional[str] = Header(None)):
    if not x_api_token or not hmac.compare_digest(x_api_token, APP_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing token")


guard = [Depends(require_token)]


# ---------- models ----------
class ItemIn(BaseModel):
    name: str
    category: str = "Others"
    quantity: float = 0
    unit: str = ""
    low_stock_threshold: float = 0
    restock_days: int = 0
    last_restocked: Optional[str] = None
    price_history: List[float] = Field(default_factory=list)


class BillIn(BaseModel):
    name: str
    amount: float = 0
    category: str = "Other"
    recurrence: str = "Monthly"
    due_date: str
    reminder_days: int = 3


# ---------- health ----------
@app.get("/")
def health():
    return {"status": "ok", "service": "household-api"}


# ---------- items ----------
@app.get("/items", dependencies=guard)
def list_items():
    return db.all_items()


@app.post("/items", dependencies=guard)
def create_item(item: ItemIn):
    return db.insert_item(item.model_dump())


@app.put("/items/{item_id}", dependencies=guard)
def update_item(item_id: int, item: ItemIn):
    result = db.update_item(item_id, item.model_dump())
    if result is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return result


@app.delete("/items/{item_id}", dependencies=guard)
def delete_item(item_id: int):
    db.delete_item(item_id)
    return {"status": "deleted", "id": item_id}


@app.post("/items/{item_id}/got-it", dependencies=guard)
def got_it(item_id: int):
    from datetime import datetime

    result = db.set_last_restocked(item_id, datetime.now().isoformat())
    if result is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return result


@app.post("/items/seed-staples", dependencies=guard)
def seed_staples():
    return {"added": db.seed_staples(core.STAPLES)}


# ---------- bills ----------
@app.get("/bills", dependencies=guard)
def list_bills():
    return db.all_bills()


@app.post("/bills", dependencies=guard)
def create_bill(bill: BillIn):
    return db.insert_bill(bill.model_dump())


@app.put("/bills/{bill_id}", dependencies=guard)
def update_bill(bill_id: int, bill: BillIn):
    result = db.update_bill(bill_id, bill.model_dump())
    if result is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return result


@app.delete("/bills/{bill_id}", dependencies=guard)
def delete_bill(bill_id: int):
    db.delete_bill(bill_id)
    return {"status": "deleted", "id": bill_id}


@app.post("/bills/{bill_id}/paid", dependencies=guard)
def mark_paid(bill_id: int):
    bill = db.get_bill(bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")

    if bill["recurrence"] == "Once":
        db.delete_bill(bill_id)
        return {"status": "deleted", "id": bill_id}

    months = {"Monthly": 1, "Quarterly": 3, "Yearly": 12}.get(
        bill["recurrence"], 1
    )
    parsed = core.parse_dt(bill["due_date"])
    base = parsed.date() if parsed else date.today()
    nxt = core.add_months(base, months)
    return db.set_bill_due(bill_id, nxt.isoformat())


# ---------- compute (the brain) ----------
@app.get("/to-buy", dependencies=guard)
def to_buy():
    return core.compute_to_buy(db.all_items())


@app.get("/to-pay", dependencies=guard)
def to_pay():
    return core.compute_to_pay(db.all_bills())


@app.get("/report", dependencies=guard)
def report():
    return core.compute_report(db.all_items())


# ---------- scan a bill (Claude vision, key stays server-side) ----------
@app.post("/scan", dependencies=guard)
async def scan_bill(file: UploadFile = File(...)):
    raw = await file.read()
    name = (file.filename or "").lower()
    if name.endswith(".png"):
        media_type = "image/png"
    elif name.endswith(".webp"):
        media_type = "image/webp"
    elif name.endswith(".gif"):
        media_type = "image/gif"
    else:
        media_type = "image/jpeg"
    try:
        return scan.extract_items(raw, media_type)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not read the bill: {e}")


# ---------- trigger the daily WhatsApp summary (called by an outside scheduler) ----------
@app.post("/run-daily", dependencies=guard)
def run_daily():
    try:
        return send_daily.run()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Daily send failed: {e}")
