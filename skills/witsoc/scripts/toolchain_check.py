#!/usr/bin/env python3
"""Report Witsoc formal-verification tool availability.

Default mode is diagnostic and exits 0. Use --strict when missing WIT/Lean
tooling should fail the run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def which(name: str) -> str | None:
    return shutil.which(name)


def script_status(root: Path, rel: str) -> dict[str, object]:
    path = root / rel
    return {
        "path": str(path),
        "exists": path.exists(),
        "executable": os.access(path, os.X_OK) if path.exists() else False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="exit nonzero if required formal tooling is missing")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    wit_env = os.environ.get("WITSOC_WIT_BIN")
    wit_bin = wit_env if wit_env and Path(wit_env).exists() else which("wit")
    lean_bin = which("lean")
    lake_bin = which("lake")

    scripts = {
        name: script_status(root, f"scripts/{name}")
        for name in (
            "check.sh",
            "context.sh",
            "verify.sh",
            "receipt.sh",
            "cycle.sh",
            "validate_handoff.py",
            "validate_proof_dag.py",
            "route.py",
            "research_search.py",
        )
    }

    result = {
        "wit": {"available": bool(wit_bin), "path": wit_bin},
        "lean": {"available": bool(lean_bin), "path": lean_bin},
        "lake": {"available": bool(lake_bin), "path": lake_bin},
        "safeverify_script": scripts["verify.sh"],
        "witsoc_scripts": scripts,
        "formal_verification_available": bool(wit_bin and lean_bin and lake_bin and scripts["verify.sh"]["exists"]),
    }

    print(json.dumps(result, indent=2))
    if args.strict and not result["formal_verification_available"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
