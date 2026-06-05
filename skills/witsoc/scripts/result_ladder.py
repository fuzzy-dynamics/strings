#!/usr/bin/env python3
"""Generate a tractable Lovasz result ladder for an open target."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def target(run: Path, explicit: str) -> tuple[str, str]:
    if explicit:
        return explicit, hashlib.sha256(explicit.encode("utf-8")).hexdigest()
    manifest = load(run / "lovasz_run.json", {})
    text = str(manifest.get("source_target_text") or "UNSPECIFIED_TARGET")
    return text, str(manifest.get("target_hash") or hashlib.sha256(text.encode("utf-8")).hexdigest())


def domains(text: str) -> list[str]:
    lower = text.lower()
    result = []
    checks = {
        "graph": ("graph", "tree", "clique", "chromatic", "edge", "vertex", "ramsey"),
        "number_theory": ("prime", "integer", "divisor", "mod", "diophantine", "residue"),
        "additive_combinatorics": ("sumset", "additive", "density", "fourier", "energy"),
        "logic_sat": ("sat", "cnf", "formula", "resolution", "model"),
        "finite_algebra": ("group", "semigroup", "ring", "operation", "identity"),
    }
    for name, words in checks.items():
        if any(word in lower for word in words):
            result.append(name)
    return result or ["general"]


def ladder(statement: str, target_hash: str) -> list[dict[str, Any]]:
    ds = domains(statement)
    base = [
        ("toy_case", "Prove or refute the smallest nontrivial instance with all definitions explicit.", "CHECKED_BOUNDED"),
        ("finite_search", "Run bounded counterexample search with replayable witnesses or no-witness logs.", "CHECKED_BOUNDED"),
        ("special_class", "Restrict to the narrowest natural class that still contains the main obstruction.", "PARTIAL"),
        ("obstruction", "Find a boundary example or obstruction to a stronger or common false variant.", "PARTIAL"),
        ("conditional_theorem", "Prove the target assuming one exact barrier lemma or theorem precondition.", "CONDITIONAL"),
        ("improved_bound", "Improve one numeric/asymptotic/structural bound without claiming the full target.", "PARTIAL"),
        ("reduction", "Reduce the target to a smaller formalizable statement with explicit equivalence direction.", "PARTIAL"),
        ("full_target", "Attempt the original frozen target only after preceding rungs produce composable evidence.", "VERIFIED_LEAN_REQUIRED"),
    ]
    rungs = []
    for priority, (kind, description, acceptance) in enumerate(base, start=1):
        rungs.append({
            "rung_id": f"rung_{priority:02d}_{kind}",
            "kind": kind,
            "statement": description,
            "domains": ds,
            "target_hash": target_hash,
            "dependency_path_to_target": [kind, "frozen_target"],
            "verification_gate": acceptance,
            "selected": priority == 1,
            "why_this_helps_original": "Creates a verifiable product ladder while preserving dependency back to the frozen target.",
            "status": "OPEN",
        })
    return rungs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--target", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    statement, target_hash = target(args.run_dir, args.target)
    result = {
        "schema": "witsoc.lovasz_result_ladder.v1",
        "source_target_text": statement,
        "target_hash": target_hash,
        "rungs": ladder(statement, target_hash),
    }
    out = args.out or (args.run_dir / "result_ladder.json")
    if args.write:
        dump(out, result)
        kind_map = {
            "toy_case": "special_case",
            "finite_search": "computational_certificate",
            "special_class": "special_case",
            "obstruction": "obstruction",
            "conditional_theorem": "conditional_theorem",
            "improved_bound": "partial_result",
            "reduction": "reduction",
            "full_target": "verified_lemma",
        }
        product_selection = []
        for rung in result["rungs"]:
            product_selection.append({
                "kind": kind_map[rung["kind"]],
                "statement": rung["statement"],
                "why_this_helps_original": rung["why_this_helps_original"],
                "dependency_path_to_target": rung["dependency_path_to_target"],
                "verification_plan": rung["verification_gate"],
                "selected": rung["selected"],
                "status": rung["status"],
                "target_hash": target_hash,
            })
        dump(args.run_dir / "product_selection.json", product_selection)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
