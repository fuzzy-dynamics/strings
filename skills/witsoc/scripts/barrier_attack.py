#!/usr/bin/env python3
"""Barrier-attack preparation for Lovasz open-problem campaigns.

This module turns "the target is open" into concrete work: named barriers,
saturated rungs, DAG nodes, and lemma-queue entries. It is deterministic and
honest: it only creates OPEN/OPEN_UNFALSIFIED obligations and mutation records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import domain_barrier_lemmas as dbl  # noqa: E402
import rung_saturation as rs  # noqa: E402
import witcore  # noqa: E402

MUTATION_AXES = [
    "method",
    "statement_strength",
    "encoding",
    "object_class",
    "invariant",
    "computational_bound",
    "formalization_target",
    "theorem_source",
]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _manifest(run: Path) -> dict[str, Any]:
    data = witcore.load_json(run / "lovasz_run.json", {})
    return data if isinstance(data, dict) else {}


def _target_context(run: Path, target: str | None = None, domain: str | None = None,
                    lean_target: str | None = None) -> tuple[str, str, str | None, str]:
    manifest = _manifest(run)
    t = target or str(manifest.get("source_target_text") or manifest.get("target") or "unspecified target")
    d = domain or str(manifest.get("domain") or "other")
    lean = lean_target or manifest.get("lean_target") or manifest.get("frozen_lean_target")
    th = str(manifest.get("target_hash") or sha(t))
    return t, d, str(lean) if lean else None, th


def _barrier_record(lemma: dict[str, Any], idx: int) -> dict[str, Any]:
    bid = f"BA-{witcore.slug(str(lemma.get('barrier_type') or 'barrier'))}-{idx:03d}"
    falsification = lemma.get("falsification_test") or {}
    preconditions = lemma.get("theorem_preconditions_to_audit") or []
    return {
        "barrier_id": bid,
        "node_id": str(lemma.get("node_id") or bid),
        "barrier_type": lemma.get("barrier_type"),
        "actual_barrier_lemma": lemma.get("statement"),
        "statement": lemma.get("statement"),
        "lean_statement": lemma.get("lean_statement"),
        "why_it_blocks_target": lemma.get("why_it_matters") or "blocks a dependency path to the frozen target",
        "known_equivalences": [],
        "failed_methods": [],
        "direct_attacks": [
            {"method": "kernel_probe" if lemma.get("lean_statement") else "formalization_probe",
             "status": "queued"},
            {"method": str(falsification.get("kind") or "bounded_counterexample_pressure"),
             "status": "queued"},
        ],
        "direct_attack_count": 2,
        "counterexample_pressure": falsification or {
            "kind": "manual_or_domain_search",
            "witness_refutes": True,
            "interpretation": "a witness refutes; no witness is not proof",
        },
        "theorem_precondition_gap": preconditions or [
            "closest-theorem preconditions not yet audited for this barrier"
        ],
        "next_exact_attempt": "dispatch the Lean statement if present; otherwise formalize the smallest subcase and run bounded falsification",
        "attack_families": [
            "direct_kernel_probe" if lemma.get("lean_statement") else "formalization_first",
            "bounded_refutation_search",
            "one_axis_mutation",
            "theorem_precondition_bridge",
        ],
        "mutation_history": [],
        "best_partial_result": None,
        "status": "OPEN_UNFALSIFIED",
        "arena": "SPECULATIVE",
        "target_hash": lemma.get("target_hash"),
        "priority": lemma.get("priority", 80),
        "falsification_test": falsification,
        "dependency_path_to_target": lemma.get("dependency_path_to_target") or [lemma.get("node_id"), "T"],
    }


def _node_from_barrier(barrier: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": barrier["node_id"],
        "type": "actual_barrier_lemma",
        "statement": barrier["statement"],
        "lean_statement": barrier.get("lean_statement"),
        "status": "OPEN",
        "arena": "SPECULATIVE",
        "target_hash": barrier["target_hash"],
        "dependencies": [],
        "dependency_path_to_target": barrier["dependency_path_to_target"],
        "relation_to_target": "direct",
        "barrier_id": barrier["barrier_id"],
        "priority": barrier.get("priority", 80),
        "failure_mutation_required": True,
        "actual_barrier_lemma": barrier.get("actual_barrier_lemma"),
        "direct_attacks": barrier.get("direct_attacks", []),
        "direct_attack_count": barrier.get("direct_attack_count", 0),
        "counterexample_pressure": barrier.get("counterexample_pressure"),
        "theorem_precondition_gap": barrier.get("theorem_precondition_gap"),
        "next_exact_attempt": barrier.get("next_exact_attempt"),
    }


def _node_from_rung(rung: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": rung["node_id"],
        "type": "rung_obligation",
        "statement": rung["statement"],
        "lean_statement": rung.get("lean_statement"),
        "status": "OPEN",
        "arena": "SPECULATIVE",
        "target_hash": rung["target_hash"],
        "dependencies": [],
        "dependency_path_to_target": rung["dependency_path_to_target"],
        "rung_id": rung["rung_id"],
        "priority": rung.get("priority", 70),
        "relation_to_target": rung.get("relation_to_target"),
    }


def _queue_from_node(node: dict[str, Any], lane: str) -> dict[str, Any]:
    relation = node.get("relation_to_target") or "direct dependency path to the frozen target"
    statement = str(node["statement"])
    return {
        "node_id": node["node_id"],
        "statement": statement,
        "lean_statement": node.get("lean_statement"),
        "priority": node.get("priority", 70),
        "lane": lane,
        "status": "OPEN",
        "target_hash": node.get("target_hash"),
        "dependency_path_to_target": node.get("dependency_path_to_target"),
        "why_it_matters": f"This {lane} item has relation_to_target={relation} and is on the recorded dependency path.",
        "unlocks": [f"progress on {node['node_id']} clarifies or reduces the frozen target"],
        "smallest_formalizable_subcase": (
            node.get("lean_statement")
            or node.get("next_exact_attempt")
            or f"Formalize a bounded/explicit version of: {statement[:180]}"
        ),
        "known_counterexamples_or_boundary_cases": [
            {"status": "unprobed", "note": "fresh Lovasz barrier/rung; no fabricated witness"}
        ],
        "failed_approaches": [
            {"method_family": "none_yet", "result": "unattempted"}
        ],
        "next_mutation": "after failure, mutate exactly one axis: " + ", ".join(MUTATION_AXES),
    }


def _ensure_open_ledgers(run: Path, target: str, target_hash: str, nodes: list[dict[str, Any]]) -> None:
    if not witcore.records(run / "disproof_first.json"):
        witcore.save_json(run / "disproof_first.json", [
            {
                "pass_type": "definition_stress",
                "target_statement": target,
                "search_domain": "definitions and quantifier boundary cases",
                "method": "audit exact domains, positivity, exceptional cases, and cleared equation equivalence",
                "bounds": "symbolic",
                "outcome": "planned_not_evidence",
                "next_search": "instantiate definitions and run bounded witness/counterexample search",
            },
            {
                "pass_type": "variant_stress",
                "target_statement": target,
                "search_domain": "stronger variants and residue-class variants",
                "method": "try to falsify strengthened residue or monotonicity claims before proof",
                "bounds": "small moduli and small n first",
                "outcome": "planned_not_evidence",
                "next_search": "record any refuted variant as obstruction pressure",
            },
            {
                "pass_type": "model_or_boundary_search",
                "target_statement": target,
                "search_domain": "bounded number-theory witness search",
                "method": "search for missing Egyptian-fraction witnesses or counterexamples to proposed bridges",
                "bounds": "pending orchestrator-selected bound",
                "outcome": "planned_not_evidence",
                "next_search": "run counterexample-search/research-search with replayable bounds",
            },
        ])
    if not witcore.records(run / "theorem_precondition_audit.json"):
        first = nodes[0] if nodes else {}
        witcore.save_json(run / "theorem_precondition_audit.json", [{
            "target_subgoal": first.get("statement") or target,
            "candidate_theorem": "closest known theorem pending literature/premise retrieval",
            "exact_statement": "PENDING: orchestrator must fill exact theorem statement before use",
            "required_preconditions": [],
            "missing_preconditions": ["exact theorem not selected yet"],
            "formal_availability": "unknown",
            "use_decision": "search_more",
        }])
    if not witcore.records(run / "product_selection.json"):
        first = next((n for n in nodes if n.get("lean_statement")), nodes[0] if nodes else {})
        witcore.save_json(run / "product_selection.json", [{
            "kind": "special_case" if first.get("lean_statement") else "partial_result",
            "statement": first.get("statement") or target,
            "why_this_helps_original": "selected as the first narrow product candidate on the dependency path; not accepted evidence yet",
            "dependency_path_to_target": first.get("dependency_path_to_target") or ["candidate", "T"],
            "verification_plan": "kernel replay if Lean-stated; otherwise formalize smallest subcase, then WIT/Lean/check",
            "status": "PLANNED",
            "selected": True,
        }])


def _merge_by_id(existing: list[dict[str, Any]], additions: list[dict[str, Any]], key: str) -> tuple[list[dict[str, Any]], int]:
    rows = [x for x in existing if isinstance(x, dict)]
    seen = {str(x.get(key)) for x in rows if x.get(key) is not None}
    added = 0
    for item in additions:
        ident = str(item.get(key))
        if ident in seen:
            continue
        rows.append(item)
        seen.add(ident)
        added += 1
    return rows, added


def prepare_run(
    run: Path,
    *,
    target: str | None = None,
    domain: str | None = None,
    lean_target: str | None = None,
    top_rungs: int = 18,
    max_barriers: int = 10,
) -> dict[str, Any]:
    run = Path(run)
    run.mkdir(parents=True, exist_ok=True)
    t, d, lean, th = _target_context(run, target, domain, lean_target)

    barriers_path = run / "barrier_attacks.json"
    existing_barriers = witcore.records(barriers_path)
    if existing_barriers:
        return {
            "schema": "witsoc.barrier_attack.prepare.v1",
            "run_dir": str(run),
            "target_hash": th,
            "already_prepared": True,
            "barriers": len(existing_barriers),
            "nodes_added": 0,
            "queue_added": 0,
        }

    lemmas = dbl.generate_barrier_lemmas(t, lean_target=lean, domain=d, target_hash=th, max_lemmas=max_barriers)
    barriers = [_barrier_record(lemma, i) for i, lemma in enumerate(lemmas, start=1)]
    saturation = rs.saturate(t, d, lean_target=lean, target_hash=th, top=top_rungs)

    barrier_nodes = [_node_from_barrier(b) for b in barriers]
    rung_nodes = [_node_from_rung(r) for r in saturation["rungs"][:top_rungs]]
    nodes = barrier_nodes + rung_nodes

    dag, dag_added = _merge_by_id(witcore.records(run / "proof_dependency_dag.json"), nodes, "node_id")
    queue_additions = [_queue_from_node(n, "barrier_attack" if n["type"] == "actual_barrier_lemma" else "rung_saturation")
                       for n in nodes]
    queue, queue_added = _merge_by_id(witcore.records(run / "actual_lemma_queue.json"), queue_additions, "node_id")

    witcore.save_json(barriers_path, {
        "schema": "witsoc.barrier_attack.v1",
        "target": t,
        "domain": d,
        "target_hash": th,
        "mutation_axes": MUTATION_AXES,
        "status_policy": "barriers are open obligations; kernel gates are the only upgrade path",
        "barriers": barriers,
    })
    witcore.save_json(run / "rung_saturation.json", saturation)
    witcore.save_json(run / "proof_dependency_dag.json", dag)
    witcore.save_json(run / "actual_lemma_queue.json", queue)
    _ensure_open_ledgers(run, t, th, nodes)
    return {
        "schema": "witsoc.barrier_attack.prepare.v1",
        "run_dir": str(run),
        "target_hash": th,
        "already_prepared": False,
        "barriers": len(barriers),
        "rungs": len(saturation["rungs"]),
        "nodes_added": dag_added,
        "queue_added": queue_added,
    }


def mutate_from_feedback(run: Path) -> dict[str, Any]:
    run = Path(run)
    feedback = witcore.load_json(run / "gap_feedback.json", {})
    feedback_nodes = feedback.get("nodes") if isinstance(feedback, dict) else {}
    feedback_nodes = feedback_nodes if isinstance(feedback_nodes, dict) else {}
    payload = witcore.load_json(run / "barrier_attacks.json", {})
    barriers = payload.get("barriers") if isinstance(payload, dict) else []
    barriers = [b for b in barriers if isinstance(b, dict)]
    if not barriers or not feedback_nodes:
        return {"schema": "witsoc.barrier_attack.mutate.v1", "mutations": 0, "reason": "no barriers or feedback"}

    ledger = witcore.records(run / "mutation_ledger.json")
    existing = {str(m.get("mutation_id")) for m in ledger}
    mutations = []
    by_node = {str(b.get("node_id")): b for b in barriers}
    for node_id, gap in feedback_nodes.items():
        barrier = by_node.get(str(node_id))
        if not barrier or not isinstance(gap, dict):
            continue
        axis_index = len(barrier.get("mutation_history") or []) % len(MUTATION_AXES)
        axis = MUTATION_AXES[axis_index]
        mid = f"M-{witcore.slug(str(node_id))}-{axis_index + 1:02d}"
        if mid in existing:
            continue
        mutation = {
            "mutation_id": mid,
            "barrier_id": barrier["barrier_id"],
            "node_id": node_id,
            "axis": axis,
            "axis_changed": axis,
            "target_hash": barrier.get("target_hash"),
            "method_family": str(gap.get("gap_class") or "unknown"),
            "previous_attempt_id": str(gap.get("failed_statement_sha") or node_id),
            "new_attempt_id": mid,
            "what_changed": f"mutate {axis} for blocker {gap.get('gap_class') or 'unknown'}",
            "why_this_is_not_repeat": "exactly one mutation axis changed after a recorded failed statement hash",
            "result": "PROPOSED",
            "gap_class": gap.get("gap_class"),
            "previous_statement": barrier.get("statement"),
            "mutated_statement": f"{barrier.get('statement')} [mutate axis: {axis}; blocker: {gap.get('gap_class') or 'unknown'}]",
            "evidence": gap,
            "status": "PROPOSED",
        }
        barrier.setdefault("failed_methods", []).append({
            "gap_class": gap.get("gap_class"),
            "proposed_mutation": gap.get("proposed_mutation"),
        })
        barrier.setdefault("mutation_history", []).append(mutation)
        mutations.append(mutation)

    if mutations:
        ledger.extend(mutations)
        payload["barriers"] = barriers
        witcore.save_json(run / "barrier_attacks.json", payload)
        witcore.save_json(run / "mutation_ledger.json", ledger)
    return {"schema": "witsoc.barrier_attack.mutate.v1", "mutations": len(mutations),
            "mutation_ids": [m["mutation_id"] for m in mutations]}


def status(run: Path) -> dict[str, Any]:
    payload = witcore.load_json(Path(run) / "barrier_attacks.json", {})
    barriers = payload.get("barriers") if isinstance(payload, dict) else []
    barriers = [b for b in barriers if isinstance(b, dict)]
    return {
        "schema": "witsoc.barrier_attack.status.v1",
        "run_dir": str(run),
        "barriers": len(barriers),
        "mutations": sum(len(b.get("mutation_history") or []) for b in barriers),
        "open": sum(1 for b in barriers if str(b.get("status")) in {"OPEN", "OPEN_UNFALSIFIED"}),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--target", default=None)
    p.add_argument("--domain", default=None)
    p.add_argument("--lean-target", default=None)
    p.add_argument("--top-rungs", type=int, default=18)
    p.add_argument("--max-barriers", type=int, default=10)
    m = sub.add_parser("mutate")
    m.add_argument("run_dir", type=Path)
    s = sub.add_parser("status")
    s.add_argument("run_dir", type=Path)
    args = ap.parse_args()
    if args.cmd == "init":
        out = prepare_run(args.run_dir, target=args.target, domain=args.domain,
                          lean_target=args.lean_target, top_rungs=args.top_rungs,
                          max_barriers=args.max_barriers)
    elif args.cmd == "mutate":
        out = mutate_from_feedback(args.run_dir)
    else:
        out = status(args.run_dir)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
