#!/usr/bin/env python3
"""Validate Witsoc route-state completion gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


LOVASZ = "witsoc-research-lovasz"
EXPLORER = "witsoc-explorer"
GENERATOR = "witsoc-generator"

DONE_STATUSES = {"done", "completed", "complete", "skipped_with_blocker", "blocked"}


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"INVALID_ROUTE_STATE: cannot read {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit("INVALID_ROUTE_STATE: expected JSON object")
    return data


def phase_statuses(state: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for phase in state.get("phases", []):
        if not isinstance(phase, dict):
            continue
        name = str(phase.get("phase") or "")
        status = str(phase.get("status") or "pending")
        out.setdefault(name, []).append(status)
    return out


def any_done(statuses: list[str]) -> bool:
    return any(status in DONE_STATUSES for status in statuses)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    parser.add_argument("--for-final-report", action="store_true")
    parser.add_argument("--for-generator", action="store_true")
    parser.add_argument("--allow-blocked", action="store_true")
    args = parser.parse_args()

    state = load_json(args.state)
    errors: list[str] = []
    statuses = phase_statuses(state)
    blockers = state.get("blockers") or []
    has_blocker = bool(blockers)

    if state.get("lovasz_required"):
        chain = state.get("chain") or []
        if chain[:3] != [EXPLORER, LOVASZ, EXPLORER]:
            errors.append("Lovasz-required route must start Explorer -> Lovasz -> Explorer")
        if not any_done(statuses.get(LOVASZ, [])):
            errors.append("Lovasz is required but has no completed/blocked phase status")
        if state.get("requires_explorer_review_after_lovasz") and len(statuses.get(EXPLORER, [])) < 2:
            errors.append("Lovasz route requires a second Explorer review phase")
        explorer_statuses = statuses.get(EXPLORER, [])
        if state.get("requires_explorer_review_after_lovasz") and not any_done(explorer_statuses[1:]):
            errors.append("Explorer review after Lovasz is required but not completed")

    if args.for_generator and not state.get("generator_authorized"):
        errors.append("Generator is not authorized by route state")

    if args.for_final_report:
        for phase in state.get("phases", []):
            if not isinstance(phase, dict) or not phase.get("must_not_skip"):
                continue
            status = str(phase.get("status") or "pending")
            if status not in DONE_STATUSES:
                errors.append(f"required phase {phase.get('phase')!r} is not complete: {status}")

    if errors and args.allow_blocked and has_blocker:
        print("VALID_ROUTE_STATE_WITH_BLOCKER")
        return 0

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("VALID_ROUTE_STATE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
