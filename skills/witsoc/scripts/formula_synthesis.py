#!/usr/bin/env python3
"""Creative engine: formula / construction SYNTHESIS (FunSearch-style).

The template generators only RECOMBINE known forms. This is a step toward genuine
invention: it searches the SPACE OF EXPRESSIONS itself for an explicit construction
that a deterministic evaluator certifies — discovering parametrized witness families,
invariants, or closed forms that nobody hand-coded.

Concretely it searches a grammar of arithmetic expressions in a parameter `n` (plus
`n div k`, `n mod`, affine forms, …) for a witness tuple that satisfies a target
relation on EVERY instance of a residue class up to a bound. A surviving family is
bounded-verified evidence — `CONJECTURE` — until it is formalized and the kernel proves
it for the whole class, at which point it becomes a VERIFIED infinite family. Generation
is cheap and untrusted; the evaluator (and then the kernel) is the only judge.

This is the honest creative leap: it can find constructions OUTSIDE the template set,
bounded only by the expression grammar — not the designer's anticipation.

Usage:
  formula_synthesis.py --problem erdos_straus [--moduli 1,2,3,4] [--nmax 400]
      [--consts 1,2,3,4] [--out families.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

CONJECTURE = "CONJECTURE"


def expression_blocks(consts: list[int]) -> list[tuple[str, Callable[[int], int]]]:
    """The grammar: building-block expressions e(n). Each must return a positive int
    on the instances tested (division is floor; we also keep it EXACT-only via the
    evaluator, which rechecks the cleared relation, so a non-exact n/k just fails)."""
    B: list[tuple[str, Callable[[int], int]]] = [("n", lambda n: n)]
    for c in consts:
        B.append((f"{c}", (lambda n, c=c: c)))
        B.append((f"{c}*n", (lambda n, c=c: c * n)))
        B.append((f"n+{c}", (lambda n, c=c: n + c)))
        if c >= 2:
            B.append((f"n/{c}", (lambda n, c=c: n // c)))
            B.append((f"(n+{c-1})/{c}", (lambda n, c=c: (n + c - 1) // c)))   # ceil(n/c)
    return B


# A problem = a cleared-form relation R(x,y,z,n) that the witness must satisfy.
def erdos_straus_relation(x: int, y: int, z: int, n: int) -> bool:
    # 4/n = 1/x+1/y+1/z  <=>  4*x*y*z = n*(y*z + x*z + x*y), with x,y,z > 0.
    return x > 0 and y > 0 and z > 0 and 4 * x * y * z == n * (y * z + x * z + x * y)


PROBLEMS = {"erdos_straus": erdos_straus_relation}


def synthesize(relation: Callable[[int, int, int, int], bool], moduli: list[int], nmax: int,
               consts: list[int]) -> list[dict]:
    """For each residue class n ≡ r (mod m), enumerate expression triples and keep the
    first that satisfies the relation on EVERY instance in [2, nmax] of that class."""
    blocks = expression_blocks(consts)
    families: list[dict] = []
    covered: set[tuple[int, int]] = set()
    for m in sorted(moduli):
        for r in range(m):
            cls = [n for n in range(2, nmax + 1) if n % m == r]
            if not cls:
                continue
            # skip a class already covered by a coarser modulus
            if any((m % m2 == 0 and r % m2 == r2) for (m2, r2) in covered):
                continue
            found = None
            for xb in blocks:
                for yb in blocks:
                    for zb in blocks:
                        try:
                            if all(relation(xb[1](n), yb[1](n), zb[1](n), n) for n in cls):
                                found = (xb[0], yb[0], zb[0])
                                raise StopIteration
                        except StopIteration:
                            break
                        except Exception:
                            continue
                    if found:
                        break
                if found:
                    break
            if found:
                covered.add((m, r))
                families.append({
                    "residue_class": {"mod": m, "rem": r} if m > 1 else "all n",
                    "x": found[0], "y": found[1], "z": found[2],
                    "verified_on": f"all n ≡ {r} (mod {m}) in [2,{nmax}]" if m > 1 else f"all n in [2,{nmax}]",
                    "status": CONJECTURE,
                    "note": "bounded-verified explicit witness family; CONJECTURE until the kernel proves it "
                            "for the whole residue class (then a VERIFIED infinite family).",
                })
    return families


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--problem", default="erdos_straus", choices=sorted(PROBLEMS))
    ap.add_argument("--moduli", default="1,2,3,4")
    ap.add_argument("--nmax", type=int, default=400)
    ap.add_argument("--consts", default="1,2,3,4")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    moduli = [int(x) for x in args.moduli.split(",")]
    consts = [int(x) for x in args.consts.split(",")]
    families = synthesize(PROBLEMS[args.problem], moduli, args.nmax, consts)
    result = {
        "schema": "witsoc.formula_synthesis.v1",
        "problem": args.problem,
        "discovered_families": families,
        "coverage_note": f"each family is an EXPLICIT witness construction discovered by searching expression "
                         f"space (not a template), bounded-verified on [2,{args.nmax}]; kernel-formalize to upgrade.",
        "calibration": "discovered families are CONJECTURE (bounded evidence). Only a kernel proof for the whole "
                       "class makes a family a VERIFIED infinite result; nothing is asserted on the strength of a "
                       "finite check.",
    }
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
