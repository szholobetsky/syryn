import argparse
from .syryn import serve


def main() -> None:
    p = argparse.ArgumentParser(
        prog="syryn",
        description="Bluetooth identity beacon — responds to STATUS over RFCOMM",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="suppress log output")
    p.add_argument("--pin", default=None, metavar="CODE",
                   help="hardcoded Bluetooth PIN (omit for no-PIN auto-pairing)")
    args = p.parse_args()
    serve(verbose=not args.quiet, pin=args.pin)


if __name__ == "__main__":
    main()
