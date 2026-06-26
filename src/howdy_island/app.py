"""Wires the detector to the OSD and owns the GLib main loop."""

from __future__ import annotations

import signal
from typing import Optional

from gi.repository import GLib

from .config import Config
from .detector import HowdyDetector
from .osd import IslandOsd


class Application:
    """Top-level daemon: detect Howdy activity and drive the overlay."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self._config = config or Config.load()
        self._osd = IslandOsd(self._config)
        self._detector = HowdyDetector(self._osd.handle_event, self._config)
        self._loop = GLib.MainLoop()

    def run(self) -> int:
        for sig in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, self._on_signal)

        self._detector.start()
        try:
            self._loop.run()
        finally:
            self._detector.stop()
        return 0

    def _on_signal(self) -> bool:
        self._loop.quit()
        return GLib.SOURCE_REMOVE
