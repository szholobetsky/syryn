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

### Zero-touch: the IP is the Bluetooth name

You don't even need a terminal app. While syryn runs, the device's Bluetooth name
**is** its current IP:

```
P:192.168.0.131
```

Open the ordinary Bluetooth settings on any phone or laptop and read it from the
scan list — no app, no pairing, no commands. The name follows the IP: when DHCP
hands out a new address, the name changes within `--interval` seconds (default 15).

| Where you look | What you see | How |
|---|---|---|
| Android — Settings → Bluetooth → pair new device | `P:192.168.0.131` | classic BR/EDR name (adapter alias) |
| iPhone / iPad — Settings → Bluetooth | `P:192.168.0.131` | BLE advertisement with the HID service UUID (iOS lists only "connectable kinds" of devices) |
| Windows 10/11 — Settings → Bluetooth → Add device | `P:192.168.0.131` | classic name / BLE |
| Windows 10/11 laptop nearby, with `--swiftpair` | **pop-up toast** "New Bluetooth device found: P:192.168.0.131" | Microsoft Swift Pair beacon |
| macOS / Linux — Bluetooth settings | `P:192.168.0.131` | classic name / BLE |

Notes:
- The prefix is `P` by default (`--prefix X` to change, `--prefix ""` for the bare IP).
- A BLE packet has room for ~15 name characters. If `P:` + a long IP (e.g. `P:192.168.100.200`)
  doesn't fit, the BLE name becomes the bare IP — never a truncated one. The classic name always has the full label.
- The IP shown is the one on the **LAN cable** (wired Ethernet port: `eth0`, `enp3s0`, USB-Ethernet `enx…`) —
  Wi-Fi, docker/veth bridges and VPN tunnels are ignored. With no cable / no DHCP lease the name is `P:no-lan`.
  `--iface auto` uses the default-route interface instead (may be Wi-Fi); `--iface wlan0` pins a specific one.
- Devices you already **paired** with may cache the old name; unpaired scans show the current one.
- Tapping the entry on iPhone/Windows tries to pair as a keyboard and fails harmlessly — you only need to read the name.
- The Swift Pair pop-up is **off by default**: Windows keeps offering to connect to the device every
  time it is near, which gets annoying fast. Turn it on with `--swiftpair`; it then appears only when
  the laptop is close (Windows uses a signal-strength threshold) and Settings → Bluetooth →
  "Show notifications to connect using Swift Pair" is on. That Windows switch also silences it.

### One-line install (starts on every boot)

```bash
curl -fsSL https://raw.githubusercontent.com/szholobetsky/syryn/main/install.sh | sudo sh
```

Installs BlueZ + D-Bus bindings, puts syryn into `/opt/syryn`, and registers a
systemd service. Do it once while you still have a screen or SSH; after that the
device announces its IP by itself on every boot. Logs: `journalctl -u syryn -f`.

If syryn is already installed via pip/pipx:

```bash
sudo "$(command -v syryn)" install            # deps check + systemd unit + start
sudo "$(command -v syryn)" install --pin 1234 # flags are baked into the service
sudo "$(command -v syryn)" uninstall
syryn install --dry-run                       # preview, changes nothing
```

---

