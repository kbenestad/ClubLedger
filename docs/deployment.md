# ClubLedger – Deployment Guide

## Overview

ClubLedger runs as a small web server on **one computer** (the server). Every other device on the same Wi-Fi network — tablets at the bar, a laptop at the cashier desk, a phone — opens the app in a normal web browser. No software is installed on the client devices.

```
                     Wi-Fi Router
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   Server PC        Cashier Tablet    Bar Tablet
   runs ClubLedger  opens browser     opens browser
   :8000            http://192.168.1.x:8000
```

---

## Part 1 – Initial Setup

### Prerequisites by Operating System

#### Linux (Debian / Ubuntu)

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-full
```

#### macOS

Install [Homebrew](https://brew.sh/) if you haven't already, then:

```bash
brew install git python3
```

Alternatively, download Python from [python.org](https://www.python.org/downloads/) and install Git from [git-scm.com](https://git-scm.com/).

#### Windows

1. Download and install **Python 3.11+** from [python.org](https://www.python.org/downloads/).
   - On the first installer screen, tick **"Add Python to PATH"** before clicking Install.
2. Download and install **Git** from [git-scm.com](https://git-scm.com/download/win). Accept all defaults.

---

### Get the Code

Open a terminal (Linux/Mac) or **Git Bash** / **Command Prompt** (Windows):

```bash
# Clone the repository
git clone https://github.com/kbenestad/clubledger.git
cd ClubLedger

# Or, if you downloaded a ZIP instead:
# Unzip it, then open a terminal in that folder
```

---

### Start the Server

**Linux / macOS:**

```bash
chmod +x run.sh
./run.sh
```

**Windows** — open **Command Prompt** or **PowerShell** in the project folder:

```cmd
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

> On Windows you can also create a `run.bat` file with those three lines so double-clicking it starts the server in future.

The first time it runs, the server prints the default admin credentials to the terminal:

```
============================================================
  Default admin created  →  username: admin  password: admin
  Change this immediately in the Admin → Staff Accounts area.
============================================================
```

It then starts listening:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Open `http://localhost:8000` in a browser on the same machine to confirm it works.

---

## Part 2 – Finding the Server's IP Address

For other devices to connect, you need the **local IP address** of the server machine — the address your router has assigned to it on the Wi-Fi network. This is usually something like `192.168.1.42` or `10.0.0.15`.

### Linux

```bash
hostname -I
```

The first address listed is normally the right one. Example output: `192.168.1.42`

Or with more detail:

```bash
ip addr show | grep "inet " | grep -v "127.0.0.1"
```

### macOS

Open **System Settings → Network → Wi-Fi → Details**. The IP address is listed there.

Or in a terminal:

```bash
ipconfig getifaddr en0   # Wi-Fi
ipconfig getifaddr en1   # Try this if the above gives nothing
```

### Windows

Open **Command Prompt** and run:

```cmd
ipconfig
```

Look for the section labelled **Wi-Fi** (or **Wireless LAN adapter Wi-Fi**). The value next to **IPv4 Address** is the server's address — for example `192.168.1.42`.

---

## Part 3 – Connecting Other Devices

Once you have the server's IP address, any device on the same Wi-Fi network can open ClubLedger by entering this address in any browser:

```
http://192.168.1.42:8000
```

Replace `192.168.1.42` with your actual IP address.

This works on:
- Other laptops and desktops (any browser)
- iPads and Android tablets
- Smartphones

> **No app installation needed.** The browser is the client.

---

## Part 4 – Keeping It Running

By default, ClubLedger stops when you close the terminal. To keep it running continuously, set it up as a background service.

### Linux – systemd Service

Create a service file. Replace `/home/youruser/ClubLedger` with the actual path.

```bash
sudo nano /etc/systemd/system/clubledger.service
```

Paste the following (adjust `User`, `WorkingDirectory`, and the path to Python):

```ini
[Unit]
Description=ClubLedger Store Credit App
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/ClubLedger
ExecStart=/home/youruser/ClubLedger/.venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable clubledger
sudo systemctl start clubledger
```

Check it is running:

```bash
sudo systemctl status clubledger
```

