"""User configuration for howdy-island.

Configuration is optional: every value has a sensible default. Users may
override any of them via an INI file at:

    $XDG_CONFIG_HOME/howdy-island/config.ini   (defaults to ~/.config/...)

Example::

    [osd]
    margin_top = 32
    success_text = Welcome back, {user}
    success_timeout_ms = 1400
    failure_timeout_ms = 2000

    [detector]
    poll_interval_ms = 150
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


def _config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "howdy-island" / "config.ini"


@dataclass
class Config:
    """Runtime configuration with defaults tuned for a polished feel."""

    # --- OSD appearance / behaviour ---
    margin_top: int = 28
    scanning_text: str = "Scanning your face\u2026"
    success_text: str = "Welcome back, {user}"
    success_text_no_user: str = "Face recognized"
    failure_text: str = "Face not recognized"
    success_timeout_ms: int = 1400
    failure_timeout_ms: int = 2000
    animation_ms: int = 180
    slide_distance: int = 14

    # --- Detector ---
    poll_interval_ms: int = 150
    # Grace period to wait for a journal result after the compare process
    # exits before treating a scan as cancelled.
    result_grace_ms: int = 700

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        path = _config_path()
        if not path.is_file():
            return cfg

        parser = configparser.ConfigParser()
        try:
            parser.read(path, encoding="utf-8")
        except (OSError, configparser.Error):
            # A broken config file must never take the daemon down.
            return cfg

        for section in ("osd", "detector"):
            if not parser.has_section(section):
                continue
            for f in fields(cls):
                if parser.has_option(section, f.name):
                    cfg._apply(parser, section, f.name, f.type)
        return cfg

    def _apply(self, parser: configparser.ConfigParser, section: str, name: str, ftype: Any) -> None:
        try:
            if ftype is int or ftype == "int":
                value: Any = parser.getint(section, name)
            else:
                value = parser.get(section, name)
        except (ValueError, configparser.Error):
            return
        setattr(self, name, value)
