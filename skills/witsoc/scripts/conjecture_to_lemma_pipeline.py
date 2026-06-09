#!/usr/bin/env python3
"""Layer 2 closed loop: discovery -> formalize -> dispatch (the researcher loop).

This is the engine that turns Lovasz from an *orchestrator* into a *researcher*:
it closes the gap between the existing-but-disconnected discovery islands and the
kernel prover. Today `conjecture_miner.py` finds patterns and `interestingness.py`
ranks them, but their output (`perfect(n) -> even(n)` with only a non-dispatchable
*stub*) never becomes a real Lean goal the prover can attack. This module:

  1. MINE      empirical conjectures over an exact backend (conjecture_miner), or
               consume an existing conjectures.json.
  2. RANK      score by interestingness/novelty (interestingness), kill trivial.
  3. FORMALIZE expand each ranked `P(n) -> Q(n)` into a FAITHFUL, dispatchable Lean
               `lean_statement` via a meaning-preserving predicate dictionary. No
               faithful expansion -> `lean_statement: null` + a formalization_blocker
               (honest; never a fabricated goal). An optional autoformalizer behind
               the faithfulness gate handles the rest.
  4. EMIT      schema-conforming proof-DAG nodes + actual_lemma_queue entries that
               `lovasz_prover_dispatch.py` attacks with the kernel.
  5. ARENA     the SPECULATIVE consequence step: for a frozen formal target T and a
               top-ranked hypothesis H, emit the conditional node `H -> T`. A kernel
               proof of `H -> T` is an honest CONDITIONAL theorem ("T holds if H"),
               never an unconditional solve.
  6. DISPROVE  a miner-FALSIFIED conjecture carries a concrete witness; it is
               surfaced as a bounded disproof certificate (REFUTED + witness),
               re-checkable, never dressed up as progress.

THE CALIBRATION SPINE (never moves): generation is cheap and untrusted; the kernel
is the only judge. Every emitted lemma/node is born `status = OPEN_UNFALSIFIED`,
`arena = SPECULATIVE`. This module has NO authority to assign trust — `force_open()`
coerces status and `assert_no_upgrade()` raises if anything is above
OPEN_UNFALSIFIED. A statement leaves the arena ONLY through
`lovasz_prover_dispatch.py -> validate_prover_result`. So the odd-perfect conjecture
(`perfect(n) -> even(n)`) is formalized and dispatched, the kernel honestly fails to
close it, and it stays OPEN — capability up, calibration intact.

Usage:
  conjecture_to_lemma_pipeline.py --mine 2 10000 [--falsify 10000] [--min-support 3]
      [--domain number_theory] [--top 8] [--target-lean "<frozen Lean ∀ goal>"]
      [--target-hash H] [--library DIR] [--out pipeline.json]
      [--write RUN_DIR] [--dag-out f.json] [--queue-out f.json]
      [--dispatch [--search]] [--formalizer cmd:CMD --translator cmd:A --translator cmd:B]
  conjecture_to_lemma_pipeline.py --conjectures conjectures.json [...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import concept_generator as cg  # noqa: E402  -- OPEN/ARENA constants + calibration guards
import witcore  # noqa: E402

OPEN = cg.OPEN          # "OPEN_UNFALSIFIED"
ARENA = cg.ARENA        # "SPECULATIVE"
FORBIDDEN_LEAN = ("sorry", "admit", "axiom", "native_decide")

# --------------------------------------------------------------------------- #
# Faithful, meaning-preserving predicate -> Lean dictionary.
#
# Each entry is a function of the bound variable name that returns a Lean Prop
# over `{v} : Nat`. Faithfulness is the contract here, NOT provability: a faithful
# statement the kernel cannot close is an honest OPEN, which is exactly the
# calibration behavior we want. The sum-of-divisors predicates use Mathlib's
# `Nat.divisors`, so dispatchable nodes built from them require a Mathlib
# toolchain; without one the kernel reports OPEN (honest), never a fake solve.
# --------------------------------------------------------------------------- #
def _sigma(v: str) -> str:
    return f"(∑ d ∈ Nat.divisors {v}, d)"


PREDICATE_LEAN = {
    "prime": lambda v: f"Nat.Prime {v}",
    "square": lambda v: f"(∃ k : Nat, k * k = {v})",
    "even": lambda v: f"({v} % 2 = 0)",
    "odd": lambda v: f"({v} % 2 = 1)",
    "perfect": lambda v: f"({_sigma(v)} = 2 * {v})",
    "abundant": lambda v: f"({_sigma(v)} > 2 * {v})",
    "deficient": lambda v: f"({_sigma(v)} < 2 * {v})",
    "sigma_even": lambda v: f"({_sigma(v)} % 2 = 0)",
    "sigma_odd": lambda v: f"({_sigma(v)} % 2 = 1)",
    "prime_power": lambda v: f"(∃ p k : Nat, Nat.Prime p ∧ 1 ≤ k ∧ {v} = p ^ k)",
    "square_or_2square": lambda v: f"(∃ k : Nat, k * k = {v} ∨ 2 * (k * k) = {v})",
}
# Predicates whose faithful Lean uses Mathlib-only declarations.
_NEEDS_MATHLIB = {"prime", "perfect", "abundant", "deficient",
                  "sigma_even", "sigma_odd", "prime_power"}

_FORM_RE = re.compile(r"^\s*([a-z_0-9]+)\(n\)\s*->\s*([a-z_0-9]+)\(n\)\s*$")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def formalize_form(form: str, var: str = "n") -> tuple[str | None, str | None, bool]:
    """Expand a mined `P(n) -> Q(n)` into a faithful Lean statement.

    Returns (lean_or_None, blocker_or_None, needs_mathlib). A missing predicate is
    an honest blocker, not a guess."""
    m = _FORM_RE.match(form or "")
    if not m:
        return None, f"unrecognized conjecture form `{form}` (not a P(n)->Q(n) implication)", False
    p, q = m.group(1), m.group(2)
    if p not in PREDICATE_LEAN or q not in PREDICATE_LEAN:
        missing = [x for x in (p, q) if x not in PREDICATE_LEAN]
        return None, f"no faithful Lean expansion for predicate(s) {missing}; kept prose-only", False
    body = f"{PREDICATE_LEAN[p](var)} → {PREDICATE_LEAN[q](var)}"
    lean = f"∀ {var} : Nat, 2 ≤ {var} → {body}"
    needs_mathlib = bool({p, q} & _NEEDS_MATHLIB)
    if any(t in lean for t in FORBIDDEN_LEAN):  # defensive; dictionary is clean
        return None, "expansion produced a forbidden token", needs_mathlib
    return lean, None, needs_mathlib


def falsification_test(domain: str, lean_statement: str | None) -> dict:
    base = {"witness_refutes": True, "lean_statement": lean_statement,
            "interpretation": "an explicit witness refutes; no witness under the bound is bounded evidence only, never a proof"}
    if domain in ("number_theory", "additive_combinatorics"):
        return {"kind": "number_theory_search", "script": "counterexample_search.py", "bound": 100000, **base}
    if domain in ("graph_theory", "combinatorics", "extremal"):
        return {"kind": "finite_graph_search", "script": "counterexample_search.py", "max_vertices": 8, **base}
    return {"kind": "manual_or_formalization_required", **base}


def _autoformalize(form: str, blocker: str, formalizer: str | None,
                   translators: list[str] | None, threshold: float) -> tuple[str | None, str | None]:
    """Best-effort prose->Lean behind the faithfulness gate (>=2 back-translators).
    Conservative: never changes meaning, returns (lean, None) only when faithful."""
    if not formalizer:
        return None, blocker
    try:
        import faithfulness_gate as fg
    except Exception:
        return None, blocker
    reply = witcore.run_sampler(formalizer, {"task": "formalize_statement", "statement": form})
    lean = reply.get("lean_statement") if isinstance(reply, dict) else None
    if not lean or any(t in str(lean) for t in FORBIDDEN_LEAN):
        return None, "autoformalization produced no clean Lean statement"
    if not translators or len(translators) < 2:
        return None, "autoformalization not faithfulness-checked (need >=2 back-translators); kept prose-only"
    verdict = fg.gate(str(lean), form, translators, threshold)
    if verdict.get("status") == "FAITHFUL":
        return str(lean), None
    return None, f"autoformalization rejected by faithfulness gate ({verdict.get('status')})"


def lemma_from_conjecture(conj: dict, idx: int, domain: str, target_hash: str, score: float,
                          formalizer: str | None, translators: list[str] | None,
                          threshold: float) -> tuple[dict, dict]:
    """Build (dag_node, lemma_queue_entry) for one OPEN_UNFALSIFIED conjecture.
    Both are born OPEN_UNFALSIFIED / SPECULATIVE; only the kernel can promote."""
    form = conj.get("form", "")
    lean, blocker, needs_mathlib = formalize_form(form)
    if lean is None:
        lean, blocker = _autoformalize(form, blocker or "", formalizer, translators, threshold)
        needs_mathlib = needs_mathlib or (lean is not None)
    node_id = f"M{idx}"
    priority = 80 + int(round(min(score, 1.0) * 15))  # interestingness biases order only
    imports = "import Mathlib" if needs_mathlib else ""
    fals = falsification_test(domain, lean)
    node = {
        "node_id": node_id,
        "claim_id": f"claim:{node_id}",
        "statement": f"mined stepping-stone: {form}",
        "lean_statement": lean,
        "lean_imports": imports,
        "type": "mined_barrier_lemma",
        "dependencies": ["B"],
        "relation_to_target": "decomposes_target",
        "status": "OPEN",          # node-level structural OPEN (recognized by validators)
        "research_status": OPEN,   # OPEN_UNFALSIFIED, kept off node `status`
        "arena": ARENA,
        "domain": domain,
        "target_hash": target_hash,
        "dependency_path_to_target": [node_id, "B", "T"],
        "priority": priority,
        "interestingness": round(score, 4),
        "support": conj.get("support"),
        "support_examples": conj.get("support_examples", []),
        "falsification_test": fals,
        "provenance": "conjecture_miner+interestingness",
        "evidence": [],
        "next_exact_experiment_or_lemma": (
            "dispatch to kernel prover (witsoc lovasz-prover-dispatch)" if lean
            else "formalize into a Lean goal, then dispatch"),
    }
    if blocker:
        node["formalization_blocker"] = blocker
    if needs_mathlib:
        node["toolchain_note"] = "faithful Lean uses Mathlib (Nat.divisors/Nat.Prime); needs a Mathlib toolchain or stays OPEN honestly"

    lemma = {
        "lemma_id": f"mined:{domain}:{node_id}",
        "node_id": node_id,
        "statement": node["statement"],
        "lean_statement": lean,
        "lean_imports": imports,
        "domain": domain,
        "why_it_matters": "empirically-mined invariant; a candidate stepping-stone toward the barrier lemma B",
        "unlocks": ["B", "T"],
        "dependency_path_to_target": [node_id, "B", "T"],
        "falsification_test": fals,
        "known_counterexamples_or_boundary_cases": [
            {"status": "unprobed", "boundary_probe": fals.get("kind"),
             "note": "boundary/exceptional cases to be probed by the falsification_test; no fabricated witness"}],
        "failed_approaches": [{"method_family": "none_yet", "result": "unattempted",
                               "note": "fresh mined lemma; failed approaches recorded after kernel dispatch"}],
        "next_mutation": "kernel-dispatch the lean_statement; on failure record the failure class and mutate one axis",
        "smallest_formalizable_subcase": lean or node["statement"],
        "interestingness": round(score, 4),
        "support": conj.get("support"),
        "status": OPEN,
        "arena": ARENA,
        "target_hash": target_hash,
        "priority": priority,
    }
    if blocker:
        lemma["formalization_blocker"] = blocker
    return node, lemma


def conditional_node(target_lean: str, hyp: dict, idx: int, domain: str, target_hash: str) -> dict | None:
    """SPECULATIVE consequence step: build the conditional `H -> T`. A kernel proof
    of this is an honest CONDITIONAL theorem (T holds assuming H), never a solve."""
    h_lean = hyp.get("lean_statement")
    if not h_lean or not target_lean:
        return None
    cond = f"({h_lean}) → ({target_lean})"
    if any(t in cond for t in FORBIDDEN_LEAN):
        return None
    node_id = f"C{idx}"
    imports = hyp.get("lean_imports") or ("import Mathlib" if "Nat.divisors" in cond or "Nat.Prime" in cond else "")
    return {
        "node_id": node_id,
        "claim_id": f"claim:{node_id}",
        "statement": f"conditional: target holds assuming `{hyp.get('statement', h_lean)}`",
        "lean_statement": cond,
        "lean_imports": imports,
        "type": "conditional_theorem",
        "dependencies": [hyp["node_id"], "T"],
        "relation_to_target": "conditional",
        "conditional_on": hyp["node_id"],
        "status": "OPEN",
        "research_status": OPEN,
        "arena": ARENA,
        "domain": domain,
        "target_hash": target_hash,
        "dependency_path_to_target": [node_id, "T"],
        "priority": 70,
        "falsification_test": falsification_test(domain, cond),
        "provenance": "speculative_arena",
        "evidence": [],
        "next_exact_experiment_or_lemma": (
            "kernel-dispatch `H -> T`; a discharge is a CONDITIONAL theorem, not an unconditional solve"),
    }


def disproof_record(conj: dict, domain: str) -> dict | None:
    """A miner-FALSIFIED conjecture is a bounded disproof certificate: the named
    implication is FALSE at a concrete, re-checkable witness."""
    if conj.get("status") != "FALSIFIED" or not conj.get("falsified_at"):
        return None
    form = conj.get("form", "")
    lean, _, _ = formalize_form(form)
    return {
        "claim": form,
        "status": "REFUTED",
        "witness": conj["falsified_at"],
        "lean_statement_of_refuted_claim": lean,
        "evidence": [f"counterexample at n={conj['falsified_at']} (re-checkable by the exact backend)"],
        "kind": "bounded_disproof_certificate",
        "interpretation": "the implication is FALSE; this disproves the mined conjecture (not the frozen target unless they coincide)",
    }


# --------------------------------------------------------------------------- #
def rank_conjectures(conjectures: list[dict], library: Path | None, range_size: int) -> list[dict]:
    """Score OPEN_UNFALSIFIED conjectures via interestingness.py (deterministic).
    Falls back to support-ordering if the scorer is unavailable."""
    open_conj = [c for c in conjectures if c.get("status") == "OPEN_UNFALSIFIED"]
    if not open_conj:
        return []
    import tempfile, os
    with tempfile.TemporaryDirectory() as td:
        cj = Path(td) / "conjectures.json"
        out = Path(td) / "interestingness.json"
        witcore.save_json(cj, {"schema": "witsoc.conjectures.v1", "conjectures": open_conj})
        cmd = [sys.executable, str(SCRIPT_DIR / "interestingness.py"), "--conjectures", str(cj),
               "--range-size", str(range_size), "--out", str(out)]
        if library:
            cmd += ["--library", str(library)]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
            ranked = witcore.load_json(out, {}).get("ranked", [])
        except Exception:
            ranked = []
    score_by_form = {r["form"]: r.get("interestingness", 0.0) for r in ranked}
    survive = {r["form"] for r in ranked}  # interestingness kills trivial/known forms
    out_list = []
    for c in open_conj:
        f = c.get("form", "")
        if score_by_form and f not in survive:
            continue  # killed as trivial/known by interestingness
        c = dict(c)
        c["interestingness"] = score_by_form.get(f, round(c.get("support", 0) / max(1, range_size), 4))
        out_list.append(c)
    out_list.sort(key=lambda c: -c.get("interestingness", 0.0))
    return out_list


def pipeline(conjectures: list[dict], *, domain: str, target_hash: str, top: int,
             target_lean: str | None, library: Path | None, range_size: int,
             formalizer: str | None, translators: list[str] | None,
             threshold: float) -> dict:
    ranked = rank_conjectures(conjectures, library, range_size)[:top]
    nodes: list[dict] = []
    lemmas: list[dict] = []
    for i, conj in enumerate(ranked, start=1):
        node, lemma = lemma_from_conjecture(conj, i, domain, target_hash,
                                            conj.get("interestingness", 0.0),
                                            formalizer, translators, threshold)
        nodes.append(node)
        lemmas.append(lemma)

    conditional_nodes: list[dict] = []
    if target_lean:
        for i, (node, lemma) in enumerate(zip(nodes, lemmas), start=1):
            cn = conditional_node(target_lean, lemma, i, domain, target_hash)
            if cn:
                conditional_nodes.append(cn)

    disproofs = [d for d in (disproof_record(c, domain) for c in conjectures) if d]

    # CALIBRATION GUARD (structural): every lemma stays OPEN_UNFALSIFIED/SPECULATIVE.
    cg.assert_no_upgrade(lemmas)
    for n in nodes + conditional_nodes:
        assert n.get("research_status") == OPEN and n.get("arena") == ARENA, \
            "pipeline must never emit a node above OPEN_UNFALSIFIED"

    return {
        "schema": "witsoc.conjecture_to_lemma_pipeline.v1",
        "domain": domain,
        "target_hash": target_hash,
        "target_lean": target_lean,
        "nodes": nodes,
        "conditional_nodes": conditional_nodes,
        "actual_lemmas": lemmas,
        "disproofs": disproofs,
        "ranked_count": len(ranked),
        "dispatchable_count": sum(1 for n in nodes if n.get("lean_statement")),
        "calibration": ("generation is untrusted; every lemma is OPEN_UNFALSIFIED/SPECULATIVE. "
                        "Only lovasz-prover-dispatch -> validate_prover_result can promote. "
                        "Conditional nodes yield CONDITIONAL theorems, never unconditional solves."),
    }


def mine(domain: str, a: int, b: int, falsify: int, min_support: int) -> list[dict]:
    import conjecture_miner as cm
    if domain in ("number_theory", "additive_combinatorics"):
        return cm.mine_number_theory(a, b, falsify, min_support)
    raise SystemExit(f"--mine for domain {domain!r} not supported; pass --conjectures instead")


def reanchor(nodes: list[dict], existing_ids: set[str]) -> None:
    """Resolve each node's dependencies to anchor nodes that actually exist.

    In a real run `decompose_problem.py --write` runs first and creates the target
    node `T` and barrier node `B`, so mined nodes hang off `B`/`T` as intended.
    Standalone (no decompose), fall back to a valid root so the DAG stays
    integrity-clean: mined lemmas become roots; a conditional `H -> T` keeps only
    its hypothesis dependency."""
    for n in nodes:
        path_tail = [a for a in ("B", "T") if a in existing_ids]
        if n.get("type") == "conditional_theorem":
            deps = [d for d in n.get("dependencies", []) if d in existing_ids and d != n["node_id"]]
            tail = ["T"] if "T" in existing_ids else []
            n["dependencies"] = deps
            n["dependency_path_to_target"] = [n["node_id"], *tail]
        else:
            n["dependencies"] = path_tail[:1]  # nearest existing anchor (B preferred)
            n["dependency_path_to_target"] = [n["node_id"], *path_tail]


def merge_by_id(existing: list[dict], new: list[dict], key: str) -> list[dict]:
    merged = {str(x.get(key)): x for x in existing if isinstance(x, dict) and x.get(key)}
    for item in new:
        ident = str(item.get(key))
        if ident not in merged:
            merged[ident] = item
    return list(merged.values())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--mine", nargs=2, type=int, metavar=("A", "B"), help="mine conjectures over [A,B]")
    src.add_argument("--conjectures", type=Path, help="consume an existing conjectures.json")
    ap.add_argument("--falsify", type=int, default=10000)
    ap.add_argument("--min-support", type=int, default=3)
    ap.add_argument("--domain", default="number_theory")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--target-lean", default=None, help="frozen formal target; enables conditional (H->T) nodes")
    ap.add_argument("--target-hash", default=None)
    ap.add_argument("--library", type=Path, default=None)
    ap.add_argument("--range-size", type=int, default=10000, help="mined range size (for surprise scoring)")
    ap.add_argument("--formalizer", default=None, help="cmd:CMD autoformalizer for prose-only forms")
    ap.add_argument("--translator", action="append", default=[], help="cmd:CMD faithfulness back-translator (>=2)")
    ap.add_argument("--faithfulness-threshold", type=float, default=0.4)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--dag-out", type=Path, default=None)
    ap.add_argument("--queue-out", type=Path, default=None)
    ap.add_argument("--write", type=Path, default=None, help="merge nodes/lemmas into RUN_DIR's DAG + lemma queue")
    ap.add_argument("--dispatch", action="store_true", help="run lovasz_prover_dispatch on the run dir after --write")
    ap.add_argument("--search", action="store_true", help="compound proof search during --dispatch")
    args = ap.parse_args()

    if args.mine:
        conjectures = mine(args.domain, args.mine[0], args.mine[1], args.falsify, args.min_support)
        range_size = args.mine[1] - args.mine[0] + 1
    else:
        doc = witcore.load_json(args.conjectures, {})
        conjectures = doc.get("conjectures", []) if isinstance(doc, dict) else []
        range_size = args.range_size

    target_hash = args.target_hash or (sha(args.target_lean) if args.target_lean else "UNKNOWN_TARGET_HASH")
    result = pipeline(conjectures, domain=args.domain, target_hash=target_hash, top=args.top,
                      target_lean=args.target_lean, library=args.library, range_size=range_size,
                      formalizer=args.formalizer, translators=args.translator or None,
                      threshold=args.faithfulness_threshold)

    all_nodes = result["nodes"] + result["conditional_nodes"]
    if args.write:
        run = args.write
        dag_path = run / "proof_dependency_dag.json"
        lemma_path = run / "actual_lemma_queue.json"
        dis_path = run / "disproofs.json"
        run.mkdir(parents=True, exist_ok=True)
        existing_dag = witcore.load_json(dag_path, [])
        existing_dag = existing_dag if isinstance(existing_dag, list) else []
        reanchor(all_nodes, {str(n.get("node_id")) for n in existing_dag if isinstance(n, dict)})
        witcore.save_json(dag_path, merge_by_id(existing_dag, all_nodes, "node_id"))
        witcore.save_json(lemma_path, merge_by_id(
            witcore.load_json(lemma_path, []) if isinstance(witcore.load_json(lemma_path, []), list) else [],
            result["actual_lemmas"], "lemma_id"))
        if result["disproofs"]:
            witcore.save_json(dis_path, result["disproofs"])
    if args.dag_out:
        if not args.write:
            reanchor(all_nodes, set())  # standalone: roots, no fabricated anchors
        witcore.save_json(args.dag_out, all_nodes)
    if args.queue_out:
        witcore.save_json(args.queue_out, result["actual_lemmas"])
    if args.out:
        witcore.save_json(args.out, result)

    if args.dispatch:
        if not args.write:
            print("--dispatch requires --write RUN_DIR", file=sys.stderr)
            return 2
        cmd = [sys.executable, str(SCRIPT_DIR / "lovasz_prover_dispatch.py"), str(args.write)]
        if args.search:
            cmd.append("--search")
        subprocess.run(cmd, check=False)

    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("nodes", "conditional_nodes", "actual_lemmas")}
                     | {"top_dispatchable": [
                         {"node_id": n["node_id"], "lean_statement": n["lean_statement"],
                          "interestingness": n.get("interestingness")}
                         for n in result["nodes"] if n.get("lean_statement")][:5]},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
