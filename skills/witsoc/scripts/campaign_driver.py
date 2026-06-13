#!/usr/bin/env python3
"""R5 campaign driver — `witsoc run`.

One turn of the Lovasz crank as a single deterministic command. The loop
closures lived as separate gates the agent had to remember to connect; the
driver connects them:

  witsoc run <run_dir> [--loops N] [--search]
    1. BUDGET     campaign_budget_gate.check — exhausted or HONEST_STOP ends
                  the turn honestly (nothing dispatched)
    2. DISPATCH   the kernel prover per DAG node, IN-PROCESS (R3) — one
                  process, one Lean cache for the whole batch
    3. FEEDBACK   proof_gap_to_barrier_feedback — failures classified, one
                  one-axis mutation proposed each, .soc updated
    4. RE-IDEATE  L2: when more than half the nodes failed, re-run the sketch
                  tournament SEEDED with the gap classifications; the winner's
                  fresh nodes (carrying mutation provenance) merge into the
                  DAG so the next loop attacks a different decomposition
    5. SERENDIPITY L6: audit the lemma queue's serendipity lane against the
                  20% cap; excess entries are flagged DEFERRED (never deleted,
                  never dispatched ahead of target work)
    6. PROGRESS   budget charge + record-progress; an escalation
                  recommendation is APPLIED (one ladder level, reason logged)
    7. LEDGER     run_ledger ingest + the single-pane summary

  witsoc run <run_dir> --finalize
    The production-gate sequence (score, summarize, validate, report, grade,
    return packet, phase update) as one command — replacing the 20-command
    bash block. Also syncs failure memory into the global knowledge store.

The driver decides NOTHING mathematical: every verdict is the kernel's, every
status the gates'. It is the 20 commands, in order, with the loop closed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import campaign_budget_gate as bg  # noqa: E402
import proof_gap_to_barrier_feedback as gf  # noqa: E402
import run_ledger  # noqa: E402
import witcore  # noqa: E402

REIDEATE_FAILURE_FRACTION = 0.5
SERENDIPITY_CAP = 0.2

FINALIZE_SEQUENCE = [
    ("score_lovasz_results.py", ["{run}/worker_results.json", "--out", "{run}/lovasz_result_scores.json"]),
    ("summarize_lovasz_run.py", ["{run}"]),
    ("formalization_feasibility.py", ["{run}", "--out", "{run}/formalization_feasibility.json"]),
    ("open_problem_report.py", ["{run}"]),
    ("grade_witsoc_report.py", ["{run}", "--out", "{run}/report_quality_grade.json"]),
    ("explorer_return_packet.py", ["{run}", "--out", "{run}/explorer_return_packet.json"]),
    ("lovasz_run_manifest.py", ["{run}"]),
]


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def dispatch_nodes(run: Path, search: bool, limit: int, workers: int) -> dict:
    """In-process prover dispatch via lovasz_prover_dispatch's machinery (its
    run_prover is close_goal since R3), keeping the skeptic gate and result
    merging exactly as the standalone command does them.

    A5 depth ordering: barrier nodes (the main attack) dispatch FIRST — depth
    on the committed attack before breadth on side nodes."""
    import lovasz_prover_dispatch as lpd
    nodes = lpd.collect_nodes(run, limit)
    dag = _load(run / "proof_dependency_dag.json", [])
    types = {str(n.get("node_id")): str(n.get("type") or "") for n in dag if isinstance(n, dict)}
    nodes.sort(key=lambda n: 0 if types.get(n["node_id"]) == "actual_barrier_lemma" else 1)
    packets = [lpd.packet_for_node(n, search, run / "prover_lean", workers, "driver", run)
               for n in nodes]
    lpd.apply_skeptic_gate(nodes, packets, lpd.frozen_target_hash(run))
    out = run / "worker_results.json"
    existing = _load(out, [])
    existing = existing if isinstance(existing, list) else []
    new_ids = {(p["node_id"], p["worker_type"]) for p in packets}
    merged = [w for w in existing if isinstance(w, dict)
              and (w.get("node_id"), w.get("worker_type")) not in new_ids]
    merged.extend(packets)
    out.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for p in packets:
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    return {"dispatched": len(packets), "status_counts": counts}


def reideate_if_stuck(run: Path, feedback: dict, force: bool = False) -> dict:
    """L2: more than half the nodes failed -> the decomposition is the problem,
    not the proving. Re-run the sketch tournament seeded with the recorded
    failures; merge the winner's NEW nodes (statement-deduped, OPEN, mutation
    provenance) into the DAG for the next loop. `force` (A5): a pivot
    recommendation triggers re-ideation regardless of the failure fraction."""
    dag = _load(run / "proof_dependency_dag.json", [])
    dag = [n for n in dag if isinstance(n, dict)] if isinstance(dag, list) else []
    failed = feedback.get("counts", {}).get("failed_nodes", 0)
    if not dag or (not force and failed <= len(dag) * REIDEATE_FAILURE_FRACTION):
        return {"triggered": False, "failed": failed, "nodes": len(dag)}

    manifest = _load(run / "lovasz_run.json", {})
    target = str(manifest.get("source_target_text") or "") or "unspecified target"
    target_hash = str(manifest.get("target_hash") or "")
    failure_memory = [{"method": g.get("gap_class"), "statement": str(nid),
                       "blocker": g.get("proposed_mutation")}
                      for nid, g in feedback.get("nodes", {}).items() if isinstance(g, dict)]
    theory_ctx = None
    try:
        import problem_theory as pt
        if pt.theory_path(run).exists():
            theory_ctx = pt.prompt_context(run)
    except Exception:
        pass
    try:
        import sketch_tournament as st
        result = st.tournament(target, None, target_hash, str(manifest.get("domain") or "other"),
                               failure_memory=failure_memory,
                               population_dir=run / "population",
                               theory=theory_ctx, kernel_probe=1)
        winner = result.get("winner_sketch") or {}
    except Exception as exc:
        return {"triggered": True, "failed": failed, "nodes": len(dag),
                "error": f"tournament failed: {exc}"}

    existing_statements = {str(n.get("statement") or "") for n in dag}
    added = []
    for node in winner.get("nodes") or []:
        if not isinstance(node, dict) or str(node.get("statement") or "") in existing_statements:
            continue
        fresh = dict(node)
        fresh["status"] = "OPEN"
        fresh["mutation_applied"] = f"re-ideation round (L2): {winner.get('strategy', 'tournament winner')}"
        dag.append(fresh)
        added.append(str(fresh.get("node_id")))
    if added:
        (run / "proof_dependency_dag.json").write_text(
            json.dumps(dag, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"triggered": True, "failed": failed, "nodes": len(dag),
            "winner": winner.get("sketch_id"), "nodes_added": added}


def serendipity_audit(run: Path) -> dict:
    """L6: enforce the documented 20% serendipity cap on the lemma queue.
    Excess serendipity entries (lowest priority first) are marked DEFERRED —
    kept, never deleted, but not dispatchable ahead of target work."""
    queue = _load(run / "actual_lemma_queue.json", [])
    queue = [l for l in queue if isinstance(l, dict)] if isinstance(queue, list) else []
    if not queue:
        return {"queue": 0, "serendipity": 0, "deferred": 0}
    serendipity = [l for l in queue if str(l.get("lane") or "") == "serendipity"]
    cap = max(1, int(len(queue) * SERENDIPITY_CAP)) if serendipity else 0
    deferred = 0
    if len(serendipity) > cap:
        keep = sorted(serendipity, key=lambda l: -(l.get("priority") or 0))[:cap]
        keep_ids = {id(k) for k in keep}
        for l in serendipity:
            if id(l) not in keep_ids and not l.get("deferred"):
                l["deferred"] = "L6 serendipity cap (20% of dispatch budget)"
                deferred += 1
        (run / "actual_lemma_queue.json").write_text(
            json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"queue": len(queue), "serendipity": len(serendipity), "cap": cap, "deferred": deferred}


def barrier_attack_prepare(run: Path) -> dict:
    """Open-problem campaigns need a concrete depth spine before dispatch.
    Seed named barriers + saturated rungs once, then let the normal dispatcher
    attack those OPEN nodes. This is non-fatal so legacy/minimal runs still work."""
    try:
        import barrier_attack
        return barrier_attack.prepare_run(run)
    except Exception as exc:
        return {"error": str(exc)}


def one_loop(run: Path, search: bool, limit: int, workers: int) -> dict:
    turn: dict = {"schema": "witsoc.campaign_driver.turn.v1", "run_dir": str(run)}

    # P0 Intelligence Bus: with no external fleet, the orchestrator is the
    # fleet — engines queue requests under <run>/bus this turn; the
    # orchestrator fulfills them and re-runs the loop (request_bus.py).
    # Respects an explicit WITSOC_BUS=0 and any user-set WITSOC_BUS_DIR.
    os.environ.setdefault("WITSOC_BUS_DIR", str(run / "bus"))

    turn["barrier_attack"] = barrier_attack_prepare(run)

    budget = bg.check(run)
    turn["budget"] = {k: budget[k] for k in ("dispatch_allowed", "escalation_level", "required_action")}
    if not budget["dispatch_allowed"]:
        turn["stopped"] = "budget gate blocks dispatch"
        return turn

    try:
        import bus_apply_replies as bar
        turn["bus_apply"] = {k: v for k, v in bar.apply(run).items() if k != "packets"}
    except Exception as exc:
        turn["bus_apply"] = {"error": str(exc)}

    turn["dispatch"] = dispatch_nodes(run, search, limit, workers)
    bg.charge(run, attempts=turn["dispatch"]["dispatched"])

    feedback, new_failures = gf.build_feedback(run)
    gf.record_soc_failures(run, new_failures)
    (run / "gap_feedback.json").write_text(json.dumps(feedback, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    turn["gap_feedback"] = feedback.get("counts")

    # P-loop: failed Lean-stated nodes become prove_sketch bus requests
    # AUTOMATICALLY — the orchestrator fulfills them (iterating against the
    # kernel inside the fulfillment) and re-runs the loop. Content-hash
    # dedup makes repeat emissions free; the ceiling guards runaway.
    try:
        import request_bus as rb
        if rb.enabled():
            dag_nodes = {str(n.get("node_id")): n
                         for n in _load(run / "proof_dependency_dag.json", [])
                         if isinstance(n, dict)}
            emitted = 0
            for nid in feedback.get("nodes") or {}:
                node = dag_nodes.get(str(nid))
                if not (node and node.get("lean_statement")):
                    continue
                out = rb.emit({
                    "task": "prove_sketch",
                    "goal": str(node["lean_statement"]),
                    "imports": str(node.get("lean_imports") or "import Mathlib.Tactic"),
                    "node_id": str(nid),
                    "statement": str(node.get("statement") or ""),
                    "instructions": (
                        "Produce a Lean proof of `goal`. You have shell access: CHECK candidates "
                        "yourself (witsoc prove --lean-statement '<goal>' --imports '<imports>' "
                        "[--lake-dir <mathlib>]), read the diagnostics, revise (~8 rounds), and "
                        "reply {\"proof\": \"by ...\"} with your best kernel-checked attempt or "
                        "{\"proof\": null, \"blocker\": \"...\"} honestly. You may consult "
                        "`witsoc retrieve query --text '<informal description>'` for premises."),
                }, role="prove_sketch", priority=8)
                emitted += out.get("status") == "queued"
            turn["bus_emitted_for_failures"] = emitted
    except Exception as exc:
        turn["bus_emitted_for_failures"] = {"error": str(exc)}
    try:
        import barrier_attack
        turn["barrier_mutation"] = barrier_attack.mutate_from_feedback(run)
    except Exception as exc:
        turn["barrier_mutation"] = {"error": str(exc)}

    # A1: every loop must end with a theory diff — a loop that learned nothing
    # is a wasted loop and the turn report says so.
    try:
        import problem_theory as pt
        pt.init_theory(run)
        absorb = pt.absorb_gap_feedback(run, feedback, loop_label=f"driver loop (spent="
                                        f"{bg.load_campaign(run)['spent'].get('attempts', 0)})")
        turn["theory"] = absorb
        if not absorb.get("updated"):
            turn["theory"]["warning"] = "no theory diff this loop — nothing was learned"
    except Exception as exc:
        turn["theory"] = {"error": str(exc)}

    # A2: the dialectic — every failed node becomes a refutation target;
    # kernel-verified witnesses and exhausted searches both feed the theory.
    try:
        import dialectic
        d = dialectic.couple(run, instance_bound=8)
        turn["dialectic"] = {k: d[k] for k in ("refutation_targets", "refuted", "exhausted",
                                               "theory_updates")}
    except Exception as exc:
        turn["dialectic"] = {"error": str(exc)}

    # A5: the depth spine — breaks accumulate on the committed attack; three
    # breaks without a pivot force re-ideation even below the failure fraction.
    pivot = False
    try:
        import problem_theory as pt
        attack = pt.load_theory(run)["main_attack"]
        pivot = int(attack.get("breaks", 0)) >= 3
        turn["depth"] = {"main_attack": attack.get("strategy") or "unset",
                         "stall_point": attack.get("stall_point"),
                         "breaks": attack.get("breaks", 0),
                         "pivot_forced": pivot}
    except Exception:
        turn["depth"] = {"main_attack": "unknown"}

    # Ω2: the lemma pool — mine bridging lemmas from this loop's failed goals'
    # REAL residual diagnostics (Prover-Agent style), then a budgeted
    # prove-pending pass; PROVED lemmas harvest into the library so every
    # later attempt (this run or any other) can reuse them.
    try:
        import lemma_pool as lp
        dag = _load(run / "proof_dependency_dag.json", [])
        dag = dag if isinstance(dag, list) else []
        mined_proposed = 0
        for nid in list(feedback.get("nodes") or {})[:3]:
            node = next((n for n in dag if isinstance(n, dict)
                         and str(n.get("node_id")) == str(nid)), None)
            if node and node.get("lean_statement"):
                out = lp.mine_into_pool(run, str(node["lean_statement"]), str(nid),
                                        str(node.get("lean_imports") or ""))
                mined_proposed += out["proposed"]
        pool_pass = lp.prove_pending(run, limit=3)
        turn["lemma_pool"] = {"mined_proposed": mined_proposed, **pool_pass}
    except Exception as exc:
        turn["lemma_pool"] = {"error": str(exc)}

    turn["reideation"] = reideate_if_stuck(run, feedback, force=pivot)
    if turn["reideation"].get("triggered") and turn["reideation"].get("winner"):
        try:
            import problem_theory as pt
            pt.update_theory(run, {"set_main_attack": {
                "strategy": str(turn["reideation"]["winner"]),
                "rationale": "tournament winner after re-ideation/pivot",
                "stall_point": ""}}, why="re-ideation set the new main attack")
        except Exception:
            pass
    turn["serendipity"] = serendipity_audit(run)

    counts = turn["dispatch"]["status_counts"]
    closed = sum(v for k, v in counts.items() if k in ("VERIFIED_LEAN", "CHECKED"))
    rung = "L5" if counts.get("VERIFIED_LEAN") else ("L2" if closed else "L0")
    progress = bg.record_progress(run, rung)
    turn["progress"] = progress
    if progress.get("escalation_recommended"):
        esc = bg.escalate(run, reason=f"driver: {progress['stall_count']} stalled loops at {progress['best_rung']}")
        turn["escalated"] = esc
        # P4 decision auto-recording: known decision sites log themselves so
        # the learning loop accumulates data without relying on agent diligence.
        try:
            import decision_ledger as dl
            manifest = _load(run / "lovasz_run.json", {})
            dl.record("escalation", str(manifest.get("source_target_text") or str(run)),
                      ["stay", esc.get("escalation_level", "escalate")],
                      esc.get("escalation_level", "escalate"),
                      esc.get("reason", "stall threshold"), run_dir=str(run))
        except Exception:
            pass

    run_ledger.auto_ingest(run)
    turn["ledger"] = run_ledger.status_summary(run)

    # Surface the bus state: a turn that queued intelligence requests is not
    # finished — the orchestrator must fulfill them and crank the loop again.
    try:
        import request_bus
        bus = request_bus.status(run / "bus")
        turn["bus"] = {"pending": bus["pending"], "pending_by_role": bus["pending_by_role"]}
        if bus["pending"]:
            turn["bus"]["action_required"] = (
                f"PENDING_REQUESTS({bus['pending']}): fulfill them "
                f"(`witsoc bus --dir {run / 'bus'} next-batch`; fan out subagents for "
                "parallel roles), then `witsoc bus-apply "
                f"{run}` and re-run this loop")
    except Exception:
        pass
    return turn


def finalize(run: Path) -> dict:
    """The production-gate sequence as one command."""
    steps = []
    for script, arg_templates in FINALIZE_SEQUENCE:
        cmd = [sys.executable, str(SCRIPT_DIR / script)] + \
              [a.format(run=str(run)) for a in arg_templates]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
            steps.append({"step": script, "ok": r.returncode == 0})
        except Exception as exc:
            steps.append({"step": script, "ok": False, "error": str(exc)})
    try:
        import knowledge_store
        synced = knowledge_store.sync_run(run)
    except Exception:
        synced = {"synced": 0}
    insight = None
    try:
        import problem_theory as pt
        if pt.theory_path(run).exists():
            insight = pt.insight_score(run)  # Ω10: grade understanding, not just closure
    except Exception:
        pass
    # P4: the compounding gauges — is memory reaching prompts, and what has
    # the decision loop learned? A growing store with zero attachments means
    # the flywheel is NOT turning, and the report says so.
    memory_flow = decisions = None
    try:
        import knowledge_store as ks
        memory_flow = ks.flow_report()
    except Exception:
        pass
    try:
        import decision_ledger as dl
        decisions = dl.stats()
    except Exception:
        pass
    run_ledger.auto_ingest(run)
    return {"schema": "witsoc.campaign_driver.finalize.v1", "run_dir": str(run),
            "steps": steps, "all_ok": all(s["ok"] for s in steps),
            "failure_memory_synced": synced.get("synced", 0),
            "insight": insight,
            "memory_flow": memory_flow,
            "decisions": decisions,
            "ledger": run_ledger.status_summary(run)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--loops", type=int, default=1)
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--limit", type=int, default=20, help="max nodes per dispatch")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--finalize", action="store_true",
                    help="run the production-gate sequence instead of campaign loops")
    args = ap.parse_args()

    if args.finalize:
        result = finalize(args.run_dir)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["all_ok"] else 1

    turns = []
    for _ in range(args.loops):
        turn = one_loop(args.run_dir, args.search, args.limit, args.workers)
        turns.append(turn)
        if turn.get("stopped"):
            break
    print(json.dumps({"schema": "witsoc.campaign_driver.v1", "turns": turns},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