View logs:

```bash
journalctl -u clubledger -f
```

ClubLedger now starts automatically when the computer boots.

---

### macOS – launchd

Create a file at `~/Library/LaunchAgents/com.clubledger.plist`.

Adjust the paths below to match your actual username and ClubLedger folder:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.clubledger</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/youruser/ClubLedger/.venv/bin/python</string>
        <string>/Users/youruser/ClubLedger/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/youruser/ClubLedger</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/youruser/ClubLedger/clubledger.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/youruser/ClubLedger/clubledger.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.clubledger.plist
```

To stop it:

```bash
launchctl unload ~/Library/LaunchAgents/com.clubledger.plist
```

Logs are written to `clubledger.log` in the project folder.

---

### Windows – Task Scheduler

1. Create a file called `start_clubledger.bat` in the ClubLedger folder:

```bat
@echo off
cd /d "C:\Users\YourName\ClubLedger"
.venv\Scripts\python main.py
```

2. Open **Task Scheduler** (search for it in the Start menu).
3. Click **Create Basic Task…**
4. Name it `ClubLedger`. Click Next.
5. Trigger: **When the computer starts**. Click Next.
6. Action: **Start a program**. Click Next.
7. Browse to `start_clubledger.bat`. Click Next, then Finish.
8. Right-click the new task → **Properties** → **General** tab → tick **Run whether user is logged on or not**.

ClubLedger will now start automatically at boot.

To check it manually, right-click the task and choose **Run**.

---

## Part 5 – Using a Fixed IP Address

Router DHCP can change the server's IP over time, which would break the URL bookmarked on client devices. Prevent this by assigning a **static IP** to the server machine.

### Option A – Reserve the IP in Your Router (Recommended)

1. Log in to your router admin page (usually `http://192.168.1.1` or `http://192.168.0.1`).
2. Find **DHCP Reservations** or **Static DHCP** (varies by router brand).
3. Find the server's MAC address and assign it a fixed IP (e.g. `192.168.1.10`).

The router always gives the same IP to that machine. No changes needed on the machine itself.

### Option B – Static IP on the Machine

See your operating system's network settings to assign a static IP manually. Use an address outside the router's DHCP range to avoid conflicts. Set the gateway to your router's IP and DNS to `8.8.8.8` or your router's IP.

---

## Part 6 – Changing the Port

If port 8000 is in use by something else, edit the last line of `main.py`:

```python
uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
```

Or pass it as an argument:

```bash
./run.sh --port 8080     # Linux / macOS
.venv\Scripts\python main.py --port 8080   # Windows
```

Devices would then connect to `http://192.168.1.42:8080`.

---

## Part 7 – Security Notes

ClubLedger is designed for a **trusted internal network** — a private club or venue Wi-Fi. It is not hardened for exposure to the public internet.

| Risk | Mitigation |
|---|---|
| Staff accessing admin settings | Use separate staff and admin accounts; do not share admin credentials |
| Weak PINs | Encourage members to set at least 6-digit PINs |
| Data loss | Back up `clubledger.db` regularly (copy the file) |
| Unauthorised network access | Use WPA2/WPA3 Wi-Fi with a strong password; consider a separate staff VLAN if your router supports it |
| Accidental deletion | The delete button only appears on zero-balance accounts; there is no bulk delete |

**Do not expose ClubLedger directly to the internet** (e.g. by port-forwarding port 8000 on your router) without first adding HTTPS and reviewing security. For internal-only use it is fine as-is.

---

## Quick Reference

| Task | Command |
|---|---|
| Start the server (Linux/Mac) | `./run.sh` |
| Start the server (Windows) | `.venv\Scripts\python main.py` |
| Find server IP (Linux) | `hostname -I` |
| Find server IP (Mac) | `ipconfig getifaddr en0` |
| Find server IP (Windows) | `ipconfig` → IPv4 Address under Wi-Fi |
| Access from another device | `http://<server-ip>:8000` |
| Stop the server | Press `Ctrl+C` in the terminal |
| View systemd logs (Linux) | `journalctl -u clubledger -f` |
| Backup data | Copy `clubledger.db` to a safe location |
