#!/usr/bin/env python3
"""Validate a Witsoc handoff JSON file.

This script intentionally keeps Witsoc-specific invariants outside the LLM:
- JSON schema validity when jsonschema is installed
- EV arithmetic
- lemma economics arithmetic
- selected sketch existence
- theorem candidate rank uniqueness and sorting
- open problems have a real open_product_target
- blueprint lemma_plan references and DAG shape
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_json_schema(data: object, schema_path: Path, errors: list[str]) -> None:
    try:
        import jsonschema  # type: ignore
    except Exception:
        errors.append("jsonschema package unavailable; skipped full JSON Schema validation")
        return

    schema = load_json(schema_path)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in error.path) or "<root>"
        errors.append(f"schema: {loc}: {error.message}")


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def check_handoff(data: dict, errors: list[str]) -> None:
    sketches = data.get("sketches", [])
    selected = data.get("selected_sketch_id")
    sketch_ids = {s.get("sketch_id") for s in sketches if isinstance(s, dict)}
    if selected not in sketch_ids:
        errors.append(f"selected_sketch_id {selected!r} does not match any sketch_id")

    for sketch in sketches:
        if not isinstance(sketch, dict):
            continue
        ev = sketch.get("ev", {})
        try:
            expected = (
                float(ev["theorem_fidelity"])
                * float(ev["probability_of_completion"])
                * float(ev["verifier_friendliness"])
            )
            actual = float(ev["expected_value"])
        except Exception as exc:
            errors.append(f"sketch {sketch.get('sketch_id')}: invalid ev fields: {exc}")
            continue
        if not close(expected, actual):
            errors.append(
                f"sketch {sketch.get('sketch_id')}: expected_value {actual} != "
                f"{expected} from fidelity*completion*friendliness"
            )

        for lemma in sketch.get("lemmas", []):
            econ = lemma.get("economics", {}) if isinstance(lemma, dict) else {}
            try:
                expected_value = float(econ["goals_unlocked"]) / float(econ["proof_complexity"])
                actual_value = float(econ["lemma_value"])
            except Exception as exc:
                errors.append(f"lemma {lemma.get('id') if isinstance(lemma, dict) else '<bad>'}: invalid economics: {exc}")
                continue
            if not close(expected_value, actual_value):
                errors.append(
                    f"lemma {lemma.get('id')}: lemma_value {actual_value} != "
                    f"{expected_value} from goals_unlocked/proof_complexity"
                )

    candidates = data.get("theorem_candidates", [])
    ranks = [c.get("rank") for c in candidates if isinstance(c, dict)]
    if len(ranks) != len(set(ranks)):
        errors.append("theorem_candidates ranks are not unique")
    if ranks != sorted(ranks):
        errors.append("theorem_candidates ranks are not sorted ascending")

    if data.get("problem_status") == "OPEN":
        kind = (data.get("open_product_target") or {}).get("kind")
        if kind in (None, "not_applicable"):
            errors.append("OPEN problem must have open_product_target.kind other than not_applicable")


def check_blueprint_handoff(data: dict, errors: list[str]) -> None:
    steps = data.get("lemma_plan", [])
    step_ids: list[str] = []
    seen: set[str] = set()
    for step in steps:
        step_id = step.get("step_id") if isinstance(step, dict) else None
        if not step_id:
            continue
        if step_id in seen:
            errors.append(f"lemma_plan duplicate step_id {step_id!r}")
        seen.add(step_id)
        step_ids.append(step_id)

    step_id_set = set(step_ids)
    seen_so_far: set[str] = set()
    graph: dict[str, list[str]] = {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_id = step.get("step_id")
        deps = step.get("depends_on", [])
        if not isinstance(step_id, str) or not isinstance(deps, list):
            continue
        graph[step_id] = []
        for dep in deps:
            if dep not in step_id_set:
                errors.append(f"lemma_plan step {step_id!r} depends on unknown step_id {dep!r}")
            elif dep not in seen_so_far:
                errors.append(f"lemma_plan step {step_id!r} depends on non-earlier step_id {dep!r}")
            else:
                graph[step_id].append(dep)

        method = str(step.get("method", "")).strip().lower()
        vague = ["standard", "obvious", "clear", "trivial", "routine", "by algebra", "by calculation"]
        if any(term in method for term in vague):
            errors.append(f"lemma_plan step {step_id!r} has vague method {step.get('method')!r}")
        seen_so_far.add(step_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, stack: list[str]) -> None:
        if node in visited:
            return
        if node in visiting:
            cycle = " -> ".join(stack + [node])
            errors.append(f"lemma_plan contains dependency cycle: {cycle}")
            return
        visiting.add(node)
        for dep in graph.get(node, []):
            visit(dep, stack + [node])
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node, [])

    external_names = {
        dep.get("theorem_name")
        for dep in data.get("external_dependencies", [])
        if isinstance(dep, dict)
    }
    for dep in data.get("external_dependencies", []):
        if not isinstance(dep, dict):
            continue
        if not dep.get("required_preconditions"):
            errors.append(f"external dependency {dep.get('theorem_name')!r} has no required_preconditions")

    for step in steps:
        if not isinstance(step, dict):
            continue
        method = str(step.get("method", ""))
        if "external:" in method:
            referenced = method.split("external:", 1)[1].strip()
            if referenced and referenced not in external_names:
                errors.append(
                    f"lemma_plan step {step.get('step_id')!r} references external theorem "
                    f"{referenced!r} not present in external_dependencies"
                )

    problem_class = (data.get("metadata") or {}).get("problem_class")
    directive = data.get("generator_directive") or {}
    artifact_target = directive.get("artifact_target")
    status = directive.get("status_to_assert")
    if problem_class == "OPEN_RESEARCH_SUBGOAL" and artifact_target == "FULL_PROOF":
        errors.append("OPEN_RESEARCH_SUBGOAL cannot request generator_directive.artifact_target FULL_PROOF")
    if artifact_target == "CONDITIONAL_THEOREM" and status != "CONDITIONAL":
        errors.append("CONDITIONAL_THEOREM must use status_to_assert CONDITIONAL")
    if artifact_target in {"OBSTRUCTION_LEMMA", "COUNTEREXAMPLE"} and status == "UNVERIFIED":
        errors.append(f"{artifact_target} should assert PARTIAL, CONDITIONAL, or GAP, not UNVERIFIED")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("handoff", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    errors: list[str] = []
    try:
        data = load_json(args.handoff)
    except Exception as exc:
        print(f"INVALID: could not read JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        print("INVALID: handoff root must be an object", file=sys.stderr)
        return 2

    schema_path = args.schema
    if schema_path is None:
        schema_name = (
            "witsoc-handoff-schema.json"
            if "target_formalization" in data and "lemma_plan" in data
            else "handoff.schema.json"
        )
        schema_path = Path(__file__).resolve().parents[1] / "references" / "schemas" / schema_name

    validate_json_schema(data, schema_path, errors)
    # Treat missing jsonschema as a warning, not a failure.
    warnings = [e for e in errors if e.startswith("jsonschema package unavailable")]
    errors = [e for e in errors if not e.startswith("jsonschema package unavailable")]
    if "target_formalization" in data and "lemma_plan" in data:
        check_blueprint_handoff(data, errors)
    else:
        check_handoff(data, errors)

    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
