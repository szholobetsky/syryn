"""RFCOMM server: listens for Bluetooth connections, responds to STATUS command."""
from __future__ import annotations

import datetime
import socket
import sys

try:
    import bluetooth
except ModuleNotFoundError:
    sys.exit(
        "syryn requires PyBluez2 and Linux BlueZ.\n"
        "Debian/Ubuntu:  sudo apt install bluez python3-dev libbluetooth-dev\n"
        "Fedora/RHEL:    sudo dnf install bluez bluez-libs-devel python3-devel\n"
        "Then:           pip install PyBluez2"
    )

import psutil
import requests

CACHE_TTL = 300

_ip_cache: dict = {}


def get_hostname() -> str:
    return socket.gethostname()


def get_interfaces() -> list[tuple[str, str]]:
    stats = psutil.net_if_stats()
    result = []
    for name, addr_list in psutil.net_if_addrs().items():
        if not stats.get(name) or not stats[name].isup:
            continue
        for addr in addr_list:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                result.append((name, addr.address))
    return result


def get_external_ip() -> str:
    now = datetime.datetime.now()
    if "ip" in _ip_cache and (now - _ip_cache["ts"]).total_seconds() < CACHE_TTL:
        return _ip_cache["ip"]
    try:
        ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
        _ip_cache.update({"ip": ip, "ts": now})
        return ip
    except Exception:
        return _ip_cache.get("ip", "unknown")


def build_status() -> str:
    hostname = get_hostname()
    lines = [f"hostname: {hostname}", f"mdns: {hostname}.local"]
    for name, ip in get_interfaces():
        lines.append(f"{name}: {ip}")
    lines.append(f"external_ip: {get_external_ip()}")
    return "\n".join(lines)


def _handle_client(client_sock: bluetooth.BluetoothSocket) -> None:
    try:
        while True:
            data = client_sock.recv(1024)
            if not data:
                break
            cmd = data.decode("utf-8", errors="ignore").strip()
            if not cmd or cmd.upper() == "STATUS":
                client_sock.sendall((build_status() + "\n").encode("utf-8"))
    except OSError:
        pass
    finally:
        client_sock.close()


def serve(verbose: bool = True) -> None:
    server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    server_sock.bind(("", bluetooth.PORT_ANY))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    try:
        bluetooth.advertise_service(
            server_sock,
            "Syryn",
            service_classes=[bluetooth.SERIAL_PORT_CLASS],
            profiles=[bluetooth.SERIAL_PORT_PROFILE],
        )
    except Exception as e:
        if verbose:
            print(f"[syryn] SDP advertise skipped: {e}")

    if verbose:
        print(f"[syryn] RFCOMM port {port}  |  hostname: {get_hostname()}")
        print("[syryn] waiting for connections (Ctrl+C to stop)")

    try:
        while True:
            client_sock, addr = server_sock.accept()
            if verbose:
                print(f"[syryn] connected: {addr}")
            _handle_client(client_sock)
            if verbose:
                print(f"[syryn] disconnected: {addr}")
    except KeyboardInterrupt:
        pass
    finally:
        server_sock.close()
        if verbose:
            print("[syryn] stopped")
