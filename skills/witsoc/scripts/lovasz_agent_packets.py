#!/usr/bin/env python3
"""Strict packet schemas for Lovasz open-problem agent roles.

Packets are coordination artifacts, not mathematical evidence. A packet can
propose, refute, reduce, formalize, or summarize, but it cannot promote trust.
Lovasz is outside the honesty loop: it emits candidates, and downstream gates
decide whether any candidate becomes evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROLES = {"Builder", "Destroyer", "Reducer", "Formalizer", "Historian", "Strategist", "Skeptic"}
CANDIDATE_STATUSES = {
    "ATTACK_CANDIDATE",
    "PROOF_SKETCH_CANDIDATE",
    "LEMMA_CANDIDATE",
    "REDUCTION_CANDIDATE",
    "COUNTEREXAMPLE_CANDIDATE",
    "OPEN_UNFALSIFIED",
}
PROCESS_STATUSES = {"PROPOSED", "REFUTED", "BLOCKED", "NEEDS_FORMALIZATION", "FORMALIZED", "REVIEWED", "MUTATE"}
STATUSES = CANDIDATE_STATUSES | PROCESS_STATUSES
FORBIDDEN_STATUSES = {
    "VERIFIED",
    "VERIFIED_WIT",
    "VERIFIED_LEAN",
    "VERIFIED_EXTERNAL",
    "CHECKED",
    "CHECKED_SYMBOLIC",
    "CHECKED_BOUNDED",
    "PROVED",
    "PROVED_SKETCH",
    "PARTIAL",
    "CONDITIONAL",
    "SOLVED",
    "MATHEMATICAL_SOLVE",
    "FORMAL_SOLVE",
    "SOLVE_ACCEPTED",
}

ROLE_REQUIRED = {
    "Builder": {"candidate_statement", "evidence_plan"},
    "Destroyer": {"counterexample_plan", "falsification_scope"},
    "Reducer": {"source_statement", "target_statement", "reduction_direction"},
    "Formalizer": {"informal_statement", "lean_statement", "faithfulness_risk"},
    "Historian": {"source_refs", "known_results_checked"},
    "Strategist": {"recommended_axis", "rationale"},
    "Skeptic": {"review_targets", "risk_flags"},
}


def template(role: str) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"unknown role: {role}")
    packet = {
        "schema": "witsoc.lovasz_agent_packet.v1",
        "role": role,
        "target_hash": "<frozen target hash>",
        "node_id": "<node or rung id>",
        "barrier_id": "<barrier id or null>",
        "status": "ATTACK_CANDIDATE",
        "claim_scope": "candidate_only",
        "trust_boundary": "lovasz_candidate_only",
        "evidence": [],
        "repro": {"commands": [], "artifacts": []},
    }
    for field in ROLE_REQUIRED[role]:
        packet[field] = []
    return packet


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if packet.get("schema") != "witsoc.lovasz_agent_packet.v1":
        errors.append("schema must be witsoc.lovasz_agent_packet.v1")
    role = packet.get("role")
    if role not in ROLES:
        errors.append("role is unknown")
    if not packet.get("target_hash"):
        errors.append("target_hash is required")
    if not (packet.get("node_id") or packet.get("barrier_id")):
        errors.append("node_id or barrier_id is required")
    status = str(packet.get("status") or "")
    if status in FORBIDDEN_STATUSES:
        errors.append(f"packet status may not assert trust: {status}")
    elif status not in STATUSES:
        errors.append(f"status is not in the Lovasz packet vocabulary: {status}")
    if not isinstance(packet.get("evidence"), list):
        errors.append("evidence must be a list")
    if packet.get("claim_scope") not in {"candidate_only", "planning_only", "refutation_candidate"}:
        errors.append("claim_scope must be candidate_only/planning_only/refutation_candidate")
    if status in CANDIDATE_STATUSES and packet.get("trust_boundary") not in {"lovasz_candidate_only", "downstream_gate_required"}:
        errors.append("candidate packets must declare trust_boundary=lovasz_candidate_only or downstream_gate_required")
    repro = packet.get("repro")
    if not isinstance(repro, dict) or not isinstance(repro.get("commands", []), list) or not isinstance(repro.get("artifacts", []), list):
        errors.append("repro must contain commands/artifacts lists")
    if role in ROLE_REQUIRED:
        for field in ROLE_REQUIRED[role]:
            if field not in packet:
                errors.append(f"{role} packet missing {field}")
    return {
        "schema": "witsoc.lovasz_agent_packet_validation.v1",
        "ok": not errors,
        "errors": errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template")
    t.add_argument("--role", required=True, choices=sorted(ROLES))
    v = sub.add_parser("validate")
    v.add_argument("--file", type=Path, required=True)
    args = ap.parse_args()
    if args.cmd == "template":
        out = template(args.role)
        code = 0
    else:
        out = validate_packet(json.loads(args.file.read_text(encoding="utf-8")))
        code = 0 if out["ok"] else 1
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
