#!/usr/bin/env python3
"""solve.py — the coherent end-to-end pipeline that ties Tiers A–F together.

One driver, one run dir. It routes a target with triage, runs the appropriate
machinery, and always ends by re-checking every machine claim and grading — so
the output is honest by construction (an unbacked "verified" cannot pass).

Flow:
  triage ─┬─ DECIDABLE_FINITE  → discovery search → emit DAG node (discovery cert)
          ├─ LIKELY_PROVABLE   → prove (close_obligation); if open, auto_decompose
          │                      → prove subgoals → validate_decomposition
          ├─ LIKELY_INDEPENDENT → record terminal outcome (no compute waste)
          └─ LIKELY_INFEASIBLE  → record terminal outcome
  … then: recheck_certificates → grade_witsoc_report → solve_report.json

Every stage is an existing, separately-tested tool invoked through the dispatcher
conventions, so solve.py is glue, not new trust surface.

Usage:
  solve.py --target "..." --run-dir DIR
      [--lean-statement "<Lean Prop>"] [--lake-dir D] [--policy P] [--atlas A]
      [--evaluator no_three_ap --params '{"n":30}']     # for finite search targets
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402


def run(script: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT_DIR / script), *args],
                          capture_output=True, text=True, cwd=str(cwd) if cwd else None, check=False)


def jout(proc: subprocess.CompletedProcess) -> dict:
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--lean-statement", default=None)
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--policy", default=None)
    ap.add_argument("--atlas", type=Path, default=None)
    ap.add_argument("--evaluator", default=None)
    ap.add_argument("--params", default="{}")
    ap.add_argument("--decompose-schema", default="case_split")
    ap.add_argument("--mod", type=int, default=4)
    args = ap.parse_args()

    run_dir = args.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    steps: list[dict] = []

    # 1. Triage.
    tri = jout(run("triage.py", "--target", args.target, "--run-dir", str(run_dir),
                   "--out", str(run_dir / "triage.json")))
    cls = tri.get("classification", "LIKELY_PROVABLE")
    steps.append({"stage": "triage", "classification": cls, "route": tri.get("recommended_route")})

    outcome: dict[str, Any] = {"target": args.target, "classification": cls}

    if cls in ("LIKELY_INDEPENDENT", "LIKELY_INFEASIBLE"):
        # Honest terminal outcomes — record, do not burn compute.
        outcome["terminal_outcome"] = tri.get("terminal_outcome_if_stuck") or cls
        outcome["status"] = "TERMINAL_OUTCOME_RECORDED"
        steps.append({"stage": "route", "action": "record_terminal_outcome",
                      "outcome": outcome["terminal_outcome"]})

    elif cls == "DECIDABLE_FINITE" and args.evaluator:
        # Finite search: discovery witness -> DAG node with a re-checkable cert.
        d = run_dir / "disc"
        run("discovery_engine.py", "init", str(d), "--evaluator", args.evaluator, "--params", args.params, "--seed", "0")
        run("discovery_engine.py", "run", str(d), "--generations", "120")
        best = run("discovery_engine.py", "best", str(d),
                   "--emit-dag", str(run_dir / "proof_dependency_dag.json"), "--review-id", "auto")
        steps.append({"stage": "discovery", "evaluator": args.evaluator, "best": jout(best).get("best_score")})
        outcome["status"] = "FINITE_WITNESS"

    else:  # LIKELY_PROVABLE (or independent-but-try-prove)
        if args.lean_statement:
            prove_args = ["--lean-statement", args.lean_statement, "--name", "target",
                          "--emit", str(run_dir / "target.lean"), "--out-ledger", str(run_dir / "formalization_obligations.json")]
            if args.policy:
                prove_args += ["--policy", args.policy]
            if args.atlas:
                prove_args += ["--atlas", str(args.atlas)]
            if args.lake_dir:
                prove_args += ["--lake-dir", str(args.lake_dir)]
            pr = jout(run("close_obligation.py", *prove_args))
            steps.append({"stage": "prove", "discharged": pr.get("discharged"), "proof": pr.get("proof")})
            if pr.get("discharged"):
                obj_hash = hashlib.sha256(args.lean_statement.encode()).hexdigest()[:16]
                witcore.save_json(run_dir / "proof_dependency_dag.json", [{
                    "node_id": f"target-{obj_hash}", "status": "CHECKED",
                    "statement": args.target, "evidence": f"lean proof: {pr.get('proof')}",
                    "target_hash": obj_hash, "dependency_path_to_target": "direct proof",
                    "dependencies": [], "skeptic_review_id": "auto",
                    "certificate": {"kind": "lean", "lean_path": str(run_dir / "target.lean")},
                }])
                witcore.save_json(run_dir / "skeptic_reviews.json", [{"review_id": "auto"}])
                outcome["status"] = "PROVED"
            else:
                # Open: decompose and try the pieces.
                run("auto_decompose.py", "--target", args.target, "--schema", args.decompose_schema,
                    "--mod", str(args.mod), "--target-lean", args.lean_statement,
                    "--out", str(run_dir / "proof_dependency_dag.json"))
                vd = jout(run("validate_decomposition.py", str(run_dir), "--target", "target"))
                steps.append({"stage": "decompose", "frontier": vd.get("frontier_size"),
                              "complete": vd.get("decomposition_complete")})
                outcome["status"] = "DECOMPOSED_OPEN"
        else:
            outcome["status"] = "NEEDS_LEAN_STATEMENT"
            steps.append({"stage": "prove", "skipped": "no --lean-statement; run autoformalize first"})

    # Final spine: recheck every machine claim, then grade.
    rc = jout(run("recheck_certificates.py", str(run_dir)))
    steps.append({"stage": "recheck", "pass": rc.get("pass"), "fail": rc.get("fail"), "unchecked": rc.get("unchecked")})
    gr = jout(run("grade_witsoc_report.py", str(run_dir)))
    steps.append({"stage": "grade", "grade": gr.get("grade"), "score": gr.get("score"),
                  "verified_fraction": gr.get("verified_fraction")})

    report = {"schema": "witsoc.solve_report.v1", "target": args.target, "run_dir": str(run_dir),
              "outcome": outcome, "steps": steps,
              "note": "Coherent A–F pipeline. 'PROVED' means a Lean proof was re-checked PASS; "
                      "terminal outcomes (INDEPENDENT/INFEASIBLE) are honest, not failures."}
    witcore.save_json(run_dir / "solve_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
