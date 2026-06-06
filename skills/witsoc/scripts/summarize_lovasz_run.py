#!/usr/bin/env python3
"""Generate Lovasz run summary and barriers ledger from run JSON."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def records(path: Path) -> list[dict]:
    data = load(path, [])
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def node_id(node: dict) -> str:
    return str(node.get("node_id") or node.get("id") or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--summary-out", type=Path, default=None)
    parser.add_argument("--barriers-out", type=Path, default=None)
    args = parser.parse_args()

    run = args.run_dir
    dag = records(run / "proof_dependency_dag.json")
    workers = records(run / "worker_results.json")
    lemmas = records(run / "actual_lemma_queue.json")
    retries = records(run / "retry_ledger.json")
    scores = load(run / "lovasz_result_scores.json", {}).get("scores", [])

    status_counts = Counter(str(n.get("status") or "UNKNOWN") for n in dag)
    worker_counts = Counter(str(w.get("status") or "UNKNOWN") for w in workers)
    active_barriers = []
    for node in dag:
        status = str(node.get("status") or "")
        if status in {"OPEN", "GAP", "FAILED_ATTEMPT", "REJECTED", "CONJECTURE"}:
            active_barriers.append({
                "node_id": node_id(node),
                "statement": node.get("statement"),
                "status": status,
                "failure_class": node.get("failure_class"),
                "remaining_gap_statement": node.get("remaining_gap_statement") or node.get("gap"),
                "next_exact_experiment_or_lemma": node.get("next_exact_experiment_or_lemma") or node.get("next_mutation"),
            })

    summary = {
        "schema": "witsoc.lovasz_summary.v1",
        "run_dir": str(run.resolve()),
        "dag_nodes": len(dag),
        "worker_results": len(workers),
        "actual_lemmas": len(lemmas),
        "status_counts": dict(status_counts),
        "worker_status_counts": dict(worker_counts),
        "top_worker_scores": scores[:5] if isinstance(scores, list) else [],
        "active_barriers": active_barriers,
        "retry_count": len(retries),
    }

    summary_path = args.summary_out or (run / "lovasz_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    barrier_path = args.barriers_out or (run / "barriers.md")
    lines = ["# Lovasz Barrier Ledger", "", "## Active Barriers", ""]
    if not active_barriers:
        lines.append("- No active barriers recorded.")
    for b in active_barriers:
        lines.append(f"- `{b['node_id']}` [{b['status']}]: {b.get('statement') or '(missing statement)'}")
        if b.get("failure_class"):
            lines.append(f"  - Failure class: {b['failure_class']}")
        if b.get("remaining_gap_statement"):
            lines.append(f"  - Gap: {b['remaining_gap_statement']}")
        if b.get("next_exact_experiment_or_lemma"):
            lines.append(f"  - Next: {b['next_exact_experiment_or_lemma']}")
    lines.extend(["", "## Actual Lemma Queue", ""])
    if not lemmas:
        lines.append("- No actual lemmas recorded.")
    for lemma in lemmas:
        lines.append(f"- {lemma.get('statement') or lemma.get('lemma') or lemma}")
    barrier_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"summary": str(summary_path), "barriers": str(barrier_path), "active_barriers": len(active_barriers)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
