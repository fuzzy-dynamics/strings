#!/usr/bin/env python3
"""Strict proof-DAG integrity checker for Lovasz/Witsoc runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ACCEPTED = {"VERIFIED", "CHECKED", "PROVED_SKETCH", "PARTIAL", "CONDITIONAL"}
UNUSABLE = {"CONJECTURE", "REJECTED", "FAILED_ATTEMPT", "GAP", "OPEN"}


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def records(path: Path) -> list[dict]:
    data = load(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def node_id(node: dict) -> str:
    return str(node.get("node_id") or node.get("id") or "")


def deps(node: dict) -> list[str]:
    value = node.get("dependencies", node.get("depends_on", []))
    return [str(x) for x in value] if isinstance(value, list) else []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--artifact-registry", type=Path, default=None)
    args = parser.parse_args()

    run = args.run_dir
    dag = records(run / "proof_dependency_dag.json")
    reviews = {str(r.get("review_id")) for r in records(run / "skeptic_reviews.json") if r.get("review_id")}
    registry = load(args.artifact_registry, {}) if args.artifact_registry else {}
    registered = {str(a.get("path")) for a in registry.get("artifacts", []) if isinstance(a, dict) and a.get("path")}

    errors: list[str] = []
    nodes = {node_id(n): n for n in dag if node_id(n)}
    if len(nodes) != len(dag):
        errors.append("every DAG node must have unique node_id or id")

    for nid, node in nodes.items():
        for dep in deps(node):
            if dep not in nodes:
                errors.append(f"node {nid!r} depends on missing node {dep!r}")
        if node.get("dependency_path_to_target") in (None, "", []):
            errors.append(f"node {nid!r} missing dependency_path_to_target")
        if node.get("status") in ACCEPTED:
            for field in ("statement", "evidence", "target_hash"):
                if node.get(field) in (None, "", []):
                    errors.append(f"accepted node {nid!r} missing {field}")
            review_id = node.get("skeptic_review_id")
            if review_id and str(review_id) not in reviews:
                errors.append(f"node {nid!r} references unknown skeptic_review_id {review_id!r}")
            elif not review_id:
                errors.append(f"accepted node {nid!r} missing skeptic_review_id")
            for artifact in node.get("artifacts") or []:
                p = Path(str(artifact))
                if not p.exists() and str(artifact) not in registered and str(p.resolve()) not in registered:
                    errors.append(f"accepted node {nid!r} artifact missing/unregistered: {artifact}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(nid: str, stack: list[str]) -> None:
        if nid in visiting:
            errors.append("cycle detected: " + " -> ".join(stack + [nid]))
            return
        if nid in visited:
            return
        visiting.add(nid)
        for dep in deps(nodes[nid]):
            if dep in nodes:
                dfs(dep, stack + [nid])
        visiting.remove(nid)
        visited.add(nid)

    for nid in nodes:
        dfs(nid, [])

    for nid, node in nodes.items():
        for dep in deps(node):
            dep_status = nodes.get(dep, {}).get("status")
            if dep_status in UNUSABLE and node.get("status") in ACCEPTED:
                errors.append(f"accepted node {nid!r} uses unusable dependency {dep!r} with status {dep_status!r}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("VALID_PROOF_DAG_INTEGRITY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
