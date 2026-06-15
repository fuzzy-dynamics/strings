#!/usr/bin/env python3
"""Validate that Lovasz worker results are useful candidate packets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CANDIDATE_OR_PROCESS = {
    "ATTACK_CANDIDATE",
    "PROOF_SKETCH_CANDIDATE",
    "LEMMA_CANDIDATE",
    "REDUCTION_CANDIDATE",
    "COUNTEREXAMPLE_CANDIDATE",
    "OPEN_UNFALSIFIED",
    "PROPOSED",
    "REFUTED",
    "BLOCKED",
    "NEEDS_FORMALIZATION",
    "FORMALIZED",
    "REVIEWED",
    "MUTATE",
    "FAILED_ATTEMPT",
    "REJECTED",
    "GAP",
    "OPEN",
}
ACCEPTED_WITH_EVIDENCE = {"VERIFIED", "VERIFIED_WIT", "VERIFIED_LEAN", "VERIFIED_EXTERNAL", "CHECKED", "CHECKED_BOUNDED", "CHECKED_SYMBOLIC", "PROVED_SKETCH", "PARTIAL", "CONDITIONAL"}
FORBIDDEN = {"SOLVED", "SOLVE_ACCEPTED"}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def validate_worker(worker: dict[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    label = worker.get("worker_id") or worker.get("node_id") or f"<index {index}>"
    status = str(worker.get("status") or "").upper()
    if status in FORBIDDEN:
        errors.append(f"{label}: Lovasz worker may not assert trust status {status}")
    elif status in ACCEPTED_WITH_EVIDENCE:
        if not (worker.get("evidence") or worker.get("receipt_ids") or worker.get("receipts") or worker.get("artifacts") or worker.get("proof") or worker.get("lean_path") or worker.get("wit_path")):
            errors.append(f"{label}: accepted worker status {status} requires downstream evidence/artifact")
    elif status and status not in CANDIDATE_OR_PROCESS:
        errors.append(f"{label}: unknown Lovasz worker status {status}")
    for field in ("node_id", "target_hash"):
        if not worker.get(field):
            errors.append(f"{label}: missing {field}")
    if not (worker.get("claim") or worker.get("statement") or worker.get("exact_subproblem")):
        errors.append(f"{label}: missing exact subproblem/claim")
    if not (worker.get("dependency_path_to_target") or worker.get("path_to_target")):
        errors.append(f"{label}: missing dependency_path_to_target")
    if not worker.get("next_mutation") and status in {"FAILED_ATTEMPT", "GAP", "OPEN", "BLOCKED", "MUTATE"}:
        errors.append(f"{label}: failed/open worker result missing next_mutation")
    if not worker.get("failure_class") and status in {"FAILED_ATTEMPT", "GAP", "REJECTED"}:
        errors.append(f"{label}: failed worker result missing failure_class")
    return errors


def validate(path: Path) -> dict[str, Any]:
    data = load(path, [])
    workers = data if isinstance(data, list) else []
    errors: list[str] = []
    for i, worker in enumerate(workers):
        if not isinstance(worker, dict):
            errors.append(f"worker_results[{i}] is not an object")
            continue
        errors.extend(validate_worker(worker, i))
    return {"schema": "witsoc.lovasz_worker_quality.v1", "valid": not errors, "errors": errors, "workers": len(workers)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worker_results", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    result = validate(args.worker_results)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
