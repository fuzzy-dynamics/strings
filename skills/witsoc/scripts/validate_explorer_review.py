#!/usr/bin/env python3
"""Validate Explorer arbitration of a Lovasz return packet.

Explorer is the trust boundary after Lovasz: candidate bundles become either a
new Lovasz packet, a repair request, an honest stop, or a Generator handoff.
This gate keeps that decision explicit and blocks Generator-ready claims unless
the packet carries downstream evidence and target-level reduction facts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ACCEPTED_RESULT = {
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
ACTION_ALIASES = {
    "generator_ready": "GENERATOR_READY",
    "explorer_review_partial": "DEMOTE",
    "relaunch_lovasz": "LOVASZ_AGAIN",
    "repair": "LOVASZ_AGAIN",
    "stop_open": "HONEST_STOP",
    "GENERATOR_READY": "GENERATOR_READY",
    "LOVASZ_AGAIN": "LOVASZ_AGAIN",
    "DEMOTE": "DEMOTE",
    "HONEST_STOP": "HONEST_STOP",
}
FORMALIZATION_READY = {"FORMALIZATION_READY", "NEEDS_LOCAL_DEFINITIONS"}


def load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def grade_value(grade: Any) -> int:
    return {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}.get(str(grade or "").upper(), 0)


def packet_path(path: Path) -> Path:
    return path / "explorer_return_packet.json" if path.is_dir() else path


def validate(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if packet.get("schema") != "witsoc.explorer_return_packet.v1":
        errors.append("schema must be witsoc.explorer_return_packet.v1")
    if not packet.get("target_hash"):
        errors.append("target_hash is required")

    raw_action = str(packet.get("recommended_action") or "")
    canonical = ACTION_ALIASES.get(raw_action)
    if canonical is None:
        errors.append(f"recommended_action {raw_action!r} is not an Explorer decision")

    accepted = packet.get("accepted_products") if isinstance(packet.get("accepted_products"), list) else []
    selected = packet.get("selected_products") if isinstance(packet.get("selected_products"), list) else []
    barriers = packet.get("remaining_barriers") if isinstance(packet.get("remaining_barriers"), list) else []
    demoted = packet.get("demoted_claims") if isinstance(packet.get("demoted_claims"), list) else []
    formal = packet.get("formalization") if isinstance(packet.get("formalization"), dict) else {}
    report = packet.get("report_quality") if isinstance(packet.get("report_quality"), dict) else {}
    reduction = packet.get("reduction") if isinstance(packet.get("reduction"), dict) else None

    for index, item in enumerate(accepted):
        if not isinstance(item, dict):
            errors.append(f"accepted_products[{index}] is not an object")
            continue
        status = str(item.get("status") or "").upper()
        if status in CANDIDATE_ONLY:
            errors.append(f"accepted_products[{index}] is candidate-only, not accepted evidence")
        elif status not in ACCEPTED_RESULT:
            errors.append(f"accepted_products[{index}] has unsupported status {status!r}")
        if not item.get("evidence"):
            errors.append(f"accepted_products[{index}] missing evidence")
        if not item.get("dependency_path_to_target"):
            errors.append(f"accepted_products[{index}] missing dependency_path_to_target")

    for index, item in enumerate(barriers):
        if not isinstance(item, dict):
            errors.append(f"remaining_barriers[{index}] is not an object")
            continue
        if not item.get("next_exact_experiment_or_lemma"):
            warnings.append(f"remaining_barriers[{index}] lacks next_exact_experiment_or_lemma")

    if canonical == "GENERATOR_READY":
        if not accepted:
            errors.append("GENERATOR_READY requires accepted_products")
        if len(selected) != 1:
            errors.append("GENERATOR_READY requires exactly one selected product")
        if barriers:
            errors.append("GENERATOR_READY cannot have remaining_barriers")
        if str(formal.get("label") or "") not in FORMALIZATION_READY:
            errors.append("GENERATOR_READY requires FORMALIZATION_READY or NEEDS_LOCAL_DEFINITIONS")
        if grade_value(report.get("grade")) < 4:
            errors.append("GENERATOR_READY requires report grade A/B")
        if report.get("progress_grade") is not None and grade_value(report.get("progress_grade")) < 3:
            errors.append("GENERATOR_READY requires progress grade at least C")
        if reduction:
            if reduction.get("reduced") is not True or reduction.get("open_core_open") not in (0, False, None):
                errors.append("GENERATOR_READY requires reduced target with no open core")
            if reduction.get("band") not in (None, "REDUCED"):
                errors.append("GENERATOR_READY reduction band must be REDUCED")
    elif canonical == "LOVASZ_AGAIN":
        if not barriers and not demoted:
            errors.append("LOVASZ_AGAIN/repair requires remaining_barriers or demoted_claims")
    elif canonical == "DEMOTE":
        if not accepted and not demoted:
            errors.append("DEMOTE requires partial accepted products or demoted claims")
    elif canonical == "HONEST_STOP":
        if accepted:
            warnings.append("HONEST_STOP with accepted products should explain why no handoff follows")
        if not barriers and not demoted and not report.get("gaps"):
            warnings.append("HONEST_STOP has no barriers, demotions, or report gaps recorded")

    return {
        "schema": "witsoc.explorer_review_validation.v1",
        "valid": not errors,
        "canonical_decision": canonical,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet_or_run", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    path = packet_path(args.packet_or_run)
    try:
        packet = load(path)
    except Exception as exc:
        result = {
            "schema": "witsoc.explorer_review_validation.v1",
            "valid": False,
            "canonical_decision": None,
            "errors": [f"cannot read explorer return packet {path}: {exc}"],
            "warnings": [],
        }
    else:
        if not isinstance(packet, dict):
            result = {
                "schema": "witsoc.explorer_review_validation.v1",
                "valid": False,
                "canonical_decision": None,
                "errors": ["explorer return packet root must be an object"],
                "warnings": [],
            }
        else:
            result = validate(packet)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
