#!/usr/bin/env python3
"""Create an auditable worker dispatch manifest from Lovasz spawn packets."""

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

    packet_paths = load(run / "spawn_requests.json", [])
    dispatches = []
    for path_text in packet_paths:
        path = Path(path_text)
        packet = load(path, {})
        memory = soc_query(run, packet)
        repeat_risk = memory.get("repeat_risk") == "HIGH"
        packet["soc_memory"] = {
            "lovasz_soc": memory.get("soc"),
            "repeat_risk": memory.get("repeat_risk"),
            "matching_failed_approaches": memory.get("matching_failed_approaches", [])[:3],
            "required_action": "record one-axis mutation before retry" if repeat_risk else "proceed",
        }
        if args.write:
            path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        dispatches.append({
            "packet": str(path),
            "target_node_id": packet.get("target_node_id"),
            "worker_type": packet.get("worker_type"),
            "repeat_risk": memory.get("repeat_risk"),
            "dispatch_status": "BLOCKED_REPEAT_RISK" if repeat_risk else "READY",
            "soc": memory.get("soc"),
        })

    manifest = {
        "schema": "witsoc.lovasz_worker_dispatch.v1",
        "run_dir": str(run),
        "dispatches": dispatches,
        "ready_count": sum(1 for d in dispatches if d["dispatch_status"] == "READY"),
        "blocked_repeat_count": sum(1 for d in dispatches if d["dispatch_status"] == "BLOCKED_REPEAT_RISK"),
    }
    if args.write:
        (run / "worker_dispatch_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
