#!/usr/bin/env python3
"""Normalize Generator failures into a repair packet."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CLASSES = [
    ("placeholder_receipt", re.compile(r"placeholder|env_check|environment", re.I), "Generator"),
    ("target_drift", re.compile(r"target.*(mismatch|drift)|hash.*mismatch", re.I), "Explorer"),
    ("missing_external_theorem", re.compile(r"unknown identifier|missing theorem|external dependency", re.I), "Explorer"),
    ("lean_import", re.compile(r"unknown module|import|package", re.I), "Generator"),
    ("lean_type_mismatch", re.compile(r"type mismatch|failed to synthesize|application type mismatch", re.I), "Generator"),
    ("lean_syntax", re.compile(r"syntax|unexpected token|parser", re.I), "Generator"),
    ("wit_structure", re.compile(r"missing reference|self_reference|gap step|structural", re.I), "Generator"),
    ("thin_justification", re.compile(r"vague|thin|obvious|standard", re.I), "Generator"),
    ("toolchain_unavailable", re.compile(r"no lean|toolchain|network|dns|not found", re.I), "Toolchain"),
    ("proof_gap", re.compile(r"gap|sorry|admit|obligation_open", re.I), "Explorer"),
]


def classify(text: str) -> tuple[str, str]:
    for name, pattern, owner in CLASSES:
        if pattern.search(text):
            return name, owner
    return "unknown_generator_failure", "Generator"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--diagnostic", type=Path, required=True)
    parser.add_argument("--artifact", default="")
    parser.add_argument("--node-id", default="")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    try:
        text = args.diagnostic.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        text = f"could not read diagnostic: {exc}"
    failure_class, owner = classify(text)
    packet = {
        "schema": "witsoc.generator_repair_packet.v1",
        "run_dir": str(args.run_dir),
        "artifact": args.artifact,
        "node_id": args.node_id,
        "failure_class": failure_class,
        "repair_owner": owner,
        "diagnostic_excerpt": text[:1200],
        "next_action": {
            "Generator": "repair artifact mechanics without changing the frozen target",
            "Explorer": "repair the target, premise, or missing mathematical dependency",
            "Toolchain": "repair or install the external verification toolchain",
        }.get(owner, "inspect failure"),
    }
    out = args.out or (args.run_dir / "generator_repair_packet.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(packet, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
