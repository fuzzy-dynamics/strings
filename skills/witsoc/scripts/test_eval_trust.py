#!/usr/bin/env python3
"""Unit tests for Layer 3.7 eval_harness.classify_trust (deterministic, no Lean)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_harness as eh


def main() -> int:
    failures: list[str] = []

    def expect(label, got, want):
        if got != want:
            failures.append(f"{label}: expected {want}, got {got}")

    expect("kernel", eh.classify_trust({"label": "PROOF_DISCHARGED"}, "solved"), "KERNEL_VERIFIED")
    expect("budget", eh.classify_trust({"label": "BUDGET_EXHAUSTED"}, "solved"), "NOT_CLOSED")
    expect("open", eh.classify_trust({"label": "OBLIGATION_OPEN"}, "solved"), "NOT_CLOSED")
    expect("no-toolchain", eh.classify_trust({"label": "UNCHECKED_NO_TOOLCHAIN"}, "solved"), "UNCHECKED")
    expect("smt", eh.classify_trust({"verdict": "unsat"}, "bounds"), "SOLVER_CHECKED")
    expect("witness", eh.classify_trust({"best_size": 4}, "bounds"), "WITNESS_CHECKED")
    # calibration: honest non-solve is the CORRECT outcome
    expect("calib-honest", eh.classify_trust({"label": "OBLIGATION_OPEN", "passed": True}, "calibration"), "OPEN_UNFALSIFIED")
    expect("calib-conj", eh.classify_trust({"found": True, "passed": True}, "calibration"), "OPEN_UNFALSIFIED")
    # a fake-solve on calibration must NOT read as OPEN_UNFALSIFIED
    expect("calib-violation", eh.classify_trust({"VIOLATION": "x", "passed": False}, "calibration"), "NOT_CLOSED")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("EVAL_TRUST_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
