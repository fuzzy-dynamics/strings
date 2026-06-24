#!/usr/bin/env python3
"""F2 sampler fleet — `witsoc fleet`.

Scale the insight engine: the kernel/falsification stack makes untrusted
generation safe, so generation should be wide. This module turns the single
`cmd:` sampler bridge (witcore.run_sampler) into a FLEET of diverse model
samplers queried concurrently. Everything a fleet returns is born
OPEN_UNFALSIFIED/SPECULATIVE — the fleet multiplies candidates; verification
(falsification pass, skeptic gates, kernel dispatch) remains the only filter.

Configuration (first hit wins):
  1. WITSOC_SAMPLER_FLEET  — `;;`-separated entries, each `[id=]cmd:<shell command>`
       e.g.  WITSOC_SAMPLER_FLEET='fast=cmd:my-model-a;;deep=cmd:my-model-b'
  2. ~/.witsoc/sampler_fleet.json — [{"id": "...", "command": "cmd:..."}, ...]
  3. WITSOC_IDEATION_SAMPLER — the legacy single sampler, as a fleet of one.

Each sampler is an external command speaking the established protocol: JSON
request on stdin, JSON reply on stdout (witcore.run_sampler). A failing or
malformed sampler contributes nothing — never an error.

Consumers: ideate.py (fleet-wide idea generation), sketch_population.py
(LLM mutation operators), sketch_tournament.py (LLM-proposed decompositions).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

DEFAULT_TIMEOUT = 120.0
MAX_WORKERS = 8


def fleet_config_path() -> Path:
    return witcore.witsoc_home() / "sampler_fleet.json"


def samplers(extra: str | None = None) -> list[dict]:
    """The configured fleet as [{id, command}]. `extra` (e.g. an ideate
    --sampler argument) joins the fleet without duplicating an existing entry."""
    out: list[dict] = []
    env = os.environ.get("WITSOC_SAMPLER_FLEET", "").strip()
    if env:
        for i, entry in enumerate(e.strip() for e in env.split(";;") if e.strip()):
            m = re.match(r"^([A-Za-z0-9_-]+)=(cmd:.*)$", entry)
            if m:
                out.append({"id": m.group(1), "command": m.group(2)})
            elif entry.startswith("cmd:"):
                out.append({"id": f"fleet{i + 1}", "command": entry})
    else:
        cfg = witcore.load_json(fleet_config_path(), [])
        if isinstance(cfg, list):
            for i, e in enumerate(c for c in cfg if isinstance(c, dict) and c.get("command")):
                out.append({"id": str(e.get("id") or f"fleet{i + 1}"), "command": str(e["command"])})
    if not out:
        legacy = os.environ.get("WITSOC_IDEATION_SAMPLER", "").strip()
        if legacy:
            out.append({"id": "legacy", "command": legacy})
    if not out:
        # P0 Intelligence Bus: with no external fleet configured, the
        # ORCHESTRATOR is the fleet — requests queue on the bus, the
        # orchestrator fulfills them, the re-run consumes the replies
        # (request_bus.py; enable via WITSOC_BUS_DIR or WITSOC_BUS=1).
        try:
            import request_bus
            if request_bus.enabled():
                out.append({"id": "orchestrator", "command": "bus:"})
        except Exception:
            pass
    if extra and extra not in {s["command"] for s in out}:
        out.append({"id": "arg", "command": extra})
    return out


def sample(request: dict, *, per_sampler: int = 1, timeout: float = DEFAULT_TIMEOUT,
           extra: str | None = None) -> list[dict]:
    """Query every fleet sampler `per_sampler` times concurrently.
    -> [{sampler_id, round, reply}] for the calls that returned valid JSON."""
    fleet = samplers(extra)
    if not fleet:
        return []
    jobs = [(s["id"], s["command"], rnd)
            for s in fleet for rnd in range(1, per_sampler + 1)]

    def run(job: tuple[str, str, int]) -> dict | None:
        sid, command, rnd = job
        reply = witcore.run_sampler(command, {**request, "fleet_sampler": sid, "fleet_round": rnd},
                                    timeout=timeout)
        if not isinstance(reply, dict):
            return None
        return {"sampler_id": sid, "round": rnd, "reply": reply}

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(jobs))) as pool:
        results = list(pool.map(run, jobs))
    return [r for r in results if r is not None]


def dedup(items: list[dict], key: str) -> list[dict]:
    """Order-preserving dedup by a normalized text field."""
    seen: set[str] = set()
    out = []
    for item in items:
        norm = re.sub(r"\s+", " ", str(item.get(key, ""))).strip().lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(item)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p_sample = sub.add_parser("sample")
    p_sample.add_argument("--request-json", required=True, help="JSON request passed to every sampler")
    p_sample.add_argument("--per-sampler", type=int, default=1)
    p_sample.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    args = ap.parse_args()

    if args.cmd == "status":
        fleet = samplers()
        print(json.dumps({"schema": "witsoc.sampler_fleet.v1", "size": len(fleet),
                          "samplers": [{"id": s["id"],
                                        "command_preview": s["command"][:60]} for s in fleet],
                          "config": ("env WITSOC_SAMPLER_FLEET" if os.environ.get("WITSOC_SAMPLER_FLEET")
                                     else str(fleet_config_path()) if fleet_config_path().exists()
                                     else "legacy WITSOC_IDEATION_SAMPLER" if fleet else "none"),
                          "note": "fleet output is OPEN_UNFALSIFIED candidates; verification is the only filter"},
                         indent=2))
        return 0
    request: dict[str, Any] = json.loads(args.request_json)
    results = sample(request, per_sampler=args.per_sampler, timeout=args.timeout)
    print(json.dumps({"calls_returned": len(results), "results": results}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
