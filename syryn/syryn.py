"""Bluetooth identity beacon: registers SPP profile via BlueZ D-Bus, responds to STATUS."""
from __future__ import annotations

import datetime
import os
import signal
import socket
import sys
import threading

import psutil
import requests

CACHE_TTL = 300
SPP_UUID = "00001101-0000-1000-8000-00805f9b34fb"

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


def _default_route_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # UDP connect sends nothing, only picks a route
            ip = s.getsockname()[0]
        if not ip.startswith("127."):
            return ip
    except OSError:
        pass
    return None


def get_primary_ip() -> str | None:
    """IP of the interface that holds the default route; first non-loopback otherwise."""
    ip = _default_route_ip()
    if ip:
        return ip
    interfaces = get_interfaces()
    return interfaces[0][1] if interfaces else None


def _read_sys(path: str) -> str:
    try:
        with open(path, encoding="ascii") as f:
            return f.read().strip()
    except OSError:
        return ""


def is_wired(name: str) -> bool:
    """Physical Ethernet port (LAN cable) — not Wi-Fi, not docker/veth/bridge/VPN."""
    sys_path = f"/sys/class/net/{name}"
    if os.path.isdir(sys_path):
        return (os.path.exists(f"{sys_path}/device")          # real NIC (incl. USB), not virtual
                and not os.path.exists(f"{sys_path}/wireless")
                and not os.path.exists(f"{sys_path}/phy80211")
                and _read_sys(f"{sys_path}/type") == "1")      # ARPHRD_ETHER
    # no sysfs (not Linux): go by the usual names
    return name.lower().startswith(("eth", "en"))


def get_lan_ip() -> str | None:
    """IP on the wired Ethernet port; with several, the one holding the default route wins."""
    lan = [(name, ip) for name, ip in get_interfaces() if is_wired(name)]
    if not lan:
        return None
    route_ip = _default_route_ip()
    for _, ip in lan:
        if ip == route_ip:
            return ip
    return lan[0][1]


def get_ip(iface: str = "lan") -> str | None:
    """iface: 'lan' — wired Ethernet only, 'auto' — default-route interface, else an interface name."""
    if iface == "lan":
        return get_lan_ip()
    if iface == "auto":
        return get_primary_ip()
    for name, ip in get_interfaces():
        if name == iface:
            return ip
    return None


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


def _handle_client(sock: socket.socket, verbose: bool) -> None:
    try:
        while True:
            data = sock.recv(1024)
            if not data:
                if verbose:
                    print("[syryn] client closed connection")
                break
            cmd = data.decode("utf-8", errors="ignore").strip()
            if verbose:
                print(f"[syryn] recv: {cmd!r}")
            if not cmd or cmd.upper() == "STATUS":
                response = (build_status() + "\n").encode("utf-8")
                sock.sendall(response)
                if verbose:
                    print(f"[syryn] sent {len(response)} bytes")
    except OSError as e:
        if verbose:
            print(f"[syryn] client error: {e}")
    finally:
        sock.close()


