# ClubLedger – Staff User Guide

## What is ClubLedger?

ClubLedger is a store-credit system for clubs and venues. Members load credit onto their account at the cashier desk, then spend it at the bar or other service points. All transactions are tracked and receipts are printed automatically.

---

## Signing In

Open the ClubLedger address in any web browser. You will see a sign-in screen. Enter the username and password given to you by your administrator, then click **Sign In**.

Your name appears in the top-right corner of every screen while you are signed in. Click **Sign out** when you are done.

> Sessions expire after 8 hours. The sign-in screen will reappear automatically when your session ends.

---

## The Three Tabs

The navigation bar at the top has three tabs: **Members**, **Cashier**, and **Bar**. Click a tab to switch between them. Administrators also see an **Admin** tab.

---

## Members Tab

Use this tab to register new members, look up existing members, and print account statements.

### Registering a New Member

Fill in the **Register New Member** form:

| Field | Notes |
|---|---|
| Member Number | A unique ID for the member — a number, code, or anything you choose |
| Full Name | The member's name as it should appear on receipts |
| PIN | A secret 4-digit (or longer) code the member uses at the bar. Tell the member their PIN privately. |

Click **Register**. The member appears in the table below.

### Searching for a Member

Type part of a name or member number into the search box and click **Search** (or press Enter). Leave the box empty and search to list everyone.

### The Member Table

Each row shows the member's number, name, current balance, and join date.

| Button | What it does |
|---|---|
| **Statement** | Opens a printable full transaction history in a new tab |
| **Edit** | Change the member's name, number, or PIN |
| **Delete** | Only appears when balance is exactly zero. Permanently removes the member. |

### Editing a Member

Click **Edit** on any row. A panel appears with the current name and member number pre-filled. Change what you need. Leave the **New PIN** field blank to keep their current PIN. Click **Save**.

### Printing a Statement

Click **Statement** to open the statement in a new tab. Use the **A4 / A5** toggle to choose the paper size, then click **Print Statement**.

---

## Cashier Tab

Use this tab to add credit to a member's account (top-up).

### How to Top Up

1. Search for the member by name or number and click their row.
2. The selected member's name and current balance appear at the top of the form.
3. Enter the **Amount** — type it in the major currency unit (e.g. `10.00` for ten pounds).
4. Add an optional **Note** (e.g. "cash payment", "card payment").
5. Click **Top Up**.

A receipt opens automatically in a new tab. Print it or close it.

If you need to start over, click **Cancel** to deselect the member.

### Receipts

Receipts show: member name and number, transaction type, amount, balance after, staff name, timestamp, and any footer text set by the administrator.

Use the **A4 / A5** toggle at the top of the receipt page before printing.

---

## Bar Tab

Use this tab to charge a member's account (debit). The member must enter their PIN.

### How to Charge

1. Search for the member and click their row.
2. Enter the **Amount** to charge (e.g. `3.50`).
3. The member enters their **PIN** into the field.
4. Add an optional **Note** (e.g. the item name).
5. Click **Charge**.

If the PIN is wrong, an error appears and nothing is charged. If the balance is insufficient, the charge is also blocked (unless the administrator has enabled overdraft).

A receipt opens automatically in a new tab on a successful charge.

---

## Common Questions

**The member forgot their PIN.** An administrator can reset it: Members tab → Edit → enter a new PIN.

**I topped up the wrong amount.** Contact an administrator. There is no undo button — a correcting charge or top-up must be applied manually and noted.

**The receipt tab didn't open.** Your browser may be blocking pop-ups. Allow pop-ups for this site in your browser settings, or navigate directly to the statement page via Members → Statement.

**The balance shows in the wrong currency.** Contact your administrator to update the currency settings in the Admin area.
