#!/usr/bin/env python3
"""Validate mandatory open-problem research discipline for Witsoc/Lovasz."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


PRODUCT_KINDS = {
    "counterexample",
    "obstruction",
    "reduction",
    "special_case",
    "conditional_theorem",
    "computational_certificate",
    "verified_lemma",
    "failed_attempt",
    "conjecture",
    "partial_result",
}

MUTATION_AXES = {
    "method",
    "statement_strength",
    "encoding",
    "object_class",
    "invariant",
    "computational_bound",
    "formalization_target",
    "theorem_source",
}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


from witcore import records  # noqa: E402  -- shared substrate, was a local copy

def nonempty(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    return any(line.strip() and not line.lstrip().startswith("#") for line in text.splitlines())


def validate_actual_lemma_queue(run: Path, errors: list[str]) -> None:
    lemmas = records(run / "actual_lemma_queue.json")
    if not lemmas:
        errors.append("actual_lemma_queue.json must contain at least one exact barrier lemma")
        return
    for i, lemma in enumerate(lemmas):
        label = f"actual_lemma_queue[{i}]"
        for field in (
            "statement",
            "why_it_matters",
            "unlocks",
            "known_counterexamples_or_boundary_cases",
            "failed_approaches",
            "next_mutation",
            "smallest_formalizable_subcase",
            "status",
        ):
            if lemma.get(field) in (None, "", []):
                errors.append(f"{label} missing {field}")


def validate_disproof_first(run: Path, errors: list[str]) -> None:
    records_ = records(run / "disproof_first.json")
    if not records_:
        errors.append("disproof_first.json must record definition/variant/counterexample pressure before proof campaign")
        return
    passes = {str(r.get("pass_type") or "") for r in records_}
    for required in ("definition_stress", "variant_stress", "model_or_boundary_search"):
        if required not in passes:
            errors.append(f"disproof_first.json missing required pass_type {required!r}")
    for i, rec in enumerate(records_):
        label = f"disproof_first[{i}]"
        for field in ("target_statement", "search_domain", "method", "bounds", "outcome", "next_search"):
            if rec.get(field) in (None, "", []):
                errors.append(f"{label} missing {field}")


def validate_theorem_audit(run: Path, errors: list[str]) -> None:
    audit = records(run / "theorem_precondition_audit.json")
    if not audit:
        errors.append("theorem_precondition_audit.json must contain theorem candidates and precondition decisions")
        return
    for i, item in enumerate(audit):
        label = f"theorem_precondition_audit[{i}]"
        for field in ("target_subgoal", "candidate_theorem", "exact_statement", "required_preconditions", "missing_preconditions", "formal_availability", "use_decision"):
            if item.get(field) in (None, ""):
                errors.append(f"{label} missing {field}")
        if item.get("use_decision") == "use" and item.get("missing_preconditions") not in ([], "", None):
            errors.append(f"{label} cannot use theorem with missing_preconditions")


def validate_product_selection(run: Path, errors: list[str]) -> None:
    products = records(run / "product_selection.json")
    if not products:
        errors.append("product_selection.json must record selected research products")
        return
    selected = [p for p in products if p.get("selected") is True]
    if not selected:
        errors.append("product_selection.json must mark one product selected=true")
    for i, product in enumerate(products):
        label = f"product_selection[{i}]"
        kind = product.get("kind")
        if kind not in PRODUCT_KINDS:
            errors.append(f"{label} invalid kind {kind!r}")
        for field in ("statement", "why_this_helps_original", "dependency_path_to_target", "verification_plan", "status"):
            if product.get(field) in (None, "", []):
                errors.append(f"{label} missing {field}")


def validate_mutations(run: Path, errors: list[str]) -> None:
    mutations = records(run / "mutation_ledger.json")
    if not mutations:
        errors.append("mutation_ledger.json must record controlled one-axis retries")
        return
    by_target_method: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for i, mutation in enumerate(mutations):
        label = f"mutation_ledger[{i}]"
        axis = mutation.get("axis_changed")
        if axis not in MUTATION_AXES:
            errors.append(f"{label} invalid axis_changed {axis!r}")
        for field in ("target_hash", "previous_attempt_id", "new_attempt_id", "what_changed", "why_this_is_not_repeat", "result"):
            if mutation.get(field) in (None, "", []):
                errors.append(f"{label} missing {field}")
        by_target_method[(str(mutation.get("target_hash")), str(mutation.get("method_family")))].append(mutation)
    for (target_hash, method), items in by_target_method.items():
        if len(items) > 1 and not all(item.get("axis_changed") for item in items):
            errors.append(f"repeated method {method!r} on target {target_hash!r} lacks recorded axis changes")


def validate_failure_memory(run: Path, errors: list[str]) -> None:
    jsonl = run / "failure_memory.jsonl"
    md = run / "failure_memory.md"
    soc = run / "lovasz.soc"
    if not jsonl.exists() and not md.exists() and not soc.exists():
        errors.append("failure_memory.jsonl, failure_memory.md, or lovasz.soc must exist")
        return
    if jsonl.exists():
        for line_no, line in enumerate(jsonl.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except Exception:
                errors.append(f"failure_memory.jsonl:{line_no} invalid JSONL")
                continue
            for field in ("statement_hash", "method_family", "why_failed", "blocker_or_counterexample", "retry_condition"):
                if item.get(field) in (None, "", []):
                    errors.append(f"failure_memory.jsonl:{line_no} missing {field}")
    elif md.exists() and not nonempty(md):
        errors.append("failure_memory.md has no substantive entries")
    if soc.exists():
        text = soc.read_text(encoding="utf-8", errors="replace")
        for section in ("FAILED_APPROACHES:", "INSIGHTS:", "PROGRESS:"):
            if section not in text:
                errors.append(f"lovasz.soc missing {section.rstrip(':')}")


def validate_dependency_paths(run: Path, errors: list[str]) -> None:
    dag = records(run / "proof_dependency_dag.json")
    if not dag:
        errors.append("proof_dependency_dag.json required for dependency path validation")
        return
    nodes = {str(n.get("node_id") or n.get("id")): n for n in dag if n.get("node_id") or n.get("id")}
    target_nodes = {node_id for node_id, n in nodes.items() if n.get("relation_to_target") in {"target", "direct", "unlocks_target"} or n.get("is_target") is True}
    if not target_nodes:
        errors.append("proof_dependency_dag must mark at least one target/direct relation_to_target node")
    for node_id, node in nodes.items():
        if node.get("type") in {"side_note", "literature_note"}:
            continue
        path = node.get("dependency_path_to_target") or node.get("path_to_target")
        if path in (None, "", []):
            errors.append(f"proof_dependency_dag node {node_id!r} missing dependency_path_to_target")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--allow-missing-disproof", action="store_true")
    args = parser.parse_args()

    run = args.run_dir
    if not run.is_dir():
        print(f"INVALID_OPEN_PROBLEM_RUN: not a directory: {run}", file=sys.stderr)
        return 2
    errors: list[str] = []
    validate_actual_lemma_queue(run, errors)
    if not args.allow_missing_disproof:
        validate_disproof_first(run, errors)
    validate_theorem_audit(run, errors)
    validate_product_selection(run, errors)
    validate_mutations(run, errors)
    validate_failure_memory(run, errors)
    validate_dependency_paths(run, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("VALID_OPEN_PROBLEM_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
