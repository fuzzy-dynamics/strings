#!/usr/bin/env python3
"""Validate completion gates for a Lovasz run directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_LEDGER_FILES = [
    "statement-ledger.md",
    "proof-dag.md",
    "computational-search.md",
    "failure-taxonomy.md",
    "novelty-ledger.md",
]

REQUIRED_JSON_FILES = [
    "actual_lemma_queue.json",
    "proof_dependency_dag.json",
    "worker_results.json",
    "skeptic_reviews.json",
]

ACCEPTED_STATUSES = {"VERIFIED", "CHECKED", "PROVED_SKETCH", "PARTIAL", "CONDITIONAL"}
FINAL_STATUSES = {"VERIFIED", "PARTIAL", "CONDITIONAL", "CHECKED", "FAILED_ATTEMPT", "REJECTED", "OPEN"}
EVIDENCE_STATUSES = ACCEPTED_STATUSES | {"CONJECTURE", "FAILED_ATTEMPT", "REJECTED"}


def load_json(path: Path, errors: list[str]) -> object:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        errors.append(f"{path.name}: could not read JSON: {exc}")
        return None


def nonempty_text(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    return bool(lines)


def list_records(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def registry_paths(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {str(item.get("path")) for item in data.get("artifacts", []) if isinstance(item, dict) and item.get("path")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--mode", choices=["quick", "deep", "campaign"], default="deep")
    parser.add_argument("--final-status", choices=sorted(FINAL_STATUSES), default="OPEN")
    parser.add_argument("--allow-empty-computation", action="store_true")
    parser.add_argument("--artifact-registry", type=Path, default=None)
    args = parser.parse_args()

    run_dir = args.run_dir
    errors: list[str] = []
    if not run_dir.is_dir():
        print(f"INVALID: run_dir does not exist or is not a directory: {run_dir}", file=sys.stderr)
        return 2

    for name in REQUIRED_LEDGER_FILES:
        path = run_dir / name
        if not path.exists():
            errors.append(f"missing required ledger {name}")
        elif name != "computational-search.md" or not args.allow_empty_computation:
            if not nonempty_text(path):
                errors.append(f"required ledger {name} has no substantive entries")

    payloads: dict[str, object] = {}
    for name in REQUIRED_JSON_FILES:
        path = run_dir / name
        if not path.exists():
            errors.append(f"missing required JSON {name}")
            payloads[name] = []
        else:
            payloads[name] = load_json(path, errors)

    actual_lemmas = list_records(payloads.get("actual_lemma_queue.json"))
    dag = list_records(payloads.get("proof_dependency_dag.json"))
    workers = list_records(payloads.get("worker_results.json"))
    skeptic_reviews = list_records(payloads.get("skeptic_reviews.json"))
    registered_artifacts = registry_paths(args.artifact_registry)

    if not actual_lemmas:
        errors.append("actual_lemma_queue.json must contain at least one actual barrier lemma or exact blocker")
    if not dag:
        errors.append("proof_dependency_dag.json must contain at least one node")
    if args.mode in {"deep", "campaign"} and not workers:
        errors.append(f"{args.mode} Lovasz run must contain worker_results.json entries")

    node_ids = {str(node.get("node_id") or node.get("id")) for node in dag if node.get("node_id") or node.get("id")}
    review_ids = {str(review.get("review_id")) for review in skeptic_reviews if review.get("review_id")}
    accepted_nodes = [node for node in dag if node.get("status") in ACCEPTED_STATUSES]
    if accepted_nodes and not skeptic_reviews:
        errors.append("accepted DAG nodes require skeptic_reviews.json entries")

    for index, node in enumerate(dag):
        node_id = str(node.get("node_id") or node.get("id") or f"<index {index}>")
        for field in ("statement", "status", "type"):
            if not node.get(field):
                errors.append(f"proof_dependency_dag node {node_id!r} missing {field}")
        if node.get("status") in ACCEPTED_STATUSES:
            review_id = node.get("skeptic_review_id")
            if not review_id:
                errors.append(f"accepted proof_dependency_dag node {node_id!r} missing skeptic_review_id")
            elif str(review_id) not in review_ids:
                errors.append(f"accepted proof_dependency_dag node {node_id!r} references unknown skeptic_review_id {review_id!r}")
            for field in ("evidence", "target_hash"):
                if node.get(field) in (None, "", []):
                    errors.append(f"accepted proof_dependency_dag node {node_id!r} missing {field}")
            if "dependencies" not in node:
                errors.append(f"accepted proof_dependency_dag node {node_id!r} missing dependencies")
        if node.get("status") in {"PARTIAL", "CONDITIONAL"}:
            for field in ("remaining_gap_statement", "why_not_full_solution", "next_exact_experiment_or_lemma"):
                if not node.get(field):
                    errors.append(f"partial/conditional node {node_id!r} missing {field}")
        if node.get("status") in EVIDENCE_STATUSES and node.get("status") not in {"PARTIAL", "CONDITIONAL"}:
            if node.get("evidence") in (None, "", []):
                errors.append(f"proof_dependency_dag node {node_id!r} status {node.get('status')!r} missing evidence")

    for index, worker in enumerate(workers):
        worker_id = str(worker.get("worker_id") or f"<index {index}>")
        if worker.get("node_id") and node_ids and str(worker.get("node_id")) not in node_ids:
            errors.append(f"worker_results {worker_id!r} references unknown node_id {worker.get('node_id')!r}")
        for field in ("claim", "status", "evidence", "failure_class", "next_mutation"):
            if worker.get(field) in (None, "", []):
                errors.append(f"worker_results {worker_id!r} missing {field}")
        if worker.get("status") in ACCEPTED_STATUSES and not worker.get("skeptic_review_id"):
            errors.append(f"accepted worker_results {worker_id!r} missing skeptic_review_id")
        for artifact in worker.get("artifacts") or []:
            artifact_path = Path(str(artifact))
            resolved = str(artifact_path.resolve())
            if not artifact_path.exists() and str(artifact) not in registered_artifacts and resolved not in registered_artifacts:
                errors.append(f"worker_results {worker_id!r} artifact not found or registered: {artifact}")

    for index, review in enumerate(skeptic_reviews):
        review_id = str(review.get("review_id") or f"<index {index}>")
        for field in ("target_drift_checked", "hidden_assumptions_checked", "circularity_checked", "weaker_target_checked"):
            if review.get(field) is not True:
                errors.append(f"skeptic_reviews {review_id!r} must set {field}=true")
        if review.get("verdict") != "pass":
            errors.append(f"skeptic_reviews {review_id!r} verdict must be pass")

    if args.final_status in {"PARTIAL", "CONDITIONAL"}:
        has_remaining_gap = any(node.get("remaining_gap_statement") for node in dag)
        if not has_remaining_gap:
            errors.append(f"final status {args.final_status} requires at least one remaining_gap_statement in the DAG")
    if args.final_status == "VERIFIED":
        verified = [node for node in dag if node.get("status") == "VERIFIED"]
        if not verified:
            errors.append("final status VERIFIED requires at least one VERIFIED DAG node")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("VALID_LOVASZ_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
