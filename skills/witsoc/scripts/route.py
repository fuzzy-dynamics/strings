#!/usr/bin/env python3
"""Deterministic Witsoc subskill router.

This is intentionally simple and conservative. It exists to prevent the most
expensive routing errors: skipping Explorer's status triage before Lovasz, or
sending a nontrivial theorem directly to Generator before Explorer freezes and
accepts the target.
"""

from __future__ import annotations

import argparse
import json
import re
import sys


LOVASZ = "witsoc-research-lovasz"
EXPLORER = "witsoc-explorer"
GENERATOR = "witsoc-generator"
DIRECT = "witsoc-direct"


UNSOLVED_PATTERNS = [
    r"\bunsolved\b",
    r"\bopen problem\b",
    r"\bopen\b",
    r"\bunresolved\b",
    r"\bfrontier\b",
    r"\bresearch[- ]level\b",
    r"\bnot known\b",
    r"\bunknown\b",
    r"\bconjecture\b",
    r"\bprove or disprove\b",
    r"\bprov(e|ing)\b.*\bdisprov(e|ing)\b",
    r"\bdisprov(e|ing)\b.*\bprov(e|ing)\b",
    r"\bdeep run\b",
    r"\bdeep research\b",
    r"\boriginal research\b",
]

NAMED_OPEN_PATTERNS = [
    r"\berd[őo]s\b",
    r"\berdos\b",
    r"\bproblem\s*#?\s*\d+\b",
    r"\bpolymath\b",
    r"\boeis\b",
    r"\bmillennium\b",
    r"\bprize problem\b",
    r"\briemann hypothesis\b",
    r"\bgoldbach\b",
    r"\btwin prime\b",
    r"\bcollatz\b",
    r"\bp\s*(=|vs\.?|versus)\s*np\b",
]

ARTIFACT_PATTERNS = [
    r"\bwit\b",
    r"\.wit\b",
    r"\blean\b",
    r"\bformaliz(e|ation)\b",
    r"\bproof artifact\b",
]

REPAIR_PATTERNS = [
    r"\brepair\b.*(\.wit|\bwit\b)",
    r"(\.wit|\bwit\b).*\brepair\b",
    r"\bfix\b.*(\.wit|\bwit\b)",
    r"(\.wit|\bwit\b).*\bfix\b",
]

EXPLORER_PATTERNS = [
    r"\bcounterexample\b",
    r"\bfind a counterexample\b",
    r"\bproof sketch\b",
    r"\brank .*sketch",
    r"\blemma\b",
    r"\bpremise\b",
    r"\btheorem lookup\b",
]

SIMPLE_PATTERNS = [
    r"\bcalculate\b",
    r"\bcompute\b",
    r"\bsimplify\b",
    r"\bwhat is\b",
]


def any_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return pattern
    return None


def route(prompt: str) -> dict[str, object]:
    text = prompt.strip()
    lower = text.lower()

    unsolved_hit = any_match(UNSOLVED_PATTERNS, lower)
    named_hit = any_match(NAMED_OPEN_PATTERNS, lower)
    artifact_hit = any_match(ARTIFACT_PATTERNS, lower)
    repair_hit = any_match(REPAIR_PATTERNS, lower)
    explorer_hit = any_match(EXPLORER_PATTERNS, lower)
    simple_hit = any_match(SIMPLE_PATTERNS, lower)

    if repair_hit:
        return {
            "route": GENERATOR,
            "announcement": f"Using witsoc with {GENERATOR}.",
            "reason": f"existing WIT repair guard matched {repair_hit!r}",
            "chain": [GENERATOR],
        }

    if unsolved_hit:
        return {
            "route": EXPLORER,
            "announcement": f"Using witsoc with {EXPLORER}.",
            "reason": f"unsolved/open guard matched {unsolved_hit!r}; Explorer must triage before Lovasz",
            "chain": [EXPLORER],
            "required_followup": LOVASZ,
            "completion_guard": "status-only report is incomplete; Explorer must dispatch Lovasz unless the target is solved/false/routine or Lovasz is operationally blocked",
        }

    if named_hit:
        return {
            "route": EXPLORER,
            "announcement": f"Using witsoc with {EXPLORER}.",
            "reason": f"named open/problem-list guard matched {named_hit!r}; Explorer must triage before Lovasz",
            "chain": [EXPLORER],
            "required_followup": LOVASZ,
            "completion_guard": "status-only report is incomplete; Explorer must dispatch Lovasz unless the target is solved/false/routine or Lovasz is operationally blocked",
        }

    if artifact_hit:
        return {
            "route": EXPLORER,
            "announcement": f"Using witsoc with {EXPLORER}.",
            "reason": f"explicit artifact guard matched {artifact_hit!r}; Explorer must freeze nontrivial targets before Generator",
            "chain": [EXPLORER],
        }

    if explorer_hit:
        return {
            "route": EXPLORER,
            "announcement": f"Using witsoc with {EXPLORER}.",
            "reason": f"exploration guard matched {explorer_hit!r}",
            "chain": [EXPLORER],
        }

    if simple_hit:
        return {
            "route": DIRECT,
            "announcement": "Using witsoc.",
            "reason": f"simple/direct guard matched {simple_hit!r}",
            "chain": [],
        }

    return {
        "route": EXPLORER,
        "announcement": f"Using witsoc with {EXPLORER}.",
        "reason": "default nontrivial math route",
        "chain": [EXPLORER],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="*", help="Prompt text. If omitted, stdin is read.")
    parser.add_argument("--field", choices=["route", "announcement", "reason", "json"], default="json")
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip()
    if not prompt:
        prompt = sys.stdin.read()

    result = route(prompt)
    if args.field == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result[args.field])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
