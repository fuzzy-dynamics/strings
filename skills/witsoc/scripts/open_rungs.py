#!/usr/bin/env python3
"""Build rung-first open-problem targets.

The output is a planning artifact: reachable partial products that Lovasz can
attack before spending budget on the full open target. Rungs are never reported
as solves of the original problem.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def erdos_straus_rungs(target: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "es-even-family",
            "type": "special_case_family",
            "status": "candidate_true_rung",
            "domain": "number_theory",
            "statement": "For n = 2m, the triple (2m, 2m, m) satisfies the cleared Erdős-Straus equation.",
            "lean_statement": "∀ m : Nat, 0 < m → 4 * ((2 * m) * ((2 * m) * m)) = (2 * m) * ((2 * m) * m + (2 * m) * m + (2 * m) * (2 * m))",
            "proof_hint": "intro m hm; ring",
            "relation_to_target": "covers the even residue class only",
        },
        {
            "id": "es-mult3-family",
            "type": "special_case_family",
            "status": "candidate_true_rung",
            "domain": "number_theory",
            "statement": "For n = 3k, the triple (6k, 6k, k) satisfies the cleared Erdős-Straus equation.",
            "lean_statement": "∀ k : Nat, 0 < k → 4 * ((6 * k) * ((6 * k) * k)) = (3 * k) * ((6 * k) * k + (6 * k) * k + (6 * k) * (6 * k))",
            "proof_hint": "intro k hk; ring",
            "relation_to_target": "covers the divisible-by-3 residue class only",
        },
        {
            "id": "es-hard-residue-search",
            "type": "formula_synthesis",
            "status": "open_search",
            "domain": "number_theory",
            "statement": "Search parametric witnesses for unresolved residue classes modulo 12 and 24.",
            "backend": "formula_synthesis",
            "params": {"problem": "erdos_straus", "moduli": [12, 24], "nmax": 600},
            "relation_to_target": "new verified residue families shrink the open core but do not solve the target",
        },
    ]


def generic_rungs(target: str, domain: str) -> list[dict[str, Any]]:
    base = [
        {
            "id": "bounded-counterexample-pressure",
            "type": "counterexample_search",
            "status": "open_search",
            "domain": domain,
            "statement": "Search small and boundary instances for counterexamples to stronger or misstated variants.",
            "relation_to_target": "negative evidence or a refutation of a stronger variant",
        },
        {
            "id": "finite-or-special-case",
            "type": "special_case",
            "status": "candidate_partial",
            "domain": domain,
            "statement": "Extract the smallest formalizable nontrivial special case of the target.",
            "relation_to_target": "verified partial only",
        },
        {
            "id": "reduction-or-obstruction",
            "type": "reduction",
            "status": "candidate_partial",
            "domain": domain,
            "statement": "Find a one-direction reduction or obstruction family tied to the target barrier.",
            "relation_to_target": "barrier progress without upgrading the original target",
        },
    ]
    if domain in {"combinatorics", "graph_theory"}:
        base.append({
            "id": "finite-certificate-scan",
            "type": "finite_certificate",
            "status": "checked_bounded_only",
            "domain": domain,
            "statement": "Run exact finite search on the smallest meaningful parameter range.",
            "relation_to_target": "bounded CHECKED evidence only",
        })
    return base


def is_erdos_straus(target: str) -> bool:
    """Erdős–Straus has a SPECIFIC signature: the named conjecture, or the
    equation 4/n = 1/x+1/y+1/z. The bare token 'erdos'/'erdős' is NOT enough —
    Erdős posed hundreds of problems, so matching on his name alone injected the
    Straus arithmetic rungs into every Erdős target (e.g. the unit-distance
    conjecture got 4/n lemmas)."""
    lower = target.lower()
    if "straus" in lower:
        return True
    has_4_over_n = ("4/n" in lower or "4 / n" in lower
                    or ("4/" in lower and "= 1/" in lower))
    reciprocal_sum = lower.count("1/") >= 3 or ("1/x" in lower and "1/y" in lower)
    return has_4_over_n and reciprocal_sum


def build(target: str, domain: str) -> dict[str, Any]:
    if is_erdos_straus(target):
        rungs = erdos_straus_rungs(target)
        detected = "erdos_straus"
    else:
        rungs = generic_rungs(target, domain)
        detected = "generic"
    return {
        "schema": "witsoc.open_rungs.v1",
        "target": target,
        "target_sha256": _hash(target),
        "domain": domain,
        "detected_template": detected,
        "status_policy": "rungs_are_partial_products; original_open_target_stays_OPEN",
        "rungs": rungs,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build")
    p.add_argument("--target", required=True)
    p.add_argument("--domain", default="other")
    p.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = build(args.target, args.domain)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
