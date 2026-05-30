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
from fastapi import FastAPI, HTTPException, Cookie, Depends, Response, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# Hard defaults (overridden by app_settings table via Admin area)
# ---------------------------------------------------------------------------
CONFIG = {
    "club_name":              "ClubLedger",
    "currency_symbol":        "£",
    "currency_major":         "pounds",
    "currency_minor":         "pence",
    "currency_divisor":       100,
    "overdraft_policy":       "never",
    "min_topup":              100,
    "max_topup":              100_000,
    "max_charge":             50_000,
    # Business contact
    "biz_address1":           "",
    "biz_address2":           "",
    "biz_address3":           "",
    "biz_address4":           "",
    "biz_country":            "",
    "biz_phone":              "",
    "biz_email":              "",
    "biz_website":            "",
    # Branding
    "logo_url":               "",
    "logo_align":             "left",
    "logo_max_width":         200,
    "logo_max_height":        80,
    "bar_name":               "Bar",
    "cashier_name":           "Cashier",
    # Transactions
    "txn_ref_prefix":         "TXN",
    "transfer_types":         "Bank Transfer,Cash,QR",
    # Receipt labels (localizable)
    "lbl_receipt":            "RECEIPT",
    "lbl_topup_receipt":      "TOP-UP RECEIPT",
    "lbl_withdrawal_receipt": "WITHDRAWAL RECEIPT",
    "lbl_staff":              "STAFF",
    "lbl_transaction":        "TRANSACTION",
    "lbl_charge_venue":       "CHARGE",
    "lbl_txn_time":           "TRANSACTION TIME",
    "lbl_amount_charged":     "AMOUNT CHARGED",
    "lbl_remaining_balance":  "REMAINING BALANCE",
    "lbl_balance_transfer":   "BALANCE TRANSFER",
    "lbl_amount_topup":       "AMOUNT TOPPED-UP",
    "lbl_amount_withdrawal":  "AMOUNT WITHDRAWN",
    "lbl_transfer_type":      "TRANSFER TYPE",
    "lbl_transfer_ref":       "TRANSFER REFERENCE",
    # Receipt footers
    "receipt_footer":         "",
    "receipt_footer_charge":  "",
    "receipt_footer_cashier": "",
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
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                member_number TEXT UNIQUE NOT NULL,
                name          TEXT NOT NULL,
                pin_hash      TEXT NOT NULL,
                overdraft_override INTEGER DEFAULT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS ledger_entries (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id     INTEGER NOT NULL REFERENCES members(id),
                amount        INTEGER NOT NULL,
                type          TEXT NOT NULL CHECK(type IN ('topup','charge','withdrawal')),
                venue         TEXT NOT NULL CHECK(venue IN ('cashier','bar')),
                note          TEXT,
                staff_name    TEXT NOT NULL,
                transfer_type TEXT,
                transfer_ref  TEXT,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
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
        # --- members: add overdraft_override column ---
        cols = [r[1] for r in conn.execute("PRAGMA table_info(members)").fetchall()]
        if "overdraft_override" not in cols:
            conn.execute("ALTER TABLE members ADD COLUMN overdraft_override INTEGER DEFAULT NULL")

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

        # --- app_settings: rename allow_negative_balance → overdraft_policy ---
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key='allow_negative_balance'"
        ).fetchone()
        if row is not None:
            old_val = json.loads(row[0])
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key,value) VALUES (?,?)",
                ("overdraft_policy", json.dumps("always" if old_val else "never"))
            )
            conn.execute("DELETE FROM app_settings WHERE key='allow_negative_balance'")

        # --- ledger_entries: add transfer_type and transfer_ref columns ---
        le_cols = [r[1] for r in conn.execute("PRAGMA table_info(ledger_entries)").fetchall()]
        if "transfer_type" not in le_cols:
            conn.execute("ALTER TABLE ledger_entries ADD COLUMN transfer_type TEXT")
        if "transfer_ref" not in le_cols:
            conn.execute("ALTER TABLE ledger_entries ADD COLUMN transfer_ref TEXT")

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
    member_number:     Optional[str] = None
    name:              Optional[str] = None
    pin:               Optional[str] = None
    overdraft_override: Optional[int] = None  # NULL=default, 1=allow, 0=block

class TopupRequest(BaseModel):
    member_id:     int
    amount:        int
    note:          Optional[str] = None
    transfer_type: Optional[str] = None
    transfer_ref:  Optional[str] = None

