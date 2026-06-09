#!/usr/bin/env python3
"""Failure-grounded next-lemma proposer.

Open problems are not solved by generic brainstorming; progress comes from
systematically attacking the *barrier lemmas* that blocked prior attempts. This
tool reads a run's recorded failures and produces a ranked work-queue of the next
lemmas to try — deterministically. It is a search-frontier organiser, not an
idea generator: every proposal is a templated mutation of a recorded barrier
along a named mutation axis, grounded (when available) by related verified
lemmas retrieved from the persistent lemma library.

Inputs (Lovasz/open-problem ledgers, any that exist):
  actual_lemma_queue.json   barrier lemmas: statement, unlocks, failed_approaches,
                            next_mutation, smallest_formalizable_subcase
  mutation_ledger.json      mutations already applied (to avoid repeats)
  proof_dependency_dag.json GAP / OPEN / FAILED_ATTEMPT nodes become barriers too

Mutation axes (from validate_open_problem_run.py):
  statement_strength, encoding, object_class, invariant, computational_bound,
  formalization_target, method, theorem_source

Output: next_lemma_queue.json — ranked proposals.

Usage:
  propose_next_lemma.py <run_dir> [--library DIR] [--top 10] [--out next_lemma_queue.json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

# axis -> (applies_when_predicate, template(statement, subcase))
AXIS_TEMPLATES = {
    "statement_strength": lambda s, sub: f"Prove the weakened form restricted to {sub or 'the smallest open subcase'}: {s}",
    "computational_bound": lambda s, sub: f"Establish the bounded/finite case of: {s} (push the verified range, then seek the analytic extension)",
    "object_class": lambda s, sub: f"Prove {s} for a structured subclass (e.g. {sub or 'a symmetric/extremal subfamily'}) before the general object",
    "invariant": lambda s, sub: f"Find and verify a monotone invariant that forces: {s}",
    "encoding": lambda s, sub: f"Re-encode and decide a finite instance of: {s} (SAT/SMT certificate), then generalise",
    "formalization_target": lambda s, sub: f"Formalize and machine-check the cleanest true fragment of: {s}",
    "method": lambda s, sub: f"Attack {s} by a different method than the recorded failures",
    "theorem_source": lambda s, sub: f"Locate a citable theorem whose preconditions are met and that implies: {s}",
}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def records(path: Path) -> list[dict]:
    data = load(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def related_lemmas(library: Path | None, query: str, limit: int = 3) -> list[dict]:
    if not library:
        return []
    try:
        r = subprocess.run([sys.executable, str(SCRIPT_DIR / "lemma_library.py"),
                            "--library", str(library), "search", "--query", query, "--limit", str(limit)],
                           capture_output=True, text=True, timeout=30, check=False)
        return json.loads(r.stdout).get("matches", []) if r.returncode == 0 else []
    except Exception:
        return []


def gather_barriers(run: Path) -> list[dict]:
    barriers = list(records(run / "actual_lemma_queue.json"))
    # Promote GAP/OPEN/FAILED DAG nodes to barriers so they get worked too.
    for node in records(run / "proof_dependency_dag.json"):
        status = str(node.get("status") or "").upper()
        if status in {"GAP", "OPEN", "FAILED_ATTEMPT", "CONJECTURE"}:
            barriers.append({
                "statement": node.get("statement") or node.get("node_id"),
                "unlocks": node.get("unlocks", []),
                "failed_approaches": node.get("failed_approaches", []),
                "smallest_formalizable_subcase": node.get("smallest_formalizable_subcase"),
                "_source": f"dag:{node.get('node_id')}",
            })
    return barriers


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--library", type=Path, default=None, help="lemma library dir for grounding")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    run = args.run_dir
    barriers = gather_barriers(run)
    applied = {str(m.get("axis") or m.get("next_mutation") or "").lower()
               for m in records(run / "mutation_ledger.json")}

    proposals: list[dict] = []
    for b in barriers:
        statement = str(b.get("statement") or "").strip()
        if not statement:
            continue
        subcase = b.get("smallest_formalizable_subcase")
        unlocks = b.get("unlocks") or []
        tried = {str(x).lower() for x in (b.get("failed_approaches") or [])}
        priority = len(unlocks) if isinstance(unlocks, list) else 0
        grounded = related_lemmas(args.library, statement)
        for axis, template in AXIS_TEMPLATES.items():
            # Skip axes that the barrier already records as a failed approach.
            if any(axis in t for t in tried):
                continue
            proposals.append({
                "from_barrier": statement[:200],
                "barrier_source": b.get("_source", "actual_lemma_queue"),
                "mutation_axis": axis,
                "proposed_next_step": template(statement, subcase),
                "smallest_subcase": subcase,
                "priority": priority,
                "unlocks_count": priority,
                "already_applied_globally": axis in applied,
                "grounding_lemmas": [{"id": g.get("id"), "tier": g.get("trust_tier"),
                                      "statement": g.get("statement")} for g in grounded],
            })

    # Rank: higher unlocks first; deprioritise globally-applied axes; stable.
    proposals.sort(key=lambda p: (-p["priority"], p["already_applied_globally"], p["mutation_axis"]))
    proposals = proposals[: args.top]

    payload = {
        "schema": "witsoc.next_lemma_queue.v1",
        "run_dir": str(run),
        "barriers_considered": len(barriers),
        "proposals": proposals,
        "note": "Deterministic mutations of recorded barriers along named axes; "
                "a work queue, not a claim that any proposal is true or easy.",
    }
    out = args.out or (run / "next_lemma_queue.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "proposals"} | {"proposals_emitted": len(proposals)}, indent=2))
    return 0 if proposals else 1


if __name__ == "__main__":
    raise SystemExit(main())
