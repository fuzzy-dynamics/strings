#!/usr/bin/env python3
"""Bounded-parallel, resumable campaign runner for long Witsoc research runs.

Tier-C scale: a single deep run is small; settling even a finite open subcase
often means sweeping many discovery seeds, many obligations, many re-checks. This
runner executes a manifest of tasks with bounded parallelism, respects
dependencies, checkpoints per-task status, and resumes (already-completed tasks
are skipped) — Temporal-friendly without requiring Temporal.

Manifest (JSON):
  {"tasks": [
     {"id": "disc-cap",      "cmd": ["python3", "@witsoc/discovery_engine.py", "init", "runs/cap",
                                      "--evaluator", "cap_set", "--params", "{\\"d\\":3}"]},
     {"id": "disc-cap-run",  "depends_on": ["disc-cap"],
                              "cmd": ["python3", "@witsoc/discovery_engine.py", "run", "runs/cap", "--generations", "60"]}
  ]}

`@witsoc/<name>` in any argv expands to this scripts directory, so manifests stay
portable. Commands run with NO shell (argv only). cwd defaults to the campaign
dir; set per-task "cwd" to override.

Usage:
  campaign.py init   <campaign_dir> --manifest m.json
  campaign.py run    <campaign_dir> [--workers N] [--time-budget S]
  campaign.py status <campaign_dir>
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
STATE = "campaign_state.json"


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def expand(argv: list[str]) -> list[str]:
    out = []
    for a in argv:
        if isinstance(a, str) and a.startswith("@witsoc/"):
            out.append(str(SCRIPT_DIR / a[len("@witsoc/"):]))
        else:
            out.append(str(a))
    return out


def cmd_init(args: argparse.Namespace) -> int:
    manifest = load(args.manifest, None)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("tasks"), list):
        raise SystemExit("manifest must be a JSON object with a 'tasks' list")
    tasks = {}
    for t in manifest["tasks"]:
        tid = str(t["id"])
        tasks[tid] = {"id": tid, "cmd": t["cmd"], "depends_on": [str(x) for x in t.get("depends_on", [])],
                      "cwd": t.get("cwd"), "status": "pending", "returncode": None,
                      "started_at": None, "ended_at": None, "tail": None}
    state = {"schema": "witsoc.campaign.v1", "tasks": tasks}
    save(args.campaign_dir / STATE, state)
    print(json.dumps({"status": "initialized", "tasks": len(tasks)}, indent=2))
    return 0


def _run_task(task: dict, campaign_dir: Path) -> dict:
    cwd = Path(task["cwd"]) if task.get("cwd") else campaign_dir
    cwd.mkdir(parents=True, exist_ok=True)
    argv = expand(task["cmd"])
    try:
        r = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, check=False)
        tail = (r.stdout or "")[-500:] + (("\n[stderr] " + r.stderr[-300:]) if r.returncode else "")
        return {"returncode": r.returncode, "tail": tail.strip()}
    except Exception as exc:
        return {"returncode": 127, "tail": f"launch error: {exc}"}


def cmd_run(args: argparse.Namespace) -> int:
    state_path = args.campaign_dir / STATE
    state = load(state_path, None)
    if not state:
        raise SystemExit("no campaign; run `init` first")
    tasks: dict[str, dict] = state["tasks"]
    deadline = time.monotonic() + args.time_budget if args.time_budget > 0 else None

    def ready(t: dict) -> bool:
        return t["status"] == "pending" and all(
            tasks.get(d, {}).get("status") == "completed" for d in t["depends_on"])

    def blocked(t: dict) -> bool:
        return any(tasks.get(d, {}).get("status") in ("failed", "blocked") for d in t["depends_on"])

    ran = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        while True:
            if deadline and time.monotonic() > deadline:
                break
            # Mark tasks whose deps failed as blocked.
            for t in tasks.values():
                if t["status"] == "pending" and blocked(t):
                    t["status"] = "blocked"
            batch = [t for t in tasks.values() if ready(t)]
            if not batch:
                break
            futures = {}
            for t in batch:
                t["status"] = "running"
                t["started_at"] = time.time()
                futures[pool.submit(_run_task, t, args.campaign_dir)] = t
            save(state_path, state)
            for fut in concurrent.futures.as_completed(futures):
                t = futures[fut]
                res = fut.result()
                t["returncode"] = res["returncode"]
                t["tail"] = res["tail"]
                t["ended_at"] = time.time()
                t["status"] = "completed" if res["returncode"] == 0 else "failed"
                ran += 1
            save(state_path, state)

    summary = _summary(tasks)
    summary["ran_this_call"] = ran
    save(state_path, state)
    print(json.dumps(summary, indent=2))
    return 0 if summary["failed"] == 0 and summary["blocked"] == 0 else 1


def _summary(tasks: dict[str, dict]) -> dict:
    by = {}
    for t in tasks.values():
        by[t["status"]] = by.get(t["status"], 0) + 1
    return {"total": len(tasks), "completed": by.get("completed", 0),
            "failed": by.get("failed", 0), "blocked": by.get("blocked", 0),
            "pending": by.get("pending", 0), "running": by.get("running", 0)}


def cmd_status(args: argparse.Namespace) -> int:
    state = load(args.campaign_dir / STATE, None)
    if not state:
        raise SystemExit("no campaign; run `init` first")
    s = _summary(state["tasks"])
    s["tasks"] = {tid: {"status": t["status"], "returncode": t["returncode"]}
                  for tid, t in state["tasks"].items()}
    print(json.dumps(s, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("campaign_dir", type=Path)
    p_init.add_argument("--manifest", type=Path, required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("campaign_dir", type=Path)
    p_run.add_argument("--workers", type=int, default=4)
    p_run.add_argument("--time-budget", type=float, default=0.0)
    p_status = sub.add_parser("status")
    p_status.add_argument("campaign_dir", type=Path)
    args = ap.parse_args()
    return {"init": cmd_init, "run": cmd_run, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
