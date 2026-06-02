#!/usr/bin/env python3
"""Small exact number-theory search helpers for Lovasz experiments."""

from __future__ import annotations

import argparse
import json
import math
from fractions import Fraction


def factor(n: int) -> dict[int, int]:
    d: dict[int, int] = {}
    p = 2
    while p * p <= n:
        while n % p == 0:
            d[p] = d.get(p, 0) + 1
            n //= p
        p += 1 if p == 2 else 2
    if n > 1:
        d[n] = d.get(n, 0) + 1
    return d


def sigma_from_factor(f: dict[int, int]) -> int:
    total = 1
    for p, a in f.items():
        total *= (p ** (a + 1) - 1) // (p - 1)
    return total


def abundancy(n: int) -> Fraction:
    return Fraction(sigma_from_factor(factor(n)), n)


def scan_multiperfect(limit: int) -> list[dict[str, object]]:
    out = []
    for n in range(1, limit + 1):
        r = abundancy(n)
        if r.denominator == 1:
            out.append({
                "n": n,
                "k": r.numerator,
                "factorization": factor(n),
                "omega": len(factor(n)),
                "Omega": sum(factor(n).values()),
                "loglog_n": math.log(math.log(n)) if n > math.e else None,
            })
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["factor", "abundancy", "multiperfect"], required=True)
    parser.add_argument("--n", type=int)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    if args.mode == "factor":
        if args.n is None:
            parser.error("--n required")
        result = {"n": args.n, "factorization": factor(args.n)}
    elif args.mode == "abundancy":
        if args.n is None:
            parser.error("--n required")
        r = abundancy(args.n)
        result = {"n": args.n, "sigma_over_n": [r.numerator, r.denominator], "is_integer": r.denominator == 1}
    else:
        if args.limit is None:
            parser.error("--limit required")
        result = {"limit": args.limit, "multiperfect": scan_multiperfect(args.limit)}

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
