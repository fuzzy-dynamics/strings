#!/usr/bin/env python3
"""Create or update the authoritative Lovasz run manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PHASES = [
    "EXPLORER_PACKET_REQUIRED",
    "TARGET_FROZEN",
    "BARRIER_LEDGERS_READY",
    "DISPROOF_FIRST_DONE",
    "PROOF_DAG_READY",
    "WORKERS_DISPATCHED",
    "WORKER_RESULTS_SCORED",
    "SKEPTIC_REVIEW_DONE",
    "FORMALIZATION_SCORED",
    "EXPLORER_RETURN_READY",
    "NO_GO",
]

PHASE_REQUIREMENTS = {
    "EXPLORER_PACKET_REQUIRED": [],
    "TARGET_FROZEN": ["handoff_v1.json"],
    "BARRIER_LEDGERS_READY": ["actual_lemma_queue.json", "theorem_precondition_audit.json", "product_selection.json"],
    "DISPROOF_FIRST_DONE": ["disproof_first.json", "counterexample_search_templates.json"],
    "PROOF_DAG_READY": ["proof_dependency_dag.json"],
    "WORKERS_DISPATCHED": ["spawn_requests.json"],
    "WORKER_RESULTS_SCORED": ["worker_results.json", "lovasz_result_scores.json"],
    "SKEPTIC_REVIEW_DONE": ["skeptic_reviews.json"],
    "FORMALIZATION_SCORED": ["formalization_feasibility.json"],
    "EXPLORER_RETURN_READY": ["explorer_return_packet.json", "open_problem_report.md", "report_quality_grade.json"],
    "NO_GO": ["failure_memory.md"],
}

ALLOWED_NEXT = {
    "EXPLORER_PACKET_REQUIRED": ["TARGET_FROZEN", "NO_GO"],
    "TARGET_FROZEN": ["BARRIER_LEDGERS_READY", "NO_GO"],
    "BARRIER_LEDGERS_READY": ["DISPROOF_FIRST_DONE", "PROOF_DAG_READY", "NO_GO"],
    "DISPROOF_FIRST_DONE": ["PROOF_DAG_READY", "NO_GO"],
    "PROOF_DAG_READY": ["WORKERS_DISPATCHED", "NO_GO"],
    "WORKERS_DISPATCHED": ["WORKER_RESULTS_SCORED", "NO_GO"],
    "WORKER_RESULTS_SCORED": ["SKEPTIC_REVIEW_DONE", "NO_GO"],
    "SKEPTIC_REVIEW_DONE": ["FORMALIZATION_SCORED", "NO_GO"],
    "FORMALIZATION_SCORED": ["EXPLORER_RETURN_READY", "BARRIER_LEDGERS_READY", "NO_GO"],
    "EXPLORER_RETURN_READY": [],
    "NO_GO": [],
}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def records(path: Path) -> list[dict]:
    data = load(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def infer_target(run: Path, explicit: str) -> tuple[str, str]:
    if explicit:
        return explicit, sha256_text(explicit)
    handoff = load(run / "handoff_v1.json", {})
    for key in ("frozen_target", "target", "statement"):
        if handoff.get(key):
            target = str(handoff[key])
            return target, str(handoff.get("target_hash") or handoff.get("frozen_target_hash") or sha256_text(target))
    statement = run / "statement-ledger.md"
    if statement.exists():
        text = statement.read_text(encoding="utf-8", errors="replace")
        marker = "## Frozen Target"
        if marker in text:
            tail = text.split(marker, 1)[1].strip().split("\n\n", 1)[0].strip()
            if tail:
                return tail, sha256_text(tail)
    return "", ""


def nonempty(path: Path) -> bool:
    if not path.exists():
        return False
    if path.suffix == ".json":
        data = load(path, None)
        if isinstance(data, list):
            return len(data) > 0
        if isinstance(data, dict):
            return bool(data)
        return data is not None
    return bool(path.read_text(encoding="utf-8", errors="replace").strip())


def phase_ready(run: Path, phase: str) -> bool:
    return all(nonempty(run / name) for name in PHASE_REQUIREMENTS.get(phase, []))


def infer_phase(run: Path) -> str:
    for phase in reversed(PHASES):
        if phase == "NO_GO":
            continue
        if phase_ready(run, phase):
            return phase
    return "TARGET_FROZEN" if (run / "handoff_v1.json").exists() else "EXPLORER_PACKET_REQUIRED"


def manifest(run: Path, phase: str, target: str, target_hash: str) -> dict:
    ledgers = {
        "actual_lemma_queue": "actual_lemma_queue.json",
        "proof_dag": "proof_dependency_dag.json",
        "worker_results": "worker_results.json",
        "skeptic_reviews": "skeptic_reviews.json",
        "formalization_feasibility": "formalization_feasibility.json",
        "explorer_return": "explorer_return_packet.json",
    }
    validators = {
        "open_problem": "validate_open_problem_run.py",
        "dag_integrity": "validate_proof_dag_integrity.py",
        "status_lattice": "status_lattice.py",
        "formalization": "formalization_feasibility.py",
        "report_grade": "grade_witsoc_report.py",
    }
    blocking_gaps = []
    for required in PHASE_REQUIREMENTS.get(phase, []):
        if not nonempty(run / required):
            blocking_gaps.append(f"{phase} requires nonempty {required}")
    if not target_hash and phase != "EXPLORER_PACKET_REQUIRED":
        blocking_gaps.append("missing frozen target hash")
    return {
        "schema": "witsoc.lovasz_run.v1",
        "run_id": run.name,
        "run_dir": str(run),
        "phase": phase,
        "allowed_next_phases": ALLOWED_NEXT.get(phase, []),
        "target_hash": target_hash,
        "source_target_text": target,
        "normalization_version": "witsoc.target.v1",
        "explorer_packet": "handoff_v1.json" if (run / "handoff_v1.json").exists() else "",
        "ledgers": ledgers,
        "validators": validators,
        "counts": {
            "actual_lemmas": len(records(run / "actual_lemma_queue.json")),
            "dag_nodes": len(records(run / "proof_dependency_dag.json")),
            "worker_results": len(records(run / "worker_results.json")),
            "skeptic_reviews": len(records(run / "skeptic_reviews.json")),
        },
        "blocking_gaps": blocking_gaps,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--phase", choices=PHASES, default=None)
    parser.add_argument("--target", default="")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    target, target_hash = infer_target(args.run_dir, args.target)
    phase = args.phase or infer_phase(args.run_dir)
    result = manifest(args.run_dir, phase, target, target_hash)
    out = args.out or (args.run_dir / "lovasz_run.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
