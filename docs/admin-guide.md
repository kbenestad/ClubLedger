# ClubLedger – Administrator Guide

Administrators have access to everything in the [Staff User Guide](user-guide.md) plus the **Admin** tab.

---

## First Login

On first startup the system creates a default admin account:

| Username | Password |
|---|---|
| `admin` | `admin` |

**Change this password immediately.** Go to **Admin → Staff Accounts**, find the admin row, click **Edit**, and set a strong password.

---

## Roles

ClubLedger has three roles:

| Role | Tabs visible |
|---|---|
| **POS Staff** | Members, Bar |
| **Cashier** | Members, Cashier |
| **Admin** | Members, Cashier, Bar, Admin |

---

## Admin Tab

The Admin tab contains two sections: **App Settings** and **Staff Accounts**.

---

## App Settings

These settings control how ClubLedger looks and behaves. Changes take effect immediately without restarting the server.

### General

| Setting | Description |
|---|---|
| **Club Name** | Appears in the navigation bar, on receipts, and on statements |
| **Timezone** | IANA timezone name (e.g. `Europe/London`, `Asia/Bangkok`). All receipt and statement timestamps are shown in this timezone. Leave blank to use the server's local time. |

### Currency

ClubLedger stores all monetary values as integers in a minor unit (e.g. pence) internally. The settings below control how amounts are displayed and entered.

| Setting | Example | Description |
|---|---|---|
| **Currency Symbol** | `£`, `$`, `€`, `฿` | Prepended to every displayed amount |
| **Currency Name** | `pounds` | The major unit. Shown in amount field labels. Users enter amounts in this unit. |
| **Subunit Name** | `pence` | The minor unit stored in the database. Used in internal labels only. |
| **Subunits per unit** | `100` | How many minor units make one major unit. 100 for most currencies, 1 for currencies with no subunit. |

> **Important:** If you change **Subunits per unit**, all existing balances will be re-displayed using the new divisor. The stored integers do not change. Only change this on a fresh installation.

### Transaction Limits

All limits are entered in the **major unit** (e.g. pounds).

| Setting | Description |
|---|---|
| **Minimum top-up** | Cashier cannot top up less than this amount |
| **Maximum top-up** | Cashier cannot top up more than this in a single transaction |
| **Maximum single charge** | Bar cannot charge more than this in a single transaction |

### Business Address

These fields populate the business header printed at the top of every receipt and statement. All fields are optional — leave blank to omit.

| Field | Description |
|---|---|
| **Address Line 1–4** | Street address, city, postcode, etc. |
| **Country** | Country name or code |
| **Phone** | Contact phone number |
| **Email** | Contact email address |
| **Website** | Contact website URL |

### Branding

| Setting | Description |
|---|---|
| **Logo** | Upload an image file (PNG, JPG, GIF, WebP, or SVG). The file is stored in the `static/` folder of the application. |
| **Logo URL** | The path used to display the logo — set automatically when you upload. Can also be set manually (e.g. `/static/yourlogo.png`) if you are copying a file directly to the server. |
| **Logo Alignment** | `Left`, `Centre`, or `Right` — controls where the logo appears in the receipt/statement header |
| **Logo Max Width** | Maximum display width in pixels (default 200) |
| **Logo Max Height** | Maximum display height in pixels (default 80) |
| **Bar Name** | Label used for the bar/POS venue on receipts (default `Bar`) |
| **Cashier Name** | Label used for the cashier venue on receipts (default `Cashier`) |

### Transactions

| Setting | Description |
|---|---|
| **Transaction Reference Prefix** | Prepended to the auto-generated transaction number. For example, `TXN` produces references like `TXN0000001` (default `TXN`). |
| **Transfer Types** | Comma-separated list of payment methods shown to cashiers in the Transfer Type dropdown on the Cashier tab (e.g. `Bank Transfer,Cash,QR`). |

### Overdraft Policy

Controls whether members are allowed to have a negative balance. The setting is a dropdown with five options:

| Policy | Meaning |
|---|---|
| **Never allowed** | No member can ever go into overdraft |
| **Always allowed** | All members can always go into overdraft |
| **Staff override** | Staff can tick a per-member checkbox to allow overdraft for that specific member |
| **Admin override** | Only admins can tick the per-member overdraft checkbox |
| **Staff block** | Staff can tick a per-member checkbox to block overdraft for a specific member (all others are allowed) |

When the policy is **Staff override**, **Admin override**, or **Staff block**, an **Overdraft override** checkbox appears in the Edit Member modal.

### Receipt Labels

All fields in this section are optional and are provided for localisation. Each field overrides the default label printed on receipts and statements.

| Field | Default |
|---|---|
| Receipt title | `RECEIPT` |
| Top-up receipt title | `TOP-UP RECEIPT` |
| Withdrawal receipt title | `WITHDRAWAL RECEIPT` |
| Staff label | `STAFF` |
| Transaction label | `TRANSACTION` |
| Charge venue label | `CHARGE` |
| Transaction time label | `TRANSACTION TIME` |
| Amount charged label | `AMOUNT CHARGED` |
| Remaining balance label | `REMAINING BALANCE` |
| Balance transfer label | `BALANCE TRANSFER` |
| Amount topped-up label | `AMOUNT TOPPED-UP` |
| Amount withdrawn label | `AMOUNT WITHDRAWN` |
| Transfer type label | `TRANSFER TYPE` |
| Transfer reference label | `TRANSFER REFERENCE` |

