#!/usr/bin/env python3
"""Preflight gate before Generator writes a new proof artifact."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def run_check(script: str, args: list[str], name: str) -> dict[str, Any]:
    cmd = [sys.executable, str(SCRIPT_DIR / script), *args] if script.endswith(".py") else ["bash", str(SCRIPT_DIR / script), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
    return {
        "name": name,
        "command": cmd,
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def owner_for(message: str) -> str:
    m = message.lower()
    if "route" in m or "target hash" in m or "explorer" in m or "source" in m:
        return "Explorer"
    if "lovasz" in m or "dag" in m or "open" in m or "barrier" in m:
        return "Lovasz"
    if "toolchain" in m or "lean" in m:
        return "Toolchain"
    return "Generator"


def preflight(run: Path, *, existing_artifact_repair: bool = False) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    handoff = run / "handoff_v1.json"
    if not handoff.exists() and not existing_artifact_repair:
        blockers.append({"owner": "Explorer", "message": "handoff_v1.json is required before new Generator artifacts"})
    if handoff.exists():
        args = [str(handoff), "--manifest-out", str(run / "generator_handoff_validation.json")]
        route = run / "witsoc_route_state.json"
        if route.exists():
            args.extend(["--route-state", str(route)])
        if existing_artifact_repair:
            args.append("--existing-artifact-repair")
        checks.append(run_check("validate_generator_handoff.py", args, "validate_generator_handoff"))
    if (run / "explorer_return_packet.json").exists() and not existing_artifact_repair:
        checks.append(run_check("validate_explorer_review.py", [str(run), "--out", str(run / "explorer_review_validation.json")], "validate_explorer_review"))
    if (run / "proof_dependency_dag.json").exists():
        checks.append(run_check("validate_proof_dag_integrity.py", [str(run)], "validate_dag_integrity"))
    if (run / "witsoc_research_state.json").exists() or not existing_artifact_repair:
        checks.append(run_check("validate_research_state.py", [str(run), "--mode", "balanced"], "validate_research_state"))
    for check in checks:
        if not check["ok"]:
            text = (check.get("stderr") or check.get("stdout") or check["name"]).strip()
            blockers.append({"owner": owner_for(text), "message": f"{check['name']} failed: {text[:500]}"})
    result = {
        "schema": "witsoc.generator_preflight.v1",
        "run_dir": str(run),
        "existing_artifact_repair": existing_artifact_repair,
        "allowed": not blockers,
        "blockers": blockers,
        "checks": checks,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--existing-artifact-repair", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    result = preflight(args.run_dir, existing_artifact_repair=args.existing_artifact_repair)
    out = args.out or (args.run_dir / "generator_preflight.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
