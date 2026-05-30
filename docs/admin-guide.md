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

## Admin Tab

The Admin tab contains two sections: **App Settings** and **Staff Accounts**.

---

## App Settings

These settings control how ClubLedger looks and behaves. Changes take effect immediately without restarting the server.

### Club Identity

| Setting | Description |
|---|---|
| **Club Name** | Appears in the navigation bar, on receipts, and on statements |

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

### Receipt Footer

Optional text printed at the bottom of every receipt and statement. Useful for:
- A thank-you message
- A refund or returns policy
- Contact details

Accepts plain text. Line breaks are preserved.

### Allow Negative Balance (Overdraft)

When ticked, the bar can charge a member even if their balance would go below zero. When unticked (the default), charges are blocked if the member has insufficient funds.

---

## Staff Accounts

### Creating an Account

Fill in the **Add Account** form at the bottom of the Staff Accounts panel:

| Field | Notes |
|---|---|
| Name | The person's real name — appears on receipts and transaction logs |
| Username | Used to sign in. Lowercase letters and numbers recommended. |
| Password | Minimum length enforced by the browser. Choose something strong. |
| Role | **Staff** or **Admin** — see below |

### Roles

| Role | Capabilities |
|---|---|
| **Staff** | Members, Cashier, Bar tabs |
| **Admin** | Everything above, plus the Admin tab (settings and account management) |

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

- **Overcharged:** Apply a top-up for the difference, with a note explaining the correction.
- **Under-charged:** Apply a charge for the difference, with a note.
- **Wrong member charged:** Top up the affected member and charge the correct one, with matching notes on both.

### Resetting a Member's PIN

Members tab → click **Edit** on the row → enter a new PIN → Save.

### Deleting a Member

The **Delete** button only appears when a member's balance is exactly zero. Deletion is permanent and removes all transaction history for that member. If a member has a non-zero balance, bring it to zero first with a correcting transaction before deleting.

### Printing Statements

Members tab → click **Statement** on any row. Statements open in a new browser tab. Use the A4/A5 toggle before printing.

---

## Backing Up Data

All data is stored in a single SQLite file: `clubledger.db` in the application folder. To back up, simply copy this file to another location.

```
# Linux / Mac – copy to home directory
cp /path/to/ClubLedger/clubledger.db ~/clubledger-backup-$(date +%Y%m%d).db
```

The `staff.json` file stores the legacy staff name list (used only by the standalone `/cashier` and `/bar` pages, not the main app). Back this up too if you use those pages.

To restore, stop the server, replace `clubledger.db` with the backup copy, and restart.

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