def serve(verbose: bool = True, pin: str | None = None, name: bool = True,
          ble: bool = True, swiftpair: bool = True, prefix: str | None = None,
          interval: int = 15, iface: str = "lan") -> None:
    try:
        import dbus
        import dbus.service
        import dbus.mainloop.glib
        from gi.repository import GLib
    except ImportError:
        sys.exit(
            "syryn requires python3-dbus and python3-gi.\n"
            "  Debian/Ubuntu/Xubuntu:  sudo apt install python3-dbus python3-gi\n"
            "  Fedora/RHEL:            sudo dnf install python3-dbus python3-gobject"
        )

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    # Find first Bluetooth adapter and make it discoverable
    try:
        obj_mgr = dbus.Interface(
            bus.get_object("org.bluez", "/"),
            "org.freedesktop.DBus.ObjectManager",
        )
        for path, ifaces in obj_mgr.GetManagedObjects().items():
            if "org.bluez.Adapter1" in ifaces:
                props = dbus.Interface(
                    bus.get_object("org.bluez", path),
                    "org.freedesktop.DBus.Properties",
                )
                props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(True))
                props.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(True))
                props.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(True))
                props.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(0))
                if verbose:
                    print(f"[syryn] adapter {path}: discoverable on")
                break
    except Exception as e:
        if verbose:
            print(f"[syryn] could not set discoverable: {e}")

    PROFILE_PATH = "/syryn/profile"
    AGENT_PATH = "/syryn/agent"
    AGENT_IFACE = "org.bluez.Agent1"

    class SyrynProfile(dbus.service.Object):
        @dbus.service.method("org.bluez.Profile1",
                             in_signature="oha{sv}", out_signature="")
        def NewConnection(self, path, fd, properties):
            raw_fd = fd.take() if hasattr(fd, "take") else int(fd)
            sock = socket.socket(fileno=raw_fd)
            sock.setblocking(True)
            if verbose:
                print(f"[syryn] connected: {path}")
            threading.Thread(
                target=_handle_client, args=(sock, verbose), daemon=True
            ).start()

        @dbus.service.method("org.bluez.Profile1",
                             in_signature="o", out_signature="")
        def RequestDisconnection(self, path):
            if verbose:
                print(f"[syryn] disconnected: {path}")

        @dbus.service.method("org.bluez.Profile1",
                             in_signature="", out_signature="")
        def Release(self):
            pass

    class Agent(dbus.service.Object):
        @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
        def RequestPinCode(self, device):
            return pin or "0000"

        @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
        def RequestPasskey(self, device):
            return dbus.UInt32(int(pin or "0"))

        @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
        def RequestConfirmation(self, device, passkey):
            pass

        @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
        def AuthorizeService(self, device, uuid):
            pass

        @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
        def RequestAuthorization(self, device):
            pass

        @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
        def Release(self):
            pass

        @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
        def Cancel(self):
            pass

    SyrynProfile(bus, PROFILE_PATH)
    Agent(bus, AGENT_PATH)

    bluez = bus.get_object("org.bluez", "/org/bluez")

    agent_mgr = dbus.Interface(bluez, "org.bluez.AgentManager1")
    capability = "KeyboardDisplay" if pin else "NoInputNoOutput"
    try:
        agent_mgr.RegisterAgent(AGENT_PATH, capability)
        agent_mgr.RequestDefaultAgent(AGENT_PATH)
    except Exception as e:
        if verbose:
            print(f"[syryn] agent skipped: {e}")

    profile_mgr = dbus.Interface(bluez, "org.bluez.ProfileManager1")
    try:
        profile_mgr.RegisterProfile(
            PROFILE_PATH,
            SPP_UUID,
            {"Name": dbus.String("Syryn"), "AutoConnect": dbus.Boolean(False)},
        )
        if verbose:
            print(f"[syryn] SPP registered  |  hostname: {get_hostname()}")
    except Exception as e:
        if verbose:
            print(f"[syryn] SPP registration failed: {e}")
        sys.exit(1)

    beacon = None
    if name or ble:
        from .beacon import Beacon
        beacon = Beacon(bus, verbose=verbose, alias=name, ble=ble,
                        swiftpair=swiftpair, prefix=prefix, iface=iface)
        beacon.refresh()
        GLib.timeout_add_seconds(max(interval, 1), beacon.refresh)

    if verbose:
        print("[syryn] waiting for connections (Ctrl+C to stop)", flush=True)

    loop = GLib.MainLoop()

    def _on_sigterm():
        loop.quit()
        return False

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, _on_sigterm)
    try:
        loop.run()
    except KeyboardInterrupt:
        loop.quit()
    finally:
        if beacon is not None:
            beacon.stop()
        if verbose:
            print("[syryn] stopped")
