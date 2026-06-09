#!/usr/bin/env python3
"""Test Phase E: harvest -> library -> cross-run reuse wiring.

- The consumption side (library_premises) is tested deterministically by seeding a
  library, with no Lean needed.
- The harvest side (generator_package --record-library) and the end-to-end reuse
  are tested when a real Lean toolchain is present.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import close_obligation as c  # noqa: E402

HAVE_LEAN = shutil.which("lean") is not None
STMT = "∀ a b : Nat, a * b = b * a"

WIT = """-- Status: UNVERIFIED
MODULE MulComm

THEOREM MulComm:
  GIVEN:
    - a: a natural number
    - b: a natural number
  CLAIM:
    a * b = b * a.

PROOF OF MulComm:
  [1] SHOW a * b = b * a.
      BY @Nat.mul_comm.
  QED BY [1].
"""


def lib_add(library: Path, statement: str, provenance: str, tier: str = "LEAN_VERIFIED") -> None:
    subprocess.run([sys.executable, str(SCRIPT_DIR / "lemma_library.py"), "--library", str(library),
                    "add", "--statement", statement, "--tier", tier, "--provenance", provenance],
                   capture_output=True, text=True, timeout=30, check=False)


def lib_stats(library: Path) -> dict:
    r = subprocess.run([sys.executable, str(SCRIPT_DIR / "lemma_library.py"), "--library", str(library), "stats"],
                       capture_output=True, text=True, timeout=20, check=False)
    return json.loads(r.stdout)


def main() -> int:
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="witsoc_phasee_"))
    try:
        # --- consumption side (no Lean needed) ---
        seed = tmp / "lib_seed"
        lib_add(seed, STMT, "close_obligation:by exact Nat.mul_comm")
        if lib_stats(seed).get("total", 0) < 1:
            failures.append("library add did not persist a lemma")
        cands = c.library_premises(STMT, seed)
        if "by exact Nat.mul_comm" not in cands:
            failures.append(f"library_premises should reuse the harvested proof, got {cands}")
        # a non-proof provenance must not surface as a candidate
        lib_add(seed, "∀ n : Nat, n = n", "manual_note_no_proof")
        cands_rr = c.library_premises("∀ n : Nat, n = n", seed)
        if any("manual_note_no_proof" in x for x in cands_rr):
            failures.append("non-proof provenance must not be offered as a candidate")

        # --- harvest side + end-to-end reuse (needs Lean) ---
        # Use a statement `by simp` genuinely closes (n + 0 = n); mul_comm is NOT
        # closed by simp (the package correctly REJECTS a non-proof).
        if HAVE_LEAN:
            lib2 = tmp / "lib_harvest"
            stmt2 = "∀ n : Nat, n + 0 = n"
            wit2 = tmp / "addzero.wit"
            wit2.write_text(
                "-- Status: UNVERIFIED\nMODULE AddZero\n\nTHEOREM AddZero:\n  GIVEN:\n    - n: a natural number\n"
                "  CLAIM:\n    n + 0 = n.\n\nPROOF OF AddZero:\n  [1] SHOW n + 0 = n.\n      BY @Nat.add_zero.\n  QED BY [1].\n",
                encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "generator_package.py"), str(wit2),
                 "--lean-statement", stmt2, "--proof", "by simp",
                 "--emit", str(tmp / "az.lean"), "--record-library", "--library", str(lib2)],
                capture_output=True, text=True, timeout=300, check=False)
            pkg = json.loads(proc.stdout)
            if pkg.get("witsoc_status") != "VERIFIED_LEAN":
                failures.append(f"package precondition: expected VERIFIED_LEAN, got {pkg.get('witsoc_status')}")
            if pkg.get("recorded_to_library") != "LEAN_VERIFIED":
                failures.append(f"package should record LEAN_VERIFIED, got {pkg.get('recorded_to_library')}")
            stats = lib_stats(lib2)
            if stats.get("by_tier", {}).get("LEAN_VERIFIED", 0) < 1:
                failures.append(f"library should hold a LEAN_VERIFIED lemma, got {stats}")
            # the harvested proof is now reusable on a matching goal
            reuse = c.library_premises(stmt2, lib2)
            if "by simp" not in reuse:
                failures.append(f"harvested proof should be reusable, got {reuse}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print(f"PHASE_E_TESTS_PASS (lean={'yes' if HAVE_LEAN else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
