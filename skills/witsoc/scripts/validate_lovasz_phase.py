#!/usr/bin/env python3
"""Validate Lovasz manifest phase gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from lovasz_run_manifest import ALLOWED_NEXT, PHASE_REQUIREMENTS, PHASES, nonempty


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--to-phase", choices=PHASES, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    run = args.run_dir
    manifest = load(run / "lovasz_run.json", {})
    errors: list[str] = []
    phase = str(manifest.get("phase") or "")
    if phase not in PHASES:
        errors.append("lovasz_run.json missing valid phase")
    for required in PHASE_REQUIREMENTS.get(phase, []):
        if not nonempty(run / required):
            errors.append(f"phase {phase} requires nonempty {required}")
    if phase != "EXPLORER_PACKET_REQUIRED" and not manifest.get("target_hash"):
        errors.append("target_hash is required after EXPLORER_PACKET_REQUIRED")
    if args.to_phase:
        allowed = ALLOWED_NEXT.get(phase, [])
        if args.to_phase not in allowed:
            errors.append(f"illegal phase transition {phase} -> {args.to_phase}; allowed next: {allowed}")
        if args.to_phase == "WORKERS_DISPATCHED":
            import campaign_budget_gate as bg
            budget = bg.check(run)
            if not budget["dispatch_allowed"]:
                errors.append(f"campaign budget gate blocks dispatch: {budget['required_action']}")
    result = {"valid": not errors, "phase": phase, "errors": errors}
    if args.json:
        print(json.dumps(result, indent=2))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        print("VALID_LOVASZ_PHASE")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
