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

## Part 7 – Keeping It Off the Internet

ClubLedger has no HTTPS, no brute-force protection, and no rate limiting. It is designed exclusively for use on a private local network. This section explains why it is safe by default, and how to make that guarantee explicit.

### Why it is already protected by default

Every home and business router uses **NAT (Network Address Translation)**. NAT means:

- Your router has one public IP address (assigned by your internet provider).
- All devices on your network share that one address.
- Inbound connections from the internet are **dropped by the router** unless you explicitly tell it to forward them.

ClubLedger listens on port 8000. Unless you specifically create a port-forwarding rule for port 8000 in your router settings, **no one on the internet can reach it**. This is the default state of every standard router.

### What never to do

- **Do not create a port-forwarding rule** for port 8000 (or whichever port ClubLedger uses) in your router's admin panel. This is the only action that would expose it.
- **Do not use a reverse proxy** (nginx, Caddy, Apache) to publish it under a public domain unless you have added authentication, HTTPS, and rate limiting first.
- **Do not run it on a cloud server** (VPS, AWS, etc.) without those same protections.

### Verify it is not reachable from outside

To confirm ClubLedger is not publicly accessible, check from a device that is **not on your Wi-Fi** (e.g. a phone on mobile data, or ask someone outside the building):

1. Find your public IP address — visit [https://ifconfig.me](https://ifconfig.me) from a computer on your network.
2. From the external device, try to open `http://<your-public-ip>:8000`.
3. It should time out or refuse the connection. If it loads ClubLedger, you have an unintended port-forwarding rule — remove it from your router immediately.

### Restrict the server to the local network interface (belt-and-suspenders)

By default ClubLedger binds to `0.0.0.0`, meaning it accepts connections on all network interfaces, including the local one. For extra certainty you can bind it only to your specific Wi-Fi interface IP so it cannot be reached even if a forwarding rule is accidentally added.

Find the server's local IP (e.g. `192.168.1.42`), then edit the last line of `main.py`:

```python
uvicorn.run("main:app", host="192.168.1.42", port=8000, reload=True)
```

With this change, the app only accepts connections from devices on your local network. Nothing outside the router can reach it regardless of router configuration.

> Note: if the server's local IP changes (e.g. after a reboot), the app will fail to start. Use this option only after setting a fixed/reserved IP (see Part 5).

### Add a firewall rule (optional, Linux only)

On Linux you can use `ufw` (Uncomplicated Firewall) to explicitly allow port 8000 only from your local network range and block everything else:

```bash
sudo ufw enable
# Allow from local network (adjust 192.168.1.0/24 to match your network)
sudo ufw allow from 192.168.1.0/24 to any port 8000
# Block port 8000 from everywhere else
sudo ufw deny 8000
sudo ufw status
```

This means even if your router accidentally forwarded port 8000, the firewall on the server itself would drop those packets.

To find your local network range: if your server's IP is `192.168.1.42`, your range is almost certainly `192.168.1.0/24`.

---

## Part 8 – Security Notes

| Risk | Mitigation |
|---|---|
| Internet exposure | NAT protects by default — do not add port-forwarding rules (see Part 7) |
| Unauthorised Wi-Fi access | Use WPA2/WPA3 with a strong passphrase; consider a guest network for members separate from the staff network |
| Staff accessing admin settings | Use separate staff and admin accounts; do not share admin credentials |
| Weak member PINs | Encourage members to set at least 6-digit PINs |
| Data loss | Back up `clubledger.db` regularly — just copy the file |
| Accidental deletion | Delete only appears on zero-balance accounts; there is no bulk delete |

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
| Verify not internet-accessible | From mobile data: `http://<public-ip>:8000` should time out |
