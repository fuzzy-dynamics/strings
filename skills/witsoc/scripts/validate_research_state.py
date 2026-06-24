#!/usr/bin/env python3
"""Validate the derived Explorer/Generator state for a Witsoc run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import research_state  # noqa: E402


OPEN_STATUSES = {"OPEN", "UNSOLVED", "UNCONFIRMED"}
RESEARCH_MODES = {"research", "open"}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def validate(state: dict[str, Any], mode: str = "balanced") -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    target = state.get("target") if isinstance(state.get("target"), dict) else {}
    route = state.get("route") if isinstance(state.get("route"), dict) else {}
    explorer = state.get("explorer") if isinstance(state.get("explorer"), dict) else {}
    lovasz = state.get("lovasz") if isinstance(state.get("lovasz"), dict) else {}
    generator = state.get("generator") if isinstance(state.get("generator"), dict) else {}
    hashes = state.get("hashes") if isinstance(state.get("hashes"), dict) else {}
    quality = state.get("quality") if isinstance(state.get("quality"), dict) else {}

    if not target.get("text"):
        errors.append("target text is missing")
    if not target.get("hash"):
        errors.append("target hash is missing")
    direct = {k: hashes.get(k) for k in ("manifest", "explorer_return") if isinstance(hashes.get(k), str) and hashes.get(k)}
    if len(direct) > 1 and len(set(direct.values())) > 1:
        errors.append(f"target hash mismatch across manifest/explorer return: {direct}")
    seen_hashes = {k: v for k, v in hashes.items() if isinstance(v, str) and v}
    if seen_hashes and len(set(seen_hashes.values())) > 1:
        warnings.append(f"heterogeneous target hashes recorded; check hash domains before using as evidence: {seen_hashes}")

    status = str(target.get("problem_status") or "").upper()
    research_like = mode in RESEARCH_MODES or status in OPEN_STATUSES or route.get("lovasz_required")
    if mode == "routine":
        research_like = False

    if research_like:
        if not route.get("exists"):
            warnings.append("research/open run has no route state")
        if not explorer.get("handoff_exists") and not explorer.get("handoff_v1_exists"):
            errors.append("research/open run requires Explorer handoff state")
        if explorer.get("source_count", 0) == 0:
            warnings.append("research/open run has no source citations in handoff.json")
        if explorer.get("falsification_count", 0) == 0:
            warnings.append("research/open run has no recorded falsification pass")
        if explorer.get("obstruction_count", 0) + explorer.get("barrier_count", 0) + explorer.get("actual_lemma_queue_count", 0) == 0:
            errors.append("research/open run requires obstruction, barrier, or actual lemma queue records")
        if route.get("lovasz_required") and not explorer.get("return_packet_exists"):
            errors.append("Lovasz-required route requires explorer_return_packet.json before final arbitration")

    decision = str(explorer.get("return_decision") or "")
    if decision in {"generator_ready", "GENERATOR_READY"}:
        if explorer.get("selected_product_count") != 1:
            errors.append("GENERATOR_READY requires exactly one selected product")
        if lovasz.get("remaining_openish", 0):
            errors.append("GENERATOR_READY blocked by remaining open/GAP DAG nodes")
        if quality.get("formalization_label") == "POOR_FORMALIZATION_TARGET":
            errors.append("GENERATOR_READY blocked by poor formalization target")

    if generator.get("has_wit_or_lean_artifact") and not generator.get("receipt_gate_exists"):
        warnings.append("WIT/Lean artifacts exist but generator receipt gate has not run")

    return {
        "schema": "witsoc.research_state_validation.v1",
        "valid": not errors,
        "mode": mode,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--mode", choices=["routine", "balanced", "research", "open"], default="balanced")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    state_path = args.run_dir / "witsoc_research_state.json"
    state = load(state_path, None)
    if not isinstance(state, dict):
        state = research_state.assemble(args.run_dir)
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result = validate(state, args.mode)
    out = args.out or (args.run_dir / "research_state_validation.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
