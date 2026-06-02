#!/usr/bin/env python3
"""Validate a Witsoc handoff JSON file.

This script intentionally keeps Witsoc-specific invariants outside the LLM:
- JSON schema validity when jsonschema is installed
- EV arithmetic
- lemma economics arithmetic
- selected sketch existence
- theorem candidate rank uniqueness and sorting
- open problems have a real open_product_target
- proof_dependency_dag edge/status/evidence sanity
- worker_results WIT/Lean/SafeVerify evidence for VERIFIED nodes
- worker_results session-scoped proof worktree metadata
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

    if data.get("problem_status") in {"OPEN", "UNSOLVED", "UNCONFIRMED"}:
        kind = (data.get("open_product_target") or {}).get("kind")
        if kind in (None, "not_applicable"):
            errors.append("OPEN/UNSOLVED/UNCONFIRMED problem must have open_product_target.kind other than not_applicable")

        task_kind = str(data.get("task_kind") or data.get("user_intent") or "").lower()
        state = str(data.get("state") or "")
        artifact_status = (data.get("artifact_target") or {}).get("status")
        has_lovasz_evidence = bool(data.get("proof_dependency_dag") or data.get("worker_results") or data.get("lovasz_barrier_attack"))
        has_lovasz_campaign = bool(
            data.get("actual_lemma_queue")
            and data.get("proof_dependency_dag")
            and data.get("lovasz_barrier_attack")
            and (
                data.get("worker_results")
                or data.get("lovasz_dispatch_blocker")
            )
        )
        blocked = bool(data.get("lovasz_dispatch_blocker"))
        proof_disproof_intent = any(term in task_kind for term in ("prove", "disprove", "solve", "deep"))
        if proof_disproof_intent and state in {"REPORT", "COMPLETE"} and artifact_status in {"OPEN", "CONJECTURE", "FAILED_ATTEMPT", "GAP"}:
            if not has_lovasz_evidence and not blocked:
                errors.append(
                    "OPEN/UNSOLVED/UNCONFIRMED prove/disprove run cannot be complete with status-only report; "
                    "missing Lovasz proof_dependency_dag, worker_results, lovasz_barrier_attack, or lovasz_dispatch_blocker"
                )
            elif not has_lovasz_campaign and not blocked:
                errors.append(
                    "OPEN/UNSOLVED/UNCONFIRMED prove/disprove run cannot be complete with only a Lovasz barrier note; "
                    "missing full campaign evidence: actual_lemma_queue, proof_dependency_dag, lovasz_barrier_attack, "
                    "and worker_results or lovasz_dispatch_blocker"
                )

    check_research_machinery(data, errors)


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def check_research_machinery(data: dict, errors: list[str]) -> None:
    dag = _as_list(data.get("proof_dependency_dag"))
    workers = _as_list(data.get("worker_results"))
    generator_artifacts = _as_list(data.get("generator_artifacts"))
    actual_lemma_queue = _as_list(data.get("actual_lemma_queue"))
    retry_ledger = _as_list(data.get("retry_ledger"))
    skeptic_reviews = _as_list(data.get("skeptic_reviews"))
    if not dag and not workers and not generator_artifacts and not actual_lemma_queue and not retry_ledger and not skeptic_reviews:
        return

    node_ids: set[str] = set()
    graph: dict[str, list[str]] = {}
    allowed_node_types = {
        "lemma",
        "actual_barrier_lemma",
        "reduction",
        "special_case",
        "obstruction",
        "counterexample_search",
        "computational_certificate",
        "conditional_theorem",
        "failed_method",
    }
    allowed_statuses = {
        "VERIFIED",
        "CHECKED",
        "PROVED_SKETCH",
        "PARTIAL",
        "CONDITIONAL",
        "CONJECTURE",
        "FAILED_ATTEMPT",
        "REJECTED",
        "GAP",
        "OPEN",
    }
    accepted_statuses = {"VERIFIED", "CHECKED", "PROVED_SKETCH"}
    review_ids = {r.get("review_id") for r in skeptic_reviews if isinstance(r, dict)}

    if data.get("problem_status") in {"OPEN", "UNSOLVED", "UNCONFIRMED"}:
        if not actual_lemma_queue and not data.get("lovasz_dispatch_blocker"):
            errors.append("OPEN/UNSOLVED/UNCONFIRMED Lovasz handoff must include actual_lemma_queue or lovasz_dispatch_blocker")

        attack = data.get("lovasz_barrier_attack")
        records = _as_list((attack or {}).get("barrier_attack_records")) if isinstance(attack, dict) else []
        if attack and not records:
            errors.append("lovasz_barrier_attack must include barrier_attack_records")
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                errors.append(f"barrier_attack_records[{index}] is not an object")
                continue
            for field in ("actual_barrier_lemma", "counterexample_pressure", "theorem_precondition_gap", "next_exact_attempt"):
                if not record.get(field):
                    errors.append(f"barrier_attack_records[{index}] missing {field}")
            if len(_as_list(record.get("direct_attacks"))) < 2:
                errors.append(f"barrier_attack_records[{index}] must record at least two direct attacks")

    seen_retry: set[tuple[str, str]] = set()
    for index, entry in enumerate(retry_ledger):
        if not isinstance(entry, dict):
            errors.append(f"retry_ledger[{index}] is not an object")
            continue
        key = (str(entry.get("method_family")), str(entry.get("target_hash")))
        changed = str(entry.get("what_changed") or "").strip().lower()
        if key in seen_retry and changed in {"", "none", "unchanged", "same", "no change", "no changes"}:
            errors.append(f"retry_ledger[{index}] repeats method/target without what_changed")
        seen_retry.add(key)

    for index, review in enumerate(skeptic_reviews):
        if not isinstance(review, dict):
            errors.append(f"skeptic_reviews[{index}] is not an object")
            continue
        review_id = review.get("review_id") or f"<index {index}>"
        for field in ("target_drift_checked", "hidden_assumptions_checked", "circularity_checked", "weaker_target_checked"):
            if review.get(field) is not True:
                errors.append(f"skeptic_reviews {review_id!r} must set {field}=true")
        if review.get("verdict") != "pass":
            errors.append(f"skeptic_reviews {review_id!r} verdict must be pass for accepted downstream use")

    for index, node in enumerate(dag):
        if not isinstance(node, dict):
            errors.append(f"proof_dependency_dag[{index}] is not an object")
            continue
        node_id = node.get("node_id") or node.get("id")
        if not isinstance(node_id, str) or not node_id:
            errors.append(f"proof_dependency_dag[{index}] missing node_id")
            continue
        if node_id in node_ids:
            errors.append(f"proof_dependency_dag duplicate node_id {node_id!r}")
        node_ids.add(node_id)
        graph[node_id] = list(node.get("depends_on", [])) if isinstance(node.get("depends_on", []), list) else []

        node_type = node.get("type")
        if node_type not in allowed_node_types:
            errors.append(f"proof_dependency_dag node {node_id!r} has invalid type {node_type!r}")
        status = node.get("status")
        if status not in allowed_statuses:
            errors.append(f"proof_dependency_dag node {node_id!r} has invalid status {status!r}")
        if not node.get("statement"):
            errors.append(f"proof_dependency_dag node {node_id!r} missing statement")
        if node_type in {"actual_barrier_lemma", "lemma", "reduction", "special_case", "conditional_theorem"}:
            if not node.get("relation_to_frozen_target"):
                errors.append(f"proof_dependency_dag node {node_id!r} missing relation_to_frozen_target")
        if node_type in {"special_case", "conditional_theorem"} and not node.get("weaker_variant_justification"):
            errors.append(f"proof_dependency_dag node {node_id!r} is weaker/conditional but lacks weaker_variant_justification")
        if node_type == "actual_barrier_lemma":
            for field in ("counterexample_pressure", "theorem_precondition_gap", "next_exact_attempt"):
                if not node.get(field):
                    errors.append(f"actual_barrier_lemma node {node_id!r} missing {field}")
            if int(node.get("direct_attack_count") or 0) < 2 and status in {"FAILED_ATTEMPT", "OPEN", "GAP"}:
                errors.append(f"actual_barrier_lemma node {node_id!r} must record direct_attack_count >= 2 before failed/open/gap return")
        if status in accepted_statuses:
            fidelity = node.get("target_fidelity")
            if not isinstance(fidelity, (int, float)):
                errors.append(f"accepted proof_dependency_dag node {node_id!r} missing target_fidelity")
            elif fidelity < 0.8 and status != "PARTIAL":
                errors.append(f"accepted proof_dependency_dag node {node_id!r} target_fidelity {fidelity} < 0.8")
            review_id = node.get("skeptic_review_id")
            if not review_id:
                errors.append(f"accepted proof_dependency_dag node {node_id!r} missing skeptic_review_id")
            elif not review_ids:
                errors.append(f"accepted proof_dependency_dag node {node_id!r} has skeptic_review_id but skeptic_reviews is empty")
            elif review_ids and review_id not in review_ids:
                errors.append(f"accepted proof_dependency_dag node {node_id!r} references unknown skeptic_review_id {review_id!r}")
        if status == "VERIFIED":
            evidence = node.get("verification_evidence", {})
            if not isinstance(evidence, dict):
                errors.append(f"VERIFIED node {node_id!r} missing verification_evidence object")
            else:
                for field in ("wit_path", "lean_path", "lean_status", "safeverify_status", "wit_target_sha256", "lean_target_sha256", "frozen_target_sha256"):
                    if not evidence.get(field):
                        errors.append(f"VERIFIED node {node_id!r} missing verification_evidence.{field}")
                if evidence.get("wit_target_sha256") != evidence.get("lean_target_sha256"):
                    errors.append(f"VERIFIED node {node_id!r} WIT and Lean target hashes do not match")
                if evidence.get("wit_target_sha256") != evidence.get("frozen_target_sha256"):
                    errors.append(f"VERIFIED node {node_id!r} WIT target hash does not match frozen target hash")
                if evidence.get("lean_status") != "passed":
                    errors.append(f"VERIFIED node {node_id!r} lean_status must be 'passed'")
                if evidence.get("safeverify_status") != "passed":
                    errors.append(f"VERIFIED node {node_id!r} safeverify_status must be 'passed'")

    for node_id, deps in graph.items():
        for dep in deps:
            if dep not in node_ids:
                errors.append(f"proof_dependency_dag node {node_id!r} depends on unknown node {dep!r}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str, stack: list[str]) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            errors.append(f"proof_dependency_dag contains dependency cycle: {' -> '.join(stack + [node_id])}")
            return
        visiting.add(node_id)
        for dep in graph.get(node_id, []):
            if dep in graph:
                visit(dep, stack + [node_id])
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in graph:
        visit(node_id, [])

    if dag and data.get("problem_status") in {"OPEN", "UNSOLVED", "UNCONFIRMED"}:
        has_actual_barrier_node = any(
            isinstance(node, dict)
            and (
                node.get("type") == "actual_barrier_lemma"
                or bool(node.get("actual_barrier_lemma"))
            )
            for node in dag
        )
        if not has_actual_barrier_node and not data.get("lovasz_dispatch_blocker"):
            errors.append(
                "Lovasz DAG for OPEN/UNSOLVED/UNCONFIRMED target must include an actual_barrier_lemma node "
                "or actual_barrier_lemma field before weaker products are accepted"
            )

    worker_ids: set[str] = set()
    for index, worker in enumerate(workers):
        if not isinstance(worker, dict):
            errors.append(f"worker_results[{index}] is not an object")
            continue
        worker_id = worker.get("worker_id")
        if not isinstance(worker_id, str) or not worker_id:
            errors.append(f"worker_results[{index}] missing worker_id")
        elif worker_id in worker_ids:
            errors.append(f"worker_results duplicate worker_id {worker_id!r}")
        else:
            worker_ids.add(worker_id)

        node_id = worker.get("node_id")
        if node_id and dag and node_id not in node_ids:
            errors.append(f"worker_results {worker_id!r} references unknown node_id {node_id!r}")
        status = worker.get("status")
        if status not in allowed_statuses:
            errors.append(f"worker_results {worker_id!r} has invalid status {status!r}")
        if not worker.get("wit_path"):
            errors.append(f"worker_results {worker_id!r} missing wit_path; workers must generate WIT first")
        for field in ("session_id", "proof_worktree", "proof_worktree_dedicated", "worktree_status"):
            if field not in worker or worker.get(field) in (None, ""):
                errors.append(f"worker_results {worker_id!r} missing {field}; WIT/Lean proof artifacts must be generated in a session-scoped proof worktree")
        if worker.get("proof_worktree_dedicated") is not True:
            errors.append(f"worker_results {worker_id!r} proof_worktree_dedicated must be true")
        if worker.get("worktree_status") not in {"created", "reused_dedicated", "preserved", "cleaned", "cleanup_failed"}:
            errors.append(f"worker_results {worker_id!r} has invalid worktree_status {worker.get('worktree_status')!r}")
        fidelity = worker.get("target_fidelity")
        if status in accepted_statuses:
            if not isinstance(fidelity, (int, float)):
                errors.append(f"accepted worker_results {worker_id!r} missing target_fidelity")
            elif fidelity < 0.8 and status != "PARTIAL":
                errors.append(f"accepted worker_results {worker_id!r} target_fidelity {fidelity} < 0.8")
            review_id = worker.get("skeptic_review_id")
            if not review_id:
                errors.append(f"accepted worker_results {worker_id!r} missing skeptic_review_id")
            elif not review_ids:
                errors.append(f"accepted worker_results {worker_id!r} has skeptic_review_id but skeptic_reviews is empty")
            elif review_ids and review_id not in review_ids:
                errors.append(f"accepted worker_results {worker_id!r} references unknown skeptic_review_id {review_id!r}")
        if status == "VERIFIED":
            for field in ("lean_path", "lean_status", "safeverify_status", "wit_target_sha256", "lean_target_sha256", "frozen_target_sha256"):
                if not worker.get(field):
                    errors.append(f"VERIFIED worker {worker_id!r} missing {field}")
            if worker.get("wit_target_sha256") != worker.get("lean_target_sha256"):
                errors.append(f"VERIFIED worker {worker_id!r} WIT and Lean target hashes do not match")
            if worker.get("wit_target_sha256") != worker.get("frozen_target_sha256"):
                errors.append(f"VERIFIED worker {worker_id!r} WIT target hash does not match frozen target hash")
        elif worker.get("lean_path"):
            for field in ("wit_target_sha256", "lean_target_sha256", "frozen_target_sha256"):
                if not worker.get(field):
                    errors.append(f"Lean worker {worker_id!r} missing {field}")
            if worker.get("wit_target_sha256") != worker.get("lean_target_sha256"):
                errors.append(f"Lean worker {worker_id!r} WIT and Lean target hashes do not match")
        if worker.get("created_lean_project") and not worker.get("cleanup_status"):
            errors.append(f"worker_results {worker_id!r} created Lean project but lacks cleanup_status")

    for index, artifact in enumerate(generator_artifacts):
        if not isinstance(artifact, dict):
            errors.append(f"generator_artifacts[{index}] is not an object")
            continue
        artifact_id = artifact.get("artifact_id") or f"<index {index}>"
        for field in ("session_id", "proof_worktree", "proof_worktree_dedicated", "worktree_status", "wit_path", "status"):
            if field not in artifact or artifact.get(field) in (None, ""):
                errors.append(f"generator_artifacts {artifact_id!r} missing {field}; final WIT/Lean artifacts must be generated in a session-scoped proof worktree")
        if artifact.get("proof_worktree_dedicated") is not True:
            errors.append(f"generator_artifacts {artifact_id!r} proof_worktree_dedicated must be true")
        if artifact.get("worktree_status") not in {"created", "reused_dedicated", "preserved", "cleaned", "cleanup_failed"}:
            errors.append(f"generator_artifacts {artifact_id!r} has invalid worktree_status {artifact.get('worktree_status')!r}")
        status = artifact.get("status")
        if status in accepted_statuses:
            fidelity = artifact.get("target_fidelity")
            if not isinstance(fidelity, (int, float)):
                errors.append(f"accepted generator_artifacts {artifact_id!r} missing target_fidelity")
            elif fidelity < 0.8 and status != "PARTIAL":
                errors.append(f"accepted generator_artifacts {artifact_id!r} target_fidelity {fidelity} < 0.8")
            review_id = artifact.get("skeptic_review_id")
            if not review_id:
                errors.append(f"accepted generator_artifacts {artifact_id!r} missing skeptic_review_id")
            elif not review_ids:
                errors.append(f"accepted generator_artifacts {artifact_id!r} has skeptic_review_id but skeptic_reviews is empty")
            elif review_ids and review_id not in review_ids:
                errors.append(f"accepted generator_artifacts {artifact_id!r} references unknown skeptic_review_id {review_id!r}")
        if artifact.get("status") == "VERIFIED":
            for field in ("lean_path", "lean_status", "safeverify_status", "wit_target_sha256", "lean_target_sha256", "frozen_target_sha256"):
                if not artifact.get(field):
                    errors.append(f"VERIFIED generator_artifacts {artifact_id!r} missing {field}")
            if artifact.get("wit_target_sha256") != artifact.get("lean_target_sha256"):
                errors.append(f"VERIFIED generator_artifacts {artifact_id!r} WIT and Lean target hashes do not match")
            if artifact.get("wit_target_sha256") != artifact.get("frozen_target_sha256"):
                errors.append(f"VERIFIED generator_artifacts {artifact_id!r} WIT target hash does not match frozen target hash")
        elif artifact.get("lean_path"):
            for field in ("wit_target_sha256", "lean_target_sha256", "frozen_target_sha256"):
                if not artifact.get(field):
                    errors.append(f"Lean generator_artifacts {artifact_id!r} missing {field}")
            if artifact.get("wit_target_sha256") != artifact.get("lean_target_sha256"):
                errors.append(f"Lean generator_artifacts {artifact_id!r} WIT and Lean target hashes do not match")

    final_assembly = data.get("final_assembly_check")
    if isinstance(final_assembly, dict):
        for field in (
            "dependencies_covered",
            "no_cycles",
            "no_hidden_assumptions",
            "target_hashes_match",
            "no_conjecture_used_as_theorem",
        ):
            if final_assembly.get(field) is not True:
                errors.append(f"final_assembly_check.{field} must be true")

    if generator_artifacts:
        audit = data.get("final_synthesis_audit")
        if not isinstance(audit, dict):
            errors.append("generator_artifacts require final_synthesis_audit")
        else:
            for field in (
                "all_dag_edges_compose",
                "no_conjecture_used_as_theorem",
                "no_hidden_assumptions",
                "no_weaker_theorem_substituted",
                "external_preconditions_discharged",
                "target_hashes_match",
                "wit_lean_hashes_match",
            ):
                if audit.get(field) is not True:
                    errors.append(f"final_synthesis_audit.{field} must be true")


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
