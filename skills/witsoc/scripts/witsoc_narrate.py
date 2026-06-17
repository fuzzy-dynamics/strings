#!/usr/bin/env python3
"""Plain-language narration of witsoc run state (the UX/transparency layer).

Witsoc's engines speak JSON: gate records, status lattices, bus packets. That
is correct for machines but opaque for the human or orchestrator driving a run,
who needs to know — at any stop point — *what phase am I in, what just
happened, what does witsoc need from me, what exactly do I run next, and what
am I allowed to trust.*

This module answers exactly that, and ONLY by restating ledgers that already
exist. It computes nothing about the mathematics and changes no claim: it reads
``witsoc_run_controller.json``, the bus status, and the status lattice, and
renders them as a short human block. Narration can only restate the contract
layer, never upgrade it — a failed gate stays failed, a PROVED_SKETCH stays
unverified.

Used three ways:
  * ``witsoc narrate <run-dir>``     — render the current run state for a human
  * ``witsoc explain-status <LABEL>``— what a status label means / licenses
  * imported by ``request_bus.py`` and ``witsoc_controller.py`` to attach a
    ``human`` / ``narration`` field beside their JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import status_vocab  # noqa: E402


# --- gate legend --------------------------------------------------------------
# For each controller gate: what it checks, what a failure means in user terms,
# and the concrete next move (always including the honest-stop option, because a
# documented stop is a legitimate witsoc outcome — never a thing to paper over).
# Keyed by the gate names emitted in witsoc_controller.py.
GATE_HELP: dict[str, dict[str, str]] = {
    "route": {
        "checks": "classifies the target (routine / reachable / hard / frontier) and picks a route",
        "on_fail": "witsoc could not classify the request",
        "fix": "rephrase the target as a single frozen statement, or run `witsoc route \"<target>\"` to see the classification",
    },
    "decompose": {
        "checks": "breaks the target into a proof DAG of smaller obligations",
        "on_fail": "the target could not be decomposed into sub-goals",
        "fix": "state the target more concretely, or seed obligations via the bus `seed_lemmas` role",
    },
    "synthesize_ledgers": {
        "checks": "assembles the run's ledgers (DAG, lemma queue, blueprint) into one consistent state",
        "on_fail": "the run's ledgers are inconsistent with each other",
        "fix": "inspect `witsoc knowledge nodes <run>`; re-run after fixing the flagged ledger",
    },
    "validate_open_problem": {
        "checks": "the open-problem run has the required ledgers (lemma queue, DAG, evidence)",
        "on_fail": "the run is missing a required piece for an open-style target",
        "fix": "complete a full Lovász pass: `witsoc campaign run <run> --loops 1`",
    },
    "open_problem": {
        "checks": "the open-problem run has the required ledgers (lemma queue, DAG, evidence)",
        "on_fail": "the run is missing a required piece for an open-style target — often it has no seeded campaign yet",
        "fix": "seed and attack first: `witsoc run-open <run> --prompt \"<target>\" --loops 0`, then finalize",
    },
    "lovasz_manifest": {
        "checks": "the Lovász run manifest (frozen target + run metadata) exists and is well-formed",
        "on_fail": "the run has no valid Lovász manifest — it was never seeded as a campaign",
        "fix": "start the campaign: `witsoc run-open <run> --prompt \"<frozen target>\"`",
    },
    "route_state_final": {
        "checks": "the route classification is present and legal for a final report",
        "on_fail": "the run has no recorded route state to finalize against",
        "fix": "run the full path: `witsoc run-open <run> --prompt \"<target>\"` (it records route state)",
    },
    "campaign_finalize": {
        "checks": "the campaign-driver finalize pass (ledger ingest + audits) completed",
        "on_fail": "the campaign could not be finalized — usually an upstream ledger is missing or inconsistent",
        "fix": "fix the earlier failing gate, then re-run `witsoc finalize <run>`",
    },
    "validate_dag_integrity": {
        "checks": "every DAG node has a dependency path to the frozen target and no broken edges",
        "on_fail": "the proof DAG has an open node with no path to the target, or a dangling dependency",
        "fix": "re-attack the open node (`witsoc campaign run <run> --loops 1`), or report PARTIAL with the closed sub-results",
    },
    "dag_integrity": {
        "checks": "every DAG node has a dependency path to the frozen target and no broken edges",
        "on_fail": "the proof DAG has an open node with no path to the target, or a dangling dependency",
        "fix": "re-attack the open node (`witsoc campaign run <run> --loops 1`), or report PARTIAL with the closed sub-results",
    },
    "campaign_loop": {
        "checks": "runs one or more barrier-attack loops (dispatch → feedback → re-ideate)",
        "on_fail": "skipped because a prerequisite gate failed, or the loop itself errored",
        "fix": "fix the earlier failing gate first; loops=0 intentionally skips this — set --loops 1 to attack",
    },
    "status_lattice": {
        "checks": "no node carries a status stronger than its evidence (e.g. VERIFIED without a receipt)",
        "on_fail": "a claim is labelled stronger than its evidence supports",
        "fix": "demote the over-claimed node to its earned status; the lattice never lets confidence stand in for proof",
    },
    "lovasz_phase": {
        "checks": "the campaign is in a legal phase with the artifacts that phase requires",
        "on_fail": "the Lovász campaign is in an inconsistent phase state",
        "fix": "re-run `witsoc campaign run <run>` to advance the phase, then finalize again",
    },
    "explorer_review": {
        "checks": "Explorer reviewed the Lovász return and one product has a dependency path + evidence + formalization readiness",
        "on_fail": "no Lovász product is ready for Generator hand-off",
        "fix": "run another Explorer→Lovász→Explorer round, or stop honestly with the partial products you have",
    },
    "research_state": {
        "checks": "derives the cross-phase research state from the ledgers",
        "on_fail": "the run's cross-phase state could not be derived",
        "fix": "ensure the core ledgers exist (route, DAG, lovasz run); re-run after a campaign loop",
    },
    "validate_research_state": {
        "checks": "target hashes match, coverage holds, Lovász was reviewed, Generator was authorized",
        "on_fail": "the run is not in a finalizable state (hash mismatch, missing review, or unauthorized Generator)",
        "fix": "complete the missing step the validator names; do not hand-wave a frozen-target mismatch",
    },
    "lovasz_run": {
        "checks": "deep validation of the whole Lovász run (DAG, worker quality, skeptic minima, independence)",
        "on_fail": "the Lovász run does not meet the deep-run quality bar",
        "fix": "read the validator output for the specific shortfall (often: too few skeptics per node) and re-dispatch",
    },
    "report_grade": {
        "checks": "grades the run's report for quality and honesty",
        "on_fail": "the report did not meet the quality floor",
        "fix": "address the graded weaknesses (usually missing evidence links or status justification) and re-finalize",
    },
    "generator_receipt": {
        "checks": "every generated WIT/Lean artifact has an accepted receipt and matches the frozen target",
        "on_fail": "an artifact was generated without a clean receipt or with a target-hash mismatch",
        "fix": "repair the artifact and re-run the receipt gate; never report LEAN_VERIFIED without a passing receipt",
    },
}

# Gate -> the single concrete recovery command, templated with the real run
# path so the guided next-step engine can hand the user a copy-paste command
# (no `<run>` placeholders). Falls back to `narrate` when there's no one move.
GATE_CMD: dict[str, str] = {
    "route": 'witsoc route "<frozen target>"',
    "decompose": "witsoc run-open {run} --prompt \"<frozen target>\" --loops 1",
    "validate_open_problem": "witsoc campaign run {run} --loops 1",
    "open_problem": "witsoc run-open {run} --prompt \"<frozen target>\" --loops 0",
    "validate_dag_integrity": "witsoc campaign run {run} --loops 1",
    "dag_integrity": "witsoc campaign run {run} --loops 1",
    "campaign_loop": "witsoc run-open {run} --prompt \"<frozen target>\" --loops 1",
    "lovasz_phase": "witsoc campaign run {run}",
    "explorer_review": "witsoc campaign run {run} --loops 1",
    "lovasz_run": "witsoc validate-all {run} --mode deep",
    "report_grade": "witsoc finalize {run}",
    "generator_receipt": "witsoc gates generator-receipt {run}",
    "lovasz_manifest": "witsoc run-open {run} --prompt \"<frozen target>\"",
    "route_state_final": "witsoc run-open {run} --prompt \"<frozen target>\"",
    "campaign_finalize": "witsoc finalize {run}",
    "synthesize_ledgers": "witsoc knowledge nodes {run}",
    "status_lattice": "witsoc gates status-lattice {run}",
}

# Friendly one-liners for the controller's synthesized final_status.
FINAL_STATUS_MEANINGS: dict[str, str] = {
    "VERIFIED_FULL_SOLUTION": "Full solve accepted — math-solve audit + formal receipt + independent re-derivation all passed.",
    "VERIFIED_PARTIAL": "Verified progress: some obligations are machine-proved, but the full target is not solved.",
    "CHECKED_BOUNDED": "Confirmed on bounded/finite instances — real evidence, not a general proof.",
    "CONDITIONAL": "A result that holds under a stated assumption.",
    "CONJECTURE": "Evidence gathered, no proof — a hypothesis.",
    "PARTIAL": "Partial progress recorded; the target remains open.",
    "FAILED_ATTEMPT": "Attempts ran but did not close the target — recorded as failure memory.",
    "STILL_OPEN": "No supported result yet. The target is still open.",
    "FAILED_GATE": "The run halted at a gate before producing a finalizable result (see below).",
}


def _f(value: Any, default: str = "?") -> str:
    return str(value) if value not in (None, "") else default


def explain_status_block(labels: list[str]) -> str:
    """Render a legend for one or more status labels."""
    lines = []
    for label in labels:
        lines.append(f"  {status_vocab.normalize(label)} — {status_vocab.explain(label)}")
    return "\n".join(lines)


# --- bus narration ------------------------------------------------------------
def bus_human(status: dict) -> str:
    """One-line + guidance header for a `witsoc bus status` record."""
    pend = int(status.get("pending", 0) or 0)
    if not status.get("enabled", True):
        return "Intelligence Bus: disabled for this run (engines run without orchestrator help)."
    if pend == 0:
        return "Intelligence Bus: nothing pending — engines have everything they asked for. Re-run your last witsoc command to proceed."
    by_role = status.get("pending_by_role", {}) or {}
    roles = ", ".join(f"{n}×{r}" for r, n in sorted(by_role.items(), key=lambda kv: -kv[1]))
    return (
        f"Intelligence Bus: PAUSED — {pend} request(s) need you" + (f" ({roles})." if roles else ".") + "\n"
        f"  These are asks for intelligence (ideas, proof sketches, skeptic checks). Witsoc cannot continue until they're answered.\n"
        f"  Next:  witsoc bus next-batch --max {pend}      (get a self-contained packet; answer each)\n"
        f"  Then:  witsoc bus-apply <run-dir>  and re-run your last command (engines consume the replies and proceed)\n"
        f"  Every reply enters as an OPEN_UNFALSIFIED candidate — answering NEVER upgrades a claim; witsoc's gates still verify everything."
    )


def batch_human(batch: dict) -> str:
    """Header for a `witsoc bus next-batch` fulfillment packet."""
    count = int(batch.get("count", 0) or 0)
    if count == 0:
        return "No pending requests to fulfill — re-run your last witsoc command."
    by_role: dict[str, int] = {}
    for r in batch.get("requests", []):
        by_role[str(r.get("role"))] = by_role.get(str(r.get("role")), 0) + 1
    roles = ", ".join(f"{n}×{r}" for r, n in sorted(by_role.items(), key=lambda kv: -kv[1]))
    return (
        f"You are fulfilling {count} witsoc Intelligence-Bus request(s): {roles}.\n"
        f"  For each: read its `payload.instructions`, follow its `reply_shape_hint`, and submit ONE JSON object.\n"
        f"  Submit:  witsoc bus fulfill --id <id> --reply-json '<json>'   (or fulfill-batch --file replies.jsonl)\n"
        f"  Independent requests can be fanned out to parallel subagents (~10 each).\n"
        f"  Then:    witsoc bus-apply <run-dir>  and re-run your last command. Your replies are untrusted candidates — the kernel/gates verify them."
    )


# --- controller narration -----------------------------------------------------
def _phase_progress(gates: list[dict]) -> str:
    total = len(gates)
    done = sum(1 for g in gates if g.get("ok"))
    first_fail = next((g for g in gates if not g.get("ok")), None)
    if first_fail is None:
        return f"all {total} checks passed"
    idx = gates.index(first_fail) + 1
    return f"halted at check {idx} of {total} ({first_fail.get('gate')})"


def controller_human(result: dict) -> str:
    """Render a witsoc_run_controller.json result as a 'you are here' block."""
    gates = result.get("gates", []) or []
    status = result.get("status", {}) or {}
    final = str(status.get("final_status") or "?")
    run_dir = _f(result.get("run_dir"))
    valid = bool(result.get("valid"))

    head = f"WITSOC · {run_dir}\n  {_phase_progress(gates)}."
    final_line = f"  Final status: {final} — {FINAL_STATUS_MEANINGS.get(final, status_vocab.explain(final))}"

    if valid:
        products = status.get("accepted_products", []) or []
        prod_line = (
            f"  Accepted products: {len(products)} "
            f"({', '.join(sorted({str(p.get('status')) for p in products}))})." if products
            else "  No accepted products — the target is not closed."
        )
        return "\n".join([head, "  All gates passed.", final_line, prod_line, *_snapshot_lines(Path(run_dir))])

    # failure path: explain the FIRST failing gate and how to recover.
    fail = result.get("next_repair") or next((g for g in gates if not g.get("ok")), None)
    if not fail:
        return f"{head}\n{final_line}"
    gate = str(fail.get("gate") or "?")
    help_ = GATE_HELP.get(gate)
    block = [head, f"  Gate that stopped the run: {gate}"]
    if help_:
        block.append(f"  What it checks: {help_['checks']}.")
        block.append(f"  What happened: {help_['on_fail']}.")
        block.append(f"  Your options:")
        block.append(f"    • {help_['fix']}")
        block.append(f"    • Stop honestly: report the partial results you have — a documented stop is a valid outcome.")
    else:
        block.append(f"  What happened: this gate returned a non-zero exit. See its log for detail.")
        block.append(f"  Your options:")
        block.append(f"    • Inspect: {_f(fail.get('stderr_path'), 'controller_logs/' + gate + '.stderr')}")
        block.append(f"    • Stop honestly with the partial results you have.")
    block.extend(_snapshot_lines(Path(run_dir)))
    block.append(f"  Witsoc did NOT downgrade this gate to prose — the failure is real. (Full record: witsoc_run_controller.json)")
    block.append(final_line)
    return "\n".join(block)


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _bus_status() -> dict:
    """Live bus status (global/env bus dir). Lazy import avoids a load-time cycle."""
    try:
        import request_bus
        return request_bus.status()
    except Exception:
        return {}


def _target_of(run_dir: Path, controller: dict | None) -> str:
    if controller and controller.get("prompt"):
        return str(controller["prompt"])
    lov = _load(run_dir / "lovasz_run.json") or {}
    if isinstance(lov, dict):
        for k in ("target", "frozen_target", "prompt", "statement"):
            if lov.get(k):
                return str(lov[k])
    return "(target not recorded)"


def _records_flexible(path: Path, *keys: str) -> list[dict]:
    value = _load(path)
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        for key in keys:
            rows = value.get(key)
            if isinstance(rows, list):
                return [x for x in rows if isinstance(x, dict)]
        if value:
            return [value]
    return []


def _open_problem_snapshot(run_dir: Path) -> dict:
    barriers = _records_flexible(run_dir / "barrier_attacks.json", "barriers", "records")
    barrier = barriers[0] if barriers else {}
    feedback = _load(run_dir / "gap_feedback.json")
    gap_nodes = (feedback or {}).get("nodes", {}) if isinstance(feedback, dict) else {}
    first_gap = {}
    first_gap_id = ""
    if isinstance(gap_nodes, dict):
        for node_id, gap in gap_nodes.items():
            if isinstance(gap, dict):
                first_gap_id = str(node_id)
                first_gap = gap
                break
    products = _records_flexible(run_dir / "product_selection.json")
    selected = next((p for p in products if p.get("selected") is True), {})
    return {
        "barrier_id": barrier.get("barrier_id"),
        "barrier": barrier.get("actual_barrier_lemma") or barrier.get("statement"),
        "why_blocks": barrier.get("why_it_blocks_target"),
        "next_attempt": barrier.get("next_exact_attempt"),
        "gap_node": first_gap_id,
        "gap_class": first_gap.get("gap_class"),
        "next_mutation": first_gap.get("proposed_mutation"),
        "selected_product": selected.get("statement"),
        "selected_product_kind": selected.get("kind"),
    }


def _snapshot_lines(run_dir: Path) -> list[str]:
    snap = _open_problem_snapshot(run_dir)
    lines: list[str] = []
    if snap.get("barrier"):
        lines.append(f"  Current barrier: {_f(snap.get('barrier_id'), 'barrier')} — {snap['barrier']}")
    if snap.get("gap_class"):
        lines.append(
            f"  Current gap: {snap['gap_class']} on {_f(snap.get('gap_node'), 'unknown node')}; "
            f"next mutation: {_f(snap.get('next_mutation'), 'not recorded')}"
        )
    elif snap.get("barrier"):
        lines.append(f"  Next barrier attempt: {_f(snap.get('next_attempt'), 'not recorded')}")
    if snap.get("selected_product"):
        lines.append(
            f"  Selected product: {_f(snap.get('selected_product_kind'), 'product')} — {snap['selected_product']}"
        )
    return lines


# --- U3: guided next-step engine ----------------------------------------------
def recommend_next(run_dir: Path) -> dict:
    """The single recommended next command for a run, fully substituted with the
    real run path (no placeholders the user must edit) + a one-line why. Pure
    inspection of existing ledgers — it never runs anything."""
    run = str(run_dir)
    bus = _bus_status()
    pend = int(bus.get("pending", 0) or 0)
    if pend > 0 and bus.get("enabled", True):
        return {"command": f"witsoc bus next-batch --max {pend}",
                "why": f"{pend} intelligence request(s) are blocking the run — answer them, then re-run your last command."}
    controller = _load(run_dir / "witsoc_run_controller.json")
    if not isinstance(controller, dict):
        return {"command": f'witsoc run-open {run} --prompt "<frozen target>" --loops 0',
                "why": "No run here yet — seed and attack the target (fill in the frozen statement)."}
    if controller.get("valid"):
        return {"command": f"witsoc dashboard {run}",
                "why": "All gates passed — review the result and its accepted products."}
    gates = controller.get("gates", []) or []
    fail = controller.get("next_repair") or next((g for g in gates if not g.get("ok")), None)
    if not fail:
        return {"command": f"witsoc narrate {run}", "why": "Review the current run state."}
    gate = str(fail.get("gate") or "")
    tmpl = GATE_CMD.get(gate)
    command = tmpl.format(run=run) if tmpl else f"witsoc narrate {run}"
    why = (GATE_HELP.get(gate, {}) or {}).get("fix") or f"recover the failing gate ({gate})"
    return {"command": command, "why": why}


# --- U5: machine-readable UI-state contract -----------------------------------
def build_ui_state(run_dir: Path) -> dict:
    """A stable render contract (`witsoc.ui_state.v1`) the terminal dashboard
    renders from — and that an external surface (e.g. the Witsoc plugin) could
    render too. Restates ledgers; computes nothing about the mathematics."""
    controller = _load(run_dir / "witsoc_run_controller.json")
    gates = (controller or {}).get("gates", []) or []
    status = (controller or {}).get("status", {}) or {}
    done = sum(1 for g in gates if g.get("ok"))
    total = len(gates)
    first_fail = next((g for g in gates if not g.get("ok")), None)
    final = str(status.get("final_status") or ("complete" if (controller or {}).get("valid") and gates else "not_started"))

    dag = _load(run_dir / "proof_dependency_dag.json")
    closed = open_ = 0
    if isinstance(dag, list):
        for n in dag:
            if status_vocab.normalize((n or {}).get("status")) in status_vocab.ACCEPTED_STATUSES:
                closed += 1
            else:
                open_ += 1

    bus = _bus_status()
    products = status.get("accepted_products", []) or []
    if not controller:
        label, paused = "not started", False
    elif controller.get("valid") and gates:
        label, paused = "complete", False
    elif first_fail:
        label, paused = f"halted: {first_fail.get('gate')}", True
    else:
        label, paused = "in progress", int(bus.get("pending", 0) or 0) > 0

    return {
        "schema": "witsoc.ui_state.v1",
        "run_dir": str(run_dir),
        "target": _target_of(run_dir, controller),
        "phase": {"index": done, "total": total, "label": label, "paused": paused},
        "gates": [{"name": g.get("gate"), "status": "ok" if g.get("ok") else "fail"} for g in gates],
        "nodes": {"closed": closed, "open": open_},
        "bus": {"pending": int(bus.get("pending", 0) or 0), "by_role": bus.get("pending_by_role", {}) or {}},
        "products": [{"status": p.get("status"), "statement": p.get("statement")} for p in products],
        "open_problem": _open_problem_snapshot(run_dir),
        "final_status": final,
        "trust": FINAL_STATUS_MEANINGS.get(final) or status_vocab.explain(final),
        "next": recommend_next(run_dir),
    }


# --- U2: the run dashboard (terminal UI) --------------------------------------
def format_dashboard(state: dict, stream=None) -> str:
    import witsoc_ui
    if stream is None:
        stream = sys.stdout
    ui = witsoc_ui.UI.for_stream(stream)
    phase = state.get("phase", {}) or {}
    done, total = int(phase.get("index", 0) or 0), int(phase.get("total", 0) or 0)
    target = str(state.get("target") or "")
    if len(target) > 68:
        target = target[:65] + "..."
    state_glyph = ui.status("PAUSE" if phase.get("paused") else ("OK" if phase.get("label") == "complete" else "RUN"))

    lines: list[str] = []
    lines.append(f"Target  {ui.paint(target, 'cyan')}")
    lines.append(f"Phase   {phase.get('label', '?')}   {ui.bar(done, total)}  {done}/{total}  {state_glyph}")
    lines.append("__rule__")
    fail_name = next((g.get("name") for g in state.get("gates", []) if g.get("status") == "fail"), None)
    gate_line = f"Gates   {ui.status('ok')} {done}/{total} passed"
    if fail_name:
        gate_line += f"   {ui.status('fail')} {fail_name}"
    lines.append(gate_line)
    nodes = state.get("nodes", {}) or {}
    if nodes.get("closed") or nodes.get("open"):
        c, o = int(nodes.get("closed", 0)), int(nodes.get("open", 0))
        lines.append(f"Nodes   closed {c} / open {o}   {ui.bar(c, c + o, 10)}")
    open_problem = state.get("open_problem", {}) or {}
    if open_problem.get("barrier"):
        barrier = str(open_problem.get("barrier"))
        if len(barrier) > 54:
            barrier = barrier[:51] + "..."
        gap = str(open_problem.get("gap_class") or "gap pending")
        mutation = str(open_problem.get("next_mutation") or open_problem.get("next_attempt") or "")
        if len(mutation) > 42:
            mutation = mutation[:39] + "..."
        lines.append(f"Barrier {ui.paint(gap, 'yellow')} · {barrier}")
        if mutation:
            lines.append(f"Mutate  {mutation}")
    bus = state.get("bus", {}) or {}
    if int(bus.get("pending", 0) or 0) > 0:
        roles = ", ".join(f"{n}×{r}" for r, n in sorted((bus.get("by_role", {}) or {}).items(), key=lambda kv: -kv[1]))
        lines.append(f"Bus     {ui.status('PAUSE')} {bus['pending']} pending ({roles})")
    products = state.get("products", []) or []
    if products:
        kinds = ", ".join(sorted({str(p.get("status")) for p in products}))
        lines.append(f"Output  {len(products)} accepted product(s) ({kinds})")
    final = str(state.get("final_status") or "?")
    trust = str(state.get("trust") or "")
    if len(trust) > 60:
        trust = trust[:57] + "..."
    fstyle = "green" if final.startswith(("VERIFIED", "CHECKED", "complete")) else ("red" if "FAIL" in final else "yellow")
    lines.append(f"Status  {ui.paint(final, fstyle, 'bold')} — {trust}")
    lines.append("__rule__")
    nxt = state.get("next", {}) or {}
    why = str(nxt.get("why", ""))
    if len(why) > 84:
        why = why[:81] + "..."
    lines.append(f"{ui.glyph('arrow')} NEXT   {ui.paint(nxt.get('command', ''), 'bold', 'cyan')}")
    lines.append(f"        {ui.paint(why, 'dim')}")
    return ui.box(f"WITSOC · {state.get('run_dir')}", lines)


def render_dashboard(run_dir: Path, as_json: bool = False, stream=None) -> str:
    state = build_ui_state(run_dir)
    if as_json:
        return json.dumps(state, indent=2, ensure_ascii=False)
    return format_dashboard(state, stream)


# --- CLI ----------------------------------------------------------------------
def narrate_run(run_dir: Path) -> str:
    parts: list[str] = []
    controller = _load(run_dir / "witsoc_run_controller.json")
    if isinstance(controller, dict):
        parts.append(controller_human(controller))
    else:
        parts.append(f"WITSOC · {run_dir}\n  No controller record yet (run `witsoc run-open {run_dir} --prompt \"<target>\"`).")
    # bus state, if a bus lives under the run dir
    bus_status_file = run_dir / "bus" / "status.json"
    bus = _load(bus_status_file)
    if isinstance(bus, dict):
        parts.append(bus_human(bus))
    return "\n\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(prog="witsoc narrate",
                                     description="Plain-language narration of witsoc run state.")
    sub = parser.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="narrate a run directory (default)")
    p_run.add_argument("run_dir", type=Path)

    p_dash = sub.add_parser("dashboard", help="one-screen terminal dashboard for a run")
    p_dash.add_argument("run_dir", type=Path)
    p_dash.add_argument("--json", action="store_true", help="emit the witsoc.ui_state.v1 contract instead of the rendered view")

    p_next = sub.add_parser("next-step", help="the single recommended next command for a run")
    p_next.add_argument("run_dir", type=Path)

    p_status = sub.add_parser("explain-status", help="explain one or more status labels")
    p_status.add_argument("labels", nargs="+")

    # allow `witsoc narrate <run-dir>` with no subcommand
    argv = sys.argv[1:]
    known = {"run", "dashboard", "next-step", "explain-status", "-h", "--help"}
    if argv and argv[0] not in known:
        argv = ["run", *argv]
    args = parser.parse_args(argv)

    if args.cmd == "explain-status":
        print(explain_status_block(args.labels))
        return 0
    if args.cmd == "dashboard":
        print(render_dashboard(args.run_dir, as_json=args.json))
        return 0
    if args.cmd == "next-step":
        nxt = recommend_next(args.run_dir)
        import witsoc_ui
        ui = witsoc_ui.UI.for_stream(sys.stdout)
        print(f"{ui.glyph('arrow')} NEXT   {ui.paint(nxt['command'], 'bold', 'cyan')}")
        print(f"        {ui.paint(nxt['why'], 'dim')}")
        return 0
    if args.cmd == "run":
        print(narrate_run(args.run_dir))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
