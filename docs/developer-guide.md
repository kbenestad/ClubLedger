# ClubLedger – Developer Guide

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+ · FastAPI · SQLite (via stdlib `sqlite3`) |
| Auth | bcrypt password hashing · in-memory session tokens · httpOnly cookies |
| Frontend | Vanilla HTML/CSS/JS — no build step, no framework |
| Dependencies | `fastapi`, `uvicorn[standard]`, `bcrypt`, `python-multipart` |

`python-multipart` is required for file upload support via FastAPI's `UploadFile`.

---

## Project Structure

```
ClubLedger/
├── main.py              # Entire backend — one file
├── manage.py            # CLI for database/admin management (reset-admin, reset-db)
├── requirements.txt     # pip dependencies
├── run.sh               # Start script (creates venv, installs deps, runs server)
├── clubledger.db        # SQLite database (created on first run, git-ignored)
├── staff.json           # Legacy staff name list (created on first use)
├── docs/
│   ├── user-guide.md
│   ├── admin-guide.md
│   ├── developer-guide.md
│   └── deployment.md
└── static/
    ├── index.html       # Main SPA (Members / Cashier / Bar / Admin tabs)
    ├── style.css        # All styles
    ├── app.js           # Main SPA logic
    ├── common.js        # Shared helpers (also used by standalone pages)
    ├── cashier.html     # Standalone cashier page (/cashier)
    ├── cashier.js
    ├── bar.html         # Standalone bar page (/bar)
    ├── bar.js
    └── logo.*           # Uploaded logo file (created when admin uploads a logo; git-ignored)
```

`main.py` is kept as a single file for simplicity. Split it only if it grows substantially.

---

## Running Locally

```bash
git clone <repo>
cd ClubLedger
./run.sh          # creates .venv, installs deps, starts server on :8000
```

With auto-reload during development:

```bash
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

The default admin account (`admin` / `admin`) is printed to the console on first run.

---

## manage.py

The `manage.py` script provides CLI commands for server-side administration. Run it from the project root with the virtual environment active.

### `python manage.py reset-admin`

Interactively resets an admin account password from the terminal. Safe to run while the app is running (SQLite WAL mode). Uses `getpass` so the password is not echoed.

### `python manage.py reset-db`

Wipes `clubledger.db`, `clubledger.db-wal`, and `clubledger.db-shm`. Requires typing `RESET` to confirm. The app must be stopped before running this command.

---

## Database Schema

### `members`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| member_number | TEXT UNIQUE | Human-readable ID |
| name | TEXT | |
| pin_hash | TEXT | bcrypt hash |
| overdraft_override | INTEGER | NULL = use global policy; 1 = override allowed; 0 = override blocked |
| created_at | TEXT | `datetime('now')` UTC |

### `ledger_entries`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| member_id | INTEGER FK | → members.id |
| amount | INTEGER | Minor currency units — always positive |
| type | TEXT | `topup`, `charge`, or `withdrawal` |
| venue | TEXT | `cashier` or `bar` |
| note | TEXT | Optional free text |
| staff_name | TEXT | Name of logged-in staff at time of transaction |
| transfer_type | TEXT | Payment method for top-ups/withdrawals (e.g. "Cash") |
| transfer_ref | TEXT | Optional payment reference for top-ups/withdrawals |
| created_at | TEXT | UTC datetime |

Balance is computed on-the-fly: `SUM(topups) - SUM(charges) - SUM(withdrawals)`. There is no stored balance column — this avoids drift and makes the audit trail self-consistent.

### `staff_accounts`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | Display name, used as `staff_name` on transactions |
| username | TEXT UNIQUE | Login credential |
| password_hash | TEXT | bcrypt hash |
| role | TEXT | `pos-staff`, `cashier`, or `admin` |
| active | INTEGER | 0 or 1 |
| created_at | TEXT | |

On startup, any existing rows with `role = 'staff'` are automatically migrated to `role = 'pos-staff'`.

### `products`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | |
| brand | TEXT | Optional |
| price | INTEGER | Minor units |
| member_price | INTEGER | Optional discounted price |
| search_tags | TEXT | Space/comma separated search terms |
| active | INTEGER | 0 or 1 |

Products are searchable via `GET /products?q=<term>` and managed via `POST /products`. No UI exists yet — use the API directly or SQLite directly to seed products.

### `app_settings`
| Column | Type |
|---|---|
| key | TEXT PK |
| value | TEXT (JSON) |

Settings are loaded at startup into the module-level `_settings` dict and re-read after every admin save. The `CONFIG` dict in `main.py` provides fallback defaults.

---

## Settings System

```
CONFIG dict          ← hard defaults in main.py
    +
