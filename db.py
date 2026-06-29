"""
db.py — all SQLite access lives here.

Connection handling, table creation, and every read/write. Nothing else in the
project touches the database directly, so if storage ever changes (Postgres,
say), this is the only file that moves.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from config import DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Others',
                quantity REAL NOT NULL DEFAULT 0,
                unit TEXT NOT NULL DEFAULT '',
                low_stock_threshold REAL NOT NULL DEFAULT 0,
                restock_days INTEGER NOT NULL DEFAULT 0,
                last_restocked TEXT,
                price_history TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                category TEXT NOT NULL DEFAULT 'Other',
                recurrence TEXT NOT NULL DEFAULT 'Monthly',
                due_date TEXT NOT NULL,
                reminder_days INTEGER NOT NULL DEFAULT 3
            )
            """
        )


# ---------- row mappers ----------
def row_to_item(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "quantity": row["quantity"],
        "unit": row["unit"],
        "low_stock_threshold": row["low_stock_threshold"],
        "restock_days": row["restock_days"],
        "last_restocked": row["last_restocked"],
        "price_history": json.loads(row["price_history"] or "[]"),
    }


def row_to_bill(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "amount": row["amount"],
        "category": row["category"],
        "recurrence": row["recurrence"],
        "due_date": row["due_date"],
        "reminder_days": row["reminder_days"],
    }


# ---------- items ----------
def all_items() -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM items ORDER BY name").fetchall()
    return [row_to_item(r) for r in rows]


def get_item(item_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    return row_to_item(row) if row else None


def insert_item(d: dict) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO items
               (name, category, quantity, unit, low_stock_threshold,
                restock_days, last_restocked, price_history)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                d["name"],
                d.get("category", "Others"),
                d.get("quantity", 0),
                d.get("unit", ""),
                d.get("low_stock_threshold", 0),
                d.get("restock_days", 0),
                d.get("last_restocked") or datetime.now().isoformat(),
                json.dumps(d.get("price_history", [])),
            ),
        )
        row = conn.execute(
            "SELECT * FROM items WHERE id=?", (cur.lastrowid,)
        ).fetchone()
    return row_to_item(row)


def update_item(item_id: int, d: dict) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            """UPDATE items SET
               name=?, category=?, quantity=?, unit=?, low_stock_threshold=?,
               restock_days=?, last_restocked=?, price_history=?
               WHERE id=?""",
            (
                d["name"],
                d.get("category", "Others"),
                d.get("quantity", 0),
                d.get("unit", ""),
                d.get("low_stock_threshold", 0),
                d.get("restock_days", 0),
                d.get("last_restocked") or row["last_restocked"],
                json.dumps(d.get("price_history", [])),
                item_id,
            ),
        )
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    return row_to_item(row)


def delete_item(item_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM items WHERE id=?", (item_id,))


def set_last_restocked(item_id: int, ts: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE items SET last_restocked=? WHERE id=?", (ts, item_id)
        )
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    return row_to_item(row)


def seed_staples(staples: List[dict]) -> int:
    now = datetime.now().isoformat()
    added = 0
    with get_conn() as conn:
        existing = {
            r["name"].lower()
            for r in conn.execute("SELECT name FROM items").fetchall()
        }
        for s in staples:
            if s["name"].lower() in existing:
                continue
            conn.execute(
                """INSERT INTO items
                   (name, category, quantity, unit, low_stock_threshold,
                    restock_days, last_restocked, price_history)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    s["name"],
                    s["category"],
                    s["quantity"],
                    s["unit"],
                    0,
                    s["restock_days"],
                    now,
                    "[]",
                ),
            )
            added += 1
    return added


# ---------- bills ----------
def all_bills() -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM bills ORDER BY due_date").fetchall()
    return [row_to_bill(r) for r in rows]


def get_bill(bill_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    return row_to_bill(row) if row else None


def insert_bill(d: dict) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO bills
               (name, amount, category, recurrence, due_date, reminder_days)
               VALUES (?,?,?,?,?,?)""",
            (
                d["name"],
                d.get("amount", 0),
                d.get("category", "Other"),
                d.get("recurrence", "Monthly"),
                d["due_date"],
                d.get("reminder_days", 3),
            ),
        )
        row = conn.execute(
            "SELECT * FROM bills WHERE id=?", (cur.lastrowid,)
        ).fetchone()
    return row_to_bill(row)


def update_bill(bill_id: int, d: dict) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            """UPDATE bills SET
               name=?, amount=?, category=?, recurrence=?, due_date=?,
               reminder_days=? WHERE id=?""",
            (
                d["name"],
                d.get("amount", 0),
                d.get("category", "Other"),
                d.get("recurrence", "Monthly"),
                d["due_date"],
                d.get("reminder_days", 3),
                bill_id,
            ),
        )
        row = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    return row_to_bill(row)


def delete_bill(bill_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM bills WHERE id=?", (bill_id,))


def set_bill_due(bill_id: int, due_date: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE bills SET due_date=? WHERE id=?", (due_date, bill_id)
        )
        row = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    return row_to_bill(row)
