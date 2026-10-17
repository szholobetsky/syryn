"""Name beacon: puts the device's IP into its Bluetooth name so any phone or laptop
sees it in its ordinary Bluetooth scan list — no app, no pairing, no commands.

Two channels, both via BlueZ D-Bus:
  * classic (BR/EDR) adapter Alias  -> Android / Windows / macOS / Linux scan lists
  * BLE advertisement               -> advertises the HID service UUID so iOS shows it
                                       in Settings > Bluetooth, plus the Microsoft
                                       Swift Pair beacon so Windows pops up a toast
Imported only after serve() has verified that python3-dbus / python3-gi exist.
"""
from __future__ import annotations

import dbus
import dbus.exceptions
import dbus.service

from .syryn import get_ip

BLUEZ = "org.bluez"
ADAPTER_IFACE = "org.bluez.Adapter1"
ADV_IFACE = "org.bluez.LEAdvertisement1"
ADV_MGR_IFACE = "org.bluez.LEAdvertisingManager1"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
ADV_PATH = "/syryn/advertisement0"

HID_UUID = "00001812-0000-1000-8000-00805f9b34fb"
MS_COMPANY_ID = 0x0006
SWIFT_PAIR = [0x03, 0x00, 0x80]  # Microsoft beacon id, Swift Pair sub-scenario, reserved RSSI

# Legacy BLE advertising packet = 31 bytes: flags (3) + 16-bit UUID list (4)
# + Swift Pair manufacturer data (7) + local name header (2) -> what's left is the name.
ADV_BYTES = 31
FLAGS_BYTES = 3
UUID_BYTES = 4
SWIFT_PAIR_BYTES = 7
NAME_HEADER_BYTES = 2


DEFAULT_PREFIX = "P"


def make_label(prefix: str | None = None, iface: str = "lan") -> tuple[str, str | None]:
    """'P:192.168.0.131' — short constant prefix + IP of the LAN cable (see get_ip). Returns (label, ip)."""
    if prefix is None:
        prefix = DEFAULT_PREFIX
    ip = get_ip(iface)
    if ip:
        label = f"{prefix}:{ip}"
    else:
        label = f"{prefix}:no-lan" if iface == "lan" else f"{prefix}:no-ip"  # e.g. cable unplugged
    if not prefix:
        label = label[1:]
    return label, ip


def ble_name(label: str, ip: str | None, swiftpair: bool) -> str:
    """Label if it fits the advertising packet, otherwise the bare IP (never a truncated IP)."""
    budget = ADV_BYTES - FLAGS_BYTES - UUID_BYTES - NAME_HEADER_BYTES
    if swiftpair:
        budget -= SWIFT_PAIR_BYTES
    if len(label.encode("utf-8")) <= budget or not ip:
        return label
    return ip


def find_adapter(bus) -> str | None:
    obj_mgr = dbus.Interface(bus.get_object(BLUEZ, "/"), "org.freedesktop.DBus.ObjectManager")
    for path, ifaces in obj_mgr.GetManagedObjects().items():
        if ADAPTER_IFACE in ifaces:
            return str(path)
    return None


class Advertisement(dbus.service.Object):
    def __init__(self, bus, name: str, swiftpair: bool):
        self.name = name
        self.swiftpair = swiftpair
        super().__init__(bus, ADV_PATH)

    def properties(self) -> dict:
        props = {
            "Type": dbus.String("peripheral"),
            "ServiceUUIDs": dbus.Array([HID_UUID], signature="s"),
            "LocalName": dbus.String(self.name),
            "Discoverable": dbus.Boolean(True),
        }
        if self.swiftpair:
            props["ManufacturerData"] = dbus.Dictionary(
                {dbus.UInt16(MS_COMPANY_ID): dbus.Array([dbus.Byte(b) for b in SWIFT_PAIR], signature="y")},
                signature="qv",
            )
        return props

    @dbus.service.method(PROPS_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != ADV_IFACE:
            raise dbus.exceptions.DBusException(
                "org.freedesktop.DBus.Error.InvalidArgs", f"unknown interface {interface}"
            )
        return dbus.Dictionary(self.properties(), signature="sv")

    @dbus.service.method(ADV_IFACE, in_signature="", out_signature="")
    def Release(self):
        pass


class Beacon:
    """Keeps the Bluetooth name equal to the current IP; refresh() is a GLib timeout callback."""

    def __init__(self, bus, verbose: bool = True, alias: bool = True, ble: bool = True,
                 swiftpair: bool = True, prefix: str | None = None, iface: str = "lan"):
        self.bus = bus
        self.verbose = verbose
        self.alias = alias
        self.ble = ble
        self.swiftpair = swiftpair
        self.prefix = prefix
        self.iface = iface
        self.adapter: str | None = None
        self.adv: Advertisement | None = None
        self.adv_registered = False
        self.label: str | None = None
        self._warned_no_adapter = False

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[syryn] {msg}", flush=True)

    def _adapter_props(self):
        return dbus.Interface(self.bus.get_object(BLUEZ, self.adapter), PROPS_IFACE)

    def refresh(self) -> bool:
        try:
            if self.adapter is None:
                self.adapter = find_adapter(self.bus)
                if self.adapter is None:
                    if not self._warned_no_adapter:
                        self._log("no Bluetooth adapter yet — will keep checking")
                        self._warned_no_adapter = True
                    return True
                self.label = None

            label, ip = make_label(self.prefix, self.iface)
            if label == self.label:
                return True

            if self.alias:
                self._adapter_props().Set(ADAPTER_IFACE, "Alias", dbus.String(label))
            if self.ble:
                self._advertise(ble_name(label, ip, self.swiftpair))
            self.label = label
            self._log(f"name -> {label}")
        except dbus.exceptions.DBusException as e:
            self._log(f"beacon update failed: {e.get_dbus_message()}")
        return True  # keep the GLib timeout alive

    def _advertise(self, name: str) -> None:
        mgr = dbus.Interface(self.bus.get_object(BLUEZ, self.adapter), ADV_MGR_IFACE)
        if self.adv_registered:
            # LocalName is read only at registration, so re-register with the new name
            mgr.UnregisterAdvertisement(ADV_PATH, reply_handler=lambda: None,
                                        error_handler=lambda e: None)
            self.adv_registered = False
        if self.adv is None:
            self.adv = Advertisement(self.bus, name, self.swiftpair)
        else:
            self.adv.name = name

        # async: BlueZ calls back GetAll() on our object before replying,
        # a blocking call here would deadlock the main loop
        def ok():
            self.adv_registered = True
            self._log(f"BLE advertising as {name!r}")

        def failed(e):
            self._log(f"BLE advertising unavailable ({e.get_dbus_message()}) — classic name only")
            self.ble = False

        mgr.RegisterAdvertisement(ADV_PATH, dbus.Dictionary({}, signature="sv"),
                                  reply_handler=ok, error_handler=failed)

    def stop(self) -> None:
        """Withdraw the advertisement and give the adapter its system name back."""
        if self.adapter is None:
            return
        try:
            if self.adv_registered:
                dbus.Interface(self.bus.get_object(BLUEZ, self.adapter),
                               ADV_MGR_IFACE).UnregisterAdvertisement(ADV_PATH)
            if self.alias:
                self._adapter_props().Set(ADAPTER_IFACE, "Alias", dbus.String(""))
        except dbus.exceptions.DBusException:
            pass