app_settings table   ← admin overrides stored as JSON strings
    ↓
_settings dict       ← merged at startup and after each /admin/settings POST
    ↓
format_amount()      ← reads _settings at call time
/config endpoint     ← returns _settings to the frontend on every page load
```

### CONFIG keys

| Key | Default / Notes |
|---|---|
| `club_name` | Club display name |
| `currency_symbol` | e.g. `£` |
| `currency_major` | e.g. `GBP` |
| `currency_minor` | e.g. `pence` |
| `currency_divisor` | e.g. `100` |
| `overdraft_policy` | `"never"` / `"always"` / `"staff-override"` / `"admin-override"` / `"staff-block"` |
| `min_topup` | Minimum top-up amount (minor units) |
| `max_topup` | Maximum top-up amount (minor units) |
| `max_charge` | Maximum single charge amount (minor units) |
| `biz_address1` – `biz_address4` | Business address lines |
| `biz_country` | |
| `biz_phone` | |
| `biz_email` | |
| `biz_website` | |
| `logo_url` | URL path to uploaded logo (set automatically on upload) |
| `logo_align` | |
| `logo_max_width` | Default `200` |
| `logo_max_height` | Default `80` |
| `bar_name` | Default `"Bar"` |
| `cashier_name` | Default `"Cashier"` |
| `txn_ref_prefix` | Default `"TXN"` |
| `transfer_types` | Comma-separated string (e.g. `"Bank Transfer,Cash,QR"`); returned as an array by `/config` |
| `lbl_receipt` | Receipt label keys (14 total — see source for full list) |
| `lbl_topup_receipt` | |
| `lbl_withdrawal_receipt` | |
| `lbl_staff` | |
| `lbl_transaction` | |
| `lbl_charge_venue` | |
| `lbl_txn_time` | |
| `lbl_amount_charged` | |
| `lbl_remaining_balance` | |
| `lbl_balance_transfer` | |
| `lbl_amount_topup` | |
| `lbl_amount_withdrawal` | |
| `lbl_transfer_type` | |
| `lbl_transfer_ref` | |
| `receipt_footer` | Footer text for all receipts |
| `receipt_footer_charge` | Override footer for charge receipts |
| `receipt_footer_cashier` | Override footer for cashier receipts |
| `timezone` | IANA timezone name; defaults to server local timezone via `_server_timezone()` |

To add a new configurable value:
1. Add a default to `CONFIG`
2. Add the field to the `AppSettingsUpdate` Pydantic model
3. Add the input to the Admin settings form in `index.html`
4. Load and save it in `loadAdminSettings()` / `saveSettings()` in `app.js`

---

## Auth System

- `POST /auth/login` validates credentials against `staff_accounts`, creates a `secrets.token_hex(32)` token, stores it in the module-level `_sessions` dict, and sets it as an `httpOnly` cookie.
- All protected endpoints use a `Depends()` guard appropriate to the required role:
  - `Depends(pos_user)` — allows `pos-staff` and `admin`. Used by bar endpoints.
  - `Depends(cashier_user)` — allows `cashier` and `admin`. Used by cashier endpoints.
  - `Depends(admin_user)` — `admin` only.
- Sessions expire after 8 hours (configurable via `SESSION_TTL` in `main.py`).
- Sessions are lost on server restart (in-memory). This is intentional for simplicity; upgrade to a DB-backed session store if persistence is needed.
- Print views (`/receipt/`, `/members/*/statement`) have no auth — they are opened as pop-up tabs from an authenticated session.

---

## API Reference

All endpoints except `/config`, `/auth/login`, and the print views require a valid session cookie.

### Auth

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/auth/login` | `{username, password}` | `{name, role}` + sets cookie |
| POST | `/auth/logout` | — | `{ok}` + clears cookie |
| GET | `/auth/me` | — | `{name, role}` |

### Members

| Method | Path | Notes |
|---|---|---|
| GET | `/members?q=` | List/search. Returns balance per member. |
| POST | `/members` | `{member_number, name, pin}` |
| PUT | `/members/{id}` | `{member_number?, name?, pin?, overdraft_override?}` — all optional |
| DELETE | `/members/{id}` | Blocked if balance ≠ 0 |
| GET | `/members/{id}/transactions` | `?limit=50&offset=0` |
| GET | `/members/{id}/statement` | Returns printable HTML. No auth. |

### Transactions

| Method | Path | Body |
|---|---|---|
| POST | `/topup` | `{member_id, amount, transfer_type?, transfer_ref?, note?}` — amount in minor units |
| POST | `/charge` | `{member_id, amount, pin, note?}` |
| POST | `/withdrawal` | `{member_id, amount, pin, transfer_type?, transfer_ref?, note?}` |

All return `{ok, entry_id, new_balance, new_balance_display}`.

### Receipts

| Method | Path | Notes |
|---|---|---|
| GET | `/receipt/{entry_id}` | Returns printable HTML. No auth. |

### Products

| Method | Path | Notes |
|---|---|---|
| GET | `/products?q=` | Search by name/brand/tags |
| POST | `/products` | `{name, brand?, price, member_price?, search_tags?}` |

### Admin

| Method | Path | Notes |
|---|---|---|
| GET | `/admin/settings` | Admin only |
| POST | `/admin/settings` | Admin only. Partial update — only sent fields are changed. |
| POST | `/admin/logo` | Admin only. Multipart file upload. Saves image to `static/logo.<ext>`, updates `logo_url` setting, returns `{url}`. Accepts PNG, JPG, GIF, WebP, SVG. |
| GET | `/admin/staff-accounts` | Admin only |
| POST | `/admin/staff-accounts` | `{name, username, password, role}` |
| PUT | `/admin/staff-accounts/{id}` | All fields optional |
| DELETE | `/admin/staff-accounts/{id}` | Cannot delete self or last admin |

### Config (public)

| Method | Path | Notes |
|---|---|---|
| GET | `/config` | Returns live `_settings`. Called by the frontend on every page load. `transfer_types` is returned as an array. |

---

## Frontend Architecture

`index.html` loads `common.js` then `app.js`.

- **`common.js`** — shared utilities: `loadConfig()`, `apiFetch()`, `esc()`, `fmtAmount()`, `balanceClass()`, `setMsg()`, and the staff name dropdown helpers (used only by the standalone cashier/bar pages).
- **`app.js`** — all SPA logic: auth flow, tab switching, Members/Cashier/Bar/Admin views, modal management.

The boot sequence in `app.js`:
1. `loadConfig()` — fetches `/config` so the login screen shows the club name.
2. `GET /auth/me` — if 401, show login overlay and stop.
3. On successful login or existing session: `startApp()` which wires up all event listeners and loads the members list.

Amount conversion: `toMinor(inputId)` reads a decimal input and multiplies by `cfg.currency_divisor` before posting. All amounts sent to the API are in minor units.

---

## Extending the App

### Adding a new setting

See the Settings System section above.

### Adding a new transaction venue

1. Add the new venue value to the `CHECK` constraint in the `ledger_entries` schema — requires a migration or database recreation.
2. Add a new endpoint (or extend existing transaction endpoints with a `venue` parameter).
3. Add a new tab or form in `index.html` / `app.js`.

### Adding product management UI

The `/products` API exists but only the GET endpoint is exposed in the main UI (products were removed from the bar tab). A products management panel in the Admin tab would follow the same pattern as Staff Accounts.

### Persistent sessions

Replace the `_sessions` dict with a `sessions` table in SQLite:

```sql
CREATE TABLE sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES staff_accounts(id),
    expires TEXT
);
```

Adjust `current_user()` to query the table instead of the dict.

---

## Environment Notes

- The database file `clubledger.db` is created automatically in the working directory on first run. Add it to `.gitignore`.
- `staff.json` is also created in the working directory. Add to `.gitignore`.
- `static/logo.*` is created when an admin uploads a logo via the Admin panel. Add to `.gitignore`.
- No environment variables are required. All configuration is in `CONFIG` (code) or `app_settings` (database).
- The app binds to `0.0.0.0:8000` by default — accessible from any device on the network. Pass `--host 127.0.0.1` to restrict to localhost only.
