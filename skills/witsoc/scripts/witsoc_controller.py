#!/usr/bin/env python3
"""Witsoc-only run controller and final status gate.

The controller composes existing Witsoc scripts into a fail-closed workflow so
the skill can enforce its own discipline even when the surrounding orchestrator
only invokes Witsoc as a normal skill.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def narrate(result: dict) -> str:
    """Plain-language 'you are here / what happened / what's next' for a
    controller result. Pure presentation over the gate records — it can only
    restate the outcome, never change a gate verdict."""
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        import witsoc_narrate
        return witsoc_narrate.controller_human(result)
    except Exception:
        status = result.get("status", {}) or {}
        fail = status.get("failed_gates") or []
        if fail:
            return f"Run halted at gate: {fail[0]}. See witsoc_run_controller.json for detail."
        return f"Final status: {status.get('final_status', '?')}."


def records(path: Path) -> list[dict]:
    value = load(path, [])
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def has_generator_artifacts(run: Path) -> bool:
    registry = load(run / "witsoc_artifacts.json", {})
    artifacts = registry.get("artifacts", []) if isinstance(registry, dict) else []
    if any(isinstance(a, dict) and str(a.get("type") or "").lower() in {"wit", "lean"} for a in artifacts):
        return True
    return (run / "generator_package.json").exists()


def command_for(script: str, args: list[str]) -> list[str]:
    path = SCRIPT_DIR / script
    if script.endswith(".py"):
        return [sys.executable, str(path), *args]
    return ["bash", str(path), *args]


def run_gate(run: Path, gate: str, script: str, args: list[str], *, timeout: int = 300) -> dict:
    logs = run / "controller_logs"
    logs.mkdir(parents=True, exist_ok=True)
    cmd = command_for(script, args)
    started = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
        error = ""
    except Exception as exc:
        stdout = ""
        stderr = ""
        exit_code = 124
        error = str(exc)
    safe_gate = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in gate)
    stdout_path = logs / f"{safe_gate}.stdout"
    stderr_path = logs / f"{safe_gate}.stderr"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    return {
        "gate": gate,
        "script": script,
        "command": cmd,
        "exit_code": exit_code,
        "ok": exit_code == 0,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "error": error,
        "duration_ms": round((time.time() - started) * 1000, 2),
    }


def required_status(statuses: set[str]) -> str:
    if statuses & {"VERIFIED_LEAN", "VERIFIED_WIT", "VERIFIED_EXTERNAL", "VERIFIED"}:
        return "VERIFIED_PARTIAL"
    if statuses & {"CHECKED", "CHECKED_BOUNDED", "CHECKED_SYMBOLIC"}:
        return "CHECKED_BOUNDED"
    if "CONDITIONAL" in statuses:
        return "CONDITIONAL"
    if "PARTIAL" in statuses:
        return "VERIFIED_PARTIAL"
    if "CONJECTURE" in statuses:
        return "CONJECTURE"
    if statuses and statuses <= {"FAILED_ATTEMPT", "REJECTED", "DEMOTED"}:
        return "FAILED_ATTEMPT"
    return "STILL_OPEN"


def synthesize_status(run: Path, gate_results: list[dict]) -> dict:
    failed = [g for g in gate_results if not g.get("ok")]
    solve_claim = load(run / "solve_claim.json", {})
    if isinstance(solve_claim, dict) and solve_claim.get("status") == "SOLVE_ACCEPTED":
        final_status = "VERIFIED_FULL_SOLUTION"
    elif failed:
        final_status = "FAILED_GATE"
    else:
        statuses = {str(x.get("status") or "").strip().upper() for x in records(run / "proof_dependency_dag.json")}
        statuses |= {str(x.get("status") or "").strip().upper() for x in records(run / "worker_results.json")}
        final_status = required_status(statuses)
    return {
        "schema": "witsoc.final_status.v1",
        "run_dir": str(run),
        "final_status": final_status,
        "failed_gates": [g["gate"] for g in failed],
        "solve_claim_status": solve_claim.get("status") if isinstance(solve_claim, dict) else None,
        "accepted_products": [
            {
                "node_id": n.get("node_id") or n.get("id"),
                "statement": n.get("statement"),
                "status": n.get("status"),
            }
            for n in records(run / "proof_dependency_dag.json")
            if str(n.get("status") or "").strip().upper()
            in {"VERIFIED", "VERIFIED_WIT", "VERIFIED_LEAN", "VERIFIED_EXTERNAL", "CHECKED", "CHECKED_BOUNDED", "CHECKED_SYMBOLIC", "PARTIAL", "CONDITIONAL"}
        ],
    }


def finalize(run: Path, *, require_route: bool = False) -> dict:
    gates: list[dict] = []
    if require_route and (run / "witsoc_route_state.json").exists():
        gates.append(run_gate(run, "route_state_final", "validate_route_state.py",
                              [str(run / "witsoc_route_state.json"), "--for-final-report"]))
    gates.extend([
        run_gate(run, "lovasz_manifest", "lovasz_run_manifest.py", [str(run)]),
        run_gate(run, "lovasz_phase", "validate_lovasz_phase.py", [str(run)]),
        run_gate(run, "open_problem", "validate_open_problem_run.py", [str(run)]),
        run_gate(run, "dag_integrity", "validate_proof_dag_integrity.py", [str(run)]),
        run_gate(run, "status_lattice", "status_lattice.py", [str(run)]),
        run_gate(run, "campaign_finalize", "campaign_driver.py", [str(run), "--finalize"]),
        run_gate(run, "research_state", "research_state.py",
                 [str(run), "--out", str(run / "witsoc_research_state.json")]),
        run_gate(run, "validate_research_state", "validate_research_state.py",
                 [str(run), "--out", str(run / "research_state_validation.json")]),
        run_gate(run, "explorer_review", "validate_explorer_review.py",
                 [str(run), "--out", str(run / "explorer_review_validation.json")]),
        run_gate(run, "lovasz_run", "validate_lovasz_run.py", [str(run), "--mode", "deep"]),
        run_gate(run, "report_grade", "grade_witsoc_report.py", [str(run), "--out", str(run / "report_quality_grade.json")]),
    ])
    if has_generator_artifacts(run):
        gates.append(run_gate(run, "generator_receipt", "generator_receipt_gate.py",
                              [str(run), "--out", str(run / "generator_artifact_receipt.json")]))
    status = synthesize_status(run, gates)
    result = {
        "schema": "witsoc.controller.finalize.v1",
        "run_dir": str(run),
        "valid": not any(not g["ok"] for g in gates),
        "gates": gates,
        "status": status,
    }
    result["narration"] = narrate(result)
    dump(run / "witsoc_final_status.json", status)
    dump(run / "witsoc_run_controller.json", result)
    return result


def run_open(args: argparse.Namespace) -> dict:
    run = args.run_dir
    run.mkdir(parents=True, exist_ok=True)
    gates: list[dict] = []
    gates.append(run_gate(run, "route", "route.py",
                          [args.prompt, "--field", "json", "--state-out", str(run / "witsoc_route_state.json")]))
    gates.append(run_gate(run, "manifest", "lovasz_run_manifest.py", [str(run), "--target", args.prompt]))
    gates.append(run_gate(run, "decompose", "decompose_problem.py",
                          [str(run), "--target", args.prompt, "--write", "--out", str(run / "problem_decomposition.json")]))
    gates.append(run_gate(run, "synthesize_ledgers", "synthesize_open_ledgers.py", [str(run)]))
    gates.append(run_gate(run, "counterexample_packets", "counterexample_search.py",
                          [str(run), "--out", str(run / "counterexample_search_templates.json")]))
    gates.append(run_gate(run, "manifest_after_seed", "lovasz_run_manifest.py", [str(run), "--target", args.prompt]))
    gates.append(run_gate(run, "validate_open_problem", "validate_open_problem_run.py", [str(run)]))
    gates.append(run_gate(run, "validate_dag_integrity", "validate_proof_dag_integrity.py", [str(run)]))
    if all(g["ok"] for g in gates[-2:]) and args.loops > 0:
        campaign_args = [str(run), "--loops", str(args.loops), "--limit", str(args.limit)]
        if args.workers is not None:
            campaign_args.extend(["--workers", str(args.workers)])
        gates.append(run_gate(run, "campaign_loop", "campaign_driver.py",
                              campaign_args, timeout=args.timeout))
    else:
        gates.append({
            "gate": "campaign_loop",
            "script": "campaign_driver.py",
            "command": [],
            "exit_code": 1,
            "ok": False,
            "stdout_path": "",
            "stderr_path": "",
            "error": "skipped because prerequisite validation failed or loops=0",
            "duration_ms": 0,
        })
    final = finalize(run, require_route=True)
    gates.extend(final["gates"])
    status = synthesize_status(run, gates)
    result = {
        "schema": "witsoc.controller.run_open.v1",
        "run_dir": str(run),
        "prompt": args.prompt,
        "valid": not any(not g["ok"] for g in gates),
        "gates": gates,
        "status": status,
        "next_repair": next((g for g in gates if not g["ok"]), None),
    }
    result["narration"] = narrate(result)
    dump(run / "witsoc_final_status.json", status)
    dump(run / "witsoc_run_controller.json", result)
    return result


def validate_all(args: argparse.Namespace) -> dict:
    run = args.run_dir
    gates = [
        run_gate(run, "research_state", "research_state.py",
                 [str(run), "--out", str(run / "witsoc_research_state.json")]),
        run_gate(run, "validate_research_state", "validate_research_state.py",
                 [str(run), "--out", str(run / "research_state_validation.json")]),
        run_gate(run, "lovasz_phase", "validate_lovasz_phase.py", [str(run)]),
        run_gate(run, "open_problem", "validate_open_problem_run.py", [str(run)]),
        run_gate(run, "dag_integrity", "validate_proof_dag_integrity.py", [str(run)]),
        run_gate(run, "status_lattice", "status_lattice.py", [str(run)]),
        run_gate(run, "lovasz_run", "validate_lovasz_run.py", [str(run), "--mode", args.mode]),
    ]
    result = {
        "schema": "witsoc.controller.validate_all.v1",
        "run_dir": str(run),
        "valid": not any(not g["ok"] for g in gates),
        "gates": gates,
        "status": synthesize_status(run, gates),
    }
    result["narration"] = narrate(result)
    dump(run / "witsoc_run_controller.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run-open")
    p_run.add_argument("run_dir", type=Path)
    p_run.add_argument("--prompt", required=True)
    p_run.add_argument("--loops", type=int, default=0,
                       help="0 means adaptive Lovasz loop until stop conditions")
    p_run.add_argument("--limit", type=int, default=0,
                       help="0 means all currently eligible Lovasz DAG nodes")
    p_run.add_argument("--workers", type=int, default=None,
                       help="local prover thread fanout, not Lovasz subagent fanout (default: WITSOC_PROVER_WORKERS or 4; capped at 10)")
    p_run.add_argument("--timeout", type=int, default=600)

    p_final = sub.add_parser("finalize")
    p_final.add_argument("run_dir", type=Path)
    p_final.add_argument("--require-route", action="store_true")

    p_validate = sub.add_parser("validate-all")
    p_validate.add_argument("run_dir", type=Path)
    p_validate.add_argument("--mode", choices=["quick", "deep", "campaign"], default="deep")

    args = parser.parse_args()
    if args.cmd == "run-open":
        result = run_open(args)
    elif args.cmd == "finalize":
        result = finalize(args.run_dir, require_route=args.require_route)
    else:
        result = validate_all(args)
    # Human narration on stderr (so a person sees what happened and what's next);
    # machine-readable JSON on stdout (the `narration` field is also embedded).
    if result.get("narration"):
        print(result["narration"], file=sys.stderr)
        print("", file=sys.stderr)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
