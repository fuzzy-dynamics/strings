#!/usr/bin/env python3
"""Advisory Witsoc planning packets for an external orchestrator.

This is intentionally runtime-agnostic. It does not spawn agents, choose
budgets, or enforce a fixed workflow. It converts Witsoc route/run ledgers into
decision-support packets: candidate lanes, evidence gates, UI state, and report
expectations. The orchestrator remains in charge of strategy.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import route as route_mod  # noqa: E402


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def report_contract() -> dict[str, object]:
    return {
        "schema": "witsoc.report_contract.v1",
        "orchestrator_authority": "The orchestrator chooses report emphasis and narrative; Witsoc gates police honesty.",
        "required_sections_for_deep_runs": [
            "Frozen Target",
            "Route And Strategy Actually Used",
            "Source/Status Summary",
            "Barrier Map",
            "Proof DAG Summary",
            "Counterexample/Computation Evidence",
            "Gap Feedback And Next Mutation",
            "Products Accepted",
            "What Remains Open",
            "Next Plausible Moves",
            "Trust Status",
        ],
        "must_not_claim": [
            "full solve without solve-claim acceptance",
            "verified without named verifier/kernel/receipt mechanism",
            "Generator output as mathematical certification",
            "bounded negative search as proof",
            "side lemma as progress without dependency path to target",
        ],
    }


def route_packet(prompt: str) -> dict[str, object]:
    routed = route_mod.route(prompt)
    return {
        "schema": "witsoc.orchestrator_plan.route.v1",
        "orchestrator_authority": (
            "The orchestrator owns strategy, fanout, ordering, budget, agent assignment, and reframing. "
            "Witsoc provides options and honesty gates."
        ),
        "route": routed,
        "candidate_lanes": (routed.get("deep_run_spec") or {}).get("mission_menu", []),
        "composition_hints": (routed.get("deep_run_spec") or {}).get("composition_hints", []),
        "alternative_strategies": (routed.get("deep_run_spec") or {}).get("alternative_strategies", []),
        "hard_gates": (routed.get("deep_run_spec") or {}).get("hard_gates", []),
        "report_contract": report_contract(),
    }


def run_packet(run_dir: Path) -> dict[str, object]:
    try:
        import witsoc_narrate
        ui_state = witsoc_narrate.build_ui_state(run_dir)
    except Exception:
        ui_state = {"schema": "witsoc.ui_state.v1", "run_dir": str(run_dir), "error": "ui_state_unavailable"}
    controller = load(run_dir / "witsoc_run_controller.json", {})
    return {
        "schema": "witsoc.orchestrator_plan.run.v1",
        "run_dir": str(run_dir),
        "orchestrator_authority": "The orchestrator decides the next strategy; Witsoc names gates, gaps, and evidence.",
        "ui_state": ui_state,
        "controller_status": (controller or {}).get("status", {}),
        "first_failed_gate": next((g for g in (controller or {}).get("gates", []) if not g.get("ok")), None),
        "report_contract": report_contract(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_route = sub.add_parser("route", help="emit advisory route and lane menu for a prompt")
    p_route.add_argument("prompt", nargs="+")

    p_run = sub.add_parser("run", help="emit advisory state packet for a run directory")
    p_run.add_argument("run_dir", type=Path)

    sub.add_parser("report-contract", help="emit the deep-run report contract")

    args = parser.parse_args()
    if args.cmd == "route":
        packet = route_packet(" ".join(args.prompt))
    elif args.cmd == "run":
        packet = run_packet(args.run_dir)
    else:
        packet = report_contract()
    print(json.dumps(packet, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
