"""howdy-island — a Dynamic Island–style OSD for Howdy face authentication.

The package is split into focused modules:

* :mod:`howdy_island.config`   — user configuration (with sane defaults).
* :mod:`howdy_island.detector` — turns Howdy/PAM activity into high-level events.
* :mod:`howdy_island.osd`      — the GTK layer-shell overlay that renders state.
* :mod:`howdy_island.app`      — wires the detector to the OSD.
* :mod:`howdy_island.cli`      — command-line entry point.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
