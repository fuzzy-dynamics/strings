#!/usr/bin/env python3
"""Create an auditable worker dispatch manifest from Lovasz spawn packets.

Enforced before any packet is READY:
  - campaign budget gate (L3): exhausted run budget or HONEST_STOP blocks the
    whole dispatch; a barrier at its per-barrier attempt cap blocks that node
    until it is converted to an obstruction target or the gate is re-budgeted.
  - gap feedback contract (L1): a node that failed before may be re-dispatched
    only after its statement changed or its packet carries `mutation_applied`
    (set on the DAG node, copied in by spawn_workers_from_dag).
  - `.soc` repeat-risk check (existing): matching FAILED_APPROACHES entries
    require a recorded one-axis mutation before retry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import campaign_budget_gate as bg  # noqa: E402


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def run_helper(script: str, args: list[str]) -> None:
    subprocess.check_call([sys.executable, str(SCRIPT_DIR / script), *args], stdout=subprocess.DEVNULL)


def soc_query(run: Path, packet: dict[str, Any]) -> dict[str, Any]:
    command = [
        sys.executable,
        str(SCRIPT_DIR / "lovasz_soc_memory.py"),
        "query",
        str(run),
        "--statement",
        str(packet.get("exact_statement") or ""),
        "--method",
        str(packet.get("worker_type") or ""),
    ]
    output = subprocess.check_output(command, text=True)
    return json.loads(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--session-id", default="manual")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    run = args.run_dir
    run_helper("lovasz_soc_memory.py", ["init", str(run)])
    run_helper("spawn_workers_from_dag.py", [str(run), "--limit", str(args.limit), "--session-id", args.session_id])

    budget = bg.check(run)
    blocked_barriers = set(budget.get("exhausted_barriers", []))
    gap_feedback = load(run / "gap_feedback.json", {})
    gap_nodes = gap_feedback.get("nodes", {}) if isinstance(gap_feedback, dict) else {}

    packet_paths = load(run / "spawn_requests.json", [])
    dispatches = []
    for path_text in packet_paths:
        path = Path(path_text)
        packet = load(path, {})
        node_id = str(packet.get("target_node_id") or "")
        statement_sha = hashlib.sha256(str(packet.get("exact_statement") or "").encode("utf-8")).hexdigest()
        memory = soc_query(run, packet)
        repeat_risk = memory.get("repeat_risk") == "HIGH"

        gap_entry = gap_nodes.get(node_id) if isinstance(gap_nodes.get(node_id), dict) else None
        unmutated_refail = bool(gap_entry
                                and gap_entry.get("failed_statement_sha") == statement_sha
                                and not packet.get("mutation_applied"))

        if not budget["dispatch_allowed"]:
            status, required = "BLOCKED_BUDGET", budget["required_action"]
        elif node_id in blocked_barriers:
            status = "BLOCKED_BARRIER_BUDGET"
            required = "per-barrier attempt cap reached; convert to obstruction target or re-budget the gate"
        elif unmutated_refail:
            status = "BLOCKED_NO_MUTATION"
            required = (f"apply the one-axis mutation from gap_feedback.json before retry: "
                        f"{gap_entry.get('proposed_mutation')}")
        elif repeat_risk:
            status, required = "BLOCKED_REPEAT_RISK", "record one-axis mutation before retry"
        else:
            status, required = "READY", "proceed"

        packet["soc_memory"] = {
            "lovasz_soc": memory.get("soc"),
            "repeat_risk": memory.get("repeat_risk"),
            "matching_failed_approaches": memory.get("matching_failed_approaches", [])[:3],
            "required_action": required,
        }
        if gap_entry:
            packet["gap_feedback"] = {"gap_class": gap_entry.get("gap_class"),
                                      "mutation_round": gap_entry.get("mutation_round"),
                                      "proposed_mutation": gap_entry.get("proposed_mutation")}
        if args.write:
            path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        dispatches.append({
            "packet": str(path),
            "target_node_id": packet.get("target_node_id"),
            "worker_type": packet.get("worker_type"),
            "repeat_risk": memory.get("repeat_risk"),
            "dispatch_status": status,
            "required_action": required,
            "soc": memory.get("soc"),
        })

    ready = [d for d in dispatches if d["dispatch_status"] == "READY"]
    manifest = {
        "schema": "witsoc.lovasz_worker_dispatch.v1",
        "run_dir": str(run),
        "budget_check": {k: budget[k] for k in ("escalation_level", "dispatch_allowed", "required_action",
                                                "exhausted_barriers", "spent")},
        "dispatches": dispatches,
        "ready_count": len(ready),
        "blocked_repeat_count": sum(1 for d in dispatches if d["dispatch_status"] == "BLOCKED_REPEAT_RISK"),
        "blocked_no_mutation_count": sum(1 for d in dispatches if d["dispatch_status"] == "BLOCKED_NO_MUTATION"),
        "blocked_budget_count": sum(1 for d in dispatches
                                    if d["dispatch_status"] in ("BLOCKED_BUDGET", "BLOCKED_BARRIER_BUDGET")),
    }
    if args.write:
        (run / "worker_dispatch_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if ready:
            # Charge the run budget for what is actually being dispatched.
            bg.charge(run, attempts=len(ready), barriers=[str(d["target_node_id"]) for d in ready])
        import run_ledger
        run_ledger.auto_ingest(run)  # R1.5: the unified ledger stays fresh
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