class ChargeRequest(BaseModel):
    member_id: int
    amount:    int
    pin:       str
    note:      Optional[str] = None

class WithdrawalRequest(BaseModel):
    member_id:     int
    amount:        int
    pin:           str
    note:          Optional[str] = None
    transfer_type: Optional[str] = None
    transfer_ref:  Optional[str] = None

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
    overdraft_policy:       Optional[str]  = None
    min_topup:              Optional[int]  = None
    max_topup:              Optional[int]  = None
    max_charge:             Optional[int]  = None
    # Business contact
    biz_address1:           Optional[str]  = None
    biz_address2:           Optional[str]  = None
    biz_address3:           Optional[str]  = None
    biz_address4:           Optional[str]  = None
    biz_country:            Optional[str]  = None
    biz_phone:              Optional[str]  = None
    biz_email:              Optional[str]  = None
    biz_website:            Optional[str]  = None
    # Branding
    logo_url:               Optional[str]  = None
    logo_align:             Optional[str]  = None
    logo_max_width:         Optional[int]  = None
    logo_max_height:        Optional[int]  = None
    bar_name:               Optional[str]  = None
    cashier_name:           Optional[str]  = None
    # Transactions
    txn_ref_prefix:         Optional[str]  = None
    transfer_types:         Optional[str]  = None
    # Receipt labels
    lbl_receipt:            Optional[str]  = None
    lbl_topup_receipt:      Optional[str]  = None
    lbl_withdrawal_receipt: Optional[str]  = None
    lbl_staff:              Optional[str]  = None
    lbl_transaction:        Optional[str]  = None
    lbl_charge_venue:       Optional[str]  = None
    lbl_txn_time:           Optional[str]  = None
    lbl_amount_charged:     Optional[str]  = None
    lbl_remaining_balance:  Optional[str]  = None
    lbl_balance_transfer:   Optional[str]  = None
    lbl_amount_topup:       Optional[str]  = None
    lbl_amount_withdrawal:  Optional[str]  = None
    lbl_transfer_type:      Optional[str]  = None
    lbl_transfer_ref:       Optional[str]  = None
    # Receipt footers
    receipt_footer:         Optional[str]  = None
    receipt_footer_charge:  Optional[str]  = None
    receipt_footer_cashier: Optional[str]  = None

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
        if "overdraft_override" in body.model_fields_set:
            updates["overdraft_override"] = body.overdraft_override  # None, 0, or 1
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
                "overdraft_override": r["overdraft_override"],
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
            "INSERT INTO ledger_entries (member_id,amount,type,venue,note,staff_name,transfer_type,transfer_ref) VALUES (?,?,?,?,?,?,?,?)",
            (body.member_id, body.amount, "topup", "cashier", body.note, user["name"],
             body.transfer_type, body.transfer_ref)
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
        policy = s.get("overdraft_policy", "never")
        member_ov = member["overdraft_override"]  # None, 0, or 1
        if policy == "never":
            overdraft_ok = False
        elif policy == "always":
            overdraft_ok = True
        elif policy in ("staff_override", "admin_override"):
            overdraft_ok = (member_ov == 1)
        elif policy == "staff_block":
            overdraft_ok = (member_ov != 0)  # None or 1 = allowed; 0 = explicitly blocked
        else:
            overdraft_ok = False
        if not overdraft_ok and bal < body.amount:
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
            "INSERT INTO ledger_entries (member_id,amount,type,venue,note,staff_name,transfer_type,transfer_ref) VALUES (?,?,?,?,?,?,?,?)",
            (body.member_id, body.amount, "withdrawal", "cashier", body.note, user["name"],
             body.transfer_type, body.transfer_ref)
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
  el.textContent='@media print{@page{size:'+s+';margin:'+(s==='A5'?'10mm':'16mm')+';}}';}
setSize('A4');
</script>"""

def _print_controls():
    return """<div class="no-print controls">
  <span class="size-label">Paper:</span>
  <label><input type="radio" name="ps" value="A4" checked onchange="setSize('A4')"> A4</label>
  <label><input type="radio" name="ps" value="A5" onchange="setSize('A5')"> A5</label>
  <button class="print-btn" onclick="window.print()">Print</button>
