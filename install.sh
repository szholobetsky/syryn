#!/bin/sh
# syryn one-line installer (Debian/Ubuntu/Raspberry Pi OS/Fedora):
#   curl -fsSL https://raw.githubusercontent.com/szholobetsky/syryn/main/install.sh | sudo sh
# extra flags go to `syryn install`, e.g.:
#   curl -fsSL .../install.sh | sudo sh -s -- --pin 1234
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "run as root:  curl -fsSL .../install.sh | sudo sh" >&2
    exit 1
fi

if command -v apt-get >/dev/null 2>&1; then
    apt-get update -q
    apt-get install -y bluez python3-dbus python3-gi python3-venv python3-pip
elif command -v dnf >/dev/null 2>&1; then
    dnf install -y bluez python3-dbus python3-gobject python3-pip
else
    echo "unsupported package manager - install bluez, python3-dbus, python3-gi manually" >&2
    exit 1
fi

# own venv that still sees the system dbus/gi bindings (avoids PEP 668 / pipx PATH issues)
python3 -m venv --system-site-packages /opt/syryn
/opt/syryn/bin/pip install --upgrade syryn
ln -sf /opt/syryn/bin/syryn /usr/local/bin/syryn

/opt/syryn/bin/syryn install "$@"
