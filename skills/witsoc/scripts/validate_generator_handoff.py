#!/usr/bin/env python3
"""Validate that Generator is allowed to write a new WIT/Lean artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


GENERATOR = "witsoc-generator"


def load(path: Path) -> object:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_schema_optional(data: object, schema_path: Path, errors: list[str]) -> None:
    try:
        import jsonschema  # type: ignore
    except Exception:
        return
    schema = load(schema_path)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in error.path) or "<root>"
        errors.append(f"schema: {loc}: {error.message}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("handoff_v1", type=Path)
    parser.add_argument("--route-state", type=Path, default=None)
    parser.add_argument("--existing-artifact-repair", action="store_true")
    parser.add_argument("--manifest-out", type=Path, default=None)
    args = parser.parse_args()

    errors: list[str] = []
    try:
        handoff = load(args.handoff_v1)
    except Exception as exc:
        print(f"INVALID_GENERATOR_HANDOFF: cannot read handoff: {exc}", file=sys.stderr)
        return 2
    if not isinstance(handoff, dict):
        print("INVALID_GENERATOR_HANDOFF: handoff root must be object", file=sys.stderr)
        return 2

    schema_path = Path(__file__).resolve().parents[1] / "references" / "schemas" / "witsoc-handoff-schema.json"
    validate_schema_optional(handoff, schema_path, errors)

    target = handoff.get("target_formalization") or {}
    if not isinstance(target, dict):
        errors.append("target_formalization must be an object")
        target = {}
    claim = str(target.get("claim") or "")
    if not claim.strip():
        errors.append("target_formalization.claim is required")
    target_hash = sha256_text(json.dumps(target, sort_keys=True, ensure_ascii=False))

    directive = handoff.get("generator_directive") or {}
    if not isinstance(directive, dict):
        errors.append("generator_directive must be an object")
        directive = {}
    if directive.get("status_to_assert") not in {"UNVERIFIED", "PARTIAL", "CONDITIONAL", "GAP"}:
        errors.append("generator_directive.status_to_assert must not overclaim")

    route_state = None
    if args.route_state and args.route_state.exists():
        try:
            route_state = load(args.route_state)
        except Exception as exc:
            errors.append(f"could not read route state: {exc}")
    if route_state and not args.existing_artifact_repair:
        if GENERATOR in (route_state.get("chain") or []) and not route_state.get("generator_authorized"):
            errors.append("route state includes Generator but generator_authorized is false")
        if route_state.get("lovasz_required") and not route_state.get("requires_explorer_review_after_lovasz"):
            errors.append("Lovasz-required route must require Explorer review before Generator")

    manifest = {
        "schema": "witsoc.generator_handoff_validation.v1",
        "handoff_v1": str(args.handoff_v1.resolve()),
        "target_hash": target_hash,
        "claim": claim,
        "artifact_target": directive.get("artifact_target"),
        "status_to_assert": directive.get("status_to_assert"),
        "route_state": str(args.route_state.resolve()) if args.route_state else None,
        "existing_artifact_repair": args.existing_artifact_repair,
        "valid": not errors,
        "errors": errors,
    }
    if args.manifest_out:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
