#!/usr/bin/env python3
"""Domain-specific barrier-lemma generation (open-problem campaigns).

Generic decomposition (base/step/even/odd/strengthen/bound) is not enough to make
progress on a real open problem. This proposes DOMAIN-SPECIFIC barrier lemmas —
residue splits, valuation/descent, local obstructions, minimal-counterexample,
degree bounds, density/energy increments, encoding-preservation, etc. — each as a
dispatchable speculative node with a falsification test and a dependency path.

HARD RULE: every lemma is born `status = OPEN_UNFALSIFIED`, `arena = SPECULATIVE`.
This module has NO authority to assign trust — it can never emit CHECKED/VERIFIED/
PROVED. A lemma leaves the speculative arena ONLY by being proved through the
kernel gate (witsoc lovasz-prover-dispatch -> validate_prover_result). Lean
statements are generated only by MEANING-PRESERVING transforms of a formal target;
otherwise `lean_statement: null` + a `formalization_blocker`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import concept_generator as cg  # noqa: E402  -- parse_forall + OPEN/ARENA constants
import faithfulness_gate as fg  # noqa: E402  -- gate autoformalized Lean against the prose
import witcore  # noqa: E402

OPEN = "OPEN_UNFALSIFIED"
ARENA = "SPECULATIVE"
FORBIDDEN_LEAN = ("sorry", "admit", "axiom", "native_decide")


def slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_+-]+", "-", text.strip()).strip("-").lower()
    return s or "node"


def falsification_test(domain: str, lean_statement: str | None = None) -> dict:
    """A bounded, dispatchable refutation descriptor. A witness REFUTES; no witness
    under the bound is bounded evidence only, never a proof."""
    base = {"witness_refutes": True, "lean_statement": lean_statement,
            "interpretation": "an explicit witness refutes; no witness under the bound is bounded evidence only, never a proof"}
    if domain == "number_theory":
        return {"kind": "number_theory_search", "script": "counterexample_search.py", "bound": 10000, **base}
    if domain in ("graph_theory", "combinatorics", "extremal"):
        return {"kind": "finite_graph_search", "script": "counterexample_search.py", "max_vertices": 8, **base}
    if domain == "additive_combinatorics":
        return {"kind": "number_theory_search", "script": "counterexample_search.py", "bound": 10000, **base}
    if domain == "logic":
        return {"kind": "finite_model_or_smt", "script": "counterexample_search.py", "bound": 64, **base}
    return {"kind": "manual_or_formalization_required", **base}


def _bt(barrier_type: str, statement: str, *, lean: str | None = None, why: str | None = None,
        unlocks: list[str] | None = None, expected: list[str] | None = None,
        preconditions: list[str] | None = None, priority: int = 80,
        formalization_blocker: str | None = None, domain: str | None = None,
        falsification: dict | None = None) -> dict:
    return {"barrier_type": barrier_type, "statement": statement, "lean_statement": lean,
            "why": why or f"{barrier_type.replace('_', ' ')} toward the frozen target",
            "unlocks": unlocks or ["T"], "expected": expected or [], "preconditions": preconditions or [],
            "priority": priority, "formalization_blocker": formalization_blocker,
            "domain": domain, "falsification": falsification}


# --------------------------------------------------------------------------- #
# Domain families
# --------------------------------------------------------------------------- #
def nt_family(_: str) -> list[dict]:
    return [
        _bt("residue_class_split", "Residue-class split: prove the target separately on each residue class n ≡ r (mod m) for a small modulus m, then recombine.", expected=["a residue class with no solution refutes the split"]),
        _bt("valuation_descent", "Valuation/descent lemma: bound the p-adic valuation of the controlling quantity and run an infinite-descent / minimal-counterexample argument."),
        _bt("local_obstruction", "Local obstruction lemma: exhibit a prime/modulus at which the equation has no local solution.", expected=["a modulus with no local solution refutes the universal claim"]),
        _bt("finite_range_certificate", "Finite-range certificate: verify the target for all parameters up to an explicit bound K by exhaustive checked computation.", priority=82),
        _bt("parametrized_witness_family", "Parametrized witness family: construct an explicit witness family (e.g. x(n),y(n),z(n)) valid for all n outside finitely many residues; reduce to the exceptional residues.", formalization_blocker="requires an explicit witness construction; not safely auto-formalizable"),
        _bt("local_to_global_bridge", "Local-to-global bridge: separate congruence/local constraints from the global statement and audit the missing lifting hypotheses.", priority=78),
    ]


def graph_family(_: str) -> list[dict]:
    return [
        _bt("minimal_counterexample", "Minimal-counterexample lemma: assume a minimum-order counterexample and derive structure (min degree, 2-connectivity) it must satisfy.", priority=84),
        _bt("degree_bound", "Degree-bound lemma: bound the minimum/maximum degree of any extremal or counterexample graph under the frozen hypotheses.", expected=["a graph violating the degree bound refutes it"]),
        _bt("forbidden_substructure", "Forbidden-substructure lemma: show the hypotheses force absence/presence of a fixed small subgraph, then use it.", expected=["a graph containing the forbidden structure"]),
        _bt("extremal_configuration", "Extremal-configuration lemma: identify the unique extremal configuration and prove every other case is strictly dominated.", priority=83),
        _bt("deletion_contraction_reduction", "Deletion/contraction reduction: reduce the target to strictly smaller graphs via vertex/edge deletion or contraction preserving the invariant."),
        _bt("finite_model_certificate", "Finite-model certificate: enumerate all graphs up to a small order and record extremal witnesses or a no-witness bound.", priority=82),
    ]


def additive_family(_: str) -> list[dict]:
    return [
        _bt("density_increment", "Density-increment lemma: if the set lacks the structure, find a sub-progression on which its relative density strictly increases.", priority=84),
        _bt("energy_increment", "Energy-increment lemma: bound additive energy and iterate an increment until structure is forced.", priority=83),
        _bt("structured_random_decomposition", "Structured/random decomposition: split the indicator into structured + pseudorandom parts and control each."),
        _bt("small_doubling", "Small-doubling lemma: if |A+A| is small, derive approximate-group / progression structure (Freiman-type).", expected=["a set with small doubling and no progression structure"]),
        _bt("bohr_set_containment", "Bohr-set / progression containment: locate a long arithmetic progression or Bohr set inside the large spectrum.", formalization_blocker="Bohr-set machinery not represented formally; prose/speculative node"),
    ]


def logic_family(_: str) -> list[dict]:
    return [
        _bt("encoding_preservation", "Encoding-preservation lemma: normalize the formula/encoding and prove the transformation preserves the frozen target's truth value."),
        _bt("bounded_model_search", "Bounded-model-search lemma: decide the statement on all models up to a bound K (a counter-model refutes).", priority=82, expected=["a small counter-model"]),
        _bt("resolution_refutation_certificate", "Resolution/refutation certificate: produce a bounded resolution proof or an explicit satisfying assignment.", priority=82),
        _bt("compactness_reduction", "Compactness/reduction lemma: reduce an infinite statement to a family of finite instances via compactness, auditing the side conditions."),
    ]


def general_family(_: str) -> list[dict]:
    return [
        _bt("definition_audit", "Definition audit: formalize every object, quantifier, parameter range, and exceptional case in the target.", priority=76, falsification=falsification_test("other")),
        _bt("theorem_precondition_bridge", "Theorem-precondition bridge: identify the closest known theorem and prove/refute each missing precondition.", priority=77, falsification=falsification_test("other")),
        _bt("counterexample_pressure", "Counterexample pressure: search smallest finite/boundary models satisfying the hypotheses and falsifying the conclusion.", priority=75),
        _bt("formalizable_core", "Formalizable core: state the smallest WIT/Lean-ready subcase that still exercises the main barrier.", priority=74),
        _bt("strengthened_invariant", "Strengthened invariant: propose an intermediate invariant Q with Q -> target, strong enough to be inductive.", priority=73, formalization_blocker="invariant must be discovered/formalized before dispatch"),
    ]


def nat_formal_family(lean_target: str) -> list[dict]:
    """Meaning-preserving formal decompositions of a `∀ v : Nat, body` target."""
    f = cg.parse_forall(lean_target)
    if not f or f["type"] not in ("Nat", "ℕ"):
        return []
    v, body = f["var"], f["body"]
    sub = lambda x: re.sub(rf"\b{re.escape(v)}\b", x, body)
    return [
        _bt("base_case", f"Base case: the target at {v}=0.", lean=sub("0"), priority=79, domain="formal_nat"),
        _bt("inductive_step", f"Inductive step: assume the target at {v}, prove it at {v}+1.",
            lean=f"∀ {v} : Nat, ({body}) → ({sub(f'({v}+1)')})", priority=79, domain="formal_nat"),
        _bt("even_case", f"Even case: the target restricted to even {v}.",
            lean=f"∀ {v} : Nat, (∃ k : Nat, {v} = 2*k) → ({body})", priority=78, domain="formal_nat"),
        _bt("odd_case", f"Odd case: the target restricted to odd {v}.",
            lean=f"∀ {v} : Nat, (∃ k : Nat, {v} = 2*k+1) → ({body})", priority=78, domain="formal_nat"),
        _bt("bounded_finite_case", f"Bounded finite case: the target for {v} ≤ 16.",
            lean=f"∀ {v} : Nat, {v} ≤ 16 → ({body})", priority=77, domain="formal_nat"),
    ]


def precondition_bridges(theorem_audit: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for entry in theorem_audit or []:
        thm = str(entry.get("theorem") or entry.get("name") or "the candidate theorem")
        for pre in entry.get("missing_preconditions", []) or []:
            out.append(_bt(
                "precondition_bridge",
                f"Precondition bridge for {thm}: prove `{pre}` under the frozen hypotheses, or record a counterexample.",
                why=f"unlocks the application of {thm}", unlocks=["T"], preconditions=[str(pre)],
                priority=90, expected=[f"a model satisfying the hypotheses but not `{pre}`"]))
    return out


# --------------------------------------------------------------------------- #
def _mutate_after_failure(part: dict) -> dict | None:
    """A barrier whose method family already failed for this target may only be
    re-proposed if something changed (stronger bound / different encoding)."""
    fals = part.get("falsification") or {}
    if "bound" in fals:
        new = dict(part)
        nf = dict(fals)
        nf["bound"] = int(nf["bound"]) * 2
        new["falsification"] = nf
        new["statement"] = part["statement"] + " [retry: doubled bound after prior failure]"
        new["mutated_from_failure"] = "stronger_bound"
        return new
    if "max_vertices" in fals:
        new = dict(part)
        nf = dict(fals)
        nf["max_vertices"] = int(nf["max_vertices"]) + 2
        new["falsification"] = nf
        new["statement"] = part["statement"] + " [retry: larger search after prior failure]"
        new["mutated_from_failure"] = "stronger_bound"
        return new
    return None  # no admissible mutation -> skip (do not repeat an identical failed barrier)


FAMILIES = {
    "number_theory": nt_family, "graph_theory": graph_family, "combinatorics": graph_family,
    "extremal": graph_family, "additive_combinatorics": additive_family, "logic": logic_family,
}


def _method_order(domain: str) -> list[str]:
    return [p["barrier_type"] for p in FAMILIES.get(domain, lambda _t: [])("")]


def llm_proposed_parts(target: str, lean_target: str | None, domain: str, sampler: str | None) -> list[dict]:
    """Fix 1 (invention): ask a model to propose PROBLEM-SPECIFIC barrier lemmas.
    Each is untrusted speculation — it is forced OPEN_UNFALSIFIED downstream and can
    only be promoted by the kernel. Graceful no-op without a sampler."""
    if not sampler:
        return []
    reply = witcore.run_sampler(sampler, {"task": "propose_barrier_lemmas", "target": target,
                                          "lean_target": lean_target, "domain": domain})
    if not isinstance(reply, dict):
        return []
    out: list[dict] = []
    for c in reply.get("lemmas", []) or []:
        if not isinstance(c, dict) or not c.get("statement"):
            continue
        lean = c.get("lean_statement")
        if lean and any(t in str(lean) for t in FORBIDDEN_LEAN):
            lean = None  # never accept a model-proposed proof token as a statement
        out.append(_bt(str(c.get("barrier_type") or "llm_proposed_barrier"), str(c["statement"]),
                       lean=lean, why=str(c.get("why") or "model-proposed problem-specific barrier"),
                       expected=list(c.get("expected") or []), priority=int(c.get("priority", 81)),
                       domain=domain))
        out[-1]["source"] = "llm"
    return out


def autoformalize(statement: str, formalizer: str | None, translators: list[str] | None,
                  threshold: float) -> tuple[str | None, str | None]:
    """Fix 2: try to turn a prose barrier into a Lean statement, but ONLY accept it
    if it back-translates faithfully to the prose (>=2 independent translators).
    Returns (lean_or_None, blocker_or_None). Never changes meaning; conservative."""
    if not formalizer:
        return None, "no autoformalizer configured; prose lemma not yet dispatchable"
    reply = witcore.run_sampler(formalizer, {"task": "formalize_statement", "statement": statement})
    lean = reply.get("lean_statement") if isinstance(reply, dict) else None
    if not lean or any(t in str(lean) for t in FORBIDDEN_LEAN):
        return None, "autoformalization produced no clean Lean statement"
    if not translators or len(translators) < 2:
        return None, "autoformalization not faithfulness-checked (need >=2 back-translators); kept prose-only"
    verdict = fg.gate(str(lean), statement, translators, threshold)
    if verdict.get("status") == "FAITHFUL":
        return str(lean), None
    return None, f"autoformalization rejected by faithfulness gate ({verdict.get('status')})"


def generate_barrier_lemmas(
    target: str,
    *,
    lean_target: str | None = None,
    domain: str = "other",
    target_hash: str,
    failure_memory: list[dict] | None = None,
    theorem_audit: list[dict] | None = None,
    max_lemmas: int = 12,
    sampler: str | None = None,
    formalizer: str | None = None,
    faithfulness_translators: list[str] | None = None,
    faithfulness_threshold: float = 0.4,
) -> list[dict]:
    families = FAMILIES
    parts: list[dict] = []
    parts += precondition_bridges(theorem_audit)          # highest priority
    parts += llm_proposed_parts(target, lean_target, domain, sampler)  # Fix 1: invention
    parts += families.get(domain, lambda _t: [])(target)  # domain-specific templates
    if lean_target:
        parts += nat_formal_family(lean_target)           # dispatchable formal family
    parts += general_family(target)                       # always-present fallback

    failed = {(str(f.get("target_hash")), str(f.get("barrier_type") or f.get("method_family")))
              for f in (failure_memory or [])}

    out: list[dict] = []
    seen_types: set[str] = set()
    for i, p in enumerate(parts, start=1):
        bt_type = p["barrier_type"]
        dom = p.get("domain") or domain
        lean = p.get("lean_statement")
        # safety: never emit a Lean statement carrying a proof/forbidden token
        if lean and any(t in lean for t in FORBIDDEN_LEAN):
            lean, p["formalization_blocker"] = None, "rejected: candidate Lean contained a forbidden token"
        # Fix 2: try to autoformalize a prose lemma, gated by faithfulness.
        if lean is None and formalizer:
            af_lean, af_blocker = autoformalize(p["statement"], formalizer, faithfulness_translators, faithfulness_threshold)
            if af_lean:
                lean = af_lean
                p["formalized_by"] = "autoformalizer+faithfulness_gated"
                p.pop("formalization_blocker", None)
            elif af_blocker:
                p["formalization_blocker"] = af_blocker
        p["lean_statement"] = lean
        # assign the falsification descriptor up front so failure-memory mutation
        # (which may double a bound) can see it.
        p["falsification"] = p.get("falsification") or falsification_test(
            dom if dom != "formal_nat" else (domain or "other"), lean)
        # failure-memory awareness: skip an identical failed barrier unless mutated
        if (target_hash, bt_type) in failed:
            mutated = _mutate_after_failure(p)
            if mutated is None:
                continue
            p = mutated
            lean = p.get("lean_statement")
        node_id = f"B-{slug(bt_type)}-{i}"
        fals = p["falsification"]
        lemma = {
            "lemma_id": f"barrier:{dom}:{bt_type}:{i}",
            "node_id": node_id,
            "statement": p["statement"],
            "lean_statement": lean,
            "domain": dom,
            "barrier_type": bt_type,
            "why_it_matters": p["why"],
            "unlocks": p.get("unlocks", ["T"]),
            "dependency_path_to_target": [node_id, "T"],
            "falsification_test": fals,
            "expected_counterexamples_or_obstructions": p.get("expected", []),
            "theorem_preconditions_to_audit": p.get("preconditions", []),
            # standard actual_lemma_queue fields (validate_open_problem_run.py).
            # Honest non-empty defaults: boundary cases point at the (unrun)
            # falsification search; no method has failed yet on a fresh lemma.
            "known_counterexamples_or_boundary_cases": p.get("expected") or [
                {"status": "unprobed", "boundary_probe": fals.get("kind"),
                 "note": "boundary/exceptional cases to be probed by the falsification_test; no fabricated witness"}],
            "failed_approaches": [
                {"method_family": "none_yet", "result": "unattempted",
                 "note": "fresh barrier lemma; failed approaches are recorded after kernel dispatch"}],
            "next_mutation": "kernel-dispatch the lean_statement (or run the falsification search); on failure record the failure class and mutate one axis: bound / encoding / premise / domain-split / formalization route",
            "smallest_formalizable_subcase": lean or p["statement"],
            "status": OPEN,
            "arena": ARENA,
            "target_hash": target_hash,
            "priority": p.get("priority", 80),
        }
        if p.get("formalization_blocker"):
            lemma["formalization_blocker"] = p["formalization_blocker"]
        if p.get("mutated_from_failure"):
            lemma["mutated_from_failure"] = p["mutated_from_failure"]
        if p.get("source") == "llm":
            lemma["source"] = "llm"
        if p.get("formalized_by"):
            lemma["formalized_by"] = p["formalized_by"]
        out.append(lemma)
        seen_types.add(bt_type)

    # Fix 3: on a failed method family, promote a genuinely DIFFERENT sibling family
    # (a real method switch), not merely a bound bump. Fires for every failed family,
    # whether the same family was skipped or bound-retried above.
    failed_types = {bt for (th, bt) in failed if th == target_hash}
    order = _method_order(domain)
    by_type = {l["barrier_type"]: l for l in out}
    for ft in failed_types:
        if ft not in order:
            continue
        idx = order.index(ft)
        for step in range(1, len(order)):
            sib = order[(idx + step) % len(order)]
            if sib != ft and sib not in failed_types and sib in by_type and not by_type[sib].get("mutated_from_failure"):
                by_type[sib]["mutated_from_failure"] = f"method_switch_from:{ft}"
                by_type[sib]["priority"] = by_type[sib].get("priority", 80) + 6
                break

    out.sort(key=lambda l: -l["priority"])
    out = out[:max_lemmas]

    # HARD INVARIANT (structural): nothing leaves this module above OPEN_UNFALSIFIED.
    for l in out:
        assert l["status"] == OPEN and l["arena"] == ARENA, "barrier generator must never assign trust"
        if l["lean_statement"]:
            assert not any(t in l["lean_statement"] for t in FORBIDDEN_LEAN), "no sorry/axiom/admit in generated Lean"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True)
    ap.add_argument("--lean-target", default=None)
    ap.add_argument("--domain", default="other")
    ap.add_argument("--target-hash", default=None)
    ap.add_argument("--max-lemmas", type=int, default=12)
    ap.add_argument("--sampler", default=None, help="cmd:CMD model proposing problem-specific barrier lemmas")
    ap.add_argument("--formalizer", default=None, help="cmd:CMD model autoformalizing prose lemmas")
    ap.add_argument("--translator", action="append", default=[], help="cmd:CMD faithfulness back-translator (repeatable, need >=2)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    import hashlib
    th = args.target_hash or hashlib.sha256(args.target.encode()).hexdigest()
    lemmas = generate_barrier_lemmas(args.target, lean_target=args.lean_target, domain=args.domain,
                                     target_hash=th, max_lemmas=args.max_lemmas, sampler=args.sampler,
                                     formalizer=args.formalizer, faithfulness_translators=args.translator)
    out = {"schema": "witsoc.domain_barrier_lemmas.v1", "target": args.target, "domain": args.domain,
           "target_hash": th, "count": len(lemmas), "lemmas": lemmas}
    if args.out:
        witcore.save_json(args.out, out)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
