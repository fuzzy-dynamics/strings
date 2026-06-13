#!/usr/bin/env python3
"""Generate deterministic counterexample-search packets for Lovasz workers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DOMAIN_TEMPLATES = {
    "graph": [
        {
            "engine": "finite_graph_backend.py",
            "purpose": "enumerate small finite graphs under structural constraints",
            "command_template": "python3 finite_graph_backend.py --n {n} --triangle-free --min-chromatic {min_chromatic} --limit {limit}",
            "certificate": "json graph edge list plus checked predicates",
        }
    ],
    "number-theory": [
        {
            "engine": "bounded_python",
            "purpose": "scan small integers, residue classes, divisibility obstructions, and extremal witnesses",
            "command_template": "python3 <bounded_search.py> --max-n {max_n} --target-hash {target_hash}",
            "certificate": "input bounds, witness tuple, exact arithmetic transcript",
        }
    ],
    "finite-model": [
        {
            "engine": "exhaustive_structures",
            "purpose": "enumerate finite structures satisfying hypotheses and falsify conclusion",
            "command_template": "python3 <finite_model_search.py> --size {n} --target-hash {target_hash}",
            "certificate": "finite carrier, operations/relations, hypothesis checks, failed conclusion",
        }
    ],
    "sat-smt": [
        {
            "engine": "smt_synthesizer.py",
            "purpose": "encode bounded countermodel search as SAT/SMT constraints",
            "command_template": "python3 smt_synthesizer.py --target {target_hash} --bound {n}",
            "certificate": "model assignment plus independent verifier script",
        }
    ],
    "additive-combinatorics": [
        {
            "engine": "bounded_python",
            "purpose": "search finite groups/intervals for sumset, energy, or density counterpatterns",
            "command_template": "python3 <additive_search.py> --group cyclic --order {n} --target-hash {target_hash}",
            "certificate": "set representation, invariant values, failed inequality",
        }
    ],
    "ramsey-extremal": [
        {
            "engine": "finite_graph_backend.py",
            "purpose": "search extremal colored/forbidden-subgraph witnesses at small orders",
            "command_template": "python3 finite_graph_backend.py --n {n} --max-graphs {max_graphs} --limit {limit}",
            "certificate": "graph/coloring witness plus forbidden-pattern checks",
        }
    ],
    "finite-algebra": [
        {
            "engine": "exhaustive_tables",
            "purpose": "enumerate small operation tables satisfying identities and falsify target identity",
            "command_template": "python3 <finite_algebra_search.py> --size {n} --target-hash {target_hash}",
            "certificate": "operation tables, identity checks, failed conclusion",
        }
    ],
    "analysis": [
        {
            "engine": "symbolic_numeric_boundary",
            "purpose": "stress-test limiting, compactness, continuity, measurability, and boundary assumptions",
            "command_template": "python3 <analysis_boundary_search.py> --samples {max_n} --target-hash {target_hash}",
            "certificate": "explicit function/sequence family, parameter bounds, evaluated hypotheses, failed conclusion",
        }
    ],
    "algebra": [
        {
            "engine": "finite_algebra_or_gap",
            "purpose": "search small groups/rings/modules or produce a missing-theorem-precondition certificate",
            "command_template": "python3 <algebra_structure_search.py> --size {n} --target-hash {target_hash}",
            "certificate": "operation tables or structure descriptors plus identity/property checks",
        }
    ],
    "topology": [
        {
            "engine": "finite_space_search",
            "purpose": "enumerate small finite topological spaces and specialization preorders for false variants",
            "command_template": "python3 <finite_topology_search.py> --points {n} --target-hash {target_hash}",
            "certificate": "open-set lattice, hypothesis checks, failed conclusion",
        }
    ],
    "probability": [
        {
            "engine": "finite_distribution_search",
            "purpose": "search finite probability spaces for independence, moment, tail, or coupling counterpatterns",
            "command_template": "python3 <probability_finite_search.py> --support {n} --target-hash {target_hash}",
            "certificate": "finite distribution table, exact rational probabilities, checked event/property transcript",
        }
    ],
}


def has_word(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


from witcore import records  # noqa: E402  -- shared substrate, was a local copy

def infer_domains(run: Path, explicit: list[str]) -> list[str]:
    if explicit:
        return explicit
    text_parts: list[str] = []
    for name in ("research.md", "barriers.md", "claims.md"):
        path = run / name
        if path.exists():
            text_parts.append(path.read_text(encoding="utf-8", errors="replace").lower())
    manifest = load(run / "lovasz_run.json", {})
    if manifest.get("source_target_text"):
        text_parts.append(str(manifest["source_target_text"]).lower())
    for node in records(run / "proof_dependency_dag.json"):
        text_parts.append(str(node.get("statement") or "").lower())
        text_parts.append(str(node.get("type") or "").lower())
    text = "\n".join(text_parts)
    domains: list[str] = []
    if has_word(text, ("graph", "tree", "chromatic", "ramsey", "clique", "triangle")):
        domains.append("graph")
    if has_word(text, ("integer", "prime", "divisor", "mod", "residue", "diophantine")):
        domains.append("number-theory")
    if has_word(text, ("sumset", "additive", "fourier", "density")):
        domains.append("additive-combinatorics")
    if has_word(text, ("continuous", "compact", "measure", "integral", "limit", "norm")):
        domains.append("analysis")
    if has_word(text, ("group", "ring", "field", "module", "ideal", "homomorphism")):
        domains.append("algebra")
    if has_word(text, ("topology", "open set", "closed set", "compactness", "connected", "hausdorff")):
        domains.append("topology")
    if has_word(text, ("probability", "random", "independent", "expectation", "variance", "martingale")):
        domains.append("probability")
    return domains or ["finite-model", "sat-smt"]


def target_hash(run: Path) -> str:
    handoff = load(run / "handoff_v1.json", {})
    for key in ("target_hash", "frozen_target_hash", "sha256"):
        if handoff.get(key):
            return str(handoff[key])
    for node in records(run / "proof_dependency_dag.json"):
        if node.get("target_hash"):
            return str(node["target_hash"])
    return "UNKNOWN_TARGET_HASH"


def packet_for(run: Path, domain: str, args: argparse.Namespace) -> dict:
    templates = DOMAIN_TEMPLATES[domain]
    lemmas = records(run / "actual_lemma_queue.json")
    focus = [str(x.get("statement") or x.get("lemma")) for x in lemmas[:3] if x.get("statement") or x.get("lemma")]
    params = {
        "n": args.bound,
        "max_n": args.max_n,
        "min_chromatic": args.min_chromatic,
        "max_graphs": args.max_graphs,
        "limit": args.limit,
        "target_hash": target_hash(run),
    }
    rendered = []
    for template in templates:
        item = dict(template)
        item["command"] = template["command_template"].format(**params)
        rendered.append(item)
    return {
        "domain": domain,
        "target_hash": params["target_hash"],
        "focus_lemmas": focus,
        "boundedness_warning": "A bounded search can refute by explicit witness, but absence of a witness is not proof.",
        "templates": rendered,
        "worker_acceptance_criteria": [
            "state exact finite bounds",
            "emit machine-readable witness or UNSAT/no-witness transcript",
            "include an independent verifier for any claimed counterexample",
            "record target drift checks against the frozen target hash",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--domain", action="append", choices=sorted(DOMAIN_TEMPLATES), default=[])
    parser.add_argument("--bound", type=int, default=6)
    parser.add_argument("--max-n", type=int, default=2000)
    parser.add_argument("--min-chromatic", type=int, default=4)
    parser.add_argument("--max-graphs", type=int, default=20000)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    unknown = [d for d in args.domain if d not in DOMAIN_TEMPLATES]
    if unknown:
        print(f"unknown domain(s): {unknown}", file=sys.stderr)
        return 2
    domains = infer_domains(args.run_dir, args.domain)
    result = {
        "schema": "witsoc.counterexample_search_templates.v1",
        "run_dir": str(args.run_dir),
        "packets": [packet_for(args.run_dir, domain, args) for domain in domains],
    }
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
