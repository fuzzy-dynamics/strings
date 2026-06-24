#!/usr/bin/env python3
"""Assemble a compact Lovasz campaign health state from existing ledgers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CANDIDATE_STATUSES = {
    "ATTACK_CANDIDATE",
    "PROOF_SKETCH_CANDIDATE",
    "LEMMA_CANDIDATE",
    "REDUCTION_CANDIDATE",
    "COUNTEREXAMPLE_CANDIDATE",
    "OPEN_UNFALSIFIED",
}
OPENISH = {"OPEN", "OPEN_UNFALSIFIED", "CONJECTURE", "GAP", "FAILED_ATTEMPT", "REJECTED", "DEMOTED"}
ACCEPTED = {"VERIFIED", "VERIFIED_WIT", "VERIFIED_LEAN", "VERIFIED_EXTERNAL", "CHECKED", "CHECKED_SYMBOLIC", "CHECKED_BOUNDED", "PROVED_SKETCH", "PARTIAL", "CONDITIONAL"}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def records(path: Path) -> list[dict[str, Any]]:
    value = load(path, [])
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def dict_records(path: Path, key: str) -> list[dict[str, Any]]:
    value = load(path, {})
    rows = value.get(key) if isinstance(value, dict) else []
    return [x for x in rows if isinstance(x, dict)] if isinstance(rows, list) else []


def assemble(run: Path) -> dict[str, Any]:
    manifest = load(run / "lovasz_run.json", {})
    barriers = dict_records(run / "barrier_attacks.json", "barriers")
    rungs = dict_records(run / "rung_saturation.json", "rungs")
    dag = records(run / "proof_dependency_dag.json")
    queue = records(run / "actual_lemma_queue.json")
    workers = records(run / "worker_results.json")
    feedback = load(run / "gap_feedback.json", {})
    mutations = records(run / "mutation_ledger.json")
    scores = load(run / "lovasz_result_scores.json", {})
    explorer = load(run / "explorer_return_packet.json", {})
    theory = load(run / "problem_theory.json", {})
    doctor = load(run / "lovasz_doctor.json", {})

    barrier_nodes = [n for n in dag if n.get("type") == "actual_barrier_lemma" or n.get("actual_barrier_lemma")]
    formalizable = [n for n in dag if n.get("lean_statement")]
    main_barrier_workers = [
        w for w in workers
        if any((w.get("node_id") == b.get("node_id")) for b in barrier_nodes)
    ]
    status_counts: dict[str, int] = {}
    for row in dag + workers:
        status = str(row.get("status") or "OPEN").upper()
        status_counts[status] = status_counts.get(status, 0) + 1
    method_counts: dict[str, int] = {}
    for row in workers:
        method = str(row.get("method_family") or row.get("worker_type") or row.get("role") or "unknown")
        method_counts[method] = method_counts.get(method, 0) + 1
    score_rows = scores.get("scores") if isinstance(scores, dict) and isinstance(scores.get("scores"), list) else []
    theory_log = theory.get("theory_log") if isinstance(theory, dict) and isinstance(theory.get("theory_log"), list) else []
    feedback_nodes = feedback.get("nodes") if isinstance(feedback, dict) and isinstance(feedback.get("nodes"), dict) else {}

    return {
        "schema": "witsoc.lovasz_campaign_state.v1",
        "run_dir": str(run),
        "target": {
            "text": manifest.get("source_target_text") if isinstance(manifest, dict) else "",
            "hash": manifest.get("target_hash") if isinstance(manifest, dict) else "",
            "domain": manifest.get("domain") if isinstance(manifest, dict) else "",
        },
        "barrier_spine": {
            "barriers": len(barriers),
            "barrier_nodes": len(barrier_nodes),
            "main_barrier_workers": len(main_barrier_workers),
            "formalizable_barrier_nodes": sum(1 for n in barrier_nodes if n.get("lean_statement")),
        },
        "breadth": {
            "rungs": len(rungs),
            "queue": len(queue),
            "serendipity": sum(1 for q in queue if q.get("lane") == "serendipity"),
        },
        "formalization": {
            "formalizable_nodes": len(formalizable),
            "workers_with_wit": sum(1 for w in workers if w.get("wit_path")),
            "workers_with_lean": sum(1 for w in workers if w.get("lean_path")),
        },
        "results": {
            "dag_nodes": len(dag),
            "worker_results": len(workers),
            "status_counts": status_counts,
            "accepted": sum(1 for s, c in status_counts.items() if s in ACCEPTED for _ in range(c)),
            "candidate_only": sum(1 for s, c in status_counts.items() if s in CANDIDATE_STATUSES for _ in range(c)),
            "openish": sum(1 for s, c in status_counts.items() if s in OPENISH for _ in range(c)),
            "top_score": max((float(s.get("score") or 0) for s in score_rows if isinstance(s, dict)), default=0.0),
        },
        "learning": {
            "gap_feedback_nodes": len(feedback_nodes),
            "mutation_records": len(mutations),
            "theory_revisions": max(0, int(theory.get("version", 1) or 1) - 1) if isinstance(theory, dict) else 0,
            "theory_log_entries": len(theory_log),
            "method_counts": method_counts,
        },
        "explorer_return": {
            "exists": bool(explorer),
            "recommended_action": explorer.get("recommended_action") if isinstance(explorer, dict) else None,
            "remaining_barriers": len(explorer.get("remaining_barriers", [])) if isinstance(explorer, dict) and isinstance(explorer.get("remaining_barriers"), list) else 0,
        },
        "doctor": {
            "exists": bool(doctor),
            "health": doctor.get("health") if isinstance(doctor, dict) else None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    state = assemble(args.run_dir)
    out = args.out or (args.run_dir / "lovasz_campaign_state.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(state, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
