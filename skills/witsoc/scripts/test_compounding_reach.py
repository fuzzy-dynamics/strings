#!/usr/bin/env python3
"""Item 5: compounding INCREASES REACH (not just efficiency).

A target that the atomic portfolio cannot close (no --search) stays OPEN — until a
prior verified proof of it is harvested into the library; then `--use-library`
reuses that proof and the SAME portfolio-only call closes it. Reach unlocked by the
library, demonstrated on real Lean.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
HAVE_LEAN = shutil.which("lean") is not None
STMT = "∀ n : Nat, dbl n = 2 * n"
PRE = "def dbl : Nat → Nat\n  | 0 => 0\n  | (n+1) => dbl n + 2"


def close(*extra, library=None, search=False):
    cmd = [sys.executable, str(SCRIPT_DIR / "close_obligation.py"),
           "--lean-statement", STMT, "--imports", PRE, "--out-ledger", "/dev/null"]
    if search:
        cmd.append("--search")
    if library:
        cmd += ["--use-library", "--library", str(library)]
    cmd += list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    return json.loads(r.stdout)


def main() -> int:
    if not HAVE_LEAN:
        print("COMPOUNDING_REACH_TESTS_SKIP (no lean)")
        return 0
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="witsoc_reach_"))
    try:
        lib = tmp / "lib"
        # 1. portfolio only (no search, empty library): dbl-rec needs induction -> OPEN
        before = close()  # no --use-library, no --search
        if before["label"] == "PROOF_DISCHARGED":
            failures.append("precondition: dbl-rec should NOT close on the atomic portfolio alone")

        # 2. harvest a verified proof into the library (search finds the induction proof)
        harvest = close("--record-library", "--library", str(lib), search=True)
        if harvest["label"] != "PROOF_DISCHARGED":
            failures.append(f"harvest step should discharge via search, got {harvest['label']}")

        # 3. SAME portfolio-only call, now WITH the library -> reuse -> closes (REACH)
        after = close(library=lib)  # --use-library, still NO --search
        if after["label"] != "PROOF_DISCHARGED":
            failures.append(f"with library, portfolio-only should now close dbl-rec, got {after['label']}")
        elif "induction" not in (after.get("proof") or ""):
            failures.append(f"the closing proof should be the reused induction proof, got {after.get('proof')}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("COMPOUNDING_REACH_TESTS_PASS (reach unlocked by library)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
