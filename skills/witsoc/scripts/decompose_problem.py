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
import os
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import concept_generator as cg  # noqa: E402
import domain_barrier_lemmas as dbl  # noqa: E402


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


from witcore import records  # noqa: E402  -- shared substrate, was a local copy

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


def _concept_nodes(lean_target: str, domain: str, target_hash: str) -> tuple[list[dict], list[dict]]:
    """Dispatchable concept nodes (K1..Kn): stepping-stone candidates from the
    concept generator, each carrying a lean_statement the Prover dispatcher can
    attack plus a bounded falsification descriptor. Born SPECULATIVE/OPEN —
    decompose proposes, only the kernel gates promote."""
    sampler = os.environ.get("WITSOC_BARRIER_SAMPLER")
    cands = cg.deterministic_candidates(lean_target, domain) + cg.llm_candidates(lean_target, domain, 6, sampler)
    nodes: list[dict] = []
    lemmas: list[dict] = []
    i = 0
    for c in cands:
        lean = c.get("lean_statement")
        if not lean or any(t in lean for t in dbl.FORBIDDEN_LEAN):
            continue
        i += 1
        ident = f"K{i}"
        n = node(ident, c["form"], "concept", ["B"], target_hash, [ident, "B", "T"], 72 - i)
        n["lean_statement"] = lean
        n["arena"] = cg.ARENA
        n["research_status"] = cg.OPEN
        n["falsification_test"] = dbl.falsification_test(domain, lean)
        nodes.append(n)
        lemmas.append({
            "lemma_id": f"lemma:{ident}", "node_id": ident, "statement": c["form"],
            "lean_statement": lean, "why_it_matters": f"stepping stone toward the target ({c['kind']})",
            "unlocks": ["T"],
            "known_counterexamples_or_boundary_cases": [
                {"status": "unprobed", "boundary_probe": n["falsification_test"].get("kind"),
                 "note": "boundary cases to be probed by the falsification_test; no fabricated witness"}],
            "failed_approaches": [{"method_family": "none_yet", "result": "unattempted",
                                   "note": "fresh concept node; failures recorded after kernel dispatch"}],
            "next_mutation": "kernel-dispatch the lean_statement; on failure mutate one axis",
            "smallest_formalizable_subcase": lean, "status": "OPEN", "arena": cg.ARENA,
            "target_hash": target_hash, "priority": 72 - i,
        })
    return nodes, lemmas


def _barrier_nodes(statement: str, lean_target: str | None, domain: str,
                   target_hash: str) -> tuple[list[dict], list[dict]]:
    """Domain-specific barrier-lemma nodes via domain_barrier_lemmas (env-gated
    LLM sampler/formalizer; templates-only by default)."""
    translators = [t for t in (os.environ.get("WITSOC_FAITHFULNESS_TRANSLATORS") or "").split(",") if t]
    lemmas = dbl.generate_barrier_lemmas(
        statement, lean_target=lean_target, domain=domain, target_hash=target_hash,
        sampler=os.environ.get("WITSOC_BARRIER_SAMPLER"),
        formalizer=os.environ.get("WITSOC_BARRIER_FORMALIZER"),
        faithfulness_translators=translators or None)
    nodes: list[dict] = []
    for l in lemmas:
        n = node(l["node_id"], l["statement"], "mined_barrier_lemma", ["B"], target_hash,
                 l.get("dependency_path_to_target") or [l["node_id"], "T"], l.get("priority", 80))
        n["barrier_type"] = l["barrier_type"]
        n["lean_statement"] = l.get("lean_statement")
        n["arena"] = l.get("arena", "SPECULATIVE")
        n["research_status"] = l.get("status", "OPEN_UNFALSIFIED")
        n["status"] = "OPEN"  # node-level status stays in the core vocabulary
        n["falsification_test"] = l.get("falsification_test")
        nodes.append(n)
    return nodes, lemmas


def decompose(statement: str, target_hash: str, lean_target: str | None = None,
              domain: str | None = None) -> tuple[list[dict], list[dict]]:
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

    # Dispatchable layers (restored wiring): concept stepping-stones when the
    # target is formal, domain barrier lemmas when a domain is declared. Both
    # arrive SPECULATIVE/OPEN with falsification descriptors — never trusted.
    extra_lemmas: list[dict] = []
    if lean_target:
        knodes, klemmas = _concept_nodes(lean_target, domain or "other", target_hash)
        nodes.extend(knodes)
        extra_lemmas.extend(klemmas)
    if domain:
        bnodes, blemmas = _barrier_nodes(statement, lean_target, domain, target_hash)
        nodes.extend(bnodes)
        extra_lemmas.extend(blemmas)

    skip_projection = {n["node_id"] for n in nodes if n.get("barrier_type") or n["node_id"].startswith("K")}
    for n in nodes:
        if n["node_id"] == "T" or n["node_id"] in skip_projection:
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
    lemmas.extend(extra_lemmas)
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
    parser.add_argument("--lean-target", default=None,
                        help="formal Lean goal; enables dispatchable concept nodes (K1..Kn)")
    parser.add_argument("--domain", default=None,
                        help="problem domain; enables domain-specific barrier-lemma nodes")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--write", action="store_true", help="Update proof_dependency_dag.json and actual_lemma_queue.json.")
    args = parser.parse_args()

    target, target_hash = infer_target(args.run_dir, args.target)
    nodes, lemmas = decompose(target, target_hash, lean_target=args.lean_target, domain=args.domain)
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
