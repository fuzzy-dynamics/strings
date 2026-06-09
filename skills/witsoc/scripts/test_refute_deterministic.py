#!/usr/bin/env python3
"""Tests for Item 8 refute_deterministic.py."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refute_deterministic as rd

HAVE_LEAN = shutil.which("lean") is not None


def main() -> int:
    failures: list[str] = []

    # target drift -> REJECTED
    r = rd.refute({"node_id": "n1", "target_hash": "a" * 64}, "b" * 64, "")
    if not r["refuted"] or r["demoted_status"] != "REJECTED":
        failures.append(f"target drift should REJECT, got {r['demoted_status']}")

    # circular -> REJECTED
    r = rd.refute({"node_id": "n2", "dependencies": ["n2", "x"], "target_hash": "a" * 64}, "a" * 64, "")
    if not r["refuted"]:
        failures.append("self-dependency should be refuted")

    # explicit counterexample -> REJECTED
    r = rd.refute({"node_id": "n3", "counterexample": "n=0", "target_hash": "a" * 64}, "a" * 64, "")
    if not r["refuted"]:
        failures.append("supplied counterexample should refute")

    # clean node survives
    r = rd.refute({"node_id": "n4", "dependencies": ["x"], "target_hash": "a" * 64,
                   "dependency_path_to_target": ["n4", "x", "T"]}, "a" * 64, "")
    if r["refuted"] or r["demoted_status"] is not None:
        failures.append(f"clean node should survive, got {r}")

    # precondition gap (needs Lean): a cited made-up lemma -> demote GAP
    if HAVE_LEAN:
        r = rd.refute({"node_id": "n5", "target_hash": "a" * 64,
                       "evidence": ["proof=by exact Nat.totally_made_up_xyz"]}, "a" * 64, "")
        if r["demoted_status"] != "GAP":
            failures.append(f"unresolved citation should demote to GAP, got {r['demoted_status']} ({r['precondition_audit']})")
        # a real lemma must NOT demote
        r2 = rd.refute({"node_id": "n6", "target_hash": "a" * 64,
                        "evidence": ["proof=by exact Nat.mul_comm"]}, "a" * 64, "")
        if r2["demoted_status"] is not None:
            failures.append(f"resolved citation must not demote, got {r2['demoted_status']}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print(f"REFUTE_DETERMINISTIC_TESTS_PASS (lean={'yes' if HAVE_LEAN else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
