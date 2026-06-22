#!/usr/bin/env python3
"""Root Witsoc launcher with self-restore.

This file intentionally lives beside SKILL.md. If `scripts/` or `src/` were
deleted, run this launcher; it restores the runtime through `bootstrap.py` and
then delegates to `scripts/witsoc.py`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BOOTSTRAP = ROOT / "bootstrap.py"
ENTRYPOINT = ROOT / "scripts" / "witsoc.py"
SRC_CLI = ROOT / "src" / "witsoc" / "cli.py"


def runtime_ok() -> bool:
    return ENTRYPOINT.exists() and SRC_CLI.exists()


def restore() -> int:
    if not BOOTSTRAP.exists():
        print(
            "Witsoc runtime is missing and bootstrap.py is not present.\n"
            "Run: python3 -m pip install -U witsoc && "
            "python3 -m witsoc restore-skill --target ~/.openscientist/skills/witsoc --replace",
            file=sys.stderr,
        )
        return 1
    return subprocess.call([sys.executable, str(BOOTSTRAP), "--replace"], cwd=str(ROOT))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not runtime_ok():
        code = restore()
        if code != 0:
            return code
    if not runtime_ok():
        print("Witsoc runtime restore did not produce scripts/witsoc.py and src/witsoc/cli.py.", file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, str(ENTRYPOINT), *args], cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
