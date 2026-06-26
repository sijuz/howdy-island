"""Shared event types used between the detector and the OSD.

Kept in a dependency-free module so both the (GLib-based) detector and the
(GTK-based) OSD can import it without creating an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class ScanState(Enum):
    """High-level state of a Howdy authentication attempt."""

    SCANNING = auto()
    SUCCESS = auto()
    FAILURE = auto()
    HIDDEN = auto()


@dataclass(frozen=True)
class ScanEvent:
    """A single state transition, optionally carrying context."""

    state: ScanState
    user: Optional[str] = None
    reason: Optional[str] = None
