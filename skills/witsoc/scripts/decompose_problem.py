#!/usr/bin/env python3
"""Decompose a Witsoc target into smaller Lovasz subproblems.

This is a deterministic scaffolding tool. It does not claim the subproblems are
true; it creates auditable DAG nodes that Explorer/Lovasz can falsify, prove, or
demote.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def records(path: Path) -> list[dict]:
    data = load(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
    manifest = load(run / "lovasz_run.json", {})
    if manifest.get("source_target_text"):
        target = str(manifest["source_target_text"])
        return target, str(manifest.get("target_hash") or sha256_text(target))
    return "UNSPECIFIED_TARGET", "UNKNOWN_TARGET_HASH"


def domain_tags(statement: str) -> set[str]:
    text = statement.lower()
    tags: set[str] = set()
    checks = {
        "graph": ("graph", "tree", "cycle", "clique", "chromatic", "vertex", "edge", "ramsey"),
        "number_theory": ("prime", "integer", "divisor", "mod", "congruence", "diophantine"),
        "analysis": ("limit", "continuous", "measure", "integral", "norm", "compact"),
        "algebra": ("group", "ring", "field", "module", "ideal", "homomorphism"),
        "combinatorics": ("set", "family", "density", "extremal", "sumset", "matching"),
        "logic": ("sat", "cnf", "formula", "model", "proof", "resolution"),
    }
    for tag, words in checks.items():
        if any(word in text for word in words):
            tags.add(tag)
    return tags or {"general"}


def split_hypotheses(statement: str) -> list[str]:
    text = re.sub(r"\s+", " ", statement.strip())
    parts = re.split(r"\b(?:and|with|such that|assuming|where)\b|[,;]", text, flags=re.IGNORECASE)
    clean = [p.strip() for p in parts if len(p.strip()) > 8]
    return clean[:5]


def node(node_id: str, statement: str, node_type: str, deps: list[str], target_hash: str, path: list[str], priority: int) -> dict:
    return {
        "node_id": node_id,
        "claim_id": f"claim:{node_id}",
        "statement": statement,
        "type": node_type,
        "dependencies": deps,
        "relation_to_target": "decomposes_target" if deps else "target",
        "status": "OPEN",
        "target_hash": target_hash,
        "dependency_path_to_target": path,
        "priority": priority,
        "evidence": [],
        "next_exact_experiment_or_lemma": "run disproof-first search, theorem-precondition audit, then assign a worker packet",
    }


def decompose(statement: str, target_hash: str) -> tuple[list[dict], list[dict]]:
    tags = domain_tags(statement)
    nodes: list[dict] = [
        node("T", statement, "target", [], target_hash, ["T"], 100),
    ]
    lemmas: list[dict] = []

    templates = [
        ("D", "Definition audit: formalize every object, quantifier, parameter range, and exceptional case in the target.", "definition_audit", 95),
        ("C", "Counterexample pressure: search smallest finite or boundary models satisfying the hypotheses and falsifying the conclusion.", "counterexample_search", 90),
        ("P", "Theorem-precondition bridge: identify the closest known theorem and prove or refute each missing precondition for the target.", "precondition_bridge", 85),
        ("B", "Barrier lemma: isolate the strongest intermediate claim whose proof would unlock the target without weakening it.", "actual_barrier_lemma", 80),
        ("F", "Formalizable core: state the smallest WIT/Lean-ready subcase that still exercises the main barrier.", "formalizable_subcase", 75),
    ]
    for ident, text, kind, priority in templates:
        nodes.append(node(ident, text, kind, ["T"], target_hash, [ident, "T"], priority))

    hyps = split_hypotheses(statement)
    for index, hyp in enumerate(hyps, start=1):
        ident = f"H{index}"
        nodes.append(node(
            ident,
            f"Hypothesis isolation {index}: test whether `{hyp}` is necessary, redundant, or replaceable by a sharper invariant.",
            "hypothesis_isolation",
            ["T"],
            target_hash,
            [ident, "T"],
            70 - index,
        ))

    if "graph" in tags:
        nodes.append(node("G1", "Graph finite-model search: enumerate small graphs at increasing order and record extremal witnesses or no-witness bounds.", "computational_certificate", ["C"], target_hash, ["G1", "C", "T"], 78))
        nodes.append(node("G2", "Graph structure lemma: prove the target for a minimal counterexample after degree, cut, and forbidden-subgraph reductions.", "lemma", ["B", "G1"], target_hash, ["G2", "B", "T"], 74))
    if "number_theory" in tags:
        nodes.append(node("N1", "Arithmetic obstruction search: scan residue classes, valuation cases, and small integer witnesses before proof search.", "computational_certificate", ["C"], target_hash, ["N1", "C", "T"], 78))
        nodes.append(node("N2", "Local-to-global bridge: separate congruence/local constraints from the global statement and audit missing lifting hypotheses.", "reduction", ["P"], target_hash, ["N2", "P", "T"], 72))
    if "logic" in tags:
        nodes.append(node("L1", "Encoding audit: normalize the logical formula and identify clauses/variables/resolution steps that preserve the frozen target.", "definition_audit", ["D"], target_hash, ["L1", "D", "T"], 78))
        nodes.append(node("L2", "Bounded refutation/search: test small instances or bounded proof objects before claiming a general proof.", "counterexample_search", ["C"], target_hash, ["L2", "C", "T"], 72))

    for n in nodes:
        if n["node_id"] == "T":
            continue
        lemmas.append({
            "lemma_id": f"lemma:{n['node_id']}",
            "node_id": n["node_id"],
            "statement": n["statement"],
            "why_it_matters": f"Dependency path to target: {' -> '.join(n['dependency_path_to_target'])}",
            "unlocks": ["T"],
            "known_counterexamples_or_boundary_cases": [],
            "failed_approaches": [],
            "next_mutation": n["next_exact_experiment_or_lemma"],
            "smallest_formalizable_subcase": n["statement"],
            "status": "OPEN",
            "target_hash": target_hash,
            "priority": n["priority"],
        })
    return nodes, lemmas


def merge_by_id(existing: list[dict], new: list[dict], key: str) -> list[dict]:
    merged = {str(item.get(key)): item for item in existing if item.get(key)}
    for item in new:
        ident = str(item.get(key))
        if ident not in merged:
            merged[ident] = item
    return list(merged.values())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--target", default="")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--write", action="store_true", help="Update proof_dependency_dag.json and actual_lemma_queue.json.")
    args = parser.parse_args()

    target, target_hash = infer_target(args.run_dir, args.target)
    nodes, lemmas = decompose(target, target_hash)
    result = {
        "schema": "witsoc.problem_decomposition.v1",
        "target_hash": target_hash,
        "source_target_text": target,
        "nodes": nodes,
        "actual_lemmas": lemmas,
    }
    if args.write:
        dag_path = args.run_dir / "proof_dependency_dag.json"
        lemma_path = args.run_dir / "actual_lemma_queue.json"
        dump(dag_path, merge_by_id(records(dag_path), nodes, "node_id"))
        dump(lemma_path, merge_by_id(records(lemma_path), lemmas, "lemma_id"))
    if args.out:
        dump(args.out, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
