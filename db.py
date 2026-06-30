"""
db.py — all database access.

Works on two backends with no change to the rest of the app:
  - Postgres, when DATABASE_URL is set (Render). Data persists across deploys.
  - SQLite, when it is not (local development). A single file, zero setup.

The same SQL is used for both; placeholders and a couple of DDL bits are
translated for Postgres. Nothing else in the project touches the database.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from config import DB_PATH

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row


@contextmanager
def get_conn():
    if USE_POSTGRES:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _q(sql: str) -> str:
    """SQL is written with '?' placeholders; Postgres wants '%s'."""
    return sql.replace("?", "%s") if USE_POSTGRES else sql


def _insert_returning_id(cur, sql: str, params) -> int:
    if USE_POSTGRES:
        cur.execute(_q(sql) + " RETURNING id", params)
        return cur.fetchone()["id"]
    cur.execute(_q(sql), params)
    return cur.lastrowid


def init_db() -> None:
    id_col = (
        "id SERIAL PRIMARY KEY"
        if USE_POSTGRES
        else "id INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    real = "DOUBLE PRECISION" if USE_POSTGRES else "REAL"
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS items (
                {id_col},
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Others',
                quantity {real} NOT NULL DEFAULT 0,
                unit TEXT NOT NULL DEFAULT '',
                low_stock_threshold {real} NOT NULL DEFAULT 0,
                restock_days INTEGER NOT NULL DEFAULT 0,
                last_restocked TEXT,
                price_history TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS bills (
                {id_col},
                name TEXT NOT NULL,
                amount {real} NOT NULL DEFAULT 0,
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
        cur = conn.cursor()
        cur.execute("SELECT * FROM items ORDER BY name")
        rows = cur.fetchall()
    return [row_to_item(r) for r in rows]


def get_item(item_id: int) -> Optional[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_q("SELECT * FROM items WHERE id=?"), (item_id,))
        row = cur.fetchone()
    return row_to_item(row) if row else None


def insert_item(d: dict) -> dict:
    with get_conn() as conn:
        cur = conn.cursor()
        new_id = _insert_returning_id(
            cur,
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
        cur.execute(_q("SELECT * FROM items WHERE id=?"), (new_id,))
        row = cur.fetchone()
    return row_to_item(row)


def update_item(item_id: int, d: dict) -> Optional[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_q("SELECT * FROM items WHERE id=?"), (item_id,))
        row = cur.fetchone()
        if not row:
            return None
        last_restocked = d.get("last_restocked") or row["last_restocked"]
        cur.execute(
            _q(
                """UPDATE items SET
                   name=?, category=?, quantity=?, unit=?, low_stock_threshold=?,
                   restock_days=?, last_restocked=?, price_history=?
                   WHERE id=?"""
            ),
            (
                d["name"],
                d.get("category", "Others"),
                d.get("quantity", 0),
                d.get("unit", ""),
                d.get("low_stock_threshold", 0),
                d.get("restock_days", 0),
                last_restocked,
                json.dumps(d.get("price_history", [])),
                item_id,
            ),
        )
        cur.execute(_q("SELECT * FROM items WHERE id=?"), (item_id,))
        row = cur.fetchone()
    return row_to_item(row)


def delete_item(item_id: int) -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_q("DELETE FROM items WHERE id=?"), (item_id,))


def set_last_restocked(item_id: int, ts: str) -> Optional[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_q("SELECT * FROM items WHERE id=?"), (item_id,))
        if not cur.fetchone():
            return None
        cur.execute(
            _q("UPDATE items SET last_restocked=? WHERE id=?"), (ts, item_id)
        )
        cur.execute(_q("SELECT * FROM items WHERE id=?"), (item_id,))
        row = cur.fetchone()
    return row_to_item(row)


def seed_staples(staples: List[dict]) -> int:
    now = datetime.now().isoformat()
    added = 0
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM items")
        existing = {r["name"].lower() for r in cur.fetchall()}
        for s in staples:
            if s["name"].lower() in existing:
                continue
            cur.execute(
                _q(
                    """INSERT INTO items
                       (name, category, quantity, unit, low_stock_threshold,
                        restock_days, last_restocked, price_history)
                       VALUES (?,?,?,?,?,?,?,?)"""
                ),
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
        cur = conn.cursor()
        cur.execute("SELECT * FROM bills ORDER BY due_date")
        rows = cur.fetchall()
    return [row_to_bill(r) for r in rows]


def get_bill(bill_id: int) -> Optional[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_q("SELECT * FROM bills WHERE id=?"), (bill_id,))
        row = cur.fetchone()
    return row_to_bill(row) if row else None


def insert_bill(d: dict) -> dict:
    with get_conn() as conn:
        cur = conn.cursor()
        new_id = _insert_returning_id(
            cur,
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
        cur.execute(_q("SELECT * FROM bills WHERE id=?"), (new_id,))
        row = cur.fetchone()
    return row_to_bill(row)


def update_bill(bill_id: int, d: dict) -> Optional[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_q("SELECT * FROM bills WHERE id=?"), (bill_id,))
        if not cur.fetchone():
            return None
        cur.execute(
            _q(
                """UPDATE bills SET
                   name=?, amount=?, category=?, recurrence=?, due_date=?,
                   reminder_days=? WHERE id=?"""
            ),
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
        cur.execute(_q("SELECT * FROM bills WHERE id=?"), (bill_id,))
        row = cur.fetchone()
    return row_to_bill(row)


def delete_bill(bill_id: int) -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_q("DELETE FROM bills WHERE id=?"), (bill_id,))


def set_bill_due(bill_id: int, due_date: str) -> Optional[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_q("SELECT * FROM bills WHERE id=?"), (bill_id,))
        if not cur.fetchone():
            return None
        cur.execute(
            _q("UPDATE bills SET due_date=? WHERE id=?"), (due_date, bill_id)
        )
        cur.execute(_q("SELECT * FROM bills WHERE id=?"), (bill_id,))
        row = cur.fetchone()
    return row_to_bill(row)
