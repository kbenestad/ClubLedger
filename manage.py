#!/usr/bin/env python3
"""
ClubLedger management CLI
Run from the server terminal (NOT through the web UI).
The app does not need to be stopped first for reset-admin;
it MUST be stopped before reset-db.

Usage:
  python manage.py reset-admin   – reset an admin account password
  python manage.py reset-db      – wipe all data and start fresh
"""

import sys
import getpass
import sqlite3
from pathlib import Path

DB_PATH = Path("clubledger.db")


def _connect():
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        print("Start the app at least once to create it.")
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def cmd_reset_admin():
    """Interactively reset the password for an admin account."""
    import bcrypt

    conn = _connect()
    admins = conn.execute(
        "SELECT id, name, username FROM staff_accounts WHERE role='admin' ORDER BY name"
    ).fetchall()

    if not admins:
        print("No admin accounts exist.")
        print("Start the app — it will create the default admin/admin account automatically.")
        conn.close()
        sys.exit(0)

    if len(admins) == 1:
        target = admins[0]
    else:
        print("Admin accounts:")
        for i, a in enumerate(admins, 1):
            print(f"  {i}. {a['name']}  ({a['username']})")
        while True:
            raw = input("Select account number: ").strip()
            try:
                target = admins[int(raw) - 1]
                break
            except (ValueError, IndexError):
                print("  Invalid — enter the number shown above.")

    print(f"\nResetting password for: {target['name']} ({target['username']})")
    while True:
        pw = getpass.getpass("New password: ")
        if len(pw) < 4:
            print("  Password must be at least 4 characters.")
            continue
        pw2 = getpass.getpass("Confirm password: ")
        if pw != pw2:
            print("  Passwords do not match — try again.")
            continue
        break

    hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    conn.execute(
        "UPDATE staff_accounts SET password_hash=? WHERE id=?",
        (hashed, target["id"]),
    )
    conn.commit()
    conn.close()
    print(f"\nDone. Password updated for '{target['username']}'.")
    print("Any existing sessions for this account will still be valid until they expire (8 h).")
    print("Restart the app now to invalidate all active sessions immediately.")


def cmd_reset_db():
    """Delete all data files and prepare for a clean start."""
    print("=" * 60)
    print("  DATABASE RESET")
    print("=" * 60)
    print()
    print("This will permanently delete:")
    print("  • All members and their balances")
    print("  • All transactions and receipts")
    print("  • All staff accounts")
    print("  • All app settings")
    print()
    print("STOP THE APP before continuing.")
    print()
    confirm = input('Type  RESET  to confirm (anything else cancels): ').strip()
    if confirm != "RESET":
        print("Cancelled — nothing was changed.")
        sys.exit(0)

    deleted = []
    for suffix in ("", "-wal", "-shm"):
        p = DB_PATH.parent / (DB_PATH.name + suffix)
        if p.exists():
            p.unlink()
            deleted.append(p.name)

    if deleted:
        print(f"\nDeleted: {', '.join(deleted)}")
    else:
        print("\nNo database files found — nothing to delete.")

    print()
    print("Reset complete. Start the app to create a fresh database.")
    print("Default admin credentials after restart:  username=admin  password=admin")
    print("Change the password immediately after logging in.")


# ---------------------------------------------------------------------------

COMMANDS = {
    "reset-admin": (cmd_reset_admin, "Reset an admin account password"),
    "reset-db":    (cmd_reset_db,    "Wipe all data and start fresh (irreversible)"),
}


def usage():
    print(__doc__)
    print("Commands:")
    for name, (_, desc) in COMMANDS.items():
        print(f"  {name:<16}  {desc}")
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        usage()
    COMMANDS[sys.argv[1]][0]()
