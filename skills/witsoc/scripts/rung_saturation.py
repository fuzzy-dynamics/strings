#!/usr/bin/env python3
"""Saturate open-problem rungs into an attackable Lovasz worklist.

The old `open_rungs` helper emits a small planning artifact. This module turns
that seed into a larger deterministic ladder: formalizable subcases, bounded
pressure tests, barrier-family reductions, theorem-precondition bridges, and
fallback obligations. It is still only planning. Every rung is born open and
untrusted; downstream kernel gates are the only route to proof status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import domain_barrier_lemmas as dbl  # noqa: E402
import open_rungs  # noqa: E402
import witcore  # noqa: E402

OPEN_STATUSES = {"OPEN", "OPEN_UNFALSIFIED", "CANDIDATE_RUNG", "BOUNDED_CHECK_PENDING"}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _score(kind: str, has_lean: bool, priority: int, relation: str) -> dict[str, float]:
    formal = 0.9 if has_lean else (0.42 if "formal" in relation.lower() else 0.25)
    attack = 0.82 if has_lean else (0.66 if "search" in kind or "bounded" in kind else 0.46)
    novelty = 0.72 if kind in {"reduction", "barrier", "bridge", "invariant"} else 0.5
    value = min(0.95, max(0.2, priority / 100.0))
    total = round(0.32 * formal + 0.28 * attack + 0.18 * novelty + 0.22 * value, 4)
    return {
        "formalization_score": round(formal, 3),
        "attackability_score": round(attack, 3),
        "novelty_potential": round(novelty, 3),
        "solve_value": round(value, 3),
        "score": total,
    }


def _rung(
    *,
    target_hash: str,
    idx: int,
    kind: str,
    statement: str,
    lean_statement: str | None = None,
    backend: str | None = None,
    relation: str = "partial progress toward the frozen target",
    priority: int = 70,
    source: str = "rung_saturation",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rid = f"R-{witcore.slug(kind)}-{idx:03d}"
    scores = _score(kind, bool(lean_statement), priority, relation)
    out: dict[str, Any] = {
        "rung_id": rid,
        "node_id": rid,
        "kind": kind,
        "type": "rung_obligation",
        "statement": statement,
        "lean_statement": lean_statement,
        "backend": backend or ("lean" if lean_statement else "research"),
        "verification_gate": "kernel_replay" if lean_statement else "bounded_or_manual_certificate_then_kernel",
        "dependency_path_to_target": [rid, "T"],
        "relation_to_target": relation,
        "status": "OPEN_UNFALSIFIED",
        "arena": "SPECULATIVE",
        "target_hash": target_hash,
        "priority": priority,
        "source": source,
        **scores,
    }
    if extra:
        out.update(extra)
    return out


def _domain_templates(target: str, domain: str, target_hash: str, start: int) -> list[dict[str, Any]]:
    templates: list[tuple[str, str, str, int, str]] = [
        ("definition_audit", "Formalize the exact hypotheses, conclusion, quantifier ranges, and exceptional cases of the frozen target.", "formalization", 76, "prevents target drift before deeper attacks"),
        ("minimal_counterexample", "Assume a smallest counterexample to the frozen target and derive its mandatory structural properties.", "research", 82, "turns the open problem into a finite list of enemy constraints"),
        ("precondition_bridge", "Choose the closest known theorem and prove or refute each missing precondition under the frozen hypotheses.", "retrieval+kernel", 84, "can unlock a known theorem without pretending it applies"),
        ("counterexample_pressure", "Search smallest boundary models satisfying the hypotheses and violating proposed strengthened variants.", "bounded_search", 74, "finds false strengthens before proof budget is wasted"),
        ("invariant_strengthening", "Invent an intermediate invariant Q such that Q implies the target and Q survives the natural reduction operation.", "research", 78, "creates a stronger inductive spine"),
        ("obstruction_conversion", "Convert the current hardest barrier into a named obstruction theorem if it cannot be crossed after repeated attacks.", "research", 75, "produces honest publishable progress below a full solve"),
    ]
    if domain == "number_theory":
        templates += [
            ("residue_ladder", "Split the target by moduli 2, 3, 4, 6, 8, 12, and isolate the first genuinely hard residue family.", "bounded_search", 83, "shrinks the open core by verified residue coverage"),
            ("valuation_descent", "State the p-adic valuation/descent lemma needed to eliminate a minimal counterexample.", "research", 80, "attacks the arithmetic obstruction directly"),
            ("parametric_witness", "Synthesize an explicit parametric witness family for every easy congruence class; record the remaining exceptional classes.", "formula_synthesis", 81, "positive families become reusable rungs"),
        ]
    elif domain in {"graph_theory", "combinatorics", "extremal"}:
        templates += [
            ("finite_graph_certificate", "Enumerate the smallest extremal graphs and extract recurring forbidden or forced substructures.", "finite_graph_search", 82, "turns examples into structural lemmas"),
            ("degree_reduction", "Prove a min/max-degree constraint on any minimal counterexample, or record the smallest graph refuting it.", "research", 80, "cuts the enemy search space"),
            ("deletion_contraction", "Find a deletion, contraction, or compression operation that preserves the hypotheses and lowers complexity.", "research", 79, "creates an inductive reduction if true"),
        ]
    elif domain == "additive_combinatorics":
        templates += [
            ("density_increment", "Prove the density-increment alternative or exhibit a pseudorandom configuration where it fails.", "research", 83, "classic route to full structural progress"),
            ("energy_increment", "Build the additive-energy increment step and quantify the iteration loss.", "research", 81, "forces structure or exposes the missing estimate"),
        ]
    return [
        _rung(target_hash=target_hash, idx=start + i, kind=kind, statement=f"{text} Target: {target}",
              backend=backend, relation=relation, priority=priority, source="domain_template")
        for i, (kind, text, backend, priority, relation) in enumerate(templates)
    ]


def saturate(
    target: str,
    domain: str = "other",
    *,
    lean_target: str | None = None,
    target_hash: str | None = None,
    top: int = 24,
) -> dict[str, Any]:
    th = target_hash or sha(target)
    rungs: list[dict[str, Any]] = []

    seed = open_rungs.build(target, domain)
    for i, src in enumerate(seed.get("rungs") or [], start=1):
        if not isinstance(src, dict):
            continue
        rungs.append(_rung(
            target_hash=th,
            idx=i,
            kind=str(src.get("type") or src.get("id") or "seed"),
            statement=str(src.get("statement") or ""),
            lean_statement=src.get("lean_statement"),
            backend=str(src.get("backend") or src.get("type") or "seed"),
            relation=str(src.get("relation_to_target") or "seed rung"),
            priority=86 if src.get("lean_statement") else 72,
            source="open_rungs",
            extra={"seed_id": src.get("id"), "proof_hint": src.get("proof_hint")},
        ))

    rungs.extend(_domain_templates(target, domain, th, len(rungs) + 1))

    barrier_lemmas = dbl.generate_barrier_lemmas(
        target, lean_target=lean_target, domain=domain, target_hash=th, max_lemmas=18
    )
    for i, lemma in enumerate(barrier_lemmas, start=len(rungs) + 1):
        relation = str(lemma.get("why_it_matters") or "barrier lemma toward target")
        rungs.append(_rung(
            target_hash=th,
            idx=i,
            kind="barrier",
            statement=str(lemma.get("statement") or ""),
            lean_statement=lemma.get("lean_statement"),
            backend="lean" if lemma.get("lean_statement") else "barrier_research",
            relation=relation,
            priority=int(lemma.get("priority") or 80),
            source="domain_barrier_lemmas",
            extra={
                "barrier_type": lemma.get("barrier_type"),
                "lemma_id": lemma.get("lemma_id"),
                "falsification_test": lemma.get("falsification_test"),
                "formalization_blocker": lemma.get("formalization_blocker"),
            },
        ))

    if lean_target:
        rungs.append(_rung(
            target_hash=th,
            idx=len(rungs) + 1,
            kind="formal_target_probe",
            statement="Probe the frozen Lean target directly with the tiered prover; failure diagnostics seed bridge lemmas.",
            lean_statement=lean_target,
            backend="tiered_prove",
            relation="direct probe for diagnostics, not a claimed proof unless kernel closes it",
            priority=88,
            source="formal_probe",
        ))

    dedup: dict[str, dict[str, Any]] = {}
    for rung in rungs:
        key = sha(str(rung.get("statement") or "") + "\n" + str(rung.get("lean_statement") or ""))
        prev = dedup.get(key)
        if prev is None or rung["score"] > prev["score"]:
            dedup[key] = rung
    selected = sorted(dedup.values(), key=lambda r: (-float(r["score"]), -int(r.get("priority") or 0), str(r["rung_id"])))[:top]
    for i, rung in enumerate(selected, start=1):
        rung["selection_rank"] = i
        assert rung["status"] in OPEN_STATUSES
    return {
        "schema": "witsoc.rung_saturation.v1",
        "target": target,
        "domain": domain,
        "target_hash": th,
        "status_policy": "all rungs are open obligations; only validators/provers can upgrade",
        "generated": len(rungs),
        "selected": len(selected),
        "rungs": selected,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", required=True)
    ap.add_argument("--domain", default="other")
    ap.add_argument("--lean-target", default=None)
    ap.add_argument("--target-hash", default=None)
    ap.add_argument("--top", type=int, default=24)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = saturate(args.target, args.domain, lean_target=args.lean_target,
                   target_hash=args.target_hash, top=args.top)
    if args.out:
        witcore.save_json(args.out, out)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
