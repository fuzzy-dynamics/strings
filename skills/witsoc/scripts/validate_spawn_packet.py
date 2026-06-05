#!/usr/bin/env python3
"""Validate Lovasz spawn requests and worker result packets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_schema(data: object, schema_path: Path, errors: list[str]) -> None:
    try:
        import jsonschema  # type: ignore
    except Exception:
        errors.append("jsonschema package unavailable; skipped JSON Schema validation")
        return

    schema = load_json(schema_path)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in error.path) or "<root>"
        errors.append(f"schema: {loc}: {error.message}")


def validate_spawn(data: dict, errors: list[str]) -> None:
    exact = str(data.get("exact_statement") or "")
    forbidden = str(data.get("forbidden_drift") or "")
    if exact.lower().strip() in {"try this", "prove it", "solve it", "check this"}:
        errors.append("spawn request exact_statement is too vague")
    if "weaken" not in forbidden.lower() and "change" not in forbidden.lower() and "drift" not in forbidden.lower():
        errors.append("spawn request forbidden_drift should explicitly name forbidden weakening/change/drift")


def validate_result(data: dict, errors: list[str]) -> None:
    status = data.get("status")
    failure_class = data.get("failure_class")
    if status in {"VERIFIED", "CHECKED", "PROVED_SKETCH"} and failure_class != "none":
        errors.append(f"accepted status {status} must use failure_class 'none'")
    if status in {"FAILED_ATTEMPT", "REJECTED", "GAP", "OPEN"} and failure_class == "none":
        errors.append(f"status {status} must use a concrete failure_class")
    if status in {"VERIFIED", "CHECKED", "PROVED_SKETCH", "PARTIAL", "CONDITIONAL"}:
        fidelity = data.get("target_fidelity")
        if not isinstance(fidelity, (int, float)):
            errors.append(f"status {status} requires target_fidelity")
        elif fidelity < 0.8 and status not in {"PARTIAL", "CONDITIONAL"}:
            errors.append(f"status {status} requires target_fidelity >= 0.8")
    if status == "VERIFIED":
        for field in ("wit_path", "lean_path", "session_id", "proof_worktree"):
            if not data.get(field):
                errors.append(f"VERIFIED result missing {field}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", type=Path)
    parser.add_argument("--kind", choices=["spawn", "result"], required=True)
    args = parser.parse_args()

    try:
        data = load_json(args.packet)
    except Exception as exc:
        print(f"INVALID: could not read JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("INVALID: packet root must be an object", file=sys.stderr)
        return 2

    schema_name = "lovasz-spawn-worker.schema.json" if args.kind == "spawn" else "lovasz-worker-result.schema.json"
    schema_path = Path(__file__).resolve().parents[1] / "references" / "schemas" / schema_name
    errors: list[str] = []
    validate_schema(data, schema_path, errors)
    warnings = [e for e in errors if e.startswith("jsonschema package unavailable")]
    errors = [e for e in errors if not e.startswith("jsonschema package unavailable")]

    if args.kind == "spawn":
        validate_spawn(data, errors)
    else:
        validate_result(data, errors)

    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("VALID_PACKET")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
