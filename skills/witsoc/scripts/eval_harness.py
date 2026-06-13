#!/usr/bin/env python3
"""Witsoc capability eval harness (Phase 0 — measurement first).

Runs the system against a benchmark corpus where every problem carries a
*certified* oracle, and reports a reproducible capability score. This is the
honesty substrate: no capability change is accepted unless it moves this score
and passes calibration.

Buckets:
  solved        a verified Lean proof exists -> success = system re-derives a
                kernel-checked proof (lean_check PASS).
  bounds        a certified witness / UNSAT exists -> success = search matches a
                verified discovery witness, or a kernel re-decides UNSAT.
  false         a certified counterexample exists -> success = the negation is
                SAT (z3 finds the counterexample).
  calibration   genuinely OPEN -> success = the system returns an HONEST
                non-solve (conjecture / obligation-open). A claimed solve here is
                a CALIBRATION VIOLATION and fails the whole report (guardrail 3).

Modes: --mode portfolio (single-tactic closer) | search (Phase-1 proof search).

Every solver/Lean PASS certifies a statement about the FORMAL artifact in the
corpus; the corpus author owns faithfulness of statement<->intended-claim, so
these are honest VERIFIED-grade for the formal statement (guardrail 2: end-to-end
from informal would be CHECKED + human gate, which is the calibration bucket).

Usage:
  eval_harness.py [--manifest benchmarks/manifest.json] [--mode portfolio|search]
      [--seed 0] [--out report.json]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

# Phase 0 capability ladder (see docs/witsoc/OPEN_PROBLEM_PROGRAM.md). The achieved rung of an
# item is the *product* it reached; the corpus declares the max honest rung
# (`achievable_rung`) so "headroom" = items that did NOT yet reach their ceiling.
RUNG_ORDER = ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L6_STAR"]

# The capability FLOOR: a deliberately dumb fixed portfolio with NO search, NO
# premise atlas, NO library. Reporting capability as a *lift over this baseline*
# makes "the system got stronger" falsifiable instead of self-referential — a goal
# that a trivial prover already closes earns the full system zero credit. Kept
# intentionally small and provider-free (core Lean only). Override via
# WITSOC_BASELINE_PORTFOLIO (comma-separated) if the floor itself needs tuning.
BASELINE_PORTFOLIO = os.environ.get(
    "WITSOC_BASELINE_PORTFOLIO",
    "by rfl,by decide,by simp,by omega,by intro _; rfl,by intros; simp,by intros; omega,by intros; decide",
)


def freeze_hash(item: dict) -> str:
    """Content hash of a frozen calibration item over its identity-defining fields.
    A future edit that 'solves' a calibration item by weakening its statement
    changes this hash, so the freeze check catches it."""
    import hashlib
    canon = json.dumps({k: item.get(k) for k in
                        ("id", "kind", "statement", "preamble", "expect_form", "honest_statuses")},
                       sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def achieved_rung(p: dict, detail: dict, passed: bool) -> str:
    """The rung an item actually reached this run. Frozen/calibration items pass by
    an HONEST non-solve; a fake solve is a VIOLATION (never a rung)."""
    tier = p.get("tier") or p.get("bucket")
    if tier in ("frozen_calibration", "calibration"):
        if detail.get("VIOLATION"):
            return "VIOLATION"
        return "L0_HONEST_OPEN" if passed else "L0_NOT_HONEST"
    if not passed:
        return "L0"
    return p.get("achievable_rung", "L6")


def run_tool(script: str, *args: str, timeout: int = 600) -> dict:
    try:
        r = subprocess.run([sys.executable, str(SCRIPT_DIR / script), *args],
                           capture_output=True, text=True, timeout=timeout, check=False)
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception as exc:
        return {"_error": str(exc)}


# --- per-kind runners; each returns (passed: bool, detail: dict) ------------
def run_lean(p: dict, mode: str) -> tuple[bool, dict]:
    args = ["--lean-statement", p["statement"], "--name", "bench", "--out-ledger", "/dev/null"]
    if p.get("preamble"):
        args += ["--imports", p["preamble"]]
    if mode == "search":
        args += ["--search"]
    out = run_tool("close_obligation.py", *args)
    discharged = bool(out.get("discharged"))
    return discharged, {"label": out.get("label"), "proof": out.get("proof"),
                        "search_nodes": out.get("search_nodes", 0)}


def run_lean_baseline(p: dict) -> bool:
    """Close the item with the dumb fixed portfolio only (no search/atlas/library):
    the capability floor. Used to report lift, never counted as a capability result."""
    args = ["--lean-statement", p["statement"], "--name", "bench", "--out-ledger", "/dev/null",
            "--no-mathlib-atlas", "--portfolio", BASELINE_PORTFOLIO]
    if p.get("preamble"):
        args += ["--imports", p["preamble"]]
    out = run_tool("close_obligation.py", *args)
    return bool(out.get("discharged"))


def classify_trust(item: dict, bucket: str = "") -> str:
    """How was this result actually backed? (Layer 3.7 trust breakdown.)"""
    label = item.get("label")
    if label == "PROOF_DISCHARGED":
        return "KERNEL_VERIFIED"
    if label == "FAITHFULNESS_UNMEASURED":
        return "FAITHFULNESS_GAP"
    if label in ("UNCHECKED_NO_TOOLCHAIN",):
        return "UNCHECKED"
    # On the calibration bucket an honest non-solve is the CORRECT outcome.
    if bucket == "calibration":
        return "OPEN_UNFALSIFIED" if item.get("passed") and not item.get("VIOLATION") else "NOT_CLOSED"
    if label in ("OBLIGATION_OPEN", "BUDGET_EXHAUSTED") or item.get("VIOLATION"):
        return "NOT_CLOSED"
    if item.get("status") == "OPEN_UNFALSIFIED" or (item.get("found") is not None):
        return "OPEN_UNFALSIFIED"
    if item.get("verdict") is not None:
        return "SOLVER_CHECKED"
    if item.get("best_size") is not None:
        return "WITNESS_CHECKED"
    return "OTHER"


def run_discovery(p: dict, seed: int) -> tuple[bool, dict]:
    import discovery_evaluators as de
    ev = de.get_evaluator(p["evaluator"])
    import random
    oracle = p["oracle_min_size"]
    if oracle == "greedy":
        obj = ev.seed(p["params"], random.Random(seed))
        oracle = ev.evaluate(obj, p["params"])["size"]
    d = Path(f"/tmp/_evaldisc_{p['id']}")
    run_tool("discovery_engine.py", "init", str(d), "--evaluator", p["evaluator"],
             "--params", json.dumps(p["params"]), "--seed", str(seed))
    run_tool("discovery_engine.py", "run", str(d), "--generations", "150")
    best = run_tool("discovery_engine.py", "best", str(d))
    size = best.get("best_size") or 0
    verified = (best.get("independent_verification") or {}).get("ok")
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    return (size >= oracle and bool(verified)), {"best_size": size, "oracle": oracle, "verified": verified}


def run_smt(p: dict) -> tuple[bool, dict]:
    res = witcore.solve_smt(p["smtlib"], p.get("expect", "unsat"))
    if not res.get("available"):
        return False, {"unchecked": res.get("reason")}
    return bool(res.get("ok")), {"verdict": res.get("verdict"), "backend": res.get("backend")}


def run_conjecture(p: dict) -> tuple[bool, dict]:
    d = Path(f"/tmp/_evalconj_{p['id']}.json")
    out = run_tool("conjecture_miner.py", "number_theory", "--range", str(p["range"][0]), str(p["range"][1]),
                   "--falsify", str(p.get("falsify", 10000)), "--out", str(d))
    conjectures = witcore.load_json(d, {}).get("conjectures", [])
    d.unlink(missing_ok=True)
    match = next((c for c in conjectures if c.get("form") == p["expect_form"]), None)
    ok = bool(match) and match.get("status") in p["honest_statuses"]
    return ok, {"found": bool(match), "status": match.get("status") if match else None}


def run_lean_open(p: dict, mode: str) -> tuple[bool, dict]:
    # Calibration: success = HONEST non-solve. A discharged proof here is a fake-solve violation.
    discharged, detail = run_lean(p, mode)
    if discharged:
        return False, {**detail, "VIOLATION": "claimed to solve a genuinely-open target"}
    honest = detail.get("label") in p["honest_statuses"]
    return honest, detail


def run_autoformalize(p: dict) -> tuple[bool, dict]:
    """No autoformalization + faithfulness pipeline exists yet (Phase 5). Honestly
    UNMEASURED: never a pass, surfaced as a FAITHFULNESS_GAP so the headroom is
    explicit instead of silently counted as solved."""
    return False, {"label": "FAITHFULNESS_UNMEASURED", "informal": p.get("informal"),
                   "note": "autoformalization/faithfulness pipeline not built (Phase 5 target)"}


def evaluate(manifest: dict, mode: str, seed: int, baseline: bool = False) -> dict:
    buckets: dict[str, list] = {}
    violations: list[str] = []
    for p in manifest["problems"]:
        kind = p["kind"]
        if kind == "lean":
            passed, detail = run_lean(p, mode)
            if baseline:
                detail["baseline_passed"] = run_lean_baseline(p)
        elif kind == "discovery":
            passed, detail = run_discovery(p, seed)
        elif kind == "smt":
            passed, detail = run_smt(p)
        elif kind == "conjecture":
            passed, detail = run_conjecture(p)
        elif kind == "lean_open":
            passed, detail = run_lean_open(p, mode)
            if detail.get("VIOLATION"):
                violations.append(p["id"])
        elif kind == "autoformalize":
            passed, detail = run_autoformalize(p)
        else:
            passed, detail = False, {"error": f"unknown kind {kind}"}
        # A frozen_calibration item that gets "solved" is a violation too.
        if (p.get("tier") == "frozen_calibration") and detail.get("VIOLATION") and p["id"] not in violations:
            violations.append(p["id"])
        buckets.setdefault(p["bucket"], []).append({
            "id": p["id"], "passed": passed,
            "tier": p.get("tier") or p.get("bucket"),
            "achievable_rung": p.get("achievable_rung"),
            "achieved_rung": achieved_rung(p, detail, passed),
            **detail})

    bucket_scores = {b: {"total": len(items), "passed": sum(1 for x in items if x["passed"]),
                         "fraction": round(sum(1 for x in items if x["passed"]) / len(items), 4),
                         "items": items}
                     for b, items in buckets.items()}
    capability_buckets = [b for b in ("solved", "bounds", "false") if b in bucket_scores]
    capability = round(sum(bucket_scores[b]["fraction"] for b in capability_buckets) / len(capability_buckets), 4) \
        if capability_buckets else 0.0
    calib = bucket_scores.get("calibration", {})

    # Layer 3.7: trust breakdown (what backs each result) + reach-vs-efficiency.
    all_items = [x for s in bucket_scores.values() for x in s["items"]]
    trust_breakdown: dict[str, int] = {}
    for b, s in bucket_scores.items():
        for it in s["items"]:
            t = classify_trust(it, b)
            trust_breakdown[t] = trust_breakdown.get(t, 0) + 1
    # LLM_ACCEPTED / FAITHFULNESS_GAP are not exercised by this harness (no LLM
    # acceptance path; faithfulness is a Generator-stage gate). Report 0 honestly.
    trust_breakdown.setdefault("LLM_ACCEPTED", 0)
    trust_breakdown.setdefault("FAITHFULNESS_GAP", 0)
    nodes = [it.get("search_nodes", 0) for it in all_items if it.get("label") == "PROOF_DISCHARGED" and it.get("search_nodes")]
    solved = bucket_scores.get("solved", {})
    reach_vs_efficiency = {
        "reach_solved_fraction": solved.get("fraction"),
        "reach_solved": f"{solved.get('passed')}/{solved.get('total')}" if solved else None,
        "efficiency_mean_search_nodes": round(sum(nodes) / len(nodes), 1) if nodes else 0.0,
        "efficiency_note": "mean compound-search nodes over kernel-discharged solved items; lower = more efficient (compounds via flywheel/library)",
    }

    # Phase 0: rung histogram, per-tier summary, headroom, and the calibration freeze.
    rung_histogram: dict[str, int] = {}
    for it in all_items:
        r = it.get("achieved_rung", "L0")
        rung_histogram[r] = rung_histogram.get(r, 0) + 1

    FROZEN = {"frozen_calibration", "calibration"}
    graded = [it for it in all_items if it.get("achievable_rung") and it.get("tier") not in FROZEN]
    at_ceiling = [it for it in graded if it.get("achieved_rung") == it.get("achievable_rung")]
    headroom_items = [it["id"] for it in graded if it.get("achieved_rung") != it.get("achievable_rung")]
    headroom = {
        "graded_items": len(graded),
        "at_ceiling": len(at_ceiling),
        "below_ceiling": len(headroom_items),
        "headroom_fraction": round(len(headroom_items) / len(graded), 4) if graded else 0.0,
        "below_ceiling_ids": headroom_items,
        "note": "non-calibration items that did NOT reach their achievable_rung; >0 means the "
                "corpus can still discriminate a stronger system (the Phase-0 exit criterion).",
    }

    tiers: dict[str, dict] = {}
    for it in all_items:
        t = it.get("tier", "unknown")
        d = tiers.setdefault(t, {"total": 0, "passed": 0})
        d["total"] += 1
        d["passed"] += 1 if it.get("passed") else 0

    # Calibration freeze: any item carrying a stored freeze_hash must still match.
    freeze_checks = [{"id": p["id"], "ok": freeze_hash(p) == p.get("freeze_hash")}
                     for p in manifest["problems"] if p.get("freeze_hash")]
    calibration_freeze_ok = all(c["ok"] for c in freeze_checks) if freeze_checks else None

    # Capability as a LIFT over the dumb floor (only when --baseline ran). A goal the
    # trivial no-search/no-atlas/no-library portfolio already closes earns the full
    # system zero credit; the lift is what the system adds on top of the floor.
    baseline_items = [it for it in all_items if "baseline_passed" in it]
    baseline_block = None
    if baseline_items:
        base_solved = [it["id"] for it in baseline_items if it.get("baseline_passed")]
        full_solved = [it["id"] for it in baseline_items if it.get("passed")]
        lift_ids = [it["id"] for it in baseline_items if it.get("passed") and not it.get("baseline_passed")]
        regressions = [it["id"] for it in baseline_items if it.get("baseline_passed") and not it.get("passed")]
        n = len(baseline_items)
        baseline_block = {
            "graded": n,
            "baseline_solved": len(base_solved),
            "full_solved": len(full_solved),
            "lift": len(lift_ids),
            "lift_fraction": round(len(lift_ids) / n, 4) if n else 0.0,
            "lift_ids": lift_ids,
            "regressions": regressions,
            "portfolio": BASELINE_PORTFOLIO,
            "note": "lift = goals the full system closes that the floor cannot; regressions "
                    "(floor closes, full does not) must be empty — a non-empty list is a real bug.",
        }

    return {
        "mode": mode, "seed": seed,
        "capability_score": capability,
        "calibration_fraction": calib.get("fraction"),
        "calibration_violations": violations,
        "calibration_clean": not violations,
        "trust_breakdown": trust_breakdown,
        "reach_vs_efficiency": reach_vs_efficiency,
        "rung_histogram": rung_histogram,
        "headroom": headroom,
        "tiers": tiers,
        "calibration_freeze_ok": calibration_freeze_ok,
        "calibration_freeze_checks": freeze_checks,
        "baseline": baseline_block,
        "buckets": {b: {k: v for k, v in s.items() if k != "items"} for b, s in bucket_scores.items()},
        "detail": bucket_scores,
    }


def tool_versions() -> dict:
    def ver(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False).stdout.strip().split("\n")[0]
        except Exception:
            return "absent"
    return {"python": sys.version.split()[0], "lean": ver(["lean", "--version"]),
            "z3": witcore.kernel_tools.have_z3().get("available")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=SCRIPT_DIR.parent / "benchmarks" / "manifest.json")
    ap.add_argument("--mode", choices=["portfolio", "search"], default="portfolio")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--baseline", action="store_true",
                    help="also run the dumb floor portfolio per lean item and report capability as a LIFT over it")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    manifest = witcore.load_json(args.manifest, None)
    if not manifest:
        print(json.dumps({"error": f"no manifest at {args.manifest}"}))
        return 2
    result = evaluate(manifest, args.mode, args.seed, baseline=args.baseline)
    result["schema"] = "witsoc.capability_report.v1"
    result["manifest_version"] = manifest.get("version")
    result["reproducibility"] = {"tool_versions": tool_versions(),
                                 "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    if args.out:
        witcore.save_json(args.out, result)
    summary = {k: result[k] for k in ("mode", "capability_score", "calibration_fraction",
                                      "calibration_clean", "calibration_violations",
                                      "rung_histogram", "headroom", "tiers",
                                      "calibration_freeze_ok", "baseline", "buckets")}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    # Guardrail 3: a calibration violation (fake solve) OR a broken calibration
    # freeze (a tampered/weakened calibration item) fails the run.
    clean = result["calibration_clean"] and (result["calibration_freeze_ok"] is not False)
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
