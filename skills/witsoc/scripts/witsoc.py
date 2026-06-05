#!/usr/bin/env python3
"""Unified Witsoc command-line entrypoint."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def run_script(script: str, args: list[str]) -> int:
    path = SCRIPT_DIR / script
    if script.endswith(".py"):
        cmd = [sys.executable, str(path), *args]
    else:
        cmd = ["bash", str(path), *args]
    return subprocess.call(cmd)


def main() -> int:
    passthrough = {
        "init": "init.sh",
        "check": "check.sh",
        "verify": "verify.sh",
        "context": "context.sh",
        "status": "status.sh",
        "validate-route-state": "validate_route_state.py",
        "validate-run": "validate_lovasz_run.py",
        "artifacts": "artifacts.py",
        "validate-generator-handoff": "validate_generator_handoff.py",
        "lint-wit": "lint_wit_quality.py",
        "score-lovasz": "score_lovasz_results.py",
        "summarize-lovasz": "summarize_lovasz_run.py",
        "generator-manifest": "generator_manifest.py",
        "validate-open-problem": "validate_open_problem_run.py",
        "open-problem-report": "open_problem_report.py",
        "synthesize-ledgers": "synthesize_open_ledgers.py",
        "validate-dag-integrity": "validate_proof_dag_integrity.py",
        "spawn-workers": "spawn_workers_from_dag.py",
        "formalization-feasibility": "formalization_feasibility.py",
        "counterexample-search": "counterexample_search.py",
        "result-ladder": "result_ladder.py",
        "soc-memory": "lovasz_soc_memory.py",
        "worker-dispatch": "lovasz_worker_dispatch.py",
        "grade-report": "grade_witsoc_report.py",
        "decompose-problem": "decompose_problem.py",
        "lovasz-manifest": "lovasz_run_manifest.py",
        "validate-lovasz-phase": "validate_lovasz_phase.py",
        "status-lattice": "status_lattice.py",
        "explorer-return": "explorer_return_packet.py",
    }
    if len(sys.argv) >= 2 and sys.argv[1] in passthrough:
        return run_script(passthrough[sys.argv[1]], sys.argv[2:])

    parser = argparse.ArgumentParser(prog="witsoc")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_route = sub.add_parser("route")
    p_route.add_argument("prompt", nargs="*")
    p_route.add_argument("--field", choices=["route", "announcement", "reason", "chain", "confidence", "state", "json"], default="json")
    p_route.add_argument("--state-out", default=None)
    p_route.add_argument("--no-state", action="store_true")

    for cmd in passthrough:
        sub.add_parser(cmd)

    args = parser.parse_args()

    if args.cmd == "route":
        route_args = ["--field", args.field]
        if args.state_out:
            route_args += ["--state-out", args.state_out]
        if args.no_state:
            route_args += ["--no-state"]
        route_args += args.prompt
        return run_script("route.py", route_args)
    if args.cmd in passthrough:
        return run_script(passthrough[args.cmd], [])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
