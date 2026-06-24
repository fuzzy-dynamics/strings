#!/usr/bin/env python3
"""Assemble the derived Explorer/Generator research state for one Witsoc run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ACCEPTED = {
    "VERIFIED",
    "VERIFIED_WIT",
    "VERIFIED_LEAN",
    "VERIFIED_EXTERNAL",
    "CHECKED",
    "CHECKED_SYMBOLIC",
    "CHECKED_BOUNDED",
    "PROVED_SKETCH",
    "PARTIAL",
    "CONDITIONAL",
}
CANDIDATE_ONLY = {
    "ATTACK_CANDIDATE",
    "PROOF_SKETCH_CANDIDATE",
    "LEMMA_CANDIDATE",
    "REDUCTION_CANDIDATE",
    "COUNTEREXAMPLE_CANDIDATE",
    "OPEN_UNFALSIFIED",
}
OPENISH = {"OPEN", "UNSOLVED", "UNCONFIRMED", "CONJECTURE", "GAP", "FAILED_ATTEMPT", "REJECTED", "DEMOTED"}

# Research-director API used by engine_dispatch/autonomous_campaign.
APPROACHES = [
    "direct_prover",
    "premise_retrieval",
    "analogical_transfer",
    "speculative_arena",
    "conjecture_mining",
    "counterexample_search",
    "finite_reduction",
    "construction_search",
    "ontology_pivot",
    "invention",
]
RUNG_REWARD = {"L0": 0.0, "L1": 0.1, "L2": 0.25, "L3": 0.4, "L4": 0.65, "L5": 0.8, "L6": 1.0}
DEADEND_STREAK = 3


def new_state(target: str) -> dict[str, Any]:
    return {
        "schema": "witsoc.research_state.v1",
        "target": target,
        "target_hash": sha(target),
        "status": "ACTIVE",
        "sessions": 0,
        "best_rung": "L0",
        "partial_results": [],
        "dead_ends": [],
        "approach_stats": {a: {"tries": 0, "reward": 0.0, "streak_l0": 0} for a in APPROACHES},
        "attempt_ledger": [],
    }


def select_approach(state: dict[str, Any], priors: dict[str, float] | None = None) -> str | None:
    priors = priors or {}
    dead = set(state.get("dead_ends") or [])
    candidates = [a for a in APPROACHES if a not in dead]
    if not candidates:
        return None
    stats = state.setdefault("approach_stats", {a: {"tries": 0, "reward": 0.0, "streak_l0": 0} for a in APPROACHES})

    def score(a: str) -> tuple[float, str]:
        s = stats.setdefault(a, {"tries": 0, "reward": 0.0, "streak_l0": 0})
        tries = int(s.get("tries", 0) or 0)
        avg = float(s.get("reward", 0.0) or 0.0) / tries if tries else 0.0
        exploration = 1.0 / (1 + tries)
        return (avg + exploration + float(priors.get(a, 0.0) or 0.0), a)

    return max(candidates, key=score)


def record(state: dict[str, Any], approach: str, outcome: dict[str, Any]) -> None:
    stats = state.setdefault("approach_stats", {a: {"tries": 0, "reward": 0.0, "streak_l0": 0} for a in APPROACHES})
    s = stats.setdefault(approach, {"tries": 0, "reward": 0.0, "streak_l0": 0})
    rung = str(outcome.get("rung") or "L0")
    reward = RUNG_REWARD.get(rung, 0.0)
    s["tries"] = int(s.get("tries", 0) or 0) + 1
    s["reward"] = float(s.get("reward", 0.0) or 0.0) + reward
    s["streak_l0"] = int(s.get("streak_l0", 0) or 0) + 1 if reward <= 0 else 0
    if s["streak_l0"] >= DEADEND_STREAK and approach not in state.setdefault("dead_ends", []):
        state["dead_ends"].append(approach)
    if reward > RUNG_REWARD.get(str(state.get("best_rung") or "L0"), 0.0):
        state["best_rung"] = rung
    if rung in {"L4", "L5"} or str(outcome.get("status") or "").upper() in {"CHECKED", "VERIFIED_LEAN", "VERIFIED"}:
        if outcome.get("partial") or rung in {"L4", "L5"}:
            state.setdefault("partial_results", []).append({"approach": approach, **outcome})
    if rung == "L6" and str(outcome.get("status") or "").upper() in {"VERIFIED", "VERIFIED_LEAN"}:
        state["status"] = "SOLVED"
    state.setdefault("attempt_ledger", []).append({"approach": approach, "outcome": outcome})


def run_campaign(target: str, execute, max_steps: int = 12, state: dict[str, Any] | None = None) -> dict[str, Any]:
    state = state or new_state(target)
    state["sessions"] = int(state.get("sessions", 0) or 0) + 1
    for _ in range(max_steps):
        if state.get("status") != "ACTIVE":
            break
        approach = select_approach(state)
        if approach is None:
            state["status"] = "HONEST_STOP"
            break
        record(state, approach, execute(approach, target))
    if state.get("status") == "ACTIVE" and state.get("best_rung") == "L0":
        state["status"] = "STALLED"
    return state


def save(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def records(path: Path) -> list[dict[str, Any]]:
    data = load(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def target_from_handoff_v1(handoff: dict[str, Any]) -> tuple[str, str]:
    target = handoff.get("target_formalization") if isinstance(handoff.get("target_formalization"), dict) else {}
    claim = first_text(target.get("claim"))
    target_hash = sha(json.dumps(target, sort_keys=True, ensure_ascii=False)) if target else ""
    return claim, target_hash


def target_from_handoff(handoff: dict[str, Any]) -> tuple[str, str, str]:
    target = handoff.get("target") if isinstance(handoff.get("target"), dict) else {}
    freeze = handoff.get("target_freeze") if isinstance(handoff.get("target_freeze"), dict) else {}
    statement = first_text(target.get("canonical_statement"), target.get("conclusion"), handoff.get("user_intent"))
    target_hash = first_text(freeze.get("target_hash"), freeze.get("frozen_target_hash"), sha(statement) if statement else "")
    status = str(handoff.get("problem_status") or "").upper()
    return statement, target_hash, status


def assemble(run: Path) -> dict[str, Any]:
    route = load(run / "witsoc_route_state.json", {})
    manifest = load(run / "lovasz_run.json", {})
    handoff = load(run / "handoff.json", {})
    handoff_v1 = load(run / "handoff_v1.json", {})
    explorer = load(run / "explorer_return_packet.json", {})
    grade = load(run / "report_quality_grade.json", {})
    formal = load(run / "formalization_feasibility.json", {})
    artifacts = load(run / "witsoc_artifacts.json", {})
    generator_package = load(run / "generator_package.json", {})
    generator_preflight = load(run / "generator_preflight.json", {})
    generator_receipt = load(run / "generator_artifact_receipt.json", {})
    controller = load(run / "witsoc_run_controller.json", {})
    dag = records(run / "proof_dependency_dag.json")
    workers = records(run / "worker_results.json")
    queue = records(run / "actual_lemma_queue.json")
    reviews = records(run / "skeptic_reviews.json")
    retry = records(run / "retry_ledger.json")
    products = records(run / "product_selection.json")

    h_text, h_hash, h_status = target_from_handoff(handoff if isinstance(handoff, dict) else {})
    v1_text, v1_hash = target_from_handoff_v1(handoff_v1 if isinstance(handoff_v1, dict) else {})
    target_text = first_text(manifest.get("source_target_text") if isinstance(manifest, dict) else "", h_text, v1_text)
    target_hash = first_text(
        manifest.get("target_hash") if isinstance(manifest, dict) else "",
        explorer.get("target_hash") if isinstance(explorer, dict) else "",
        h_hash,
        v1_hash,
        sha(target_text) if target_text else "",
    )
    statuses = [str(x.get("status") or "").upper() for x in dag + workers if isinstance(x, dict)]
    accepted_products = [
        x for x in dag + workers
        if isinstance(x, dict) and str(x.get("status") or "").upper() in ACCEPTED
    ]
    candidate_products = [
        x for x in dag + workers
        if isinstance(x, dict) and str(x.get("status") or "").upper() in CANDIDATE_ONLY
    ]
    remaining = [
        x for x in dag
        if isinstance(x, dict) and str(x.get("status") or "OPEN").upper() in OPENISH
    ]
    problem_status = h_status or ("OPEN" if remaining else ("SOLVED" if accepted_products else "UNKNOWN"))
    route_chain = route.get("chain") if isinstance(route, dict) and isinstance(route.get("chain"), list) else []
    selected_products = [p for p in products if p.get("selected") is True]
    artifact_items = artifacts.get("artifacts") if isinstance(artifacts, dict) and isinstance(artifacts.get("artifacts"), list) else []
    source_citations = handoff.get("source_citations") if isinstance(handoff, dict) and isinstance(handoff.get("source_citations"), list) else []
    falsification = handoff.get("falsification_pass") if isinstance(handoff, dict) and isinstance(handoff.get("falsification_pass"), list) else []
    obstructions = handoff.get("obstructions") if isinstance(handoff, dict) and isinstance(handoff.get("obstructions"), list) else []
    barrier_map = handoff.get("barrier_map") if isinstance(handoff, dict) and isinstance(handoff.get("barrier_map"), list) else []

    return {
        "schema": "witsoc.research_state.v1",
        "run_dir": str(run),
        "target": {"text": target_text, "hash": target_hash, "problem_status": problem_status},
        "route": {
            "exists": bool(route),
            "chain": route_chain,
            "lovasz_required": bool(route.get("lovasz_required")) if isinstance(route, dict) else False,
            "generator_authorized": bool(route.get("generator_authorized")) if isinstance(route, dict) else False,
            "requires_explorer_review_after_lovasz": bool(route.get("requires_explorer_review_after_lovasz")) if isinstance(route, dict) else False,
        },
        "explorer": {
            "handoff_exists": bool(handoff),
            "handoff_v1_exists": bool(handoff_v1),
            "source_count": len(source_citations),
            "falsification_count": len(falsification),
            "obstruction_count": len(obstructions),
            "barrier_count": len(barrier_map),
            "actual_lemma_queue_count": len(queue),
            "return_packet_exists": bool(explorer),
            "return_decision": explorer.get("recommended_action") if isinstance(explorer, dict) else None,
            "selected_product_count": len(selected_products),
        },
        "lovasz": {
            "manifest_exists": bool(manifest),
            "dag_nodes": len(dag),
            "worker_results": len(workers),
            "accepted_products": len(accepted_products),
            "candidate_products": len(candidate_products),
            "remaining_openish": len(remaining),
            "skeptic_reviews": len(reviews),
            "retry_records": len(retry),
        },
        "generator": {
            "artifact_registry_count": len(artifact_items),
            "has_wit_or_lean_artifact": any(str(a.get("type") or "").lower() in {"wit", "lean"} for a in artifact_items if isinstance(a, dict)),
            "package_exists": bool(generator_package),
            "package_status": generator_package.get("witsoc_status") if isinstance(generator_package, dict) else None,
            "preflight_exists": bool(generator_preflight),
            "receipt_gate_exists": bool(generator_receipt),
        },
        "quality": {
            "report_grade": grade.get("grade") if isinstance(grade, dict) else None,
            "progress_grade": grade.get("progress_grade") if isinstance(grade, dict) else None,
            "formalization_label": formal.get("label") if isinstance(formal, dict) else None,
        },
        "hashes": {
            "manifest": manifest.get("target_hash") if isinstance(manifest, dict) else None,
            "explorer_return": explorer.get("target_hash") if isinstance(explorer, dict) else None,
            "handoff": h_hash or None,
            "handoff_v1": v1_hash or None,
        },
        "controller_valid": controller.get("valid") if isinstance(controller, dict) else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    state = assemble(args.run_dir)
    out = args.out or (args.run_dir / "witsoc_research_state.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(state, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
