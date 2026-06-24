#!/usr/bin/env python3
"""Prover battery — `witsoc battery`. The bus-lift measurement.

  baseline   run the DETERMINISTIC prover (portfolio + frontier search) over
             benchmarks/prover_battery.json; record per-goal verdicts; emit a
             prove_sketch bus request for every failure.
  score      after the orchestrator fulfilled the requests: kernel-REPLAY each
             fulfilled proof, bank the verified ones, and report
             baseline vs bus-lifted closure side by side.

The honest number this produces: how many goals the deterministic engine
cannot close that orchestrator intelligence can — with every claimed proof
replayed by the kernel before it counts. Closures bank into the proof bank
(few-shots) and feed tactic n-grams: measurement IS compounding.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

BATTERY = SCRIPT_DIR.parent / "benchmarks" / "prover_battery.json"


def _prove_deterministic(goal: str, imports: str, lake_dir: str | None,
                         timeout: int = 420, time_budget: float = 35.0) -> dict:
    cmd = [sys.executable, str(SCRIPT_DIR / "close_obligation.py"),
           "--lean-statement", goal, "--imports", imports, "--search",
           "--time-budget", str(time_budget), "--out-ledger", "/dev/null"]
    if lake_dir:
        cmd += ["--lake-dir", lake_dir]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception as exc:
        return {"error": str(exc)}


def baseline(battery: Path, lake_dir: str | None, out: Path,
             per_goal_timeout: int = 150) -> dict:
    spec = json.loads(battery.read_text(encoding="utf-8"))
    imports = spec.get("imports", "import Mathlib.Tactic")
    rows = []
    for g in spec["goals"]:
        t0 = time.time()
        res = _prove_deterministic(g["lean"], imports, lake_dir, timeout=per_goal_timeout)
        rows.append({"id": g["id"], "tier": g["tier"], "lean": g["lean"],
                     "baseline_discharged": bool(res.get("discharged")),
                     "baseline_proof": res.get("proof"),
                     "seconds": round(time.time() - t0, 1)})
        print(f"PROGRESS {g['id']} {g['tier']} "
              f"{'CLOSED' if res.get('discharged') else 'OPEN'} {rows[-1]['seconds']}s",
              flush=True)
        witcore.save_json(out, {"schema": "witsoc.prover_battery.baseline.v1",
                                "partial": True, "rows": rows})
    closed = [r for r in rows if r["baseline_discharged"]]
    open_rows = [r for r in rows if not r["baseline_discharged"]]
    # emit a prove_sketch request per failure — the orchestrator fulfills these
    emitted = 0
    try:
        import request_bus as rb
        for r in open_rows:
            rb.emit({
                "task": "prove_sketch",
                "goal": r["lean"], "imports": imports, "lake_dir": lake_dir or "",
                "battery_id": r["id"],
                "instructions": (
                    "Produce a Lean proof of `goal`. You have shell access: CHECK candidates "
                    f"yourself with witsoc prove --lean-statement '<goal>' --imports '{imports}'"
                    + (f" --lake-dir {lake_dir}" if lake_dir else "") +
                    " , read the diagnostics, revise (up to ~8 rounds), and reply "
                    "{\"proof\": \"by ...\"} with your best kernel-checked attempt "
                    "(or {\"proof\": null, \"blocker\": \"...\"} honestly)."),
            }, role="prove_sketch", priority=7)
            emitted += 1
    except Exception:
        pass
    report = {"schema": "witsoc.prover_battery.baseline.v1",
              "goals": len(rows), "baseline_closed": len(closed),
              "baseline_open": len(open_rows), "bus_requests_emitted": emitted,
              "by_tier": _by_tier(rows, "baseline_discharged"),
              "rows": rows}
    witcore.save_json(out, report)
    return {k: v for k, v in report.items() if k != "rows"} | {"out": str(out)}


def _by_tier(rows: list[dict], key: str) -> dict:
    out: dict = {}
    for r in rows:
        t = out.setdefault(r["tier"], {"closed": 0, "total": 0})
        t["total"] += 1
        t["closed"] += bool(r.get(key))
    return out


def score(baseline_path: Path, lake_dir: str | None, out: Path) -> dict:
    import request_bus as rb
    report = json.loads(baseline_path.read_text(encoding="utf-8"))
    imports = "import Mathlib.Tactic"
    lifted = replay_failed = unanswered = 0
    for r in report["rows"]:
        if r["baseline_discharged"]:
            r["final"] = "baseline"
            continue
        payload = {
            "task": "prove_sketch",
            "goal": r["lean"], "imports": imports, "lake_dir": lake_dir or "",
            "battery_id": r["id"],
            "instructions": (
                "Produce a Lean proof of `goal`. You have shell access: CHECK candidates "
                f"yourself with witsoc prove --lean-statement '<goal>' --imports '{imports}'"
                + (f" --lake-dir {lake_dir}" if lake_dir else "") +
                " , read the diagnostics, revise (up to ~8 rounds), and reply "
                "{\"proof\": \"by ...\"} with your best kernel-checked attempt "
                "(or {\"proof\": null, \"blocker\": \"...\"} honestly)."),
        }
        reply = rb.consume(payload, role="prove_sketch")
        if not reply:
            r["final"] = "unfulfilled"
            unanswered += 1
            continue
        proof = reply.get("proof")
        if not proof:
            r["final"] = f"honest_open: {str(reply.get('blocker'))[:80]}"
            continue
        # KERNEL REPLAY — the only acceptance
        src = f"{imports}\n\ntheorem battery_{r['id'].replace('-', '_')} : {r['lean']} := {proof}\n"
        v = witcore.lean_verify_cached(src, lake_dir, use_cache=False)
        print(f"REPLAY {r['id']} {'VERIFIED' if v.get('verified') else 'REJECTED'}", flush=True)
        if v.get("verified"):
            r["final"] = "bus_lifted"
            r["bus_proof"] = proof
            lifted += 1
            try:
                import proof_bank
                proof_bank.bank(r["lean"], proof, imports=imports, pre_simplify=False)
            except Exception:
                pass
        else:
            r["final"] = "replay_rejected"
            replay_failed += 1
    summary = {
        "schema": "witsoc.prover_battery.score.v1",
        "goals": report["goals"],
        "baseline_closed": report["baseline_closed"],
        "bus_lifted": lifted,
        "total_closed": report["baseline_closed"] + lifted,
        "replay_rejected": replay_failed,
        "unfulfilled": unanswered,
        "by_tier_final": _by_tier(
            [{**r, "closed_final": r.get("final") in ("baseline", "bus_lifted")} for r in report["rows"]],
            "closed_final"),
        "note": "bus_lifted proofs were kernel-replayed and banked (few-shots + n-grams compound)",
        "rows": report["rows"],
    }
    witcore.save_json(out, summary)
    return {k: v for k, v in summary.items() if k != "rows"} | {"out": str(out)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_b = sub.add_parser("baseline")
    p_b.add_argument("--battery", type=Path, default=BATTERY)
    p_b.add_argument("--lake-dir", default=None)
    p_b.add_argument("--out", type=Path, required=True)
    p_s = sub.add_parser("score")
    p_s.add_argument("--baseline", type=Path, required=True)
    p_s.add_argument("--lake-dir", default=None)
    p_s.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.cmd == "baseline":
        result = baseline(args.battery, args.lake_dir, args.out)
    else:
        result = score(args.baseline, args.lake_dir, args.out)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
