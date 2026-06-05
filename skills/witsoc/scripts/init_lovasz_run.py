#!/usr/bin/env python3
"""Create the standard Lovasz run ledger skeleton.

This controller makes the required open-problem artifacts concrete before
workers start. It intentionally writes only empty ledgers/templates; mathematical
content still belongs to Explorer, Lovasz, and the workers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


TEMPLATE_FILES: dict[str, str] = {
    "statement-ledger.md": """# Statement Ledger

## Frozen Target

## Variants

## Sources And Status

## Definitions

## Target Hashes
""",
    "proof-dag.md": """# Proof DAG

Each node must have: node id, exact statement, type, dependencies, relation to
the frozen target, status, evidence, worker ids, and remaining gaps.
""",
    "computational-search.md": """# Computational Search

Record exact commands, bounds, predicates, seeds, witnesses, output hashes, and
negative evidence. Bounded searches are `CHECKED` only for their bounds.
""",
    "failure-taxonomy.md": """# Failure Taxonomy

Use reusable classes: false claim, target drift, theorem-precondition gap,
missing barrier lemma, artifact issue, computational obstruction, hidden
assumption, circularity, weaker target substitution, or genuine mathematical
barrier.
""",
    "novelty-ledger.md": """# Novelty Ledger

Separate known sourced facts, recovered folklore, recombinations of known tools,
new conjectures, new computations, and claims requiring formal verification.
""",
    "research.md": """# Lovasz Research Ledger

## Current Barrier

## Active Workers

## Synthesis Notes
""",
    "failure_memory.md": """# Failure Memory

Record failed routes with method family, exact statement, why it failed,
counterexample or blocker, and retry condition.
""",
    "lovasz.soc": """-- Status: RUNNING

GOAL: <exact research target>

CURRENT:
  Selected product: unset
  Active barrier: unset
  Active move: unset

INSIGHTS:

PROGRESS:
  - problems_since_last_progress: 0
  - total_verified: 0
  - total_partial: 0
  - total_failed_attempts: 0

FAILED_APPROACHES:

QUEUE:
  - source_triage: pending
  - barrier_map: pending
  - first_experiment: pending
""",
}


JSON_FILES: dict[str, object] = {
    "actual_lemma_queue.json": [],
    "proof_dependency_dag.json": [],
    "spawn_requests.json": [],
    "worker_results.json": [],
    "skeptic_reviews.json": [],
    "retry_ledger.json": [],
    "closure_attempts.json": [],
    "final_synthesis_audit.json": {},
    "disproof_first.json": [],
    "theorem_precondition_audit.json": [],
    "product_selection.json": [],
    "mutation_ledger.json": [],
    "lovasz_result_scores.json": {},
    "lovasz_summary.json": {},
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--target", default="", help="Optional frozen target statement.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing template files.")
    args = parser.parse_args()

    run_dir = args.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    for name, content in TEMPLATE_FILES.items():
        path = run_dir / name
        if path.exists() and not args.force:
            continue
        if name == "statement-ledger.md" and args.target:
            content = content.replace("## Frozen Target\n", f"## Frozen Target\n\n{args.target}\n")
        if name == "lovasz.soc" and args.target:
            content = content.replace("GOAL: <exact research target>", f"GOAL: {args.target}")
        path.write_text(content, encoding="utf-8")

    for name, value in JSON_FILES.items():
        path = run_dir / name
        if path.exists() and not args.force:
            continue
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    target_hash = hashlib.sha256(args.target.encode("utf-8")).hexdigest() if args.target else ""
    lovasz_run = {
        "schema": "witsoc.lovasz_run.v1",
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "phase": "TARGET_FROZEN" if args.target else "EXPLORER_PACKET_REQUIRED",
        "allowed_next_phases": ["BARRIER_LEDGERS_READY", "NO_GO"] if args.target else ["TARGET_FROZEN", "NO_GO"],
        "target_hash": target_hash,
        "source_target_text": args.target,
        "normalization_version": "witsoc.target.v1",
        "explorer_packet": "",
        "ledgers": {
            "actual_lemma_queue": "actual_lemma_queue.json",
            "proof_dag": "proof_dependency_dag.json",
            "worker_results": "worker_results.json",
            "skeptic_reviews": "skeptic_reviews.json",
            "formalization_feasibility": "formalization_feasibility.json",
            "explorer_return": "explorer_return_packet.json",
        },
        "validators": {
            "open_problem": "validate_open_problem_run.py",
            "dag_integrity": "validate_proof_dag_integrity.py",
            "status_lattice": "status_lattice.py",
            "phase": "validate_lovasz_phase.py",
        },
        "blocking_gaps": [],
    }
    lovasz_run_path = run_dir / "lovasz_run.json"
    if not lovasz_run_path.exists() or args.force:
        lovasz_run_path.write_text(json.dumps(lovasz_run, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "run_dir": str(run_dir),
        "required_ledgers": sorted(TEMPLATE_FILES),
        "required_json": sorted(JSON_FILES),
        "lovasz_run": "lovasz_run.json",
        "status": "initialized",
    }
    (run_dir / "lovasz_run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
