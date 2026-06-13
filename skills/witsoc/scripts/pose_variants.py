#!/usr/bin/env python3
"""Problem-posing engine — generate the neighbors of a frozen target.

Mathematicians pose their own questions around a hard target: a strictly
stronger variant (try to BREAK it — its counterexample is an obstruction), a
strictly weaker variant (try to PROVE it — a rung whose harvested proof
compounds), the boundary instances (stress the statement where it almost
fails), and the bounded/finite version (settle something checkable first).
This scripts the strength-control discipline of `conjecture_mining.md` over a
Lean target and feeds the weaker variants to `curriculum_portfolio` so self-
generated easy questions harvest lemmas that compound toward the real target.

CALIBRATION: variants are questions, not claims — all OPEN_UNFALSIFIED /
SPECULATIVE (structurally asserted). Proving any rung goes through the kernel
gate like everything else; posing can never manufacture progress.

Usage:
  pose_variants.py --target-lean "<Lean ∀ ...>" [--bound 32] [--preamble P]
      [--domain D] [--out variants.json] [--portfolio-out portfolio.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
import goal_structure as gs  # noqa: E402

OPEN = "OPEN_UNFALSIFIED"
ARENA = "SPECULATIVE"

_FORALL_NAT = re.compile(r"^\s*∀\s*([A-Za-z_][A-Za-z0-9_']*)\s*:\s*(Nat|ℕ)\s*,\s*(.+)$", re.S)


def _variant(kind: str, role: str, lean: str, why: str, route: str) -> dict:
    return {"kind": kind, "role": role, "lean_statement": lean, "why": why,
            "falsification_route": route, "status": OPEN, "arena": ARENA}


def assert_no_upgrade(variants: list[dict]) -> None:
    for v in variants:
        if v.get("status") != OPEN or v.get("arena") != ARENA:
            raise AssertionError("calibration violation: posed variant carries trust")


def generate(target_lean: str, *, bound: int = 32) -> dict:
    target = target_lean.strip()
    stronger: list[dict] = []
    weaker: list[dict] = []
    boundary: list[dict] = []

    # STRONGER: hypothesis-pruned variants (drop hypotheses = strengthen).
    for v in gs.pruned_variants(target, max_variants=3):
        stronger.append(_variant(
            "hypothesis_pruned", "try_to_break", v["statement"],
            f"dropping {len(v['dropped'])} hypothesis(es) strengthens the claim; a counterexample "
            "shows exactly which hypothesis is load-bearing (an obstruction result)",
            "lemma_repair.py / counterexample_search.py"))

    # STRONGER: anti-unify a literal into a parameter (the uniform statement).
    m = _FORALL_NAT.match(target)
    literals = sorted({x for x in re.findall(r"\b\d+\b", target)},
                      key=lambda c: -target.count(c))[:2]
    for lit in literals:
        var = next((v for v in ("m", "k", "j") if not re.search(rf"\b{v}\b", target)), "m_pose")
        gen = f"∀ {var} : Nat, " + re.sub(rf"\b{re.escape(lit)}\b", var, target)
        if gen != target:
            stronger.append(_variant(
                "literal_generalized", "try_to_break", gen,
                f"replacing the literal {lit} by a parameter is the inductive-loading form; "
                "if false, the failing parameter values locate the true boundary",
                "lemma_repair.py (bounded falsification) / close_obligation.py"))

    # WEAKER: conjunct isolation.
    for c in gs.conjunction_split(target):
        weaker.append(_variant(
            "conjunct", "try_to_prove", c,
            "one conjunct is a standalone rung; its harvested proof recombines",
            "lovasz_prover_dispatch.py"))

    # WEAKER (∀-Nat targets): bounded and parity-restricted versions.
    if m:
        var, body = m.group(1), m.group(3).strip()
        weaker.append(_variant(
            "bounded", "try_to_prove", f"∀ {var} : Nat, {var} ≤ {bound} → ({body})",
            "the finite version is decidable pressure: a refutation here kills the target, "
            "a proof is a checked special case",
            "close_obligation.py (decide) / counterexample_search.py"))
        weaker.append(_variant(
            "even_case", "try_to_prove",
            f"∀ {var} : Nat, {var} % 2 = 0 → ({body})",
            "a parity special case often has extra structure; its proof is a rung",
            "close_obligation.py"))
        weaker.append(_variant(
            "odd_case", "try_to_prove",
            f"∀ {var} : Nat, {var} % 2 = 1 → ({body})",
            "the complementary parity case; even+odd recombine to the full target",
            "close_obligation.py"))
        # BOUNDARY: smallest instances as stress checks.
        for k in (0, 1):
            boundary.append(_variant(
                f"instance_{k}", "stress", re.sub(rf"\b{re.escape(var)}\b", str(k), body),
                f"the {var}={k} boundary instance — where off-by-one hypotheses die",
                "close_obligation.py (decide)"))

    all_variants = stronger + weaker + boundary
    assert_no_upgrade(all_variants)
    return {
        "schema": "witsoc.pose_variants.v1",
        "target": target,
        "stronger": stronger,
        "weaker": weaker,
        "boundary": boundary,
        "note": "dual reformulations are ontology_pivot.py's job; run it separately",
        "calibration": f"all variants are {OPEN}/{ARENA} questions; proving a rung goes through "
                       "the kernel gate. Posing cannot manufacture progress.",
    }


def to_portfolio(variants_doc: dict, preamble: str = "", domain: str = "other") -> list[dict]:
    """Weaker variants become curriculum rungs (easy→hard), target last."""
    import curriculum_portfolio as cp
    sublemmas = [v["lean_statement"] for v in variants_doc.get("weaker", [])]
    return cp.build_portfolio(variants_doc["target"], sublemmas or None, preamble, domain)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target-lean", required=True)
    ap.add_argument("--bound", type=int, default=32)
    ap.add_argument("--preamble", default="")
    ap.add_argument("--domain", default="other")
    ap.add_argument("--out", type=Path, default=Path("variants.json"))
    ap.add_argument("--portfolio-out", type=Path, default=None,
                    help="also emit a curriculum portfolio (weaker rungs first, target last)")
    args = ap.parse_args()

    doc = generate(args.target_lean, bound=args.bound)
    witcore.save_json(args.out, doc)
    if args.portfolio_out:
        portfolio = to_portfolio(doc, args.preamble, args.domain)
        witcore.save_json(args.portfolio_out, {
            "schema": "witsoc.curriculum_portfolio.v1", "target": args.target_lean,
            "portfolio": portfolio,
            "note": "self-posed rungs: prove easy variants, harvest, the target compounds"})
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in doc.items()
                      if k != "calibration"}
                     | {"sample_weaker": [v["lean_statement"] for v in doc["weaker"][:3]]},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
