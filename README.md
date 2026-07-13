![syryn](https://raw.githubusercontent.com/szholobetsky/simrgl/main/images/logo/syryn.png)

# syryn

Bluetooth identity beacon for headless Linux devices.

The name comes from *Сирин* — a bird from Slavic mythology known for its voice. Syryn speaks when asked: it listens on a Bluetooth RFCOMM channel and responds with the device's hostname, mDNS address, and active network interfaces.

---

## What it does

Run `syryn` on a headless mini-PC. From any nearby Bluetooth device, send `STATUS` — and get back:

```
hostname: panteon-john
mdns: panteon-john.local
eth0: 192.168.0.131
wlan0: 192.168.1.44
external_ip: 93.12.34.56
```

No display needed. No SSH session. No prior knowledge of the IP address.

---

## Install & quick start

### 1. System packages (one-time)

syryn uses the BlueZ D-Bus API directly — **no PyBluez2 required**.

Debian / Ubuntu / Xubuntu:
```bash
sudo apt install bluez python3-dbus python3-gi
```

Fedora / RHEL:
```bash
sudo dnf install bluez python3-dbus python3-gobject
```

### 2. Enable Bluetooth

```bash
sudo systemctl enable bluetooth --now   # start and enable on boot

rfkill list                             # check if adapter is blocked
sudo rfkill unblock bluetooth           # unblock if needed

bluetoothctl discoverable on            # make device visible
```

To keep the device permanently discoverable, add `DiscoverableTimeout = 0` to
`/etc/bluetooth/main.conf` and restart `bluetooth.service`.

### 3. Install syryn

syryn uses system D-Bus libraries. Install with `--system-site-packages` so pipx
can find them:

```bash
pipx install syryn --system-site-packages
```

Or without pipx:
```bash
pip install syryn
```

### 4. Run

```bash
syryn               # auto-pairing, no PIN
syryn --pin 1234    # hardcoded PIN for all incoming pairs
syryn -q            # quiet mode, no log output
```

Syryn registers a Serial Port Profile (SPP) via BlueZ and a pairing agent so
connecting devices are accepted automatically (no manual PIN prompt). The device
name visible to other devices is the system hostname
(set via `hostnamectl set-hostname <name>`).

### 5. Connect from another device

From any device with a Bluetooth terminal app (e.g. **Serial Bluetooth Terminal** on Android):

1. Scan for Bluetooth devices — the headless device appears by hostname
2. Pair (accepted automatically by syryn)
3. Connect to the **Syryn** service (Serial Port)
4. Send `STATUS` — receive hostname, mDNS, interfaces, external IP

---

## Requirements

- Linux with BlueZ (`bluetoothd` running)
- Python 3.10+
- `python3-dbus` + `python3-gi` (system packages) — BlueZ D-Bus interface and pairing agent
- `psutil`, `requests` (installed automatically via pip)

---

## Part of the SIMARGL toolkit

syryn is one of eight tools that together form an **intellectual development support system**:

| Tool | Role |
|---|---|
| **[simargl](https://github.com/szholobetsky/simargl)** | Task-to-code retrieval — given a task description, finds which files and modules are likely affected, using semantic similarity over git history |
| **[svitovyd](https://github.com/szholobetsky/svitovyd)** | Project map — scans any codebase and produces a structural map of definitions and cross-file dependencies; exposes it as an MCP server |
| **[1bcoder](https://github.com/szholobetsky/1bcoder)** | AI coding assistant for small local models — surgical context management, agents, parallel inference, proc scripts |
| **[yasna](https://github.com/szholobetsky/yasna)** | Session memory — indexes conversations from all AI agents so you can find what was discussed, when, and where |
| **[radogast](https://github.com/szholobetsky/radogast)** | Context drift monitor — measures how far an AI agent's conversation has drifted from the original task |
| **[vyrii](https://github.com/szholobetsky/vyrii)** | Local AI web UI — chat, translate, web research, RAG, and file management via Gradio; powered by Ollama or any OpenAI-compatible backend |
| **[syryn](https://github.com/szholobetsky/syryn)** | Bluetooth identity beacon — returns hostname, mDNS, and active network interfaces for headless devices |
| **[alkonost](https://github.com/szholobetsky/alkonost)** | Task-board viewer/editor — Trello-style board and backlog over 1bcoder's `deepagent_task` output, with full spec rendering and autosave |

---

**(c) 2026 Stanislav Zholobetskyi, Oleh Andriichuk**
Institute for Information Recording, National Academy of Sciences of Ukraine, Kyiv
*PhD research: «Intelligent Technology for Software Development and Maintenance Support»*
