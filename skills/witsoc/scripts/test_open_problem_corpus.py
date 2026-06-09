#!/usr/bin/env python3
"""Phase 0: the headroom open-problem corpus + rung-aware eval.

Checks the MEASUREMENT substrate (mostly deterministic, no Lean needed):

  1. Rung grading: a kernel-discharged item maps to its achievable_rung; a
     non-solve maps to L0; a fake solve on a frozen item is a VIOLATION.
  2. Calibration freeze: every frozen_calibration item's stored freeze_hash matches
     its content (so a future edit that weakens a calibration item is caught), and a
     tampered statement breaks the check.
  3. Headroom: the corpus declares items below their ceiling (so it can still
     discriminate a stronger system — the Phase-0 exit criterion).
  4. The frozen calibration set is present and content-frozen, with no fake solves.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import eval_harness as eh

CORPUS = SCRIPT_DIR.parent / "benchmarks" / "open_problem_corpus.json"


def main() -> int:
    failures: list[str] = []
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    problems = corpus["problems"]
    by_id = {p["id"]: p for p in problems}

    # 1. Rung grading is deterministic and honest.
    rh = by_id["rh-ring-square"]
    if eh.achieved_rung(rh, {"label": "PROOF_DISCHARGED"}, True) != "L6":
        failures.append("a discharged reachable_hard item must reach its achievable_rung L6")
    if eh.achieved_rung(rh, {"label": "OBLIGATION_OPEN"}, False) != "L0":
        failures.append("an unsolved item must map to L0")
    pp = by_id["pp-erdos-straus-n4"]
    if eh.achieved_rung(pp, {"label": "PROOF_DISCHARGED"}, True) != "L2":
        failures.append("the Erdős–Straus n=4 product must grade as L2, not a full solve")
    fc = by_id["fc-erdos-straus-general"]
    if eh.achieved_rung(fc, {"VIOLATION": "x"}, False) != "VIOLATION":
        failures.append("a fake solve on a frozen calibration item must grade as VIOLATION")
    if eh.achieved_rung(fc, {"label": "OBLIGATION_OPEN"}, True) != "L0_HONEST_OPEN":
        failures.append("an honest non-solve on a frozen item must grade as L0_HONEST_OPEN")

    # 2. Calibration freeze integrity (+ tamper detection).
    frozen = [p for p in problems if p.get("tier") == "frozen_calibration"]
    if len(frozen) < 2:
        failures.append("expected at least 2 frozen_calibration items (odd-perfect + Erdős–Straus)")
    for p in frozen:
        if not p.get("freeze_hash"):
            failures.append(f"frozen item {p['id']} missing freeze_hash")
        elif eh.freeze_hash(p) != p["freeze_hash"]:
            failures.append(f"frozen item {p['id']} freeze_hash does not match its content")
    # tamper: weakening a calibration statement must break the hash
    if frozen:
        tampered = dict(frozen[0]); tampered["statement"] = (tampered.get("statement") or "") + " ∧ True"
        if eh.freeze_hash(tampered) == frozen[0]["freeze_hash"]:
            failures.append("freeze_hash must change when a calibration item's statement is edited")

    # 3. Headroom is declared (the corpus is not saturated by construction).
    FROZEN = {"frozen_calibration", "calibration"}
    graded = [p for p in problems if p.get("achievable_rung") and p.get("tier") not in FROZEN]
    if not graded:
        failures.append("corpus must have rung-graded non-calibration items")
    # at least one reachable_hard / autoformalization item is a known current miss
    headroom_ids = {"rh-ring-square", "rh-acc-generalize", "rh-list-len-rev",
                    "af-even-divisible", "af-prime-divisors"}
    if not (headroom_ids & set(by_id)):
        failures.append("corpus must contain explicit headroom items below their ceiling")

    # 4. Tiers present and well-formed.
    tiers = {p.get("tier") for p in problems}
    for required in ("reachable_hard", "partial_progress", "frozen_calibration", "autoformalization"):
        if required not in tiers:
            failures.append(f"corpus missing required tier {required}")

    # 5. classify_trust maps the autoformalization items to FAITHFULNESS_GAP (honest unmeasured).
    if eh.classify_trust({"label": "FAITHFULNESS_UNMEASURED"}, "autoformalization") != "FAITHFULNESS_GAP":
        failures.append("autoformalization items must classify as FAITHFULNESS_GAP, not silently solved")

    # 6. If a prior full eval report exists, it must be calibration-clean with headroom>0.
    report_path = Path("/tmp/open_eval.json")
    if report_path.exists():
        rep = json.loads(report_path.read_text(encoding="utf-8"))
        if not rep.get("calibration_clean"):
            failures.append(f"eval report shows calibration violations: {rep.get('calibration_violations')}")
        if rep.get("calibration_freeze_ok") is False:
            failures.append("eval report shows a broken calibration freeze")
        hr = rep.get("headroom", {})
        if not (hr.get("below_ceiling", 0) > 0):
            failures.append("eval report shows NO headroom — the corpus is saturated and cannot discriminate")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("OPEN_PROBLEM_CORPUS_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
