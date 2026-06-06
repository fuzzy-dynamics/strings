#!/usr/bin/env python3
"""Symbolic asymptotic tension analyzer using SymPy when available."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


def load_sympy() -> Any:
    try:
        import sympy as sp  # type: ignore
        return sp
    except Exception as exc:
        return {"missing_dependency": "sympy", "error": str(exc)}


def locals_for(sp: Any, variable: str) -> dict[str, Any]:
    n = sp.symbols(variable, positive=True)
    c = sp.symbols("c", real=True)
    return {
        variable: n,
        "n": n,
        "c": c,
        "log": sp.log,
        "ln": sp.log,
        "exp": sp.exp,
        "sqrt": sp.sqrt,
        "oo": sp.oo,
        "pi": sp.pi,
        "E": sp.E,
    }


def sympify(sp: Any, text: str, variable: str) -> Any:
    return sp.sympify(text.replace("^", "**"), locals=locals_for(sp, variable))


def classify_ratio(sp: Any, f: Any, g: Any, variable: str) -> dict[str, Any]:
    n = locals_for(sp, variable)[variable]
    ratio = sp.simplify(f / g)
    lim = sp.limit(ratio, n, sp.oo)
    if lim == 0:
        rel = "o"
    elif lim.is_finite and lim != 0:
        rel = "Theta"
    elif lim in (sp.oo, -sp.oo):
        rel = "omega"
    else:
        rel = "unknown"
    return {"ratio": str(ratio), "limit": str(lim), "relationship": rel}


def analyze_big_relation(sp: Any, expr: str, variable: str) -> dict[str, Any] | None:
    patterns = [
        (r"(.+?)\s*=\s*o\((.+)\)\s*$", "o"),
        (r"(.+?)\s*=\s*O\((.+)\)\s*$", "O"),
        (r"(.+?)\s*=\s*Omega\((.+)\)\s*$", "Omega"),
        (r"(.+?)\s*=\s*Theta\((.+)\)\s*$", "Theta"),
    ]
    for pattern, relation in patterns:
        match = re.match(pattern, expr.strip())
        if not match:
            continue
        f = sympify(sp, match.group(1), variable)
        g = sympify(sp, match.group(2), variable)
        ratio = classify_ratio(sp, f, g, variable)
        lim = ratio["limit"]
        holds = {
            "o": ratio["relationship"] == "o",
            "O": ratio["relationship"] in {"o", "Theta"},
            "Omega": ratio["relationship"] in {"Theta", "omega"},
            "Theta": ratio["relationship"] == "Theta",
        }[relation]
        return {"kind": relation, "holds": holds, **ratio}
    return None


def analyze_limit(sp: Any, expr: str, variable: str) -> dict[str, Any] | None:
    match = re.match(r"limit\((.+)\)\s*$", expr.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    n = locals_for(sp, variable)[variable]
    body = sympify(sp, match.group(1), variable)
    return {"kind": "limit", "value": str(sp.limit(body, n, sp.oo)), "expression": str(body)}


def analyze_inequality(sp: Any, expr: str, variable: str) -> dict[str, Any] | None:
    match = re.match(r"(.+?)\s*(<=|<|>=|>)\s*(.+)", expr.strip())
    if not match:
        return None
    left = sympify(sp, match.group(1), variable)
    op = match.group(2)
    right = sympify(sp, match.group(3), variable)
    ratio = classify_ratio(sp, left, right, variable)
    try:
        lim = sympify(sp, ratio["limit"], variable)
    except Exception:
        lim = None
    holds: bool | str
    if op in {"<", "<="} and lim is not None:
        holds = bool(lim < 1) if op == "<" else bool(lim <= 1)
    elif op in {">", ">="} and lim is not None:
        holds = bool(lim > 1) if op == ">" else bool(lim >= 1)
    else:
        holds = "unknown"
    return {"kind": "eventual_inequality", "operator": op, "holds_by_limit_ratio": holds, **ratio}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expr", required=True, help="Expression, inequality, limit(...), or f = O(g)/o(g)/Omega(g)/Theta(g).")
    parser.add_argument("--variable", default="n")
    args = parser.parse_args()

    sp = load_sympy()
    if isinstance(sp, dict):
        print(json.dumps({"status": "missing_dependency", **sp}, indent=2, sort_keys=True))
        return 2

    try:
        result = (
            analyze_big_relation(sp, args.expr, args.variable)
            or analyze_limit(sp, args.expr, args.variable)
            or analyze_inequality(sp, args.expr, args.variable)
        )
        if result is None:
            result = {"kind": "expression", "simplified": str(sympify(sp, args.expr, args.variable))}
        print(json.dumps({"status": "ok", "analysis": result}, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
