#!/usr/bin/env python3
"""Phase 2: the WITSOC_LAKE_ENV verifier mode (deterministic, no Lean/Mathlib needed).

`run_lean_check(lean_path, lake_dir)` defaults to `lake build` (build a self-contained
project's own targets — unchanged for existing callers). With WITSOC_LAKE_ENV set it
instead runs `lake env lean <file>`, which type-checks an EXTERNAL file against the
project's dependencies (Mathlib on LEAN_PATH) — the wiring that lets the prover verify
Mathlib goals. This patches subprocess to assert the command selection without running
a real toolchain."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lean_check


class _FakeProc:
    returncode = 0
    stdout = ""
    stderr = ""


def main() -> int:
    failures: list[str] = []
    captured: dict = {}

    real_run = lean_check.subprocess.run
    real_which = lean_check.shutil.which
    lean_check.subprocess.run = lambda cmd, **kw: (captured.__setitem__("cmd", cmd), _FakeProc())[1]
    lean_check.shutil.which = lambda x: f"/usr/bin/{x}"
    try:
        os.environ.pop("WITSOC_LAKE_ENV", None)
        lean_check.run_lean_check(Path("/tmp/x.lean"), Path("/tmp/proj"))
        if captured.get("cmd", [])[:2] != ["/usr/bin/lake", "build"]:
            failures.append(f"default lake_dir must run `lake build`, got {captured.get('cmd')}")

        os.environ["WITSOC_LAKE_ENV"] = "1"
        lean_check.run_lean_check(Path("/tmp/x.lean"), Path("/tmp/proj"))
        if captured.get("cmd", [])[:3] != ["/usr/bin/lake", "env", "lean"]:
            failures.append(f"WITSOC_LAKE_ENV must run `lake env lean <file>`, got {captured.get('cmd')}")
        if str(captured.get("cmd", [])[-1]) != "/tmp/x.lean":
            failures.append("lake env lean must be passed the file to check")
    finally:
        lean_check.subprocess.run = real_run
        lean_check.shutil.which = real_which
        os.environ.pop("WITSOC_LAKE_ENV", None)

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("LAKE_ENV_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
