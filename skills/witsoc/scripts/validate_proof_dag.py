#!/usr/bin/env python3
"""Validate Lovasz proof-DAG and worker-result invariants in a Witsoc handoff."""

from __future__ import annotations

import sys
from pathlib import Path

from validate_handoff import load_json, check_research_machinery


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_proof_dag.py runs/<task>/handoff.json", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    try:
        data = load_json(path)
    except Exception as exc:
        print(f"INVALID: could not read JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("INVALID: handoff root must be an object", file=sys.stderr)
        return 2

    errors: list[str] = []
    check_research_machinery(data, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("VALID_PROOF_DAG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
