#!/usr/bin/env python3
"""Tests for Item 3 induction search in proof_search.py."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import proof_search as ps

HAVE_LEAN = shutil.which("lean") is not None
DBL_PRE = "def dbl : Nat → Nat\n  | 0 => 0\n  | (n+1) => dbl n + 2"
SG_PRE = "def sumTo : Nat → Nat\n  | 0 => 0\n  | (n+1) => (n+1) + sumTo n"
SG_STMT = "∀ n : Nat, 2 * sumTo n = n * (n + 1)"
# Erdős–Straus, general n — a calibration target that must NEVER discharge.
ES_STMT = ("∀ n : Nat, 2 ≤ n → ∃ x y z : Nat, 0 < x ∧ 0 < y ∧ 0 < z ∧ "
           "4 * (x * y * z) = n * (y * z) + n * (x * z) + n * (x * y)")


def _close(stmt, pre, *extra):
    pr = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "close_obligation.py"), "--lean-statement", stmt,
         "--imports", pre, "--search", "--out-ledger", "/dev/null", *extra],
        capture_output=True, text=True, timeout=400, check=False)
    return json.loads(pr.stdout)


def main() -> int:
    failures: list[str] = []

    # deterministic: induction candidates are well-formed and use the IH + defs
    cands = ps.induction_candidates("∀ n : Nat, dbl n = 2 * n", DBL_PRE)
    if not cands:
        failures.append("expected induction candidates for a forall-Nat goal")
    if not all(c.startswith("by intro n; induction n with") for c in cands):
        failures.append("induction candidates must be complete induction proofs (no skip)")
    if not any("ih" in c and "dbl" in c for c in cands):
        failures.append("some candidate must use the induction hypothesis AND unfold the def")
    if "skip" in " ".join(cands):
        failures.append("induction candidates must never contain `skip`")
    # non-Nat / non-forall goal -> no induction candidates
    if ps.induction_candidates("2 + 2 = 4", ""):
        failures.append("non-forall goal should yield no induction candidates")
    if ps.induction_candidates("∀ l : List Nat, l.reverse.reverse = l", ""):
        failures.append("non-Nat binder should yield no induction candidates (this builder is Nat-only)")

    # no skip / sorry / axiom in ANY generated induction candidate (incl. helpers)
    allcands = (ps.induction_candidates(SG_STMT, SG_PRE)
                + ps.helper_induction_candidates(SG_STMT, SG_PRE)
                + ps.induction_candidates("∀ n : Nat, dbl n = 2 * n", DBL_PRE))
    blob = " ".join(allcands)
    for forbidden in ("skip", "sorry", "admit", "axiom", "native_decide"):
        if forbidden in blob:
            failures.append(f"generated candidates must not contain {forbidden!r}")
    # recursive defs + helper lemmas are detected/generated
    if [d["name"] for d in ps.recursive_defs(SG_PRE)] != ["sumTo"]:
        failures.append("sumTo recursive def should be detected")
    if len(ps.helper_lemmas(SG_PRE)) != 2:
        failures.append("expected base + recurrence helper lemmas for sumTo")

    if HAVE_LEAN:
        # dbl-rec still discharges via induction (regression)
        rec = _close("∀ n : Nat, dbl n = 2 * n", DBL_PRE)
        if rec["label"] != "PROOF_DISCHARGED" or "induction" not in (rec.get("proof") or ""):
            failures.append(f"dbl-rec should discharge via induction, got {rec['label']} / {rec.get('proof')}")

        # PRIMARY TARGET: sum-gauss-rec discharges (core-only, no Mathlib)
        sg = _close(SG_STMT, SG_PRE)
        if sg["label"] != "PROOF_DISCHARGED":
            failures.append(f"sum-gauss-rec should discharge, got {sg['label']} (trace={sg.get('search_trace')})")
        elif "induction" not in (sg.get("proof") or ""):
            failures.append(f"sum-gauss-rec proof should be induction, got {sg.get('proof')}")
        else:
            # the discharged proof must be kernel-clean (no forbidden tokens)
            if any(t in sg["proof"] for t in ("sorry", "admit", "native_decide")):
                failures.append("sum-gauss proof must be kernel-clean")

        # CALIBRATION: the general Erdős–Straus must NOT discharge under search
        es = _close(ES_STMT, "", "--search-max-nodes", "60")
        if es["label"] == "PROOF_DISCHARGED":
            failures.append(f"CALIBRATION VIOLATION: Erdős–Straus general discharged! proof={es.get('proof')}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print(f"PROOF_SEARCH_INDUCTION_TESTS_PASS (lean={'yes' if HAVE_LEAN else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
