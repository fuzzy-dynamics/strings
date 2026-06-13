#!/usr/bin/env python3
"""Invention Mode — grammar search for new definitions (the deepest creative lever).

The lovasz SKILL.md specifies a Symmetry-Maximizing Definition Generator ("do not
invent a broad new concept by prose; output a localized grammar-search constraint")
but had no implementing script. This is it: enumerative synthesis over a typed
expression grammar whose terminals are isomorphism-invariant primitive columns of
example objects, searching for an expression + threshold that SEPARATES the
positive examples from the negative ones. New named invariants ("discrepancy",
"energy", "potential") are exactly such separating quantities.

Method: bottom-up enumeration by expression size with observational-equivalence
dedup (two expressions with identical value vectors on the sample are the same
candidate — keep the smaller), then threshold search per expression. Perfect
separators become candidate DEFINITIONS ranked by parsimony then margin; the
best imperfect ones are reported as near-misses, honestly.

CALIBRATION: every synthesized definition is born `CONJECTURE` /
`SPECULATIVE` (a separating expression on a bounded sample is bounded evidence,
never a theorem) and `assert_no_upgrade` enforces it structurally. Symmetry
invariance is inherited: terminals are invariant columns, and every grammar
operation preserves invariance.

Usage:
  definition_synthesis.py --examples FILE.json --label-key is_X
      [--forbid col ...] [--max-size 7] [--max-pool 4000] [--top 5]
      [--actual-barrier-lemma "..."] [--out invented_definitions.json]
  definition_synthesis.py --domain graphs --label-key triangle_free --max-n 5 --limit 200 ...
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

STATUS = "CONJECTURE"
ARENA = "SPECULATIVE"

OPS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "min": lambda a, b: min(a, b),
    "max": lambda a, b: max(a, b),
    "//": lambda a, b: a // b if b != 0 else None,
}
_INFIX = {"+", "-", "*", "//"}


def to_string(expr) -> str:
    kind = expr[0]
    if kind == "col":
        return expr[1]
    if kind == "const":
        return str(expr[1])
    op, l, r = expr
    ls, rs = to_string(l), to_string(r)
    if op in _INFIX:
        return f"({ls} {op} {rs})"
    return f"{op}({ls}, {rs})"


def columns_of(expr) -> set[str]:
    if expr[0] == "col":
        return {expr[1]}
    if expr[0] == "const":
        return set()
    return columns_of(expr[1]) | columns_of(expr[2])


def force_open(d: dict) -> dict:
    d["status"] = STATUS
    d["arena"] = ARENA
    return d


def assert_no_upgrade(defs: list[dict]) -> None:
    for d in defs:
        if d.get("status") != STATUS or d.get("arena") != ARENA:
            raise AssertionError(
                f"calibration violation: invention emitted status={d.get('status')!r} "
                f"arena={d.get('arena')!r}; must be {STATUS}/{ARENA}")


def _numeric_primitives(rows: list[dict], label_key: str, forbid: set[str]) -> list[str]:
    keys = sorted({k for r in rows for k in r})
    out = []
    for k in keys:
        if k == label_key or k in forbid:
            continue
        vals = [r.get(k) for r in rows if k in r]
        if vals and all(isinstance(v, (int, bool)) for v in vals) and len(vals) == len(rows):
            out.append(k)
    return out


def enumerate_pool(rows: list[dict], primitives: list[str], constants: tuple[int, ...],
                   max_size: int, max_pool: int) -> list[tuple]:
    """Bottom-up enumeration with observational-equivalence dedup: identical value
    vectors on the sample collapse to the smallest expression. Returns
    [(expr, values, size)]."""
    seen: dict[tuple, int] = {}
    pool: list[tuple] = []

    def add(expr, values, size) -> bool:
        key = tuple(values)
        if key in seen:
            return False
        seen[key] = size
        pool.append((expr, values, size))
        return True

    for c in primitives:
        add(("col", c), [int(r[c]) for r in rows], 1)
    for v in constants:
        add(("const", v), [v] * len(rows), 1)

    by_size: dict[int, list[tuple]] = {}
    for item in pool:
        by_size.setdefault(item[2], []).append(item)

    for size in range(3, max_size + 1):
        if len(pool) >= max_pool:
            break
        new_items = []
        for s1 in range(1, size - 1):
            s2 = size - 1 - s1
            for (e1, v1, _), (e2, v2, _) in itertools.product(by_size.get(s1, []), by_size.get(s2, [])):
                for op, fn in OPS.items():
                    vals = []
                    ok = True
                    for a, b in zip(v1, v2):
                        out = fn(a, b)
                        if out is None or abs(out) > 10 ** 9:
                            ok = False
                            break
                        vals.append(out)
                    if ok and add((op, e1, e2), vals, size):
                        new_items.append(pool[-1])
                        if len(pool) >= max_pool:
                            break
                if len(pool) >= max_pool:
                    break
            if len(pool) >= max_pool:
                break
        by_size[size] = new_items
    return pool


def best_threshold(values: list[int], labels: list[bool]) -> dict:
    """Best separating threshold over both directions. accuracy 1.0 = perfect."""
    n = len(values)
    best = {"accuracy": 0.0, "threshold": None, "direction": None, "margin": 0}
    for t in sorted(set(values)):
        for direction in (">=", "<="):
            pred = [(v >= t) if direction == ">=" else (v <= t) for v in values]
            acc = sum(p == l for p, l in zip(pred, labels)) / n
            if acc > best["accuracy"]:
                pos_vals = [v for v, l in zip(values, labels) if l]
                neg_vals = [v for v, l in zip(values, labels) if not l]
                margin = 0
                if pos_vals and neg_vals:
                    margin = (min(pos_vals) - max(neg_vals)) if direction == ">=" \
                        else (min(neg_vals) - max(pos_vals))
                best = {"accuracy": round(acc, 4), "threshold": t,
                        "direction": direction, "margin": margin}
    return best


def synthesize(rows: list[dict], label_key: str, *, forbid: tuple[str, ...] = (),
               constants: tuple[int, ...] = (1, 2, 3), max_size: int = 7,
               max_pool: int = 4000, top: int = 5,
               symmetry_objective: str = "inherited: primitives are isomorphism-invariant columns "
                                         "and every grammar operation preserves invariance",
               actual_barrier_lemma: str = "") -> dict:
    labels = [bool(r.get(label_key)) for r in rows]
    if not rows or all(labels) or not any(labels):
        return {"schema": "witsoc.definition_synthesis.v1", "definitions": [],
                "near_misses": [], "error": "need both positive and negative examples"}
    primitives = _numeric_primitives(rows, label_key, set(forbid))
    if not primitives:
        return {"schema": "witsoc.definition_synthesis.v1", "definitions": [],
                "near_misses": [], "error": "no usable numeric primitive columns"}

    pool = enumerate_pool(rows, primitives, constants, max_size, max_pool)

    perfect, near = [], []
    for expr, values, size in pool:
        if expr[0] == "const":
            continue
        sep = best_threshold(values, labels)
        entry = {
            "expression": to_string(expr),
            "columns": sorted(columns_of(expr)),
            "size": size,
            "kind": "existing_invariant" if size == 1 else "novel_composite",
            **sep,
        }
        if sep["accuracy"] == 1.0:
            perfect.append(force_open(entry))
        elif sep["accuracy"] >= 0.85:
            near.append(entry)

    perfect.sort(key=lambda d: (d["size"], -d["margin"]))
    near.sort(key=lambda d: (-d["accuracy"], d["size"]))
    definitions = perfect[:top]
    for i, d in enumerate(definitions):
        d["name"] = f"inv_{label_key}_{i + 1}"

    lemma_candidates = []
    for d in definitions:
        lemma_candidates.append(force_open({
            "statement": f"an object is {label_key} ↔ {d['expression']} {d['direction']} "
                         f"{d['threshold']} (separates {sum(labels)} positive / "
                         f"{len(labels) - sum(labels)} negative sampled objects)",
            "lean_statement": None,
            "formalization_blocker": "needs an object encoding; expression uses integer "
                                     "arithmetic (subtraction/division may need Int or guards)",
            "invented_definition": d["name"],
            "next_attempt": "falsify on larger samples; if it survives, formalize the scoped "
                            "characterization and dispatch the Prover",
        }))

    out = {
        "schema": "witsoc.definition_synthesis.v1",
        "mode": "invention",
        "grammar_record": {
            "allowed_primitives": primitives,
            "constructors": sorted(OPS),
            "constants": list(constants),
            "max_size": max_size,
            "symmetry_objective": symmetry_objective,
            "positive_examples": sum(labels),
            "negative_examples": len(labels) - sum(labels),
            "actual_barrier_lemma": actual_barrier_lemma or "unset",
        },
        "pool_size": len(pool),
        "definitions": definitions,
        "near_misses": near[:top],
        "lemma_candidates": lemma_candidates,
        "calibration": f"every definition is {STATUS}/{ARENA}: a separating expression on a "
                       "bounded sample is bounded evidence, never a theorem. Exit only via "
                       "falsification at larger bounds + the kernel gate.",
    }
    assert_no_upgrade(definitions + lemma_candidates)
    return out


def _generated_rows(domain: str, max_n: int, limit: int, graph_family: str) -> list[dict]:
    import empirical_miner as em
    if domain == "graphs":
        return em.generate_graphs(max_n, limit, graph_family, iterations=3)
    if domain == "number_theory":
        return em.generate_number_theory(limit)
    return em.generate_matrices(2, limit)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--examples", type=Path, default=None,
                    help='JSON file {"rows": [...]} with one label column')
    ap.add_argument("--domain", choices=["graphs", "number_theory", "matrices"], default=None,
                    help="generate examples via empirical_miner instead of --examples")
    ap.add_argument("--label-key", required=True)
    ap.add_argument("--forbid", action="append", default=[],
                    help="columns the definition may NOT use (e.g. the label's own source)")
    ap.add_argument("--max-n", type=int, default=5)
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--graph-family", default="exhaustive")
    ap.add_argument("--max-size", type=int, default=7)
    ap.add_argument("--max-pool", type=int, default=4000)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--actual-barrier-lemma", default="")
    ap.add_argument("--out", type=Path, default=Path("invented_definitions.json"))
    args = ap.parse_args()

    if args.examples:
        doc = witcore.load_json(args.examples, {})
        rows = doc.get("rows", []) if isinstance(doc, dict) else []
    elif args.domain:
        rows = _generated_rows(args.domain, args.max_n, args.limit, args.graph_family)
    else:
        print(json.dumps({"error": "need --examples or --domain"}))
        return 2

    out = synthesize(rows, args.label_key, forbid=tuple(args.forbid),
                     max_size=args.max_size, max_pool=args.max_pool, top=args.top,
                     actual_barrier_lemma=args.actual_barrier_lemma)
    witcore.save_json(args.out, out)
    print(json.dumps({k: v for k, v in out.items() if k not in ("near_misses",)}
                     | {"near_miss_count": len(out.get("near_misses", []))},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
