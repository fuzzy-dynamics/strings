#!/usr/bin/env python3
"""A2 dialectic engine — `witsoc dialectic`.

Lakatos' proofs-and-refutations as code: proving and refuting run as a
COUPLED game instead of separate phases. After every worker batch, each
failed node becomes an explicit refutation target — if the proof attempt
needs the node and the node is FALSE, no amount of proving will save it, and
the witness that kills it reshapes the whole attack.

For each gap-feedback node whose `lean_statement` is a `∀ n : Nat, ...` form,
run KERNEL-GATED instance refutation (lemma_repair.falsify: a witness counts
only when the kernel proves `¬ statement[n := k]`):

  WITNESS FOUND     the node is false as stated — recorded as REFUTED_INSTANCE
                    with the witnesses; the theory gains a negative example
                    and a refuted enemy candidate; the recommended action is
                    lemma_repair (one-axis statement repair), never another
                    proof attempt;
  SEARCH EXHAUSTED  bounded negative evidence — the theory gains an enemy
                    constraint ("no counterexample below N"), which is
                    publishable negative knowledge (the Tao discipline), and
                    proving remains the right move;
  UNDECIDED         instances the kernel could not decide either way are
                    reported honestly.

Output `dialectic.json`; theory updates are versioned diffs with reasons.
Attention machinery: node statuses are untouched — the kernel verdicts here
inform the THEORY, and the acceptance layer still owns statuses.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import lemma_repair as lr  # noqa: E402
import problem_theory as pt  # noqa: E402
import witcore  # noqa: E402

DEFAULT_INSTANCE_BOUND = 10


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def couple(run: Path, instance_bound: int = DEFAULT_INSTANCE_BOUND,
           lake_dir: Path | None = None) -> dict:
    feedback = _load(run / "gap_feedback.json", {})
    gap_nodes = feedback.get("nodes", {}) if isinstance(feedback, dict) else {}
    dag = _load(run / "proof_dependency_dag.json", [])
    dag = {str(n.get("node_id")): n for n in dag if isinstance(n, dict)} if isinstance(dag, list) else {}

    targets = []
    for nid in gap_nodes:
        node = dag.get(str(nid)) or {}
        lean = node.get("lean_statement")
        parsed = lr.parse_wish(str(lean)) if lean else None
        targets.append({"node_id": str(nid), "lean_statement": lean,
                        "refutable_form": bool(parsed), "parsed": parsed,
                        "imports": str(node.get("lean_imports") or "")})

    results = []
    theory_updates = 0
    for t in targets:
        entry = {"node_id": t["node_id"], "lean_statement": t["lean_statement"]}
        if not t["refutable_form"]:
            entry["verdict"] = "NOT_INSTANCE_REFUTABLE"
            entry["note"] = "no ∀ n : Nat form; refutation needs a domain counterexample engine"
            results.append(entry)
            continue
        parsed = t["parsed"]
        fal = lr.falsify(parsed["body"], parsed["var"], list(range(instance_bound + 1)),
                         t["imports"], lake_dir)
        witnesses = fal.get("witnesses") or []
        confirmed = fal.get("confirmed") or []
        if witnesses:
            entry["verdict"] = "REFUTED_INSTANCE"
            entry["witnesses"] = witnesses
            entry["recommended_action"] = ("the node is FALSE as stated — run lemma_repair for a "
                                           "one-axis statement repair; do not re-dispatch the prover on it")
            try:
                pt.init_theory(run)
                pt.update_theory(run, {
                    "add_negative_example": {"object": f"{parsed['var']} = {witnesses[0]}",
                                             "why": f"kernel-verified counterexample to node {t['node_id']}"},
                    "add_refuted_candidate": {"candidate": t["lean_statement"],
                                              "witnesses": witnesses[:3],
                                              "node_id": t["node_id"]},
                }, why=f"dialectic: node {t['node_id']} refuted at instances {witnesses[:3]}")
                theory_updates += 1
            except Exception:
                pass
        elif confirmed and not fal.get("undecided"):
            entry["verdict"] = "SEARCH_EXHAUSTED"
            entry["confirmed_instances"] = len(confirmed)
            entry["negative_evidence"] = (f"no counterexample to node {t['node_id']} for "
                                          f"{parsed['var']} ≤ {instance_bound} (kernel-confirmed instances)")
            entry["recommended_action"] = "proving remains the right move; raise the bound or formalize"
            try:
                pt.init_theory(run)
                pt.update_theory(run, {
                    "add_enemy_constraint": {"property": entry["negative_evidence"],
                                             "evidence": "dialectic.json (kernel instance checks)"},
                }, why=f"dialectic: bounded negative evidence for node {t['node_id']}")
                theory_updates += 1
            except Exception:
                pass
        else:
            entry["verdict"] = "UNDECIDED"
            entry["confirmed"] = len(confirmed)
            entry["undecided"] = len(fal.get("undecided") or [])
            entry["note"] = "instances the kernel portfolio could not decide either way"
        results.append(entry)

    report = {
        "schema": "witsoc.dialectic.v1",
        "run_dir": str(run),
        "instance_bound": instance_bound,
        "refutation_targets": len(targets),
        "refuted": sum(1 for r in results if r.get("verdict") == "REFUTED_INSTANCE"),
        "exhausted": sum(1 for r in results if r.get("verdict") == "SEARCH_EXHAUSTED"),
        "theory_updates": theory_updates,
        "results": results,
        "note": ("attention machinery: node statuses untouched; a REFUTED_INSTANCE node should be "
                 "repaired (lemma_repair), never re-proved as stated"),
    }
    witcore.save_json(run / "dialectic.json", report)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--instance-bound", type=int, default=DEFAULT_INSTANCE_BOUND)
    args = ap.parse_args()
    report = couple(args.run_dir, args.instance_bound)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