### Receipt Footers

Optional text printed at the bottom of receipts. Useful for thank-you messages, refund policies, or contact details. Plain text; line breaks are preserved.

| Field | Appears on |
|---|---|
| **Footer — charge receipts** | Bar charge receipts |
| **Footer — cashier receipts** | Top-up and withdrawal receipts |

---

## Staff Accounts

### Creating an Account

Fill in the **Add Account** form at the bottom of the Staff Accounts panel:

| Field | Notes |
|---|---|
| **Name** | The person's real name — appears on receipts and transaction logs |
| **Username** | Used to sign in. Lowercase letters and numbers recommended. |
| **Password** | Choose something strong. |
| **Role** | **POS Staff**, **Cashier**, or **Admin** — see the Roles section above |

### Editing an Account

Click **Edit** on any row. You can change:
- Name
- Username
- Password (leave blank to keep the current one)
- Role
- **Active** checkbox — untick to disable login without deleting the account

### Deleting an Account

Click **Delete**. You cannot delete your own account, and you cannot delete the last remaining admin account.

### Resetting a Staff Member's Password

Open the edit modal for their account, enter a new password, and save. The next time they log in they use the new password. There is no email reset — passwords are changed directly by an admin.

---

## Managing Members

### Correcting a Transaction

There is no transaction editing or deletion by design (audit trail). To correct a mistake:

- **Overcharged at bar:** Apply a top-up for the difference, with a note explaining the correction.
- **Under-charged at bar:** Apply a charge for the difference, with a note.
- **Wrong member charged:** Top up the affected member and charge the correct one, with matching notes on both.
- **Incorrect top-up or withdrawal:** Apply an equal and opposite transaction (top-up to reverse a withdrawal, or withdrawal to reverse a top-up) with a note.

### Resetting a Member's PIN

Members tab → click **Edit** on the row → enter a new PIN → Save.

### Deleting a Member

The **Delete** button only appears when a member's balance is exactly zero. Deletion is permanent and removes all transaction history for that member. If a member has a non-zero balance, bring it to zero first with a correcting transaction before deleting.

### Printing Statements

Members tab → click **Statement** on any row. Statements open in a new browser tab. Use the A4/A5 toggle before printing.

---

## Backing Up Data

All application data is stored in a SQLite database in the application folder. To take a full backup, copy the following files to another location:

**Database files:**
- `clubledger.db` — the main database
- `clubledger.db-wal` and `clubledger.db-shm` — write-ahead log files that may be present while the app is running

If the app is stopped, only `clubledger.db` needs to be copied (the WAL files will have been checkpointed). If the app is running, copy all three files.

**Logo file (if applicable):**
- `static/logo.png` (or `.jpg`, `.gif`, etc.) — the uploaded logo image. Copy this if you have uploaded a logo via the Branding settings.

```
# Linux / Mac – back up the database to the home directory
cp /path/to/ClubLedger/clubledger.db ~/clubledger-backup-$(date +%Y%m%d).db
```

To restore, stop the server, replace `clubledger.db` with the backup copy (and the logo file if needed), and restart.

---

## Command-Line Tools (`manage.py`)

Two administrative commands are available from the server terminal. They do not require using the web interface.

### Reset an Admin Password

```
python manage.py reset-admin
```

- Interactively resets the password for an admin account.
- If there are multiple admin accounts, lists them and prompts you to select one.
- Prompts for a new password and a confirmation (minimum 4 characters). The password is not echoed to the screen.
- The app does **not** need to be stopped first — WAL mode allows concurrent access.
- Existing sessions for that account remain valid until they expire naturally (8 hours). To invalidate them immediately, restart the app after running this command.

### Reset the Database

```
python manage.py reset-db
```

- **Permanently deletes all data:** members, balances, transactions, staff accounts, and settings. This cannot be undone.
- You must type `RESET` to confirm. Anything else cancels the operation.
- The app **must be stopped** before running this command.
- After running: restart the app. It will create a fresh database with the default `admin` / `admin` credentials.
- Change the admin password immediately after the fresh start.

---

## Checking Transaction Logs

The database can be queried directly with any SQLite tool (e.g. [DB Browser for SQLite](https://sqlitebrowser.org/), which is free and cross-platform):

```sql
-- All transactions in the last 7 days
SELECT m.name, m.member_number, l.type, l.amount, l.staff_name, l.created_at
FROM ledger_entries l
JOIN members m ON m.id = l.member_id
WHERE l.created_at >= datetime('now', '-7 days')
ORDER BY l.created_at DESC;

-- Current balance for every member
SELECT m.name, m.member_number,
       SUM(CASE WHEN l.type='topup' THEN l.amount ELSE -l.amount END) AS balance
FROM members m
LEFT JOIN ledger_entries l ON l.member_id = m.id
GROUP BY m.id
ORDER BY m.name;
```
