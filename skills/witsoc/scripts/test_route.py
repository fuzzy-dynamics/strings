#!/usr/bin/env python3
"""Regression tests for the deterministic Witsoc router."""

from __future__ import annotations

import tempfile
from pathlib import Path
import sys

from route import EXPLORER, GENERATOR, LOVASZ, route


CASES = [
    {
        "prompt": "Prove or disprove Erdős problem 1053",
        "route": EXPLORER,
        "chain": [EXPLORER, LOVASZ, EXPLORER],
        "required_followup": LOVASZ,
        "research_mode": "campaign",
        "requires_explorer_review_after_lovasz": True,
    },
    {
        "prompt": "do a deep run trying to prove or disprove Call a number k-perfect if sigma(n)=kn. Must k=o(log log n)?",
        "route": EXPLORER,
        "chain": [EXPLORER, LOVASZ, EXPLORER],
        "required_followup": LOVASZ,
        "research_mode": "deep",
        "requires_explorer_review_after_lovasz": True,
    },
    {
        "prompt": "This is unsolved; try to prove it",
        "route": EXPLORER,
        "chain": [EXPLORER, LOVASZ, EXPLORER],
        "required_followup": LOVASZ,
        "research_mode": "deep",
        "requires_explorer_review_after_lovasz": True,
    },
    {
        "prompt": "Formalize this open conjecture in Lean",
        "route": EXPLORER,
        "chain": [EXPLORER, LOVASZ, EXPLORER, GENERATOR],
        "required_followup": LOVASZ,
        "research_mode": "deep",
        "requires_explorer_review_after_lovasz": True,
        "generator_after_explorer_authorization": True,
    },
    {
        "prompt": "prove this open conjecture and write Lean directly",
        "route": EXPLORER,
        "chain": [EXPLORER, LOVASZ, EXPLORER, GENERATOR],
        "required_followup": LOVASZ,
        "requires_explorer_review_after_lovasz": True,
        "generator_after_explorer_authorization": True,
    },
    {
        "prompt": "skip exploration and use Lovasz",
        "route": EXPLORER,
        "chain": [EXPLORER, LOVASZ, EXPLORER],
        "required_followup": LOVASZ,
        "requires_explorer_review_after_lovasz": True,
    },
    {
        "prompt": "generate WIT for RH",
        "route": EXPLORER,
        "chain": [EXPLORER, LOVASZ, EXPLORER, GENERATOR],
        "required_followup": LOVASZ,
        "requires_explorer_review_after_lovasz": True,
        "generator_after_explorer_authorization": True,
    },
    {
        "prompt": "just give final proof of this unsolved problem",
        "route": EXPLORER,
        "chain": [EXPLORER, LOVASZ, EXPLORER],
        "required_followup": LOVASZ,
        "requires_explorer_review_after_lovasz": True,
    },
    {
        "prompt": "Prove Hall's theorem",
        "route": EXPLORER,
        "research_mode": "quick",
    },
    {
        "prompt": "Find a counterexample to this proposed lemma",
        "route": EXPLORER,
        "research_mode": "quick",
    },
    {
        "prompt": "Write WIT for this already-stated theorem",
        "route": EXPLORER,
        "chain": [EXPLORER, GENERATOR],
        "research_mode": "quick",
        "requires_explorer_handoff": True,
    },
    {
        "prompt": "Repair this .wit file",
        "route": GENERATOR,
        "research_mode": "quick",
    },
]


def main() -> int:
    failures: list[str] = []
    dynamic_cases = []
    with tempfile.TemporaryDirectory() as tmp:
        wit = Path(tmp) / "existing.wit"
        wit.write_text("-- Status: UNVERIFIED\nMODULE existing\n", encoding="utf-8")
        dynamic_cases.append({
            "prompt": f"Repair {wit}",
            "route": GENERATOR,
            "chain": [GENERATOR],
            "confidence": "high",
        })
        dynamic_cases.append({
            "prompt": f"Inspect {wit}",
            "route": GENERATOR,
            "chain": [GENERATOR],
            "confidence": "high",
        })

        all_cases = CASES + dynamic_cases
        for case in all_cases:
            result = route(case["prompt"])
            for key, expected in case.items():
                if key == "prompt":
                    continue
                actual = result.get(key)
                if actual != expected:
                    failures.append(
                        f"{case['prompt']!r}: expected {key}={expected!r}, got {actual!r}; full={result!r}"
                    )
            if result.get("required_followup") == LOVASZ and "status-only" not in str(result.get("completion_guard", "")):
                failures.append(f"{case['prompt']!r}: Lovasz route missing status-only completion guard")
            for field in ("confidence", "blockers", "must_not_skip", "route_state"):
                if field not in result:
                    failures.append(f"{case['prompt']!r}: route missing common field {field!r}")
            if result.get("required_followup") == LOVASZ and result.get("chain", [None])[:3] != [EXPLORER, LOVASZ, EXPLORER]:
                failures.append(f"{case['prompt']!r}: Lovasz route must start Explorer -> Lovasz -> Explorer; full={result!r}")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("ROUTE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
