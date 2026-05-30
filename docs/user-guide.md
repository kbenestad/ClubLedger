# ClubLedger – Staff User Guide

## What is ClubLedger?

ClubLedger is a store-credit system for clubs and venues. Members load credit onto their account at the cashier desk, then spend it at the bar or other service points. All transactions are tracked and receipts are generated automatically.

---

## Signing In

Open the ClubLedger address in any web browser. Enter the username and password provided by your administrator, then click **Sign In**.

Your name appears in the top corner of every screen while you are signed in. Click **Sign out** when you are finished.

> **Sessions expire after 8 hours.** The sign-in screen reappears automatically when your session ends. If the server is restarted, everyone is logged out regardless of how long they have been signed in.

---

## Tabs and Roles

The navigation bar shows tabs depending on your role. You will only see the tabs listed for your role below.

| Role | Tabs visible |
|---|---|
| **POS Staff** | Members, Bar |
| **Cashier** | Members, Cashier |
| **Admin** | Members, Cashier, Bar, Admin |

Click any tab to switch to it.

---

## Members Tab

All roles can see this tab. Use it to register new members, search for existing members, and manage member records.

### Registering a New Member

Fill in the **Register New Member** form at the top of the tab:

| Field | Notes |
|---|---|
| Member Number | A unique identifier — a number, a code, or any text your venue uses |
| Full Name | The member's name as it will appear on receipts and statements |
| PIN | A secret code (minimum 4 characters) the member uses to authorise charges. Tell the member their PIN privately. |

Click **Register**. The new member appears in the table below.

### Searching for a Member

Type part of a name or member number into the search box and click **Search** (or press **Enter**). Searching with an empty box lists all members.

### The Member Table

Search results appear in a table with these columns:

| Column | Meaning |
|---|---|
| # | Member number |
| Name | Full name |
| Balance | Current account balance |
| Joined | Registration date |
| Actions | Buttons to act on this member |

### Actions

Each row has up to three action buttons:

| Button | What it does |
|---|---|
| **Statement** | Opens a printable full transaction history in a new tab |
| **Edit** | Opens a modal to change the member's details |
| **Delete** | Permanently removes the member. Only appears when the balance is exactly zero. |

### Editing a Member

Click **Edit** on a row. A modal appears with the current details pre-filled.

| Field | Notes |
|---|---|
| Member Number | Change the member's unique ID if needed |
| Full Name | Update the name |
| New PIN | Enter a new PIN to change it. Leave blank to keep the existing PIN. |
| Overdraft override | May appear depending on the global overdraft policy and your role — see the Overdraft section below. |

Click **Save** to apply changes or close the modal to cancel.

### Printing a Statement

Click **Statement** on any member's row. The full transaction history opens in a new tab. Use the **A4 / A5** toggle to select paper size, then print from your browser.

---

## Cashier Tab

Cashiers and Admins can see this tab. Use it to add credit to a member's account (top-up) or withdraw credit from it.

### Selecting a Member

Search for the member and click their row to select them. Their name and current balance appear at the top of the panels. Click **Cancel** at any time to deselect the member and clear all fields.

### Top Up Panel

Use this panel to add credit to the member's account.

| Field | Notes |
|---|---|
| Amount | The amount to add, in the major currency unit (e.g. `10.00`) |
| Transfer Type | How the payment was made — options are configured by your administrator (e.g. Bank Transfer, Cash, QR) |
| Transfer Reference | Optional. A reference for your records, such as a payment reference number |
| Note | Optional. Any additional note about this transaction |

Click **Top Up**. A receipt opens automatically in a new tab.

### Withdrawal Panel

Use this panel to remove credit from the member's account.

| Field | Notes |
|---|---|
| Amount | The amount to withdraw |
| Member PIN | Required. The member must provide their PIN to authorise every withdrawal. |
| Transfer Type | How the funds are being returned — options configured by your administrator |
| Transfer Reference | Optional. A reference for your records |
| Note | Optional. Any additional note |

Click **Withdraw**. A receipt opens automatically in a new tab.

---

## Bar Tab

POS Staff and Admins can see this tab. Use it to charge a member's account for purchases.

### How to Charge

1. Search for the member by name or number and click their row.
2. Enter the **Amount** to charge.
3. Enter the member's **PIN** — this is always required.
4. Optionally add a **Note** (for example, what was purchased).
5. Click **Charge**.

If the PIN is incorrect, an error appears and nothing is charged. If the balance is insufficient, the charge is blocked unless the member has overdraft permission (see the Overdraft section).

A receipt opens automatically in a new tab on a successful charge.

Click **Cancel** to deselect the member and clear all fields.

---

## Receipts and Statements

### Receipts

A receipt opens in a new tab automatically after every successful transaction. Receipts include:

- Business header (logo, name, address, contact details)
- Receipt title and transaction reference (e.g. `TXN0000001`)
- Staff name who processed the transaction
- Venue and timestamp (in the configured timezone)
- Amount and remaining balance
- For top-ups and withdrawals: the transfer type and transfer reference

Use the **A4 / A5** toggle at the top of the receipt before printing.

> **Tip:** If the receipt tab does not open, your browser may be blocking pop-ups. Allow pop-ups for this site in your browser settings.

### Statements

Statements are accessed via the **Statement** button in the Members tab. They show the member's complete transaction history as a table:

| Column | Content |
|---|---|
| Date/Time | When the transaction occurred (configured timezone) |
| Reference | Transaction reference (e.g. `TXN0000001`) |
| Type | Top-up, Withdrawal, or Charge |
| Venue | Where the transaction was processed |
| Staff | Who processed the transaction |
| Amount | Positive for top-ups, negative for charges and withdrawals |
| Balance | Account balance after that transaction |

Each transaction also has a second row showing transfer details (for top-ups and withdrawals) or the note (for charges).

Use the **A4 / A5** toggle before printing.

---

## Overdraft

By default, charges that would take a member's balance below zero are blocked. Your administrator can change this behaviour using a global overdraft policy. The policy affects what you see in the **Edit Member** modal:

| Policy | What you see in Edit Member | What it means |
|---|---|---|
| Never allowed | No checkbox | No member can go into overdraft, ever |
| Always allowed | No checkbox | All members can always go into overdraft |
| Staff override | Checkbox (staff can tick it) | Ticking the checkbox for a member allows them to go into overdraft |
| Admin override | Checkbox (only admins can tick it) | Same as above, but only admins can set it |
| Staff block | Checkbox (staff can tick it) | Ticking the checkbox for a member blocks them from overdraft |

If you are unsure whether a member should be allowed to go into overdraft, check with your administrator before changing any checkbox.

---

## Common Questions

**The member forgot their PIN.**
An admin or cashier with edit access can reset it: Members tab → Edit → enter a new PIN in the **New PIN** field → Save. Leave the field blank if you do not want to change it.

**I entered the wrong amount.**
There is no undo button. A correcting transaction must be applied manually. For a top-up error, process a withdrawal for the difference (or the full amount and re-top-up correctly). For a bar charge error, contact an administrator.

**The receipt tab did not open.**
Your browser is likely blocking pop-ups. Find the pop-up blocked notification in your browser's address bar and allow pop-ups for this site, then try the transaction again.

**A member's balance is wrong.**
Use the **Statement** button on the member's row to view their full transaction history and identify any discrepancies. Contact an administrator if a correction is needed.

**I cannot see a tab I expect.**
Tab visibility depends on your role. If you believe your role is incorrect, contact your administrator.
