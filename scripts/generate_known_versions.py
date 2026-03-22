#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = REPO_ROOT / "pants-plugins"

if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))


def _main() -> int:
    from pants_ty.known_versions import main

    return main()


if __name__ == "__main__":
    raise SystemExit(_main())