## Install & quick start (manual)

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
syryn               # auto-pairing, no PIN; name = P:<ip>
syryn --pin 1234    # hardcoded PIN for all incoming pairs
syryn -q            # quiet mode, no log output
syryn status        # print the STATUS text locally and exit
syryn --iface auto  # name from the default-route interface instead of the LAN cable
syryn --no-name     # keep the hostname as the Bluetooth name
syryn --no-ble      # classic Bluetooth only (no iPhone visibility)
syryn --swiftpair   # also pop up "New device found: P:<ip>" on Windows laptops nearby
```

Syryn registers a Serial Port Profile (SPP) via BlueZ and a pairing agent so
connecting devices are accepted automatically (no manual PIN prompt). The device
name visible to other devices is `P:<ip>` while syryn runs; on exit it reverts to
the system hostname (set via `hostnamectl set-hostname <name>`). With `--no-name`
the hostname is kept all the time.

### 5. Connect from another device

From any device with a Bluetooth terminal app (e.g. **Serial Bluetooth Terminal** on Android):

1. Scan for Bluetooth devices — the headless device appears as `P:<ip>` (or by hostname with `--no-name`)
2. Pair (accepted automatically by syryn)
3. Connect to the **Syryn** service (Serial Port)
4. Send `STATUS` — receive hostname, mDNS, interfaces, external IP

---

## Requirements

- Linux with BlueZ (`bluetoothd` running)
- Python 3.10+
- `python3-dbus` + `python3-gi` (system packages) — BlueZ D-Bus interface and pairing agent
- BLE name/pop-up: BlueZ 5.43+ with an LE-capable adapter (otherwise syryn falls back to the classic name only)
- `syryn install`: systemd
- `psutil`, `requests` (installed automatically via pip)

---

## Part of the SIMARGL toolkit

syryn is one of ten tools that together form an **intellectual development support system**:

| Tool | Role |
|---|---|
| **[simargl](https://github.com/szholobetsky/simargl)** | Task-to-code retrieval — given a task description, finds which files and modules are likely affected, using semantic similarity over git history |
| **[svitovyd](https://github.com/szholobetsky/svitovyd)** | Project map — scans any codebase and produces a structural map of definitions and cross-file dependencies; queried from the CLI, a web UI with a layered map, or an MCP server |
| **[1bcoder](https://github.com/szholobetsky/1bcoder)** | AI coding assistant for small local models — surgical context management, agents, parallel inference, proc scripts |
| **[yasna](https://github.com/szholobetsky/yasna)** | Session memory — indexes conversations from all AI agents so you can find what was discussed, when, and where |
| **[radogast](https://github.com/szholobetsky/radogast)** | Context drift monitor — measures how far an AI agent's conversation has drifted from the original task |
| **[vyrii](https://github.com/szholobetsky/vyrii)** | Local AI web UI — chat, translate, web research, RAG and file management in the browser (Flask; Gradio optional); powered by Ollama or any OpenAI-compatible backend |
| **[syryn](https://github.com/szholobetsky/syryn)** | Bluetooth identity beacon for headless devices — the device's IP is its Bluetooth name; hostname, mDNS and network interfaces on request |
| **[alkonost](https://github.com/szholobetsky/alkonost)** | Browser cockpit for 1bcoder's flows — the `deepagent_*` spec pipeline (plan tree → specs → task board) and the glossary (build, browse, search), tuned for small local models |
| **[gamayun](https://github.com/szholobetsky/gamayun)** | Statistical ontology without an LLM — builds triples of terms, identifiers, files and modules from task history or a folder of documents and code; every triple carries its significance test |
| **[mokosh](https://github.com/szholobetsky/mokosh)** | Dataset gathering — commits of a git repository and the tasks of its tracker (Jira, GitHub, GitLab, YouTrack) in one SQLite database that the other tools read |

- **simargl** finds the code related to a task by vector search over the task history (embeddings).
- **svitovyd** answers: *how is the code structured and what depends on what?*
- **1bcoder** answers: *how do I work with local models efficiently?*
- **yasna** answers: *where did I already discuss this?*
- **radogast** answers: *is the AI agent still on track toward the goal?*
- **vyrii** answers: *how do I access all of this through a browser?*
- **syryn** answers: *what is the address of this headless device?*
- **alkonost** answers: *how do I turn one task description into a reviewed, working plan — and see the project's glossary — without a big model or a big context window?*
- **gamayun** finds the code related to a task through an ontology of significant links between words, files and modules (no LLM).
- **mokosh** prepares the initial dataset from version control and the issue tracker.

Together they cover the full development loop: understand the codebase, find relevant history, work with AI locally, remember what was decided, and verify the context stays on target.

---

**(c) 2026 Stanislav Zholobetskyi, Oleh Andriichuk**
Institute for Information Recording, National Academy of Sciences of Ukraine, Kyiv
*PhD research: «Intelligent Technology for Software Development and Maintenance Support»*
