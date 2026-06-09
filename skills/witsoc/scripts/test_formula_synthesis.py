#!/usr/bin/env python3
"""Creative engine: formula synthesis (deterministic, no Lean).

Checks the engine DISCOVERS explicit witness families by searching expression space
(the easy residue classes of Erdős–Straus), that what it returns genuinely satisfies
the relation (independent recheck), and — the honest boundary — that it finds NOTHING
for the hard classes (n coprime to 6, the prime case), rather than fabricating one.
Discovered families stay CONJECTURE (bounded evidence) until the kernel verifies them."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import formula_synthesis as fs

REL = fs.PROBLEMS["erdos_straus"]


def main() -> int:
    failures: list[str] = []

    # 1. Discover families for the easy classes (divisible by 2 or 3).
    fams = fs.synthesize(REL, moduli=[2, 3], nmax=600, consts=[1, 2, 3, 4])
    classes = {(f["residue_class"]["mod"], f["residue_class"]["rem"]) for f in fams if f["residue_class"] != "all n"}
    if (2, 0) not in classes:
        failures.append("engine should discover a family for all even n")
    if (3, 0) not in classes:
        failures.append("engine should discover a family for all multiples of 3")

    # 2. Independent recheck: a discovered family really satisfies the relation, AND it
    #    is reported as CONJECTURE (bounded evidence), never VERIFIED.
    blocks = dict(fs.expression_blocks([1, 2, 3, 4]))
    for f in fams:
        if f["status"] != fs.CONJECTURE:
            failures.append("a discovered family must be CONJECTURE until kernel-verified")
        rc = f["residue_class"]
        if rc == "all n":
            continue
        m, r = rc["mod"], rc["rem"]
        xb, yb, zb = blocks[f["x"]], blocks[f["y"]], blocks[f["z"]]
        for n in range(2, 200):
            if n % m == r and not REL(xb(n), yb(n), zb(n), n):
                failures.append(f"family {f['x']},{f['y']},{f['z']} fails at n={n} (mod {m})")
                break

    # 3. HONEST BOUNDARY: for n coprime to 6 (the hard prime case), the engine finds NO
    #    simple-expression family — it does not fabricate the insight it cannot reach.
    fams6 = fs.synthesize(REL, moduli=[6], nmax=300, consts=[1, 2, 3, 4])
    hard = {(f["residue_class"]["mod"], f["residue_class"]["rem"]) for f in fams6 if f["residue_class"] != "all n"}
    if (6, 1) in hard or (6, 5) in hard:
        failures.append("engine must NOT claim a simple family for n coprime to 6 (the hard prime case)")

    # 4. The engine returns nothing (not garbage) when no family exists in the grammar.
    impossible = lambda x, y, z, n: x > 0 and (x + y + z) == n and x == n + 1  # x>n forces empty
    none_fams = fs.synthesize(impossible, moduli=[1], nmax=50, consts=[1, 2])
    if none_fams:
        failures.append("engine must return no family when none exists, not fabricate one")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("FORMULA_SYNTHESIS_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
