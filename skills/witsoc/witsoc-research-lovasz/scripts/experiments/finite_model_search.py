#!/usr/bin/env python3
"""Generic finite tuple search for small Lovasz experiments.

The predicate is a Python expression over tuple variable `x`, e.g.
`sum(x) == 5 and x[0] < x[1]`. This is for local experiments only; record the
exact expression and bounds in research.md.
"""

from __future__ import annotations

import argparse
import ast
import itertools
import json
from typing import Callable

# Pure, side-effect-free builtins the predicate may call.
_ALLOWED_FUNCS: dict[str, Callable] = {
    "sum": sum, "min": min, "max": max, "all": all, "any": any,
    "len": len, "abs": abs, "sorted": sorted, "range": range,
    "zip": zip, "enumerate": enumerate, "set": set, "tuple": tuple,
    "list": list, "int": int, "bool": bool,
}

# AST node types the predicate grammar permits. Notably absent: Attribute
# (blocks `().__class__...` sandbox escapes), Import, Lambda, assignment,
# f-strings, and any call to a name outside _ALLOWED_FUNCS.
_ALLOWED_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
    ast.USub, ast.UAdd, ast.Invert, ast.BinOp, ast.Add, ast.Sub, ast.Mult,
    ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.Compare, ast.Eq, ast.NotEq,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Call, ast.Name,
    ast.Load, ast.Store, ast.Constant, ast.Tuple, ast.List, ast.Set,
    ast.Subscript, ast.Slice, ast.IfExp, ast.GeneratorExp, ast.ListComp,
    ast.SetComp, ast.comprehension,
)


def _validate(node: ast.AST, bound: set[str]) -> None:
    """Reject any predicate that steps outside the safe grammar."""
    if not isinstance(node, _ALLOWED_NODES):
        raise ValueError(f"disallowed expression element: {type(node).__name__}")
    if isinstance(node, ast.Attribute):  # defensive; not in _ALLOWED_NODES
        raise ValueError("attribute access is not allowed in predicates")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
            raise ValueError("only whitelisted functions may be called in predicates")
        if node.keywords:
            raise ValueError("keyword arguments are not allowed in predicate calls")
    if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
        bound = set(bound)
        for gen in node.generators:
            for name in ast.walk(gen.target):
                if isinstance(name, ast.Name):
                    bound.add(name.id)
    if isinstance(node, ast.Name) and node.id not in bound and node.id not in _ALLOWED_FUNCS:
        raise ValueError(f"unknown name in predicate: {node.id!r} (only 'x' is bound)")
    for child in ast.iter_child_nodes(node):
        _validate(child, bound)


def compile_predicate(expr: str):
    """Parse and validate a predicate string, returning a callable of x."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"could not parse predicate: {e}") from e
    _validate(tree, {"x"})
    code = compile(tree, "<predicate>", "eval")
    safe_globals = {"__builtins__": {}, **_ALLOWED_FUNCS}
    return lambda x: eval(code, safe_globals, {"x": x})  # noqa: S307 - AST-validated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arity", type=int, required=True)
    parser.add_argument("--domain", type=int, required=True, help="search values 0..domain-1")
    parser.add_argument("--predicate", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    if args.arity < 1:
        parser.error("--arity must be >= 1")
    if args.domain < 1:
        parser.error("--domain must be >= 1")

    try:
        predicate = compile_predicate(args.predicate)
    except ValueError as e:
        parser.error(str(e))

    witnesses = []
    for x in itertools.product(range(args.domain), repeat=args.arity):
        if predicate(x):
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
