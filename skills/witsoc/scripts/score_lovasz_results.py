#!/usr/bin/env python3
"""Score Lovasz worker results for Explorer review priority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STATUS_WEIGHT = {
    "VERIFIED": 45,
    "CHECKED": 35,
    "PROVED_SKETCH": 25,
    "PARTIAL": 22,
    "CONDITIONAL": 20,
    "CONJECTURE": 12,
    "FAILED_ATTEMPT": 8,
    "GAP": 5,
    "OPEN": 4,
    "REJECTED": 0,
}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def registry_paths(registry: Path | None) -> set[str]:
    if not registry:
        return set()
    data = load(registry, {})
    return {str(item.get("path")) for item in data.get("artifacts", []) if isinstance(item, dict) and item.get("path")}


def score_worker(worker: dict, registered: set[str]) -> dict:
    status = str(worker.get("status") or "")
    evidence = worker.get("evidence") if isinstance(worker.get("evidence"), list) else []
    artifacts = worker.get("artifacts") if isinstance(worker.get("artifacts"), list) else []
    fidelity = worker.get("target_fidelity")
    fidelity_value = float(fidelity) if isinstance(fidelity, (int, float)) else 0.0
    artifact_hits = sum(1 for p in artifacts if str(Path(str(p)).resolve()) in registered or str(p) in registered)
    missing_artifacts = [str(p) for p in artifacts if not Path(str(p)).exists() and str(Path(str(p)).resolve()) not in registered and str(p) not in registered]
    score = STATUS_WEIGHT.get(status, 0)
    score += min(15, 3 * len(evidence))
    score += min(12, 4 * len(artifacts))
    score += min(10, 5 * artifact_hits)
    score += round(20 * fidelity_value)
    if worker.get("failure_class") in {None, "", "none"} and status in {"FAILED_ATTEMPT", "GAP", "OPEN", "REJECTED"}:
        score -= 8
    if missing_artifacts:
        score -= 12
    if not worker.get("target_hash"):
        score -= 10
    return {
        "worker_id": worker.get("worker_id"),
        "node_id": worker.get("node_id"),
        "status": status,
        "score": max(0, score),
        "target_fidelity": fidelity_value,
        "evidence_count": len(evidence),
        "artifact_count": len(artifacts),
        "registered_artifact_count": artifact_hits,
        "missing_artifacts": missing_artifacts,
        "claim": worker.get("claim"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("worker_results", type=Path)
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    data = load(args.worker_results, [])
    workers = data if isinstance(data, list) else []
    registered = registry_paths(args.registry)
    scored = sorted((score_worker(w, registered) for w in workers if isinstance(w, dict)), key=lambda x: x["score"], reverse=True)
    result = {"schema": "witsoc.lovasz_result_scores.v1", "worker_results": str(args.worker_results), "scores": scored}
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
