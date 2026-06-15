#!/usr/bin/env python3
"""`witsoc next <run_dir>` — THE one next action for an orchestrator.

Long campaigns die on orchestrator turn discipline, not mathematics: with
~100 commands, the failure mode is doing the wrong next thing. This command
reads the run's actual state (bus queue, manifest phase,
ledgers) and answers the only question that matters between turns: WHAT NOW —
one action, with the exact command to run.

Deterministic state reading only; it never decides mathematics and its
suggestion is advice about SEQUENCING, never about truth. Priority order:

  1. pending bus requests        -> fulfill them (you are the fleet)
  2. no DAG / no frozen target   -> freeze + seed the run
  3. open nodes                  -> crank the loop (witsoc run)
  4. everything closed           -> finalize (production gates + return)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402


def _step(action: str, command: str, why: str, **extra) -> dict:
    return {"schema": "witsoc.next_action.v1", "action": action,
            "command": command, "why": why, **extra}


def next_action(run: Path) -> dict:
    manifest = witcore.load_json(run / "lovasz_run.json", {})
    if not manifest:
        return _step("freeze_target",
                     f"witsoc lovasz-manifest {run} --target '<exact frozen statement>'",
                     "no run manifest yet: a campaign starts by freezing the exact target")

    # 1. The bus: queued intelligence requests outrank everything — engines
    # are waiting on YOU.
    try:
        import request_bus as rb
        bus = rb.status(run / "bus")
        if bus["pending"]:
            return _step("fulfill_bus_requests",
                         f"witsoc bus --dir {run / 'bus'} next-batch",
                         f"{bus['pending']} pending intelligence requests "
                         f"({bus['pending_by_role']}) — fulfill (fan out subagents for "
                         "parallel roles; iterate inside proving roles), then re-run the loop",
                         then=f"witsoc bus-apply {run} && witsoc run {run}")
        reqs = rb.requests_by_id(run / "bus")
        responses = rb.responses_by_id(run / "bus")
        applied_path = run / "bus" / "applied.jsonl"
        applied = {str(r.get("id")) for r in rb._read_jsonl(applied_path)} if applied_path.exists() else set()  # type: ignore[attr-defined]
        unapplied = [rid for rid in responses if rid in reqs and rid not in applied]
        if unapplied:
            return _step("apply_bus_replies",
                         f"witsoc bus-apply {run}",
                         f"{len(unapplied)} fulfilled bus replies need kernel replay before they can affect worker/DAG state",
                         then=f"witsoc run {run}")
    except Exception:
        pass

    # 3. The conjecture-distance keystone: a frozen target with no reduction yet.
    # Seed the problem-specific obligations + honest open_core via the bus before
    # cranking the DAG, so progress is measured against the CONJECTURE (open_core)
    # and not just whatever got seeded into the DAG. Emits a seed_lemmas request,
    # which priority 1 then surfaces for fulfillment next turn.
    try:
        import reduction_ledger as rl
        import request_bus as rb
        bus_driven = rb.enabled() or (run / "bus").exists()
        if bus_driven and rl.needs_seeding(run):
            return _step("seed_reduction",
                         f"witsoc reduction seed {run} --bus-dir {run / 'bus'}",
                         "no reduction ledger yet — seed the problem-specific obligations and "
                         "honest open_core (target ⟸ obligations ∧ open_core) so progress is "
                         "scored against the conjecture, not the seeded DAG",
                         then=f"witsoc bus --dir {run / 'bus'} next-batch  # fulfill the seed_lemmas request")
        # Once obligations exist, completeness-audit the reduction ONCE: an
        # adversarial check that obligations ∪ open_core actually cover the target
        # (a silent coverage hole makes the decomposition unsound).
        if bus_driven and rl.needs_coverage_audit(run):
            return _step("audit_reduction_coverage",
                         f"witsoc reduction audit-coverage {run} --bus-dir {run / 'bus'}",
                         "reduction seeded but not completeness-audited — emit an adversarial "
                         "coverage_audit (does anything escape obligations ∪ open_core?) before "
                         "trusting the decomposition",
                         then=f"witsoc bus --dir {run / 'bus'} next-batch  # fulfill the coverage_audit")
    except Exception:
        pass

    # 4. A frozen target but no attack surface yet.
    dag = witcore.records(run / "proof_dependency_dag.json")
    if not dag:
        return _step("seed_attack",
                     f"witsoc run {run}",
                     "no proof DAG yet — the driver's barrier preflight seeds named barriers "
                     "and saturated rungs on the first loop")

    # 4. Open nodes -> crank.
    open_nodes = [n for n in dag if str(n.get("status") or "OPEN").upper()
                  not in ("CLOSED", "VERIFIED_LEAN", "CHECKED", "REJECTED")]
    if open_nodes:
        why = f"{len(open_nodes)} open nodes remain"
        return _step("crank_loop", f"witsoc run {run}", why,
                     open_nodes=len(open_nodes))

    # 5. Nothing open.
    return _step("finalize", f"witsoc run {run} --finalize",
                 "no open DAG nodes — run the production gates, grade the report, and "
                 "build the Explorer return packet")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    args = ap.parse_args()
    print(json.dumps(next_action(args.run_dir), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
