#!/usr/bin/env python3
"""Draft open-problem ledgers from Lovasz/Explorer notes.

This is a deterministic convenience tool. It extracts explicitly marked lines
from research notes; it does not infer mathematical truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


MARKERS = {
    "lemma": re.compile(r"^\s*(?:[-*]\s*)?(?:ACTUAL[_ -]LEMMA|BARRIER[_ -]LEMMA|MISSING[_ -]LEMMA)\s*:\s*(.+)$", re.I),
    "failure": re.compile(r"^\s*(?:[-*]\s*)?(?:FAILED[_ -]METHOD|FAILURE)\s*:\s*(.+)$", re.I),
    "theorem": re.compile(r"^\s*(?:[-*]\s*)?(?:THEOREM[_ -]CANDIDATE|RETRIEVAL)\s*:\s*(.+)$", re.I),
    "mutation": re.compile(r"^\s*(?:[-*]\s*)?(?:MUTATION|RETRY)\s*:\s*(.+)$", re.I),
    "product": re.compile(r"^\s*(?:[-*]\s*)?(?:PRODUCT|RESEARCH[_ -]PRODUCT)\s*:\s*(.+)$", re.I),
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_notes(run: Path, extra: list[Path]) -> list[str]:
    paths = [run / "research.md", run / "proof-dag.md", run / "barriers.md", *extra]
    lines: list[str] = []
    for path in paths:
        if path.exists():
            lines.extend(path.read_text(encoding="utf-8").splitlines())
    return lines


def write_json_if_empty(path: Path, value: object, force: bool) -> None:
    if path.exists() and not force:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing:
                return
        except Exception:
            return
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--notes", type=Path, action="append", default=[])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    run = args.run_dir
    run.mkdir(parents=True, exist_ok=True)
    lines = read_notes(run, args.notes)

    lemmas = []
    failures = []
    theorem_audit = []
    mutations = []
    products = []

    for line in lines:
        if m := MARKERS["lemma"].match(line):
            statement = m.group(1).strip()
            lemmas.append({
                "statement": statement,
                "why_it_matters": "DRAFT: fill why this directly advances the frozen target.",
                "unlocks": ["DRAFT: target dependency unlocked by this lemma"],
                "known_counterexamples_or_boundary_cases": ["DRAFT: add boundary cases checked"],
                "failed_approaches": ["DRAFT: add failed approaches"],
                "next_mutation": "DRAFT: next exact mutation to try",
                "smallest_formalizable_subcase": "DRAFT: smallest subcase suitable for WIT/Lean",
                "status": "OPEN",
            })
        elif m := MARKERS["failure"].match(line):
            text = m.group(1).strip()
            failures.append({
                "statement_hash": sha(text),
                "method_family": "DRAFT",
                "why_failed": text,
                "blocker_or_counterexample": "DRAFT: exact blocker/counterexample",
                "retry_condition": "DRAFT: what must change before retry",
            })
        elif m := MARKERS["theorem"].match(line):
            text = m.group(1).strip()
            theorem_audit.append({
                "target_subgoal": "DRAFT",
                "candidate_theorem": text,
                "exact_statement": "DRAFT: exact theorem statement",
                "required_preconditions": [],
                "missing_preconditions": [],
                "formal_availability": "unknown",
                "use_decision": "search_more",
            })
        elif m := MARKERS["mutation"].match(line):
            text = m.group(1).strip()
            mutations.append({
                "target_hash": "DRAFT",
                "method_family": "DRAFT",
                "previous_attempt_id": "DRAFT",
                "new_attempt_id": sha(text)[:12],
                "axis_changed": "method",
                "what_changed": text,
                "why_this_is_not_repeat": "DRAFT: explain the one-axis change",
                "result": "DRAFT",
            })
        elif m := MARKERS["product"].match(line):
            text = m.group(1).strip()
            products.append({
                "kind": "partial_result",
                "statement": text,
                "why_this_helps_original": "DRAFT: explain dependency back to target",
                "dependency_path_to_target": ["DRAFT product", "DRAFT target"],
                "verification_plan": "DRAFT: WIT/check/Lean/computation plan",
                "status": "PLANNED",
                "selected": not products,
            })

    write_json_if_empty(run / "actual_lemma_queue.json", lemmas, args.force)
    write_json_if_empty(run / "theorem_precondition_audit.json", theorem_audit, args.force)
    write_json_if_empty(run / "mutation_ledger.json", mutations, args.force)
    write_json_if_empty(run / "product_selection.json", products, args.force)

    failure_path = run / "failure_memory.jsonl"
    if failures and (args.force or not failure_path.exists() or not failure_path.read_text(encoding="utf-8").strip()):
        failure_path.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in failures), encoding="utf-8")

    print(json.dumps({
        "actual_lemmas": len(lemmas),
        "failures": len(failures),
        "theorem_candidates": len(theorem_audit),
        "mutations": len(mutations),
        "products": len(products),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
