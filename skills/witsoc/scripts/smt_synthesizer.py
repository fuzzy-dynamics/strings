#!/usr/bin/env python3
"""Run deterministic SMT-LIB reduction synthesis through z3-solver.

Input is an SMT-LIB string from --smt, --file, or stdin. Output is JSON:

- SAT returns a model, suitable as a candidate reduction gadget.
- UNSAT returns the unsat core when the SMT-LIB uses named assertions and
  enables/provides unsat-core support.
- UNKNOWN returns Z3's reason_unknown.

This script is intentionally a thin deterministic wrapper. It does not invent
constraints or interpret mathematical meaning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def read_input(args: argparse.Namespace) -> str:
    if args.smt is not None:
        return args.smt
    if args.file is not None:
        return Path(args.file).read_text(encoding="utf-8")
    return sys.stdin.read()


def z3_value_to_json(value: Any) -> Any:
    text = str(value)
    if text == "True":
        return True
    if text == "False":
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def model_to_json(model: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for decl in sorted(model.decls(), key=lambda d: d.name()):
        out[decl.name()] = z3_value_to_json(model[decl])
    return out


def run_z3(smt: str, timeout_ms: int) -> dict[str, Any]:
    try:
        import z3  # type: ignore
    except Exception as exc:
        return {
            "status": "missing_dependency",
            "dependency": "z3-solver",
            "error": str(exc),
            "install_hint": "Install z3-solver in the runtime environment.",
        }

    solver = z3.Solver()
    solver.set(unsat_core=True)
    if timeout_ms > 0:
        solver.set(timeout=timeout_ms)

    try:
        solver.from_string(smt)
    except Exception as exc:
        return {
            "status": "parse_error",
            "error": str(exc),
        }

    result = solver.check()
    result_text = str(result)

    if result_text == "sat":
        return {
            "status": "sat",
            "model": model_to_json(solver.model()),
            "gadget": model_to_json(solver.model()),
        }
    if result_text == "unsat":
        return {
            "status": "unsat",
            "unsat_core": [str(item) for item in solver.unsat_core()],
            "obstruction": [str(item) for item in solver.unsat_core()],
        }
    return {
        "status": "unknown",
        "reason": solver.reason_unknown(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SMT-LIB through Z3 and return model/core JSON.")
    parser.add_argument("--file", help="Path to SMT-LIB input. Defaults to stdin.")
    parser.add_argument("--smt", help="Inline SMT-LIB input.")
    parser.add_argument("--timeout-ms", type=int, default=30_000, help="Z3 timeout in milliseconds; 0 disables timeout.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    args = parser.parse_args()

    smt = read_input(args)
    payload = {
        "input_sha256": hashlib.sha256(smt.encode("utf-8")).hexdigest(),
        "timeout_ms": args.timeout_ms,
        "result": run_z3(smt, args.timeout_ms),
    }
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))

    status = payload["result"]["status"]
    if status in {"sat", "unsat", "unknown"}:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
