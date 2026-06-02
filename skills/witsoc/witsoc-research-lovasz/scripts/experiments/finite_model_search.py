#!/usr/bin/env python3
"""Generic finite tuple search for small Lovasz experiments.

The predicate is a Python expression over tuple variable `x`, e.g.
`sum(x) == 5 and x[0] < x[1]`. This is for local experiments only; record the
exact expression and bounds in research.md.
"""

from __future__ import annotations

import argparse
import itertools
import json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arity", type=int, required=True)
    parser.add_argument("--domain", type=int, required=True, help="search values 0..domain-1")
    parser.add_argument("--predicate", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    witnesses = []
    safe_globals = {"__builtins__": {}, "sum": sum, "min": min, "max": max, "all": all, "any": any}
    for x in itertools.product(range(args.domain), repeat=args.arity):
        if eval(args.predicate, safe_globals, {"x": x}):
            witnesses.append(x)
            if len(witnesses) >= args.limit:
                break

    print(json.dumps({
        "arity": args.arity,
        "domain": args.domain,
        "predicate": args.predicate,
        "witness_count": len(witnesses),
        "witnesses": witnesses,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