</div>"""

def _txn_ref(entry_id: int, s: dict) -> str:
    prefix = (s.get("txn_ref_prefix") or "TXN").strip()
    return f"{prefix}{entry_id:07d}"

def _logo_html(s: dict) -> str:
    url = (s.get("logo_url") or "").strip()
    if not url:
        return ""
    align  = s.get("logo_align", "left")
    max_w  = int(s.get("logo_max_width",  200) or 200)
    max_h  = int(s.get("logo_max_height",  80) or 80)
    style  = f"max-width:{max_w}px;max-height:{max_h}px;"
    css_cl = f"biz-logo align-{align}" if align in ("left","center","right") else "biz-logo"
    return f'<img src="{url}" class="{css_cl}" style="{style}" alt="logo">'

def _biz_header_html(s: dict) -> str:
    logo = _logo_html(s)
    name = s.get("club_name") or "ClubLedger"

    addr = [( s.get(f"biz_address{i}") or "").strip() for i in range(1,5)]
    addr += [(s.get("biz_country") or "").strip()]
    addr = [l for l in addr if l]

    contacts = []
    if (s.get("biz_phone") or "").strip():   contacts.append(f'Tel. &nbsp; {s["biz_phone"]}')
    if (s.get("biz_email") or "").strip():   contacts.append(f'Email: {s["biz_email"]}')
    if (s.get("biz_website") or "").strip(): contacts.append(f'Web: &nbsp; {s["biz_website"]}')

    parts = []
    if logo: parts.append(logo)
    parts.append(f'<div class="biz-name">{name}</div>')

    if addr and contacts:
        parts.append(
            f'<div class="biz-info-row">'
            f'<div class="biz-addr">{"<br>".join(addr)}</div>'
            f'<div class="biz-contacts">{"<br>".join(contacts)}</div>'
            f'</div>'
        )
    elif addr:
        parts.append(f'<div class="biz-addr">{"<br>".join(addr)}</div>')
    elif contacts:
        parts.append(f'<div class="biz-addr">{"<br>".join(contacts)}</div>')

    return '<div class="biz-header">' + "\n".join(parts) + "</div>"

def _rx_cell(label: str, value: str, extra_cls: str = "") -> str:
    val_cls = ("rx-val " + extra_cls).strip()
    return f'<div class="rx-cell"><div class="rx-lbl">{label}</div><div class="{val_cls}">{value}</div></div>'

RECEIPT_CSS = """
  body{font-family:Arial,sans-serif;font-size:11pt;color:#111;margin:28px;}
  hr{border:none;border-top:1px solid #ccc;margin:12px 0;}
  .controls{display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap;}
  .size-label{font-size:10pt;color:#555;}
  .controls label{font-size:10pt;cursor:pointer;}
  .print-btn{padding:6px 16px;font-size:10pt;cursor:pointer;margin-left:auto;}
  @media print{.no-print{display:none;}}
  /* Business header */
  .biz-logo{display:block;margin-bottom:8px;}
  .biz-logo.align-center{margin-left:auto;margin-right:auto;}
  .biz-logo.align-right{margin-left:auto;}
  .biz-name{font-size:14pt;font-weight:bold;margin:4px 0 6px;}
  .biz-info-row{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;font-size:10pt;line-height:1.7;}
  .biz-addr{line-height:1.7;}
  .biz-contacts{text-align:right;white-space:nowrap;line-height:1.7;}
  /* Receipt */
  .rx-title{font-size:13pt;font-weight:bold;text-transform:uppercase;letter-spacing:.06em;margin:14px 0 12px;}
  .rx-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px 40px;margin:10px 0;}
  .rx-cell{}
  .rx-lbl{font-size:9pt;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px;}
  .rx-val{font-size:11pt;}
  .rx-val.bold{font-weight:bold;}
  .rx-val.large{font-size:13pt;font-weight:bold;}
  .rx-val.charge{color:#c00;}
  .rx-val.credit{color:#080;}
  .footer{margin-top:20px;font-size:10pt;color:#444;line-height:1.7;white-space:pre-wrap;}
  /* Statement */
  h2{font-size:13pt;font-weight:bold;margin:14px 0 4px;}
  .stmt-info{font-size:10pt;color:#555;margin-bottom:12px;line-height:1.6;}
  table{width:100%;border-collapse:collapse;margin-top:4px;font-size:10pt;}
  th{border-bottom:2px solid #222;padding:6px 8px 6px 0;text-align:left;font-size:9pt;font-weight:700;white-space:nowrap;}
  td{padding:5px 8px 5px 0;border-bottom:1px solid #e0e0e0;vertical-align:top;}
  th.rnum,td.rnum{text-align:right;padding-right:0;}
  .credit{color:#080;}
  .debit{color:#c00;}
  .sub-row td{font-size:10pt;color:#555;padding-top:0;border-bottom:none;padding-left:88px;}
  .balance-box{margin-top:14px;text-align:right;font-size:11pt;font-weight:bold;}
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
    footer      = s.get("receipt_footer","")
    bar_name    = s.get("bar_name","Bar")
    cashier_name= s.get("cashier_name","Cashier")

    def fmt(p): return f"{sym}{p/div:.2f}"

    rows_html, running = "", 0
    for r in rows:
        txn_ref = _txn_ref(r["id"], s)
        venue   = bar_name if r["venue"] == "bar" else cashier_name
        if r["type"] == "topup":
            running += r["amount"]
            amt_html = f'<span class="credit">+ {fmt(r["amount"])}</span>'
            type_lbl = "Top-up"
        elif r["type"] == "withdrawal":
            running -= r["amount"]
            amt_html = f'<span class="debit">- {fmt(r["amount"])}</span>'
            type_lbl = "Withdrawal"
        else:
            running -= r["amount"]
            amt_html = f'<span class="debit">- {fmt(r["amount"])}</span>'
            type_lbl = "Charge"

        rows_html += (
            f"<tr><td>{r['created_at'][:16]}</td><td>{txn_ref}</td>"
            f"<td>{type_lbl}</td><td>{venue}</td><td>{r['staff_name']}</td>"
            f"<td class='rnum'>{amt_html}</td><td class='rnum'>{fmt(running)}</td></tr>"
        )

        # Detail sub-row
        sub = ""
        if r["type"] in ("topup","withdrawal"):
            tf_type = r["transfer_type"] or ""
            tf_ref  = r["transfer_ref"]  or ""
            if tf_type and tf_ref:
                sub = f"Transfer type: {tf_type} &mdash; {tf_ref}"
            elif tf_type:
                sub = f"Transfer type: {tf_type}"
            elif tf_ref:
                sub = f"Ref: {tf_ref}"
        elif r["note"]:
            sub = r["note"]

        if sub:
            rows_html += f'<tr class="sub-row"><td colspan="7">{sub}</td></tr>'

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Statement &mdash; {member['name']}</title><style>{RECEIPT_CSS}</style></head><body>
{_print_controls()}
{_biz_header_html(s)}
<hr>
<h2>Account Statement</h2>
<div class="stmt-info">
  Member: <strong>{member['name']}</strong> &mdash; #{member['member_number']} &mdash;
  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC
</div>
<table><thead><tr>
  <th>Date and Time</th><th>Reference</th><th>Type</th><th>Venue</th>
  <th>Staff</th><th class="rnum">Amount</th><th class="rnum">Balance</th>
</tr></thead><tbody>{rows_html}</tbody></table>
<div class="balance-box">Current Balance: {fmt(bal)}</div>
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

    sym, div   = s.get("currency_symbol","£"), s.get("currency_divisor",100)
    def fmt(p): return f"{sym}{p/div:.2f}"

    txn_ref    = _txn_ref(entry_id, s)
    etype      = entry["type"]
    venue_name = s.get("bar_name","Bar") if entry["venue"]=="bar" else s.get("cashier_name","Cashier")
    tf_type    = entry["transfer_type"] or ""
    tf_ref     = entry["transfer_ref"]  or ""
    timestamp  = entry["created_at"][:16] + " UTC"

    lbl_staff     = s.get("lbl_staff",            "STAFF")
    lbl_txn       = s.get("lbl_transaction",       "TRANSACTION")
    lbl_txn_time  = s.get("lbl_txn_time",          "TRANSACTION TIME")
    lbl_remaining = s.get("lbl_remaining_balance", "REMAINING BALANCE")

    if etype == "topup":
        title        = s.get("lbl_topup_receipt",    "TOP-UP RECEIPT")
        footer       = s.get("receipt_footer_cashier") or s.get("receipt_footer","")
        lbl_tf_sec   = s.get("lbl_balance_transfer", "BALANCE TRANSFER")
        lbl_amount   = s.get("lbl_amount_topup",     "AMOUNT TOPPED-UP")
        tf_label     = "Top-up"
        amount_cls   = "large credit"
    elif etype == "withdrawal":
        title        = s.get("lbl_withdrawal_receipt","WITHDRAWAL RECEIPT")
        footer       = s.get("receipt_footer_cashier") or s.get("receipt_footer","")
        lbl_tf_sec   = s.get("lbl_balance_transfer", "BALANCE TRANSFER")
        lbl_amount   = s.get("lbl_amount_withdrawal","AMOUNT WITHDRAWN")
        tf_label     = "Withdrawal"
        amount_cls   = "large charge"
    else:
        title        = s.get("lbl_receipt",           "RECEIPT")
        footer       = s.get("receipt_footer_charge") or s.get("receipt_footer","")
        lbl_charge   = s.get("lbl_charge_venue",      "CHARGE")
        lbl_amount   = s.get("lbl_amount_charged",    "AMOUNT CHARGED")

    if etype == "charge":
        body_html = f"""<div class="rx-grid">
  {_rx_cell(lbl_staff, entry['staff_name'])}
  {_rx_cell(lbl_txn, txn_ref)}
</div>
<hr>
<div class="rx-grid">
  {_rx_cell(lbl_charge, venue_name)}
  {_rx_cell(lbl_txn_time, timestamp)}
</div>
<hr>
<div class="rx-grid">
  {_rx_cell(lbl_amount, fmt(entry['amount']), 'large charge')}
  {_rx_cell(lbl_remaining, fmt(bal_after), 'large')}
</div>"""
    else:
        lbl_tf_type = s.get("lbl_transfer_type", "TRANSFER TYPE")
        lbl_tf_ref  = s.get("lbl_transfer_ref",  "TRANSFER REFERENCE")
        body_html = f"""<div class="rx-grid">
  {_rx_cell(lbl_staff, entry['staff_name'])}
  {_rx_cell(lbl_txn, txn_ref)}
</div>
<hr>
<div class="rx-grid">
  {_rx_cell(lbl_tf_sec, tf_label)}
  {_rx_cell(lbl_txn_time, timestamp)}
</div>
<hr>
<div class="rx-grid">
  {_rx_cell(lbl_amount, fmt(entry['amount']), amount_cls)}
  {_rx_cell(lbl_remaining, fmt(bal_after), 'large')}
</div>
<hr>
<div class="rx-grid">
  {_rx_cell(lbl_tf_type, tf_type or '&mdash;')}
  {_rx_cell(lbl_tf_ref,  tf_ref  or '&mdash;')}
</div>"""

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Receipt &mdash; {member['name']}</title><style>{RECEIPT_CSS}</style></head><body>
{_print_controls()}
{_biz_header_html(s)}
<hr>
<div class="rx-title">{title}</div>
{body_html}
<hr>
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

_OVERDRAFT_POLICIES = ("never", "always", "staff_override", "admin_override", "staff_block")

@app.post("/admin/settings")
def update_admin_settings(body: AppSettingsUpdate, user: dict = Depends(admin_user)):
    if body.overdraft_policy is not None and body.overdraft_policy not in _OVERDRAFT_POLICIES:
        raise HTTPException(400, "Invalid overdraft policy")
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
# Admin – logo upload
# ---------------------------------------------------------------------------

@app.post("/admin/logo")
async def upload_logo(file: UploadFile = File(...), user: dict = Depends(admin_user)):
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(400, "Only image files are allowed")
    suffix = Path(file.filename or "logo.png").suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
        suffix = ".png"
    dest = static_dir / f"logo{suffix}"
    dest.write_bytes(await file.read())
    url = f"/static/logo{suffix}"
    with db_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO app_settings (key,value) VALUES (?,?)",
                     ("logo_url", json.dumps(url)))
    refresh_settings()
    return {"url": url}

# ---------------------------------------------------------------------------
# Config (public – loaded by frontend before login screen shows)
# ---------------------------------------------------------------------------

@app.get("/config")
def get_config():
    s = dict(_settings)
    s["currency_unit"] = s.get("currency_major", "pounds")
    raw_tt = s.get("transfer_types", "Bank Transfer,Cash,QR")
    s["transfer_types"] = [t.strip() for t in raw_tt.split(",") if t.strip()]
    return s

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
