#!/usr/bin/env python3
"""Validate Lovasz claim-status labels and status upgrades."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from status_vocab import (
    ACCEPTED_STATUSES as ACCEPTED,
    ALL_STATUSES as STATUSES,
    alias as normalize,
)

TRANSITIONS = {
    "DRAFT": {"OPEN", "CONJECTURE", "FAILED_ATTEMPT", "REJECTED"},
    "OPEN": {"CONJECTURE", "CHECKED_BOUNDED", "FAILED_ATTEMPT", "REJECTED", "GAP"},
    "CONJECTURE": {"CHECKED_BOUNDED", "CHECKED_SYMBOLIC", "PROVED_SKETCH", "FAILED_ATTEMPT", "REJECTED", "DEMOTED", "GAP"},
    "CHECKED_BOUNDED": {"CHECKED_SYMBOLIC", "PROVED_SKETCH", "PARTIAL", "CONDITIONAL", "FAILED_ATTEMPT", "DEMOTED"},
    "CHECKED_SYMBOLIC": {"PROVED_SKETCH", "VERIFIED_WIT", "VERIFIED_LEAN", "VERIFIED_EXTERNAL", "PARTIAL", "CONDITIONAL", "DEMOTED"},
    "PROVED_SKETCH": {"VERIFIED_WIT", "VERIFIED_LEAN", "VERIFIED_EXTERNAL", "PARTIAL", "CONDITIONAL", "DEMOTED"},
    "VERIFIED_WIT": {"VERIFIED_LEAN", "VERIFIED_EXTERNAL", "DEMOTED"},
    "VERIFIED_LEAN": {"DEMOTED"},
    "VERIFIED_EXTERNAL": {"DEMOTED"},
    "PARTIAL": {"VERIFIED_WIT", "VERIFIED_EXTERNAL", "DEMOTED"},
    "CONDITIONAL": {"VERIFIED_WIT", "VERIFIED_EXTERNAL", "DEMOTED"},
    "FAILED_ATTEMPT": {"OPEN", "CONJECTURE", "DEMOTED"},
    "REJECTED": {"DEMOTED"},
    "DEMOTED": {"OPEN", "CONJECTURE"},
    "GAP": {"OPEN", "CONJECTURE", "FAILED_ATTEMPT", "DEMOTED"},
    "PLANNED": {"SELECTED", "READY", "FAILED_ATTEMPT", "REJECTED"},
    "SELECTED": {"READY", "PARTIAL", "CONDITIONAL", "FAILED_ATTEMPT", "REJECTED"},
    "READY": {"VERIFIED_WIT", "VERIFIED_EXTERNAL", "DEMOTED"},
}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def records(path: Path) -> list[dict]:
    data = load(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def evidence_present(record: dict) -> bool:
    for key in ("evidence", "receipt_ids", "receipts", "artifacts", "skeptic_review_id"):
        if record.get(key) not in (None, "", []):
            return True
    return False


def check_record(label: str, record: dict, errors: list[str]) -> None:
    status = normalize(record.get("status"))
    if not status:
        errors.append(f"{label} missing status")
        return
    if status not in STATUSES:
        errors.append(f"{label} has invalid status {record.get('status')!r}")
        return
    previous = normalize(record.get("previous_status"))
    if previous:
        if previous not in STATUSES:
            errors.append(f"{label} has invalid previous_status {record.get('previous_status')!r}")
        elif status != previous and status not in TRANSITIONS.get(previous, set()):
            errors.append(f"{label} illegal transition {previous} -> {status}")
    if status in ACCEPTED and not evidence_present(record):
        errors.append(f"{label} accepted status {status} requires evidence, receipt, artifact, or skeptic review")
    if status in {"VERIFIED_WIT", "VERIFIED_LEAN", "VERIFIED_EXTERNAL"} and not record.get("target_hash"):
        errors.append(f"{label} verified status requires target_hash")
    if status == "VERIFIED_LEAN":
        evidence = record.get("evidence")
        if isinstance(evidence, dict):
            if evidence.get("lean_status") not in {"passed", "ok", "valid"}:
                errors.append(f"{label} VERIFIED_LEAN evidence must include lean_status passed/ok/valid")
            if evidence.get("safeverify_status") not in {"passed", "ok", "valid"}:
                errors.append(f"{label} VERIFIED_LEAN evidence must include safeverify_status passed/ok/valid")


def validate_run(run: Path) -> list[str]:
    errors: list[str] = []
    sources = {
        "proof_dependency_dag": records(run / "proof_dependency_dag.json"),
        "worker_results": records(run / "worker_results.json"),
        "actual_lemma_queue": records(run / "actual_lemma_queue.json"),
        "product_selection": records(run / "product_selection.json"),
    }
    for source, items in sources.items():
        for index, record in enumerate(items):
            ident = record.get("node_id") or record.get("worker_id") or record.get("claim_id") or record.get("id") or index
            check_record(f"{source}[{ident!r}]", record, errors)
    transitions = records(run / "status_transitions.json")
    for index, transition in enumerate(transitions):
        previous = normalize(transition.get("from"))
        current = normalize(transition.get("to"))
        if previous not in STATUSES:
            errors.append(f"status_transitions[{index}] invalid from={transition.get('from')!r}")
        if current not in STATUSES:
            errors.append(f"status_transitions[{index}] invalid to={transition.get('to')!r}")
        if previous in STATUSES and current in STATUSES and current != previous and current not in TRANSITIONS.get(previous, set()):
            errors.append(f"status_transitions[{index}] illegal transition {previous} -> {current}")
        if current in ACCEPTED and transition.get("receipt_id") in (None, ""):
            errors.append(f"status_transitions[{index}] accepted upgrade requires receipt_id")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path, nargs="?")
    parser.add_argument("--from-status", dest="from_status")
    parser.add_argument("--to-status", dest="to_status")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.from_status or args.to_status:
        previous = normalize(args.from_status)
        current = normalize(args.to_status)
        ok = previous in STATUSES and current in STATUSES and (current == previous or current in TRANSITIONS.get(previous, set()))
        result = {"from": previous, "to": current, "allowed": ok}
        print(json.dumps(result, indent=2))
        return 0 if ok else 1

    if not args.run_dir:
        print("run_dir or --from-status/--to-status required", file=sys.stderr)
        return 2
    errors = validate_run(args.run_dir)
    if args.json:
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        print("VALID_STATUS_LATTICE")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
