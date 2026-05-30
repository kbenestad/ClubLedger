"""
ClubLedger – Store Credit Web App
Hard defaults live in CONFIG below; everything is overridable via the Admin UI.
"""

import sqlite3
import json
import os
import secrets
from contextlib import contextmanager, asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import bcrypt
from fastapi import FastAPI, HTTPException, Cookie, Depends, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# Hard defaults (overridden by app_settings table via Admin area)
# ---------------------------------------------------------------------------
CONFIG = {
    "club_name":              "ClubLedger",
    "currency_symbol":        "£",
    "currency_major":         "pounds",   # label for major unit (what users enter)
    "currency_minor":         "pence",    # label for stored minor unit
    "currency_divisor":       100,        # minor units per major unit
    "allow_negative_balance": False,
    "min_topup":              100,        # minor units
    "max_topup":              100_000,
    "max_charge":             50_000,
    "receipt_footer":         "",
}

DB_PATH  = "clubledger.db"
STAFF_FILE = Path(__file__).parent / "staff.json"
static_dir = Path(__file__).parent / "static"

# In-memory sessions: token → {user_id, name, role, expires}
_sessions: dict = {}

# Cached settings merged from CONFIG + DB app_settings
_settings: dict = {}

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
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                member_number TEXT UNIQUE NOT NULL,
                name          TEXT NOT NULL,
                pin_hash      TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS ledger_entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id   INTEGER NOT NULL REFERENCES members(id),
                amount      INTEGER NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('topup','charge','withdrawal')),
                venue       TEXT NOT NULL CHECK(venue IN ('cashier','bar')),
                note        TEXT,
                staff_name  TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS products (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                brand        TEXT,
                price        INTEGER NOT NULL,
                member_price INTEGER,
                search_tags  TEXT,
                active       INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS staff_accounts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'pos-staff'
                                   CHECK(role IN ('cashier','pos-staff','admin')),
                active        INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ledger_member
                ON ledger_entries(member_id);
        """)

def migrate_db():
    """Run schema migrations that can't be expressed as CREATE TABLE IF NOT EXISTS."""
    with db_conn() as conn:
        # --- staff_accounts: add cashier/pos-staff roles ---
        schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='staff_accounts'"
        ).fetchone()
        if schema and "'pos-staff'" not in schema["sql"]:
            conn.execute("ALTER TABLE staff_accounts RENAME TO _staff_accounts_old")
            conn.execute("""
                CREATE TABLE staff_accounts (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    name          TEXT NOT NULL,
                    username      TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role          TEXT NOT NULL DEFAULT 'pos-staff'
                                       CHECK(role IN ('cashier','pos-staff','admin')),
                    active        INTEGER NOT NULL DEFAULT 1,
                    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                INSERT INTO staff_accounts
                    SELECT id, name, username, password_hash,
                           CASE role WHEN 'staff' THEN 'pos-staff' ELSE role END,
                           active, created_at
                    FROM _staff_accounts_old
            """)
            conn.execute("DROP TABLE _staff_accounts_old")

        # --- ledger_entries: add withdrawal type ---
        le_schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='ledger_entries'"
        ).fetchone()
        if le_schema and "'withdrawal'" not in le_schema["sql"]:
            conn.execute("ALTER TABLE ledger_entries RENAME TO _ledger_entries_old")
            conn.execute("""
                CREATE TABLE ledger_entries (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_id   INTEGER NOT NULL REFERENCES members(id),
                    amount      INTEGER NOT NULL,
                    type        TEXT NOT NULL CHECK(type IN ('topup','charge','withdrawal')),
                    venue       TEXT NOT NULL CHECK(venue IN ('cashier','bar')),
                    note        TEXT,
                    staff_name  TEXT NOT NULL,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("INSERT INTO ledger_entries SELECT * FROM _ledger_entries_old")
            conn.execute("DROP TABLE _ledger_entries_old")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_member ON ledger_entries(member_id)")

def seed_admin():
    with db_conn() as conn:
        if conn.execute("SELECT COUNT(*) FROM staff_accounts WHERE role='admin'").fetchone()[0] == 0:
            pw = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode()
            conn.execute(
                "INSERT INTO staff_accounts (name, username, password_hash, role) VALUES (?,?,?,?)",
                ("Administrator", "admin", pw, "admin")
            )
            print("=" * 60)
            print("  Default admin created  →  username: admin  password: admin")
            print("  Change this immediately in the Admin → Staff Accounts area.")
            print("=" * 60)

def refresh_settings():
    global _settings
    with db_conn() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        overrides = {r["key"]: json.loads(r["value"]) for r in rows}
    _settings = {**CONFIG, **overrides}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

def verify_pin(pin: str, hashed: str) -> bool:
    return bcrypt.checkpw(pin.encode(), hashed.encode())

def member_balance(conn, member_id: int) -> int:
    row = conn.execute("""
        SELECT COALESCE(SUM(CASE WHEN type='topup' THEN amount ELSE -amount END),0) AS b
        FROM ledger_entries WHERE member_id=?
    """, (member_id,)).fetchone()
    return row["b"] if row else 0

def format_amount(pence: int) -> str:
    sym = _settings.get("currency_symbol") or CONFIG["currency_symbol"]
    div = _settings.get("currency_divisor") or CONFIG["currency_divisor"]
    return f"{sym}{pence / div:.2f}"

def load_staff() -> list:
    if STAFF_FILE.exists():
        return json.loads(STAFF_FILE.read_text()).get("staff", [])
    return []

def save_staff(names: list):
    STAFF_FILE.write_text(json.dumps({"staff": sorted(set(names))}, indent=2))

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

SESSION_TTL = 8 * 3600  # seconds

def current_user(session: Optional[str] = Cookie(default=None)):
    if not session or session not in _sessions:
        raise HTTPException(401, "Not authenticated")
    s = _sessions[session]
    if datetime.now(timezone.utc).timestamp() > s["expires"]:
        del _sessions[session]
        raise HTTPException(401, "Session expired")
    return s

def admin_user(user: dict = Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin access required")

def cashier_user(user: dict = Depends(current_user)):
    if user["role"] not in ("cashier", "admin"):
        raise HTTPException(403, "Cashier access required")
    return user

def pos_user(user: dict = Depends(current_user)):
    if user["role"] not in ("pos-staff", "admin"):
        raise HTTPException(403, "POS staff access required")
    return user
    return user

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app):
    init_db()
    migrate_db()
    seed_admin()
    refresh_settings()
    yield

app = FastAPI(title="ClubLedger", lifespan=lifespan)
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

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

class MemberUpdate(BaseModel):
    member_number: Optional[str] = None
    name:          Optional[str] = None
    pin:           Optional[str] = None

class TopupRequest(BaseModel):
    member_id: int
    amount:    int   # minor units
    note:      Optional[str] = None

class ChargeRequest(BaseModel):
    member_id: int
    amount:    int
    pin:       str
    note:      Optional[str] = None

class WithdrawalRequest(BaseModel):
    member_id: int
    amount:    int   # minor units
    pin:       str
    note:      Optional[str] = None

class ProductCreate(BaseModel):
    name:        str
    brand:       Optional[str] = None
    price:       int
    member_price: Optional[int] = None
    search_tags: Optional[str] = None

class StaffAdd(BaseModel):
    name: str

class LoginRequest(BaseModel):
    username: str
    password: str

class StaffAccountCreate(BaseModel):
    name:     str
    username: str
    password: str
    role:     str = "pos-staff"

class StaffAccountUpdate(BaseModel):
    name:     Optional[str]  = None
    username: Optional[str]  = None
    password: Optional[str]  = None
    role:     Optional[str]  = None
    active:   Optional[bool] = None

class AppSettingsUpdate(BaseModel):
    club_name:              Optional[str]  = None
    currency_symbol:        Optional[str]  = None
    currency_major:         Optional[str]  = None
    currency_minor:         Optional[str]  = None
    currency_divisor:       Optional[int]  = None
    allow_negative_balance: Optional[bool] = None
    min_topup:              Optional[int]  = None
    max_topup:              Optional[int]  = None
    max_charge:             Optional[int]  = None
    receipt_footer:         Optional[str]  = None

# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root():
    return (static_dir / "index.html").read_text()

@app.get("/cashier", response_class=HTMLResponse)
async def cashier_page():
    return (static_dir / "cashier.html").read_text()

@app.get("/bar", response_class=HTMLResponse)
async def bar_page():
    return (static_dir / "bar.html").read_text()

# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/auth/login")
def login(body: LoginRequest, response: Response):
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM staff_accounts WHERE username=? AND active=1",
            (body.username.strip(),)
        ).fetchone()
    if not row or not bcrypt.checkpw(body.password.encode(), row["password_hash"].encode()):
        raise HTTPException(401, "Invalid username or password")
    token = secrets.token_hex(32)
    _sessions[token] = {
        "user_id": row["id"],
        "name":    row["name"],
        "role":    row["role"],
        "expires": datetime.now(timezone.utc).timestamp() + SESSION_TTL,
    }
    response.set_cookie("session", token, httponly=True, max_age=SESSION_TTL, samesite="strict")
    return {"name": row["name"], "role": row["role"]}

@app.post("/auth/logout")
def logout(response: Response, session: Optional[str] = Cookie(default=None)):
    if session and session in _sessions:
        del _sessions[session]
    response.delete_cookie("session")
    return {"ok": True}

@app.get("/auth/me")
def auth_me(user: dict = Depends(current_user)):
    return {"name": user["name"], "role": user["role"]}

# ---------------------------------------------------------------------------
# Member endpoints
# ---------------------------------------------------------------------------

@app.post("/members")
def create_member(body: MemberCreate, user: dict = Depends(current_user)):
    with db_conn() as conn:
        if conn.execute("SELECT id FROM members WHERE member_number=?",
                        (body.member_number.strip(),)).fetchone():
            raise HTTPException(400, "Member number already exists")
        cur = conn.execute(
            "INSERT INTO members (member_number, name, pin_hash) VALUES (?,?,?)",
            (body.member_number.strip(), body.name.strip(), hash_pin(body.pin))
        )
        mid = cur.lastrowid
    with db_conn() as conn:
        r = conn.execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone()
        return {"id": r["id"], "member_number": r["member_number"],
                "name": r["name"], "created_at": r["created_at"]}

@app.put("/members/{member_id}")
def update_member(member_id: int, body: MemberUpdate, user: dict = Depends(current_user)):
    with db_conn() as conn:
        if not conn.execute("SELECT id FROM members WHERE id=?", (member_id,)).fetchone():
            raise HTTPException(404, "Member not found")
        updates = {}
        if body.name is not None:
            n = body.name.strip()
            if not n: raise HTTPException(400, "Name cannot be empty")
            updates["name"] = n
        if body.member_number is not None:
            mn = body.member_number.strip()
            if not mn: raise HTTPException(400, "Member number cannot be empty")
            if conn.execute("SELECT id FROM members WHERE member_number=? AND id!=?",
                            (mn, member_id)).fetchone():
                raise HTTPException(400, "Member number already in use")
            updates["member_number"] = mn
        if body.pin is not None:
            if len(body.pin) < 4: raise HTTPException(400, "PIN must be at least 4 characters")
            updates["pin_hash"] = hash_pin(body.pin)
        if updates:
            conn.execute(
                f"UPDATE members SET {', '.join(f'{k}=?' for k in updates)} WHERE id=?",
                list(updates.values()) + [member_id]
            )
        r = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
        return {"id": r["id"], "member_number": r["member_number"], "name": r["name"]}

@app.delete("/members/{member_id}")
def delete_member(member_id: int, user: dict = Depends(current_user)):
    with db_conn() as conn:
        if not conn.execute("SELECT id FROM members WHERE id=?", (member_id,)).fetchone():
            raise HTTPException(404, "Member not found")
        bal = member_balance(conn, member_id)
        if bal != 0:
            raise HTTPException(400, f"Cannot delete: balance is {format_amount(bal)}")
        conn.execute("DELETE FROM ledger_entries WHERE member_id=?", (member_id,))
        conn.execute("DELETE FROM members WHERE id=?", (member_id,))
        return {"ok": True}

@app.get("/members")
def list_members(q: Optional[str] = None, user: dict = Depends(current_user)):
    with db_conn() as conn:
        if q:
            pat = f"%{q}%"
            rows = conn.execute(
                "SELECT * FROM members WHERE name LIKE ? OR member_number LIKE ? ORDER BY name",
                (pat, pat)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM members ORDER BY name").fetchall()
        result = []
        for r in rows:
            bal = member_balance(conn, r["id"])
            result.append({
                "id": r["id"], "member_number": r["member_number"], "name": r["name"],
                "balance": bal, "balance_display": format_amount(bal), "created_at": r["created_at"],
            })
        return result

@app.post("/topup")
def topup(body: TopupRequest, user: dict = Depends(cashier_user)):
    s = _settings
    if body.amount < s["min_topup"]:
        raise HTTPException(400, f"Minimum top-up is {format_amount(s['min_topup'])}")
    if body.amount > s["max_topup"]:
        raise HTTPException(400, f"Maximum top-up is {format_amount(s['max_topup'])}")
    with db_conn() as conn:
        if not conn.execute("SELECT id FROM members WHERE id=?", (body.member_id,)).fetchone():
            raise HTTPException(404, "Member not found")
        cur = conn.execute(
            "INSERT INTO ledger_entries (member_id,amount,type,venue,note,staff_name) VALUES (?,?,?,?,?,?)",
            (body.member_id, body.amount, "topup", "cashier", body.note, user["name"])
        )
        eid = cur.lastrowid
        bal = member_balance(conn, body.member_id)
        return {"ok": True, "entry_id": eid, "new_balance": bal, "new_balance_display": format_amount(bal)}

@app.post("/charge")
def charge(body: ChargeRequest, user: dict = Depends(pos_user)):
    s = _settings
    if body.amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    if body.amount > s["max_charge"]:
        raise HTTPException(400, f"Maximum single charge is {format_amount(s['max_charge'])}")
    with db_conn() as conn:
        member = conn.execute("SELECT * FROM members WHERE id=?", (body.member_id,)).fetchone()
        if not member:
            raise HTTPException(404, "Member not found")
        if not verify_pin(body.pin, member["pin_hash"]):
            raise HTTPException(403, "Incorrect PIN")
        bal = member_balance(conn, body.member_id)
        if not s["allow_negative_balance"] and bal < body.amount:
            raise HTTPException(400, f"Insufficient balance ({format_amount(bal)})")
        cur = conn.execute(
            "INSERT INTO ledger_entries (member_id,amount,type,venue,note,staff_name) VALUES (?,?,?,?,?,?)",
            (body.member_id, body.amount, "charge", "bar", body.note, user["name"])
        )
        eid = cur.lastrowid
        new_bal = member_balance(conn, body.member_id)
        return {"ok": True, "entry_id": eid, "new_balance": new_bal, "new_balance_display": format_amount(new_bal)}

@app.post("/withdrawal")
def withdrawal(body: WithdrawalRequest, user: dict = Depends(cashier_user)):
    if body.amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    with db_conn() as conn:
        member = conn.execute("SELECT * FROM members WHERE id=?", (body.member_id,)).fetchone()
        if not member:
            raise HTTPException(404, "Member not found")
        if not verify_pin(body.pin, member["pin_hash"]):
            raise HTTPException(403, "Incorrect PIN")
        bal = member_balance(conn, body.member_id)
        if bal < body.amount:
            raise HTTPException(400, f"Insufficient balance ({format_amount(bal)})")
        cur = conn.execute(
            "INSERT INTO ledger_entries (member_id,amount,type,venue,note,staff_name) VALUES (?,?,?,?,?,?)",
            (body.member_id, body.amount, "withdrawal", "cashier", body.note, user["name"])
        )
        eid = cur.lastrowid
        new_bal = member_balance(conn, body.member_id)
        return {"ok": True, "entry_id": eid, "new_balance": new_bal, "new_balance_display": format_amount(new_bal)}

@app.get("/members/{member_id}/transactions")
def transactions(member_id: int, limit: int = 50, offset: int = 0,
                 user: dict = Depends(current_user)):
    with db_conn() as conn:
        member = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
        if not member:
            raise HTTPException(404, "Member not found")
        rows = conn.execute("""
            SELECT * FROM ledger_entries WHERE member_id=?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        """, (member_id, limit, offset)).fetchall()
        bal = member_balance(conn, member_id)
        return {
            "member": {"id": member["id"], "member_number": member["member_number"], "name": member["name"]},
            "balance": bal, "balance_display": format_amount(bal),
            "transactions": [
                {"id": r["id"], "amount": r["amount"], "amount_display": format_amount(r["amount"]),
                 "type": r["type"], "venue": r["venue"], "note": r["note"],
                 "staff_name": r["staff_name"], "created_at": r["created_at"]}
                for r in rows
            ],
        }

# ---------------------------------------------------------------------------
# Print views (no auth – opened as new-tab popups)
# ---------------------------------------------------------------------------

def _print_size_script():
    return """<script>
function setSize(s){
  var el=document.getElementById('psStyle');
  if(!el){el=document.createElement('style');el.id='psStyle';document.head.appendChild(el);}
  el.textContent='@media print{@page{size:'+s+';margin:'+(s==='A5'?'8mm':'14mm')+';}}';}
setSize('A4');
</script>"""

def _print_controls():
    return """<div class="no-print controls">
  <span class="size-label">Paper:</span>
  <label><input type="radio" name="ps" value="A4" checked onchange="setSize('A4')"> A4</label>
  <label><input type="radio" name="ps" value="A5" onchange="setSize('A5')"> A5</label>
</div>"""

PRINT_CSS = """
  body{font-family:Arial,sans-serif;font-size:11px;color:#111;margin:24px;}
  h1{font-size:18px;margin-bottom:2px;} h2{font-size:13px;font-weight:normal;color:#555;margin:0 0 16px;}
  .controls{display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap;}
  .size-label{font-size:12px;color:#555;} .controls label{font-size:12px;cursor:pointer;}
  .print-btn{padding:7px 18px;font-size:13px;cursor:pointer;margin-left:auto;}
  .footer{margin-top:16px;font-size:10px;color:#888;text-align:center;white-space:pre-wrap;}
  @media print{.no-print{display:none;}}
"""

@app.get("/members/{member_id}/statement", response_class=HTMLResponse)
def statement(member_id: int):
    s = _settings
    with db_conn() as conn:
        member = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
        if not member: raise HTTPException(404, "Member not found")
        rows = conn.execute(
            "SELECT * FROM ledger_entries WHERE member_id=? ORDER BY created_at ASC",
            (member_id,)
        ).fetchall()
        bal = member_balance(conn, member_id)

    sym, div = s.get("currency_symbol","£"), s.get("currency_divisor",100)
    club, footer = s.get("club_name","ClubLedger"), s.get("receipt_footer","")

    def fmt(p): return f"{sym}{p/div:.2f}"

    rows_html, running = "", 0
    for r in rows:
        if r["type"] == "topup":
            running += r["amount"]; dr, cr = "", fmt(r["amount"])
        else:
            running -= r["amount"]; dr, cr = fmt(r["amount"]), ""
        rows_html += (f"<tr><td>{r['created_at'][:16]}</td><td class='cap'>{r['type']}</td>"
                      f"<td class='cap'>{r['venue']}</td><td>{r['note'] or ''}</td>"
                      f"<td>{r['staff_name']}</td><td class='num red'>{dr}</td>"
                      f"<td class='num grn'>{cr}</td><td class='num'>{fmt(running)}</td></tr>")

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Statement – {member['name']}</title><style>
  {PRINT_CSS}
  table{{width:100%;border-collapse:collapse;margin-top:16px;}}
  th{{background:#222;color:#fff;padding:5px 8px;text-align:left;}}
  td{{padding:4px 8px;border-bottom:1px solid #e0e0e0;}}
  .num{{text-align:right;font-variant-numeric:tabular-nums;}}
  .red{{color:#c00;}} .grn{{color:#080;}} .cap{{text-transform:capitalize;}}
  .balance-box{{margin-top:12px;text-align:right;font-size:14px;}}
  .balance-box span{{font-weight:bold;font-size:18px;}}
</style></head><body>
{_print_controls()}
<div class="no-print controls" style="margin-top:0">
  <button class="print-btn" onclick="window.print()">Print Statement</button>
</div>
<h1>{club} – Account Statement</h1>
<h2>Member: {member['name']} &nbsp;|&nbsp; #{member['member_number']} &nbsp;|&nbsp;
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC</h2>
<table><thead><tr>
  <th>Date/Time</th><th>Type</th><th>Venue</th><th>Note</th>
  <th>Staff</th><th class="num">Charge</th><th class="num">Top-up</th><th class="num">Balance</th>
</tr></thead><tbody>{rows_html}</tbody></table>
<div class="balance-box">Current Balance: <span>{fmt(bal)}</span></div>
{('<div class="footer">' + footer + '</div>') if footer else ''}
{_print_size_script()}</body></html>"""

@app.get("/receipt/{entry_id}", response_class=HTMLResponse)
def receipt(entry_id: int):
    s = _settings
    with db_conn() as conn:
        entry = conn.execute("SELECT * FROM ledger_entries WHERE id=?", (entry_id,)).fetchone()
        if not entry: raise HTTPException(404, "Receipt not found")
        member = conn.execute("SELECT * FROM members WHERE id=?", (entry["member_id"],)).fetchone()
        bal_after = conn.execute("""
            SELECT COALESCE(SUM(CASE WHEN type='topup' THEN amount ELSE -amount END),0)
            FROM ledger_entries WHERE member_id=? AND id<=?
        """, (entry["member_id"], entry_id)).fetchone()[0]

    sym, div = s.get("currency_symbol","£"), s.get("currency_divisor",100)
    club, footer = s.get("club_name","ClubLedger"), s.get("receipt_footer","")

    def fmt(p): return f"{sym}{p/div:.2f}"

    type_label = {"topup": "Top-up", "charge": "Charge", "withdrawal": "Withdrawal"}.get(entry["type"], entry["type"].capitalize())
    colour = "#080" if entry["type"] == "topup" else "#c00"

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Receipt – {member['name']}</title><style>
  {PRINT_CSS}
  .sub{{font-size:15px;color:#555;margin-bottom:20px;}}
  table{{border-collapse:collapse;}}
  td{{padding:5px 16px 5px 0;vertical-align:top;}}
  td:first-child{{font-weight:600;color:#555;white-space:nowrap;min-width:110px;}}
  .amount{{font-size:24px;font-weight:bold;color:{colour};}}
  .bal{{font-size:20px;font-weight:bold;}}
  hr{{border:none;border-top:1px solid #ccc;margin:16px 0;}}
</style></head><body>
{_print_controls()}
<div class="no-print controls" style="margin-top:0">
  <button class="print-btn" onclick="window.print()">Print Receipt</button>
</div>
<h1>{club}</h1><div class="sub">{type_label} Receipt</div><hr>
<table>
  <tr><td>Member</td><td><strong>{member['name']}</strong></td></tr>
  <tr><td>Member #</td><td>{member['member_number']}</td></tr>
  <tr><td>Type</td><td>{type_label}</td></tr>
  <tr><td>Amount</td><td class="amount">{fmt(entry['amount'])}</td></tr>
  <tr><td>Balance after</td><td class="bal">{fmt(bal_after)}</td></tr>
  <tr><td>Staff</td><td>{entry['staff_name']}</td></tr>
  <tr><td>Note</td><td>{entry['note'] or '—'}</td></tr>
  <tr><td>Date / Time</td><td>{entry['created_at']} UTC</td></tr>
</table>
{('<div class="footer">' + footer + '</div>') if footer else ''}
{_print_size_script()}</body></html>"""

# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@app.get("/products")
def list_products(q: Optional[str] = None, active_only: bool = True,
                  user: dict = Depends(current_user)):
    with db_conn() as conn:
        conds, params = [], []
        if active_only: conds.append("active=1")
        if q:
            conds.append("(name LIKE ? OR brand LIKE ? OR search_tags LIKE ?)")
            p = f"%{q}%"; params += [p, p, p]
        sql = "SELECT * FROM products" + (" WHERE " + " AND ".join(conds) if conds else "") + " ORDER BY name"
        rows = conn.execute(sql, params).fetchall()
        return [{"id": r["id"], "name": r["name"], "brand": r["brand"],
                 "price": r["price"], "price_display": format_amount(r["price"]),
                 "member_price": r["member_price"],
                 "member_price_display": format_amount(r["member_price"]) if r["member_price"] else None,
                 "search_tags": r["search_tags"], "active": bool(r["active"])} for r in rows]

@app.post("/products")
def create_product(body: ProductCreate, user: dict = Depends(current_user)):
    with db_conn() as conn:
        cur = conn.execute(
            "INSERT INTO products (name,brand,price,member_price,search_tags) VALUES (?,?,?,?,?)",
            (body.name, body.brand, body.price, body.member_price, body.search_tags)
        )
        return {"id": cur.lastrowid, "ok": True}

# ---------------------------------------------------------------------------
# Legacy staff name list (backward compat with cashier.html / bar.html)
# ---------------------------------------------------------------------------

@app.get("/staff")
def get_staff(user: dict = Depends(current_user)):
    return {"staff": load_staff()}

@app.post("/staff")
def add_staff(body: StaffAdd, user: dict = Depends(current_user)):
    name = body.name.strip()
    if not name: raise HTTPException(400, "Name cannot be empty")
    staff = load_staff()
    if name not in staff:
        staff.append(name); save_staff(staff)
    return {"staff": sorted(staff)}

@app.delete("/staff/{name}")
def remove_staff(name: str, user: dict = Depends(current_user)):
    staff = [s for s in load_staff() if s != name]
    save_staff(staff)
    return {"staff": staff}

# ---------------------------------------------------------------------------
# Admin – staff accounts
# ---------------------------------------------------------------------------

@app.get("/admin/staff-accounts")
def list_staff_accounts(user: dict = Depends(admin_user)):
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT id,name,username,role,active,created_at FROM staff_accounts ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]

@app.post("/admin/staff-accounts")
def create_staff_account(body: StaffAccountCreate, user: dict = Depends(admin_user)):
    if body.role not in ("cashier", "pos-staff", "admin"):
        raise HTTPException(400, "Role must be 'cashier', 'pos-staff', or 'admin'")
    with db_conn() as conn:
        if conn.execute("SELECT id FROM staff_accounts WHERE username=?",
                        (body.username.strip(),)).fetchone():
            raise HTTPException(400, "Username already taken")
        pw = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
        cur = conn.execute(
            "INSERT INTO staff_accounts (name,username,password_hash,role) VALUES (?,?,?,?)",
            (body.name.strip(), body.username.strip(), pw, body.role)
        )
        return {"id": cur.lastrowid, "ok": True}

@app.put("/admin/staff-accounts/{account_id}")
def update_staff_account(account_id: int, body: StaffAccountUpdate,
                         user: dict = Depends(admin_user)):
    with db_conn() as conn:
        if not conn.execute("SELECT id FROM staff_accounts WHERE id=?", (account_id,)).fetchone():
            raise HTTPException(404, "Account not found")
        updates = {}
        if body.name     is not None: updates["name"]     = body.name.strip()
        if body.username is not None:
            if conn.execute("SELECT id FROM staff_accounts WHERE username=? AND id!=?",
                            (body.username.strip(), account_id)).fetchone():
                raise HTTPException(400, "Username already taken")
            updates["username"] = body.username.strip()
        if body.password is not None:
            updates["password_hash"] = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
        if body.role is not None:
            if body.role not in ("cashier","pos-staff","admin"): raise HTTPException(400, "Invalid role")
            updates["role"] = body.role
        if body.active is not None:
            updates["active"] = 1 if body.active else 0
        if updates:
            conn.execute(
                f"UPDATE staff_accounts SET {', '.join(f'{k}=?' for k in updates)} WHERE id=?",
                list(updates.values()) + [account_id]
            )
        return {"ok": True}

@app.delete("/admin/staff-accounts/{account_id}")
def delete_staff_account(account_id: int, user: dict = Depends(admin_user)):
    if account_id == user["user_id"]:
        raise HTTPException(400, "Cannot delete your own account")
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM staff_accounts WHERE id=?", (account_id,)).fetchone()
        if not row: raise HTTPException(404, "Account not found")
        if row["role"] == "admin":
            if conn.execute("SELECT COUNT(*) FROM staff_accounts WHERE role='admin'").fetchone()[0] <= 1:
                raise HTTPException(400, "Cannot delete the last admin account")
        conn.execute("DELETE FROM staff_accounts WHERE id=?", (account_id,))
        return {"ok": True}

# ---------------------------------------------------------------------------
# Admin – app settings
# ---------------------------------------------------------------------------

@app.get("/admin/settings")
def get_admin_settings(user: dict = Depends(admin_user)):
    return _settings

@app.post("/admin/settings")
def update_admin_settings(body: AppSettingsUpdate, user: dict = Depends(admin_user)):
    with db_conn() as conn:
        for field in body.model_fields_set:
            val = getattr(body, field)
            if val is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings (key,value) VALUES (?,?)",
                    (field, json.dumps(val))
                )
    refresh_settings()
    return _settings

# ---------------------------------------------------------------------------
# Config (public – loaded by frontend before login screen shows)
# ---------------------------------------------------------------------------

@app.get("/config")
def get_config():
    s = dict(_settings)
    # expose currency_major as currency_unit so common.js .currency-unit spans still work
    s["currency_unit"] = s.get("currency_major", "pounds")
    return s

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
