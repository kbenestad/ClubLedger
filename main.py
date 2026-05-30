"""
ClubLedger - Store Credit Web App
Admin configuration: edit the CONFIG dict below.
"""

import sqlite3
import hashlib
import time
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from typing import Optional

# ---------------------------------------------------------------------------
# Admin configuration
# ---------------------------------------------------------------------------
CONFIG = {
    "club_name": "ClubLedger",
    "currency_symbol": "£",
    "currency_unit": "pence",          # smallest unit stored as integer
    "currency_divisor": 100,           # divide stored int by this for display
    "db_path": "clubledger.db",
    "allow_negative_balance": False,   # set True to allow overdraft at bar
    "min_topup_amount": 100,           # minimum top-up in pence (£1.00)
    "max_topup_amount": 100_000,       # maximum top-up in pence (£1000.00)
    "max_charge_amount": 50_000,       # maximum single charge in pence
}

DB_PATH = CONFIG["db_path"]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextmanager
def db_conn():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with db_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_number TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                pin_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS ledger_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL REFERENCES members(id),
                amount INTEGER NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('topup','charge')),
                venue TEXT NOT NULL CHECK(venue IN ('cashier','bar')),
                note TEXT,
                staff_name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                brand TEXT,
                price INTEGER NOT NULL,
                member_price INTEGER,
                search_tags TEXT,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_ledger_member
                ON ledger_entries(member_id);
        """)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

def verify_pin(pin: str, hashed: str) -> bool:
    return bcrypt.checkpw(pin.encode(), hashed.encode())

def member_balance(conn, member_id: int) -> int:
    row = conn.execute("""
        SELECT COALESCE(
            SUM(CASE WHEN type='topup' THEN amount ELSE -amount END), 0
        ) AS balance
        FROM ledger_entries WHERE member_id=?
    """, (member_id,)).fetchone()
    return row["balance"] if row else 0

def format_amount(pence: int) -> str:
    sym = CONFIG["currency_symbol"]
    div = CONFIG["currency_divisor"]
    return f"{sym}{pence / div:.2f}"

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title=CONFIG["club_name"])

# Serve static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.on_event("startup")
def on_startup():
    init_db()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MemberCreate(BaseModel):
    member_number: str
    name: str
    pin: str

    @field_validator("pin")
    @classmethod
    def pin_length(cls, v):
        if len(v) < 4:
            raise ValueError("PIN must be at least 4 characters")
        return v

    @field_validator("member_number")
    @classmethod
    def member_number_nonempty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("member_number cannot be empty")
        return v

class TopupRequest(BaseModel):
    member_id: int
    amount: int          # pence
    staff_name: str
    note: Optional[str] = None

class ChargeRequest(BaseModel):
    member_id: int
    amount: int          # pence
    pin: str
    staff_name: str
    note: Optional[str] = None

class ProductCreate(BaseModel):
    name: str
    brand: Optional[str] = None
    price: int
    member_price: Optional[int] = None
    search_tags: Optional[str] = None

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root():
    return (static_dir / "index.html").read_text()

@app.post("/members")
def create_member(body: MemberCreate):
    with db_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM members WHERE member_number=?",
            (body.member_number.strip(),)
        ).fetchone()
        if existing:
            raise HTTPException(400, "Member number already exists")
        pin_hash = hash_pin(body.pin)
        cur = conn.execute(
            "INSERT INTO members (member_number, name, pin_hash) VALUES (?,?,?)",
            (body.member_number.strip(), body.name.strip(), pin_hash)
        )
        member_id = cur.lastrowid
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
        return {
            "id": row["id"],
            "member_number": row["member_number"],
            "name": row["name"],
            "created_at": row["created_at"],
        }

@app.get("/members")
def list_members(q: Optional[str] = None):
    with db_conn() as conn:
        if q:
            pattern = f"%{q}%"
            rows = conn.execute(
                "SELECT * FROM members WHERE name LIKE ? OR member_number LIKE ? ORDER BY name",
                (pattern, pattern)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM members ORDER BY name").fetchall()
        result = []
        for r in rows:
            balance = member_balance(conn, r["id"])
            result.append({
                "id": r["id"],
                "member_number": r["member_number"],
                "name": r["name"],
                "balance": balance,
                "balance_display": format_amount(balance),
                "created_at": r["created_at"],
            })
        return result

@app.post("/topup")
def topup(body: TopupRequest):
    if body.amount < CONFIG["min_topup_amount"]:
        raise HTTPException(400, f"Minimum top-up is {format_amount(CONFIG['min_topup_amount'])}")
    if body.amount > CONFIG["max_topup_amount"]:
        raise HTTPException(400, f"Maximum top-up is {format_amount(CONFIG['max_topup_amount'])}")
    with db_conn() as conn:
        member = conn.execute("SELECT * FROM members WHERE id=?", (body.member_id,)).fetchone()
        if not member:
            raise HTTPException(404, "Member not found")
        conn.execute(
            "INSERT INTO ledger_entries (member_id, amount, type, venue, note, staff_name) VALUES (?,?,?,?,?,?)",
            (body.member_id, body.amount, "topup", "cashier", body.note, body.staff_name)
        )
        balance = member_balance(conn, body.member_id)
        return {
            "ok": True,
            "new_balance": balance,
            "new_balance_display": format_amount(balance),
        }

@app.post("/charge")
def charge(body: ChargeRequest):
    if body.amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    if body.amount > CONFIG["max_charge_amount"]:
        raise HTTPException(400, f"Maximum single charge is {format_amount(CONFIG['max_charge_amount'])}")
    with db_conn() as conn:
        member = conn.execute("SELECT * FROM members WHERE id=?", (body.member_id,)).fetchone()
        if not member:
            raise HTTPException(404, "Member not found")
        if not verify_pin(body.pin, member["pin_hash"]):
            raise HTTPException(403, "Incorrect PIN")
        balance = member_balance(conn, body.member_id)
        if not CONFIG["allow_negative_balance"] and balance < body.amount:
            raise HTTPException(400, f"Insufficient balance ({format_amount(balance)})")
        conn.execute(
            "INSERT INTO ledger_entries (member_id, amount, type, venue, note, staff_name) VALUES (?,?,?,?,?,?)",
            (body.member_id, body.amount, "charge", "bar", body.note, body.staff_name)
        )
        new_balance = member_balance(conn, body.member_id)
        return {
            "ok": True,
            "new_balance": new_balance,
            "new_balance_display": format_amount(new_balance),
        }

@app.get("/members/{member_id}/transactions")
def transactions(member_id: int, limit: int = 50, offset: int = 0):
    with db_conn() as conn:
        member = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
        if not member:
            raise HTTPException(404, "Member not found")
        rows = conn.execute("""
            SELECT * FROM ledger_entries
            WHERE member_id=?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (member_id, limit, offset)).fetchall()
        balance = member_balance(conn, member_id)
        return {
            "member": {
                "id": member["id"],
                "member_number": member["member_number"],
                "name": member["name"],
            },
            "balance": balance,
            "balance_display": format_amount(balance),
            "transactions": [
                {
                    "id": r["id"],
                    "amount": r["amount"],
                    "amount_display": format_amount(r["amount"]),
                    "type": r["type"],
                    "venue": r["venue"],
                    "note": r["note"],
                    "staff_name": r["staff_name"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ],
        }

@app.get("/members/{member_id}/statement", response_class=HTMLResponse)
def statement(member_id: int):
    with db_conn() as conn:
        member = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
        if not member:
            raise HTTPException(404, "Member not found")
        rows = conn.execute("""
            SELECT * FROM ledger_entries WHERE member_id=?
            ORDER BY created_at ASC
        """, (member_id,)).fetchall()
        balance = member_balance(conn, member_id)

    sym = CONFIG["currency_symbol"]
    div = CONFIG["currency_divisor"]
    club = CONFIG["club_name"]

    def fmt(p):
        return f"{sym}{p/div:.2f}"

    rows_html = ""
    running = 0
    for r in rows:
        if r["type"] == "topup":
            running += r["amount"]
            dr, cr = "", fmt(r["amount"])
        else:
            running -= r["amount"]
            dr, cr = fmt(r["amount"]), ""
        rows_html += f"""
        <tr>
          <td>{r['created_at'][:16]}</td>
          <td class="cap">{r['type']}</td>
          <td class="cap">{r['venue']}</td>
          <td>{r['note'] or ''}</td>
          <td>{r['staff_name']}</td>
          <td class="num red">{dr}</td>
          <td class="num grn">{cr}</td>
          <td class="num">{fmt(running)}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Statement – {member['name']}</title>
<style>
  @media print {{
    @page {{ size: A4; margin: 15mm; }}
    @page :first {{ size: A5; margin: 10mm; }}
    .no-print {{ display: none; }}
  }}
  body {{ font-family: Arial, sans-serif; font-size: 11px; color: #111; margin: 20px; }}
  h1 {{ font-size: 18px; margin-bottom: 2px; }}
  h2 {{ font-size: 13px; font-weight: normal; color: #555; margin-top: 0; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
  th {{ background: #222; color: #fff; padding: 5px 8px; text-align: left; }}
  td {{ padding: 4px 8px; border-bottom: 1px solid #e0e0e0; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .red {{ color: #c00; }}
  .grn {{ color: #080; }}
  .cap {{ text-transform: capitalize; }}
  .balance-box {{ margin-top: 12px; text-align: right; font-size: 14px; }}
  .balance-box span {{ font-weight: bold; font-size: 18px; }}
  .print-btn {{ margin-top: 12px; padding: 8px 18px; font-size: 13px; cursor: pointer; }}
</style>
</head>
<body>
<div class="no-print">
  <button class="print-btn" onclick="window.print()">Print Statement</button>
</div>
<h1>{club} – Account Statement</h1>
<h2>Member: {member['name']} &nbsp;|&nbsp; #{member['member_number']} &nbsp;|&nbsp; Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC</h2>
<table>
  <thead>
    <tr>
      <th>Date/Time</th><th>Type</th><th>Venue</th><th>Note</th>
      <th>Staff</th><th class="num">Charge</th><th class="num">Top-up</th><th class="num">Balance</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
<div class="balance-box">Current Balance: <span>{fmt(balance)}</span></div>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Products endpoints
# ---------------------------------------------------------------------------

@app.get("/products")
def list_products(q: Optional[str] = None, active_only: bool = True):
    with db_conn() as conn:
        base = "SELECT * FROM products"
        conds, params = [], []
        if active_only:
            conds.append("active=1")
        if q:
            conds.append("(name LIKE ? OR brand LIKE ? OR search_tags LIKE ?)")
            p = f"%{q}%"
            params += [p, p, p]
        if conds:
            base += " WHERE " + " AND ".join(conds)
        base += " ORDER BY name"
        rows = conn.execute(base, params).fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "brand": r["brand"],
                "price": r["price"],
                "price_display": format_amount(r["price"]),
                "member_price": r["member_price"],
                "member_price_display": format_amount(r["member_price"]) if r["member_price"] else None,
                "search_tags": r["search_tags"],
                "active": bool(r["active"]),
            }
            for r in rows
        ]

@app.post("/products")
def create_product(body: ProductCreate):
    with db_conn() as conn:
        cur = conn.execute(
            "INSERT INTO products (name, brand, price, member_price, search_tags) VALUES (?,?,?,?,?)",
            (body.name, body.brand, body.price, body.member_price, body.search_tags)
        )
        return {"id": cur.lastrowid, "ok": True}

@app.get("/config")
def get_config():
    safe = {k: v for k, v in CONFIG.items() if k != "db_path"}
    return safe

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
