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


def find_wit_bin(root: Path) -> tuple[str | None, str | None]:
    env = os.environ.get("WITSOC_WIT_BIN")
    if env and Path(env).exists():
        return env, "WITSOC_WIT_BIN"

    path_wit = which("wit")
    if path_wit:
        return path_wit, "PATH"

    repo_wit = root.parents[2] / "witsoc" / "env" / "bin" / "wit"
    if repo_wit.exists():
        return str(repo_wit), "repo_env"

    plugin_dir = Path(os.environ.get("WITSOC_PLUGIN_DIR", Path.home() / ".openscientist" / "plugins" / "witsoc"))
    plugin_wit = plugin_dir / "data" / "venv" / "bin" / "wit"
    if plugin_wit.exists():
        return str(plugin_wit), "witsoc_plugin"

    return None, None


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
    wit_bin, wit_source = find_wit_bin(root)
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
        "wit": {"available": bool(wit_bin), "path": wit_bin, "source": wit_source},
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
