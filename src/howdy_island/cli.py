"""Command-line entry point for howdy-island."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .config import Config
from .events import ScanEvent, ScanState


def _check_bindings() -> None:
    """Fail early with an actionable message if GTK/layer-shell is missing."""

    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import Gtk, GtkLayerShell  # noqa: F401
    except (ImportError, ValueError) as exc:
        sys.stderr.write(
            "howdy-island: required GTK / gtk-layer-shell Python bindings are "
            "missing.\n  "
            f"({exc})\n"
            "Install them, e.g. on Fedora:\n"
            "  sudo dnf install python3-gobject python3-cairo gtk3 "
            "gtk-layer-shell\n"
        )
        raise SystemExit(1)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="howdy-island",
        description=(
            "Dynamic Island-style on-screen indicator for Howdy face "
            "authentication. Run without arguments to start the daemon."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"howdy-island {__version__}"
    )
    parser.add_argument(
        "--simulate",
        choices=["scanning", "success", "failure", "cycle"],
        help="Preview the overlay without Howdy (useful for theming/screenshots).",
    )
    return parser


def _run_simulation(mode: str, config: Config) -> int:
    """Drive the OSD with synthetic events for previewing/theming."""

    from gi.repository import GLib  # local import: only needed for simulation

    from .osd import IslandOsd

    osd = IslandOsd(config)
    loop = GLib.MainLoop()

    def emit(state: ScanState, user: Optional[str] = None) -> None:
        osd.handle_event(ScanEvent(state, user=user))

    def stop() -> bool:
        loop.quit()
        return GLib.SOURCE_REMOVE

    if mode == "scanning":
        emit(ScanState.SCANNING)
        GLib.timeout_add_seconds(5, stop)
    elif mode == "success":
        emit(ScanState.SCANNING)
        GLib.timeout_add(1500, lambda: (emit(ScanState.SUCCESS, "sijuz"), False)[1])
        GLib.timeout_add_seconds(5, stop)
    elif mode == "failure":
        emit(ScanState.SCANNING)
        GLib.timeout_add(1500, lambda: (emit(ScanState.FAILURE), False)[1])
        GLib.timeout_add_seconds(5, stop)
    else:  # cycle
        emit(ScanState.SCANNING)
        GLib.timeout_add(1400, lambda: (emit(ScanState.SUCCESS, "sijuz"), False)[1])
        GLib.timeout_add(3600, lambda: (emit(ScanState.SCANNING), False)[1])
        GLib.timeout_add(5200, lambda: (emit(ScanState.FAILURE), False)[1])
        GLib.timeout_add_seconds(8, stop)

    loop.run()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    config = Config.load()

    _check_bindings()

    if args.simulate:
        return _run_simulation(args.simulate, config)

    from .app import Application  # local import keeps --simulate/--version light

    return Application(config).run()
