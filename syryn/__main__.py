import argparse
from .syryn import serve


def main() -> None:
    p = argparse.ArgumentParser(
        prog="syryn",
        description="Bluetooth identity beacon — responds to STATUS over RFCOMM",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="suppress log output")
    args = p.parse_args()
    serve(verbose=not args.quiet)


if __name__ == "__main__":
    main()
