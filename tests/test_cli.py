"""The CLI must call serve() with arguments it accepts (0.1.10 passed iface= to a serve()
without that parameter: the service crashed at start and the name stayed the hostname)."""
import inspect
import sys

from syryn import __main__ as cli
from syryn import syryn


def test_serve_accepts_every_cli_argument(monkeypatch):
    seen = {}
    real = inspect.signature(syryn.serve)

    def fake_serve(**kwargs):
        real.bind(**kwargs)   # TypeError if serve() lacks one
        seen.update(kwargs)

    monkeypatch.setattr(syryn, "serve", fake_serve)
    monkeypatch.setattr(sys, "argv", ["syryn", "serve", "--iface", "eth0", "--prefix", "X"])
    cli.main()
    assert seen["iface"] == "eth0" and seen["prefix"] == "X"
