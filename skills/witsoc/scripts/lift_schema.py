#!/usr/bin/env python3
"""Finite -> general lift schemas: turn a verified finite witness into the *exact*
Lean obligation whose discharge upgrades it to a general/asymptotic theorem.

The discovery engine produces bounded witnesses (a cap set in F_3^d for a fixed
d, a Sidon set in [1,N]). The Erdos-style target is usually a statement for all n
or an asymptotic bound. There is no sound automatic jump from "verified at n=30"
to "for all n" — so this tool does NOT fake the lift. It emits:

  1. the precise Lean bridge lemma the lift requires (as a type-checking
     obligation with `sorry`), and
  2. the numeric consequence the finite witness yields once that lemma holds.

Discharge the emitted obligation with close_obligation.py or by hand; only then
is the general statement earned.

Schemas:
  induction     P holds at base and is preserved by n -> n+1  =>  P for all n >= base
  product       a size-m valid object in dimension d, closed under self-product,
                yields size m^k in dimension d*k  (lower-bound exponent log_d(m))
  monotone      maximal-object size is monotone in the ambient size N

Usage:
  lift_schema.py --schema product --problem cap_set --witness-size 9 --base-dim 2 [--lake-dir DIR]
  lift_schema.py --schema induction --predicate "fun n => P n" --base 3
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lean_check import lean_verify  # noqa: E402


def lean_induction(base: int) -> str:
    return (
        "namespace WitsocLift\n\n"
        "/-- Lift schema: base case + successor step give the property for all n ≥ base. -/\n"
        "theorem lift_induction (P : Nat → Prop) (b : Nat)\n"
        "    (base : P b) (step : ∀ n, b ≤ n → P n → P (n + 1)) :\n"
        "    ∀ n, b ≤ n → P n := sorry\n\n"
        "end WitsocLift\n"
    )


def lean_product() -> str:
    return (
        "namespace WitsocLift\n\n"
        "/-- Lift schema: if `valid` is closed under self-product and the product\n"
        "    multiplies size, a size-m witness yields a size-(m*m) witness; iterating\n"
        "    gives the exponential lower bound. The two hypotheses are the real\n"
        "    obligation. -/\n"
        "theorem lift_product {α : Type} (valid : List α → Prop)\n"
        "    (prod : List α → List α → List α)\n"
        "    (sizeMul : ∀ s, (prod s s).length = s.length * s.length)\n"
        "    (closed : ∀ s, valid s → valid (prod s s)) :\n"
        "    ∀ s, valid s → ∃ t, valid t ∧ t.length = s.length * s.length := sorry\n\n"
        "end WitsocLift\n"
    )


def lean_monotone() -> str:
    return (
        "namespace WitsocLift\n\n"
        "/-- Lift schema: the maximal-object size is monotone in the ambient size. -/\n"
        "theorem lift_monotone (maxSize : Nat → Nat)\n"
        "    (embed : ∀ N M, N ≤ M → maxSize N ≤ maxSize M) :\n"
        "    ∀ N M, N ≤ M → maxSize N ≤ maxSize M := sorry\n\n"
        "end WitsocLift\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--schema", required=True, choices=["induction", "product", "monotone"])
    ap.add_argument("--problem", default=None, help="problem name (for the record / consequence)")
    ap.add_argument("--witness-size", type=int, default=None, help="size m of the finite witness")
    ap.add_argument("--base-dim", type=int, default=None, help="dimension d of the witness (product schema)")
    ap.add_argument("--base", type=int, default=0, help="base index (induction schema)")
    ap.add_argument("--emit", type=Path, default=None)
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--out-ledger", type=Path, default=Path("lift_obligations.json"))
    args = ap.parse_args()

    if args.schema == "induction":
        src = lean_induction(args.base)
    elif args.schema == "product":
        src = lean_product()
    else:
        src = lean_monotone()

    emit = args.emit or Path("obligations") / f"lift_{args.schema}.lean"
    emit.parent.mkdir(parents=True, exist_ok=True)
    emit.write_text(src, encoding="utf-8")

    verdict = lean_verify(emit, args.lake_dir)
    # The obligation has `sorry` by design, so it is never "verified"; what we
    # check is that the bridge STATEMENT type-checks (build green = well-formed).
    statement_compiles = ("PASS" if verdict.get("build", {}).get("ok") else "FAIL") if verdict.get("checked") else "UNCHECKED"

    consequence: dict[str, Any] = {}
    if args.schema == "product" and args.witness_size and args.base_dim:
        m, d = args.witness_size, args.base_dim
        # size m in dimension d, self-product k times -> size m^k in dimension d*k.
        # As a function of dimension D = d*k, size = m^(D/d) = (m^(1/d))^D, i.e. an
        # exponential lower bound with base c = m^(1/d).
        c = m ** (1.0 / d) if d else None
        consequence = {
            "form": "exponential lower bound via iterated self-product",
            "witness": f"size {m} in dimension {d}",
            "growth_base_c": round(c, 6) if c else None,
            "statement": f"max valid-object size in dimension D is >= {round(c, 6)}^D"
                         if c else None,
            "caveat": "valid only once `closed` (self-product preserves validity) is proven.",
        }
    elif args.schema == "induction":
        consequence = {"form": "for all n >= base", "base": args.base,
                       "caveat": "valid only once the successor `step` is proven."}

    record = {
        "schema": "witsoc.lift_obligation.v1",
        "lift_schema": args.schema,
        "problem": args.problem,
        "lean_path": str(emit),
        "statement_compiles": statement_compiles,
        "status": "OBLIGATION_OPEN",
        "numeric_consequence": consequence,
        "note": "Discharge the emitted bridge lemma (close_obligation.py / human) to earn the general claim.",
    }
    existing = []
    if args.out_ledger.exists():
        try:
            data = json.loads(args.out_ledger.read_text(encoding="utf-8"))
            if isinstance(data, list):
                existing = data
        except Exception:
            existing = []
    existing = [r for r in existing if not (isinstance(r, dict) and r.get("lean_path") == record["lean_path"])]
    existing.append(record)
    args.out_ledger.parent.mkdir(parents=True, exist_ok=True)
    args.out_ledger.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0 if statement_compiles in ("PASS", "UNCHECKED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
