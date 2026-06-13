#!/usr/bin/env python3
"""L1 proof-gap -> barrier feedback — `witsoc gap-feedback`.

Closes the loop the docs mandate but nothing enforced: worker failures used to
land in worker_results.json and stop there, so re-dispatch could retry the same
statement with cosmetic changes forever. After every worker batch this script

  1. classifies each non-closed result into exactly one gap class:
       prover_search_gap    the current prover/tactic portfolio missed
       genuine_barrier      the mathematics resisted after external/bus pressure
       formalization_block  the kernel never saw a real goal (GAP, no
                            lean_statement, artifact issues, REJECTED drift)
       precondition_gap     a needed lemma/hypothesis is missing (OPEN,
                            missing_barrier_lemma, theorem_precondition_gap)
  2. proposes ONE one-axis mutation per node, rotating axes across rounds so
     round 2 never re-proposes round 1's axis;
  3. records each new failure in lovasz.soc (FAILED_APPROACHES) with a
     do_not_repeat condition;
  4. writes gap_feedback.json — the ledger lovasz_worker_dispatch checks
     before re-dispatch: a node whose statement hash is unchanged since its
     last failure and whose DAG entry carries no `mutation_applied` is
     BLOCKED_NO_MUTATION.

Deterministic; never upgrades a status, never invents mathematics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import lovasz_soc_memory as soc

FAILED_STATUSES = {"FAILED_ATTEMPT", "OPEN", "GAP", "REJECTED"}
AXIS_FOR_GAP = {
    "genuine_barrier": "invariant",
    "formalization_block": "formalization_target",
    "precondition_gap": "theorem_source",
    "prover_search_gap": "method",
}

GAP_CLASS_FOR_FAILURE = {
    "genuine_mathematical_barrier": "genuine_barrier",
    "prover_search_gap": "prover_search_gap",
    "prover_reply_failed_kernel_replay": "prover_search_gap",
    "missing_barrier_lemma": "precondition_gap",
    "theorem_precondition_gap": "precondition_gap",
    "artifact_issue": "formalization_block",
}

GAP_CLASS_FOR_STATUS = {
    "FAILED_ATTEMPT": "genuine_barrier",
    "OPEN": "precondition_gap",
    "GAP": "formalization_block",
    "REJECTED": "formalization_block",
}

MUTATION_AXES = {
    "genuine_barrier": [
        "strengthen the induction/invariant hypothesis (one hypothesis only)",
        "weaken the node to a bounded special case and keep the residual gap explicit",
        "switch encoding: contrapositive, alternate induction scheme, or normal form",
    ],
    "formalization_block": [
        "formalize the node into an explicit Lean goal with all definitions expanded",
        "reformulate with decidable predicates so the kernel can attempt it",
        "split the node until each piece is independently formalizable",
    ],
    "precondition_gap": [
        "run premise retrieval for the missing lemma and add it as an explicit DAG dependency",
        "add the missing hypothesis and retarget the node as a conditional theorem",
        "replace the blocking external theorem with a locally provable weakening",
    ],
    "prover_search_gap": [
        "try a different tactic family or a bus-supplied proof and kernel-replay it",
        "add a proof-bank example for this goal shape and rerun the prover",
        "split the algebra/normalization step into a smaller helper lemma",
    ],
}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def classify(packet: dict) -> str:
    evidence = " ".join(str(e) for e in packet.get("evidence", []))
    if "no lean_statement" in evidence:
        return "formalization_block"
    failure_class = str(packet.get("failure_class") or "")
    if failure_class in GAP_CLASS_FOR_FAILURE:
        return GAP_CLASS_FOR_FAILURE[failure_class]
    return GAP_CLASS_FOR_STATUS.get(str(packet.get("status")), "genuine_barrier")


def proposals_for(packet: dict, gap_class: str) -> list[str]:
    """Mutation axes for a node: the worker's own next_mutation first (when it
    is concrete), then the class table. Rotation index = mutation_round."""
    axes = list(MUTATION_AXES[gap_class])
    own = str(packet.get("next_mutation") or "").strip()
    if own and not own.lower().startswith("mutate one axis"):
        axes.insert(0, own)
    return axes


def node_statement(packet: dict) -> str:
    return str(packet.get("statement") or packet.get("claim") or packet.get("node_id") or "")


def build_feedback(run: Path) -> tuple[dict, list[dict]]:
    raw = (run / "worker_results.json").read_text(encoding="utf-8") if (run / "worker_results.json").exists() else ""
    fingerprint = sha(raw)
    results = load(run / "worker_results.json", [])
    results = [r for r in results if isinstance(r, dict)] if isinstance(results, list) else []
    previous = load(run / "gap_feedback.json", {})
    previous = previous if isinstance(previous, dict) else {}
    previous_nodes = previous.get("nodes", {})
    # Idempotent per worker batch: re-running on the same results must not
    # advance mutation rounds or duplicate .soc entries.
    if previous.get("results_fingerprint") == fingerprint and previous.get("schema") == "witsoc.gap_feedback.v1":
        return previous, []

    nodes: dict[str, dict] = {}
    new_failures: list[dict] = []
    for packet in results:
        status = str(packet.get("status") or "")
        node_id = str(packet.get("node_id") or "")
        if not node_id or status not in FAILED_STATUSES:
            continue
        statement = node_statement(packet)
        statement_sha = sha(statement)
        gap_class = classify(packet)
        prior = previous_nodes.get(node_id, {})
        if prior.get("failed_statement_sha") == statement_sha:
            mutation_round = int(prior.get("mutation_round", 0)) + 1
        else:
            mutation_round = 0
        axes = proposals_for(packet, gap_class)
        proposed = axes[mutation_round % len(axes)]
        entry = {
            "node_id": node_id,
            "status": status,
            "gap_class": gap_class,
            "failed_statement_sha": statement_sha,
            "mutation_round": mutation_round,
            "proposed_mutation": proposed,
            "evidence": packet.get("evidence", []),
        }
        nodes[node_id] = entry
        is_new = prior.get("failed_statement_sha") != statement_sha or prior.get("status") != status
        if is_new:
            new_failures.append({**entry, "statement": statement, "method": str(packet.get("worker_type") or "PROVER")})

    feedback = {
        "schema": "witsoc.gap_feedback.v1",
        "run_dir": str(run),
        "generated_from": "worker_results.json",
        "results_fingerprint": fingerprint,
        "counts": {
            "failed_nodes": len(nodes),
            "genuine_barrier": sum(1 for n in nodes.values() if n["gap_class"] == "genuine_barrier"),
            "prover_search_gap": sum(1 for n in nodes.values() if n["gap_class"] == "prover_search_gap"),
            "formalization_block": sum(1 for n in nodes.values() if n["gap_class"] == "formalization_block"),
            "precondition_gap": sum(1 for n in nodes.values() if n["gap_class"] == "precondition_gap"),
        },
        "nodes": nodes,
        "redispatch_contract": ("a node listed here may be re-dispatched only after its statement changes "
                                "or its DAG entry records mutation_applied describing the one-axis change"),
    }
    return feedback, new_failures


def record_soc_failures(run: Path, new_failures: list[dict]) -> int:
    count = 0
    for failure in new_failures:
        ns = argparse.Namespace(
            run_dir=run,
            id=f"gap_{failure['node_id']}_r{failure['mutation_round']}",
            method=failure["method"],
            statement=failure["statement"],
            blocker=f"{failure['gap_class']} ({failure['status']})",
            evidence="; ".join(str(e) for e in failure["evidence"][:3]) or "worker_results.json",
            do_not_repeat="same statement and method without the recorded one-axis mutation",
            next_method=[failure["proposed_mutation"]],
        )
        soc.append_failure(ns)
        count += 1
    return count


def record_mutation_ledger(run: Path, feedback: dict) -> int:
    ledger_path = run / "mutation_ledger.json"
    ledger = load(ledger_path, [])
    ledger = [r for r in ledger if isinstance(r, dict)] if isinstance(ledger, list) else []
    existing = {str(r.get("new_attempt_id")) for r in ledger}
    manifest = load(run / "lovasz_run.json", {})
    target_hash = str(manifest.get("target_hash") or "")
    added = 0
    for node_id, gap in (feedback.get("nodes") or {}).items():
        if not isinstance(gap, dict):
            continue
        axis = AXIS_FOR_GAP.get(str(gap.get("gap_class")), "method")
        failed_sha = str(gap.get("failed_statement_sha") or sha(str(node_id)))
        new_id = f"mut-{node_id}-{gap.get('mutation_round', 0)}-{axis}"
        if new_id in existing:
            continue
        ledger.append({
            "target_hash": target_hash,
            "method_family": str(gap.get("gap_class") or "unknown"),
            "previous_attempt_id": failed_sha,
            "new_attempt_id": new_id,
            "axis_changed": axis,
            "what_changed": str(gap.get("proposed_mutation") or f"change {axis}"),
            "why_this_is_not_repeat": "recorded one-axis mutation after gap-feedback classification",
            "result": "PROPOSED",
            "node_id": str(node_id),
        })
        existing.add(new_id)
        added += 1
    if added:
        ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--no-soc", action="store_true", help="skip writing failures into lovasz.soc")
    args = parser.parse_args()

    run = args.run_dir
    feedback, new_failures = build_feedback(run)
    soc_recorded = 0 if args.no_soc else record_soc_failures(run, new_failures)
    feedback["soc_failures_recorded"] = soc_recorded
    feedback["mutation_ledger_recorded"] = record_mutation_ledger(run, feedback)
    out = args.out or (run / "gap_feedback.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(feedback, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    import run_ledger
    run_ledger.auto_ingest(run)  # R1.5: the unified ledger stays fresh
    print(json.dumps(feedback, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
