import argparse


def main() -> None:
    p = argparse.ArgumentParser(
        prog="syryn",
        description="Bluetooth identity beacon — shows the device IP as its Bluetooth name "
                    "and responds to STATUS over RFCOMM",
    )
    p.add_argument("command", nargs="?", default="serve",
                   choices=["serve", "status", "install", "uninstall"],
                   help="serve (default): run the beacon | status: print local status | "
                        "install/uninstall: systemd service that starts on boot")
    p.add_argument("-q", "--quiet", action="store_true", help="suppress log output")
    p.add_argument("--pin", default=None, metavar="CODE",
                   help="hardcoded Bluetooth PIN (omit for no-PIN auto-pairing)")
    p.add_argument("--prefix", default=None, metavar="TEXT",
                   help="name prefix before the IP (default: P  ->  P:192.168.0.131)")
    p.add_argument("--iface", default="lan", metavar="NAME",
                   help="which IP goes into the name: lan (default, wired Ethernet only), "
                        "auto (default-route interface, may be Wi-Fi), or an interface name like eth0")
    p.add_argument("--no-name", dest="name", action="store_false",
                   help="don't put the IP into the classic Bluetooth name")
    p.add_argument("--no-ble", dest="ble", action="store_false",
                   help="don't send the BLE advertisement (iPhone visibility, Windows popup)")
    p.add_argument("--no-swiftpair", dest="swiftpair", action="store_false",
                   help="don't trigger the Windows Swift Pair popup")
    p.add_argument("--interval", type=int, default=15, metavar="SEC",
                   help="how often to check for an IP change (default: 15)")
    p.add_argument("--dry-run", action="store_true",
                   help="install/uninstall: only print what would be done")
    args = p.parse_args()

    if args.command == "status":
        from .syryn import build_status
        print(build_status())
    elif args.command == "install":
        from .install import install
        install(_serve_args(args), dry=args.dry_run)
    elif args.command == "uninstall":
        from .install import uninstall
        uninstall(dry=args.dry_run)
    else:
        from .syryn import serve
        serve(verbose=not args.quiet, pin=args.pin, name=args.name, ble=args.ble,
              swiftpair=args.swiftpair, prefix=args.prefix, interval=args.interval,
              iface=args.iface)


def _serve_args(args) -> list[str]:
    """Flags given to `syryn install` are baked into the service's ExecStart."""
    out = []
    if args.quiet:
        out.append("--quiet")
    if args.pin:
        out += ["--pin", args.pin]
    if args.prefix is not None:
        out += ["--prefix", args.prefix]
    if args.iface != "lan":
        out += ["--iface", args.iface]
    if not args.name:
        out.append("--no-name")
    if not args.ble:
        out.append("--no-ble")
    if not args.swiftpair:
        out.append("--no-swiftpair")
    if args.interval != 15:
        out += ["--interval", str(args.interval)]
    return out


if __name__ == "__main__":
    main()
