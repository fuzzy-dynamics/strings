#!/usr/bin/env python3
"""Discovery-lift harness — measure whether the creative stack actually creates.

Without an ablation you cannot tell whether ideation/posing/invention produced
genuine novelty or just noise. This measures CREATIVE LIFT on a small target
fixture, kernel-gated end to end:

  BASELINE pass: the direct prover alone (a fixed small portfolio) on each target.
  FULL pass (self-play), only for targets the baseline left open:
    pose_variants generates weaker rungs -> each rung is proved independently ->
    kernel-verified rung proofs recombine onto the ORIGINAL target
    (goal_structure.recombination_candidates, re-checked by the kernel against
    the original statement — a wrong recombination simply fails).

  lift = targets closed by self-play that the baseline could not close.
  regressions (baseline-closed but full-open) MUST be empty.
  calibration: fixture items marked `frozen_calibration` must stay unsolved in
  BOTH passes — one violation fails the whole run (exit 1).

The lift is honest by construction: every closing proof, baseline or full, is a
kernel verification of the original statement. The harness only changes HOW the
proof was found, never what counts as proved.

Usage:
  discovery_lift.py [--fixture FILE.json] [--out discovery_lift.json]
  fixture = {"targets": [{"id", "lean_statement", "preamble"?, "frozen_calibration"?}]}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
import goal_structure as gs  # noqa: E402
import pose_variants as pv  # noqa: E402

BASELINE_PORTFOLIO = ("by rfl", "by decide", "by simp", "by omega")
RUNG_PORTFOLIO = ("by intro n; omega", "by intro n; simp", "by intros; omega",
                  "by intros; simp", "by decide", "by omega", "by simp")
FORBIDDEN = ("sorry", "admit", "axiom", "native_decide")

# built-in demo fixture: the conjunction needs splitting (baseline portfolio has
# no intro/constructor); the calibration item is false and must stay unsolved.
DEFAULT_FIXTURE = {
    "targets": [
        # no single baseline tactic closes the mixed list/arith conjunction, but
        # each conjunct closes alone -> recombination is a real measured lift
        {"id": "lift-conj",
         "lean_statement": "(∀ l : List Nat, l.reverse.reverse = l) ∧ (∀ n : Nat, n / 3 ≤ n)"},
        {"id": "easy-direct", "lean_statement": "1 + 1 = 2"},
        {"id": "cal-false", "lean_statement": "∀ n : Nat, n % 3 = 0",
         "frozen_calibration": True},
    ]
}


def kernel_prove(statement: str, portfolio: tuple[str, ...], preamble: str = "",
                 lake_dir: Path | None = None) -> str | None:
    pre = (preamble + "\n") if preamble else ""
    for tac in portfolio:
        if any(t in tac for t in FORBIDDEN):
            continue
        src = f"{pre}theorem lift_check : {statement} := {tac}\n"
        if witcore.lean_verify_cached(src, lake_dir).get("verified"):
            return tac
    return None


def self_play(statement: str, preamble: str, lake_dir: Path | None,
              rung_prover=None) -> dict:
    """pose -> prove rungs -> recombine onto the ORIGINAL statement, kernel-checked."""
    prove = rung_prover or (lambda s: kernel_prove(s, RUNG_PORTFOLIO, preamble, lake_dir))
    doc = pv.generate(statement)
    conjuncts = gs.conjunction_split(statement)
    rung_results = []
    for v in doc["weaker"]:
        p = prove(v["lean_statement"])
        rung_results.append({"kind": v["kind"], "lean_statement": v["lean_statement"],
                             "proof": p, "closed": bool(p)})
    closed = {r["lean_statement"]: r["proof"] for r in rung_results if r["closed"]}

    # recombination is only sound for conjunct rungs covering ALL conjuncts
    if conjuncts and all(c in closed for c in conjuncts):
        proofs = [closed[c] for c in conjuncts]
        for cand in gs.recombination_candidates(conjuncts, proofs):
            if kernel_prove(statement, (cand,), preamble, lake_dir):
                return {"closed": True, "proof": cand, "via": "conjunct_recombination",
                        "rungs": rung_results}
    return {"closed": False, "proof": None, "rungs": rung_results}


def run(fixture: dict, lake_dir: Path | None = None, rung_prover=None,
        baseline_prover=None) -> dict:
    baseline = baseline_prover or (lambda s, pre: kernel_prove(s, BASELINE_PORTFOLIO, pre, lake_dir))
    results = []
    violations = []
    for t in fixture.get("targets", []):
        stmt, pre = t["lean_statement"], t.get("preamble", "")
        base_proof = baseline(stmt, pre)
        entry = {"id": t["id"], "lean_statement": stmt,
                 "baseline_closed": bool(base_proof), "baseline_proof": base_proof,
                 "full_closed": bool(base_proof), "full_proof": base_proof, "via": "baseline"}
        if not base_proof:
            sp = self_play(stmt, pre, lake_dir, rung_prover)
            entry.update({"full_closed": sp["closed"], "full_proof": sp["proof"],
                          "via": sp.get("via", "none"),
                          "rungs_closed": sum(1 for r in sp["rungs"] if r["closed"]),
                          "rungs_total": len(sp["rungs"])})
        if t.get("frozen_calibration") and entry["full_closed"]:
            violations.append({"id": t["id"], "reason": "calibration target was closed",
                               "proof": entry["full_proof"]})
        results.append(entry)

    lift_ids = [r["id"] for r in results if r["full_closed"] and not r["baseline_closed"]]
    regressions = [r["id"] for r in results if r["baseline_closed"] and not r["full_closed"]]
    return {
        "schema": "witsoc.discovery_lift.v1",
        "targets": len(results),
        "baseline_solved": sum(1 for r in results if r["baseline_closed"]),
        "full_solved": sum(1 for r in results if r["full_closed"]),
        "lift": len(lift_ids),
        "lift_ids": lift_ids,
        "regressions": regressions,
        "calibration_clean": not violations,
        "calibration_violations": violations,
        "results": results,
        "note": "lift counts targets the direct prover could not close but self-play "
                "(pose -> prove rungs -> kernel-checked recombination) did. Every closure, "
                "either pass, is a kernel verification of the original statement.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixture", type=Path, default=None)
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("discovery_lift.json"))
    args = ap.parse_args()

    fixture = witcore.load_json(args.fixture, None) if args.fixture else DEFAULT_FIXTURE
    if not isinstance(fixture, dict) or not fixture.get("targets"):
        print(json.dumps({"error": "fixture must contain a non-empty `targets` list"}))
        return 2
    report = run(fixture, args.lake_dir)
    witcore.save_json(args.out, report)
    print(json.dumps({k: v for k, v in report.items() if k != "results"},
                     indent=2, ensure_ascii=False))
    if report["regressions"]:
        return 1
    return 0 if report["calibration_clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
