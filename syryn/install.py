"""syryn install / uninstall — a systemd unit so the beacon starts on every boot.

Run once while you still have a console:  sudo "$(command -v syryn)" install
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys

UNIT_NAME = "syryn.service"
UNIT_PATH = f"/etc/systemd/system/{UNIT_NAME}"
APT_PKGS = ["bluez", "python3-dbus", "python3-gi"]
DNF_PKGS = ["bluez", "python3-dbus", "python3-gobject"]


def _run(cmd: list[str], dry: bool, check: bool = True) -> int:
    print("+ " + shlex.join(cmd))
    if dry:
        return 0
    rc = subprocess.run(cmd).returncode
    if check and rc != 0:
        sys.exit(f"[syryn] command failed ({rc}): {shlex.join(cmd)}")
    return rc


def _imports_ok(code: str, env: dict) -> bool:
    return subprocess.run([sys.executable, "-c", code], env=env, cwd="/",
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def _service_env() -> dict:
    """Environment the unit will need: PYTHONPATH only if a bare interpreter can't import syryn
    (e.g. `pip install --user`, whose site dir root does not see)."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    if _imports_ok("import syryn", env):
        return {}
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return {"PYTHONPATH": pkg_root}


def unit_text(serve_args: list[str], extra_env: dict) -> str:
    exec_start = shlex.join([sys.executable, "-m", "syryn", "serve", *serve_args])
    env_lines = "".join(f"Environment={k}={v}\n" for k, v in extra_env.items())
    return (
        "[Unit]\n"
        "Description=syryn - Bluetooth identity beacon (device IP in its Bluetooth name)\n"
        "After=bluetooth.service\n"
        "Requires=bluetooth.service\n"
        "PartOf=bluetooth.service\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={exec_start}\n"
        "Environment=PYTHONUNBUFFERED=1\n"
        f"{env_lines}"
        "Restart=always\n"
        "RestartSec=5\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def _ensure_deps(dry: bool, env: dict) -> None:
    run_env = {**{k: v for k, v in os.environ.items() if k != "PYTHONPATH"}, **env}
    have_dbus = not dry and _imports_ok("import dbus, gi", run_env)
    have_bluez = shutil.which("bluetoothctl") is not None
    if have_dbus and have_bluez:
        return
    if shutil.which("apt-get"):
        _run(["apt-get", "install", "-y", *APT_PKGS], dry)
    elif shutil.which("dnf"):
        _run(["dnf", "install", "-y", *DNF_PKGS], dry)
    else:
        print("[syryn] unknown package manager — install BlueZ, python3-dbus and python3-gi yourself")
    if not dry and not _imports_ok("import dbus, gi", run_env):
        sys.exit(
            "[syryn] python3-dbus / python3-gi are installed system-wide, but this Python\n"
            f"        ({sys.executable}) can't see them. Reinstall syryn with access to system packages:\n"
            "          pipx reinstall syryn --system-site-packages      (pipx)\n"
            "          python3 -m venv --system-site-packages <dir>      (venv)"
        )


def install(serve_args: list[str], dry: bool = False) -> None:
    if not dry:
        if not sys.platform.startswith("linux"):
            sys.exit("[syryn] install works on Linux with systemd only (try --dry-run to preview)")
        if os.geteuid() != 0:
            sys.exit('[syryn] needs root:  sudo "$(command -v syryn)" install')
        if not shutil.which("systemctl"):
            sys.exit("[syryn] systemctl not found — this system does not use systemd")

    extra_env = {} if dry else _service_env()
    _ensure_deps(dry, extra_env)

    if shutil.which("rfkill") or dry:
        _run(["rfkill", "unblock", "bluetooth"], dry, check=False)
    _run(["systemctl", "enable", "--now", "bluetooth.service"], dry)

    text = unit_text(serve_args, extra_env)
    print(f"+ write {UNIT_PATH}")
    if dry:
        print(text)
    else:
        with open(UNIT_PATH, "w", encoding="utf-8") as f:
            f.write(text)

    _run(["systemctl", "daemon-reload"], dry)
    _run(["systemctl", "enable", UNIT_NAME], dry)
    _run(["systemctl", "restart", UNIT_NAME], dry)

    print(
        "\n[syryn] installed — starts on every boot.\n"
        "  Phones/laptops nearby: open Bluetooth settings, look for  P:<ip>\n"
        "  Logs:   journalctl -u syryn -f\n"
        "  Remove: sudo \"$(command -v syryn)\" uninstall"
    )


def uninstall(dry: bool = False) -> None:
    if not dry and os.geteuid() != 0:
        sys.exit('[syryn] needs root:  sudo "$(command -v syryn)" uninstall')
    _run(["systemctl", "disable", "--now", UNIT_NAME], dry, check=False)
    print(f"+ rm {UNIT_PATH}")
    if not dry and os.path.exists(UNIT_PATH):
        os.remove(UNIT_PATH)
    _run(["systemctl", "daemon-reload"], dry)
    print("[syryn] uninstalled")
