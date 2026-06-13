#!/usr/bin/env python3
"""Generate Lovasz worker spawn packets from actual lemmas and proof DAG."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


DEFAULT_WORKER_FOR_TYPE = {
    "counterexample_search": "COUNTEREXAMPLE",
    "computational_certificate": "COMPUTATION",
    "actual_barrier_lemma": "PROOF_BUILDER",
    "lemma": "PROOF_BUILDER",
    "reduction": "PROOF_BUILDER",
    "obstruction": "COUNTEREXAMPLE",
    "special_case": "FORMALIZER",
    "conditional_theorem": "PROOF_BUILDER",
}


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


from witcore import slug  # noqa: E402  -- shared substrate, was a local copy
from lovasz_run_manifest import default_campaign  # noqa: E402

def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def worker_budget(run: Path) -> dict:
    """Per-worker budget comes from the campaign block in lovasz_run.json
    (campaign_budget_gate owns it); packets never carry their own numbers."""
    manifest = load(run / "lovasz_run.json", {})
    campaign = manifest.get("campaign") if isinstance(manifest, dict) else None
    if isinstance(campaign, dict) and isinstance(campaign.get("budget", {}).get("worker"), dict):
        return dict(campaign["budget"]["worker"])
    return dict(default_campaign()["budget"]["worker"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--session-id", default="manual")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    run = args.run_dir
    out_dir = args.out_dir or (run / "spawn_packets")
    out_dir.mkdir(parents=True, exist_ok=True)
    dag = load(run / "proof_dependency_dag.json", [])
    lemmas = load(run / "actual_lemma_queue.json", [])
    lemma_by_statement = {str(l.get("statement")): l for l in lemmas if isinstance(l, dict)}
    budget = worker_budget(run)
    packets = []

    for node in [n for n in dag if isinstance(n, dict)][: args.limit]:
        node_id = str(node.get("node_id") or node.get("id") or slug(str(node.get("statement", "node"))))
        statement = str(node.get("statement") or node.get("exact_statement") or "")
        if not statement:
            continue
        node_type = str(node.get("type") or "lemma")
        worker_type = DEFAULT_WORKER_FOR_TYPE.get(node_type, "PROOF_BUILDER")
        target_hash = str(node.get("target_hash") or sha(statement))
        proof_worktree = str(run / "worktrees" / f"witsoc-proof-{args.session_id}-{slug(node_id)}")
        lemma = lemma_by_statement.get(statement, {})
        packet = {
            "worker_type": worker_type,
            "target_node_id": node_id,
            "exact_statement": statement,
            "method_family": worker_type,
            "expected_artifact": "WIT" if worker_type in {"PROOF_BUILDER", "FORMALIZER"} else "worker_result_json",
            "forbidden_drift": "Do not weaken, strengthen, rename variables, change hypotheses, or solve a neighboring target.",
            "stop_condition": str(lemma.get("smallest_formalizable_subcase") or "Return VERIFIED/CHECKED/PARTIAL/FAILED_ATTEMPT with evidence and next mutation."),
            "failure_memory_contract": {
                "read_before_start": str(run / "lovasz.soc"),
                "on_failure": "append exact method, blocker, evidence path, do_not_repeat condition, and next distinct methods to FAILED_APPROACHES",
                "on_progress": "append reusable reductions, counterexamples, checked computations, or theorem-precondition facts to INSIGHTS",
            },
            "target_hashes": {
                "frozen_target_sha256": target_hash,
                "definitions_sha256": str(node.get("definitions_sha256") or target_hash),
                "hypotheses_sha256": str(node.get("hypotheses_sha256") or target_hash),
                "conclusion_sha256": str(node.get("conclusion_sha256") or target_hash),
            },
            "budget": budget,
            "proof_worktree": proof_worktree,
            "dependency_path_to_target": node.get("dependency_path_to_target") or [],
        }
        if node.get("mutation_applied"):
            packet["mutation_applied"] = str(node["mutation_applied"])
        path = out_dir / f"{slug(node_id)}.spawn.json"
        path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        packets.append(str(path))

    (run / "spawn_requests.json").write_text(json.dumps(packets, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"packets": packets, "count": len(packets)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
