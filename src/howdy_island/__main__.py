"""Allow running the daemon via ``python -m howdy_island``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
