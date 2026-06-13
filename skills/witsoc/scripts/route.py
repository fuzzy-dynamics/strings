#!/usr/bin/env python3
"""Deterministic Witsoc subskill router.

This is intentionally simple and conservative. It exists to prevent the most
expensive routing errors: skipping Explorer's status triage before Lovasz, or
sending a nontrivial theorem directly to Generator before Explorer freezes and
accepts the target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys


LOVASZ = "witsoc-research-lovasz"
EXPLORER = "witsoc-explorer"
GENERATOR = "witsoc-generator"
DIRECT = "witsoc-direct"
OLYMPIAD_FAST = "witsoc-olympiad-fast-lane"


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

DEEP_RUN_PATTERNS = [
    r"\bdeep run\b",
    r"\bdeep research\b",
    r"\bserious attempt\b",
    r"\bprove or disprove\b",
    r"\bsolve\b",
    r"\bmake progress\b",
]

CAMPAIGN_PATTERNS = [
    r"\bcampaign\b",
    r"\bopen[- ]problem campaign\b",
    r"\bfrontier\b",
    r"\berd[őo]s\b",
    r"\berdos\b",
    r"\bprize problem\b",
    r"\bmillennium\b",
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
    r"\brh\b",
    r"\bgoldbach\b",
    r"\btwin prime\b",
    r"\bcollatz\b",
    r"\bp\s*(=|vs\.?|versus)\s*np\b",
]

OLYMPIAD_PATTERNS = [
    r"\bimo\b",
    r"\busamo\b",
    r"\begmo\b",
    r"\bapmo\b",
    r"\bputnam\b",
    r"\bimc\b",
    r"\baime\b",
    r"\bamc\b",
    r"\bolympiad\b",
    r"\bshortlist\b",
    r"\bcompetition (problem|math)\b",
    r"\bmath(s|ematical)? competition\b",
    r"\bminif2f\b",
]

# Serious prove/show requests. These route through Lovasz as proof-campaign
# director (sketch tournament -> decompose -> prover dispatch -> skeptic) when
# the statement has mathematical substance — see MATH_SUBSTANCE_PATTERNS.
HARD_PROOF_PATTERNS = [
    r"\bprove\b",
    r"\bdisprove\b",
    r"\bshow that\b",
    r"\bdetermine all\b",
    r"\bfind all\b",
    r"\bgive a (full |complete |rigorous )?proof\b",
    r"\bsolve\b.*\b(functional equation|diophantine|congruence|recurrence)\b",
]

# Triviality guard for HARD_PROOF: a bare "prove 1+1=2" stays on the light
# Explorer path; anything with real mathematical objects gets the campaign.
MATH_SUBSTANCE_PATTERNS = [
    r"[∀∃∑∏≤≥≠∣]",
    r"\bfor (all|every|each)\b",
    r"\bthere (exist|is|are)\b",
    r"\binfinitely many\b",
    r"\b(positive |natural |real |rational )?(integers?|numbers?|reals?)\b",
    r"\bprimes?\b",
    r"\bgraphs?\b",
    r"\bsequences?\b",
    r"\bfunctions?\b",
    r"\bpolynomials?\b",
    r"\btriangles?\b",
    r"\binequalit(y|ies)\b",
    r"\bdivisib(le|ility)\b",
    r"\btheorems?\b",
    r"\blemmas?\b",
    r"\bmodulo\b",
    r"\bset of\b",
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

LOVASZ_DIRECT_PATTERNS = [
    r"\blovasz\b",
    r"\bwitsoc-research-lovasz\b",
    r"\bskip exploration\b",
]

ARTIFACT_PATH_RE = re.compile(r"(?P<path>(?:\.{0,2}/|/|[A-Za-z0-9_.+-]+/)?[A-Za-z0-9_./+@=-]+\.(?:wit|lean))\b", re.IGNORECASE)


def any_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return pattern
    return None


def research_mode(text: str, *, open_style: bool) -> tuple[str, str]:
    if any_match(CAMPAIGN_PATTERNS, text):
        return "campaign", "unbounded within runtime/budget"
    if any_match(DEEP_RUN_PATTERNS, text) or open_style:
        return "deep", "8-20 agents by default; more if independent DAG nodes justify it"
    return "quick", "2-4 agents when worker spawning is useful"


def artifact_paths(prompt: str) -> list[dict[str, object]]:
    paths: list[dict[str, object]] = []
    seen: set[str] = set()
    for match in ARTIFACT_PATH_RE.finditer(prompt):
        raw = match.group("path").rstrip(".,;:)")
        if raw.lower() in {"wit", "lean"} or raw in seen:
            continue
        seen.add(raw)
        p = Path(raw).expanduser()
        resolved = p.resolve() if p.is_absolute() else (Path.cwd() / p).resolve()
        paths.append({
            "path": raw,
            "resolved_path": str(resolved),
            "exists": resolved.exists(),
            "kind": "wit" if raw.lower().endswith(".wit") else "lean",
        })
    return paths


def route_state(prompt: str, result: dict[str, object]) -> dict[str, object]:
    chain = list(result.get("chain") or [])
    current_phase = chain[0] if chain else result.get("route")
    phases = [
        {
            "phase": phase,
            "status": "pending",
            "must_not_skip": phase in set(result.get("must_not_skip", [])),
        }
        for phase in chain
    ]
    if phases:
        phases[0]["status"] = "ready"
    return {
        "schema": "witsoc.route_state.v1",
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "route": result.get("route"),
        "chain": chain,
        "current_phase": current_phase,
        "phases": phases,
        "lovasz_required": LOVASZ in chain or result.get("required_followup") == LOVASZ,
        "generator_authorized": result.get("route") == GENERATOR and not result.get("requires_explorer_handoff", False),
        "requires_explorer_review_after_lovasz": result.get("requires_explorer_review_after_lovasz", False),
        "blockers": result.get("blockers", []),
        "must_not_skip": result.get("must_not_skip", []),
        "completion_guard": result.get("completion_guard"),
    }


def with_common_fields(
    *,
    prompt: str,
    route_name: str,
    announcement: str,
    reason: str,
    chain: list[str],
    research_mode_value: str,
    worker_policy: str,
    confidence: str,
    blockers: list[str] | None = None,
    must_not_skip: list[str] | None = None,
    **extra: object,
) -> dict[str, object]:
    result: dict[str, object] = {
        "route": route_name,
        "announcement": announcement,
        "reason": reason,
        "chain": chain,
        "research_mode": research_mode_value,
        "worker_policy": worker_policy,
        "confidence": confidence,
        "blockers": blockers or [],
        "must_not_skip": must_not_skip or [],
        "artifact_paths": artifact_paths(prompt),
    }
    result.update(extra)
    result["route_state"] = route_state(prompt, result)
    return result


def explorer_then_lovasz(*, prompt: str, reason: str, mode: str, worker_policy: str, include_generator: bool = False) -> dict[str, object]:
    chain = [EXPLORER, LOVASZ, EXPLORER]
    must_not_skip = [EXPLORER, LOVASZ, "explorer_review_after_lovasz"]
    if include_generator:
        chain.append(GENERATOR)
        must_not_skip.append("generator_after_explorer_authorization")
    return {
        **with_common_fields(
            prompt=prompt,
            route_name=EXPLORER,
            announcement=f"Using witsoc with {EXPLORER} -> {LOVASZ} -> {EXPLORER}.",
            reason=reason,
            chain=chain,
            research_mode_value=mode,
            worker_policy=worker_policy,
            confidence="high",
            blockers=[],
            must_not_skip=must_not_skip,
            required_followup=LOVASZ,
            requires_explorer_review_after_lovasz=True,
            generator_after_explorer_authorization=include_generator,
            completion_guard="status-only report is incomplete; Explorer must dispatch Lovasz immediately after triage, then Explorer must review Lovasz output before Generator or final reporting unless the target is solved/false/routine or Lovasz is operationally blocked",
        )
    }


def route(prompt: str) -> dict[str, object]:
    text = prompt.strip()
    lower = text.lower()
    artifacts = artifact_paths(text)
    existing_artifacts = [p for p in artifacts if p.get("exists")]

    unsolved_hit = any_match(UNSOLVED_PATTERNS, lower)
    named_hit = any_match(NAMED_OPEN_PATTERNS, lower)
    olympiad_hit = any_match(OLYMPIAD_PATTERNS, lower)
    hard_proof_hit = any_match(HARD_PROOF_PATTERNS, lower)
    substance_hit = any_match(MATH_SUBSTANCE_PATTERNS, text) or len(text) > 120
    artifact_hit = any_match(ARTIFACT_PATTERNS, lower)
    repair_hit = any_match(REPAIR_PATTERNS, lower)
    explorer_hit = any_match(EXPLORER_PATTERNS, lower)
    simple_hit = any_match(SIMPLE_PATTERNS, lower)
    lovasz_direct_hit = any_match(LOVASZ_DIRECT_PATTERNS, lower)
    open_style = bool(unsolved_hit or named_hit)
    mode, worker_policy = research_mode(lower, open_style=open_style)

    if repair_hit:
        return with_common_fields(
            prompt=text,
            route_name=GENERATOR,
            announcement=f"Using witsoc with {GENERATOR}.",
            reason=f"existing WIT repair guard matched {repair_hit!r}",
            chain=[GENERATOR],
            research_mode_value="quick",
            worker_policy="no Lovasz spawning unless repair reveals a mathematical blocker requiring Explorer",
            confidence="high" if existing_artifacts else "medium",
            blockers=[] if existing_artifacts else ["no_existing_artifact_path_detected"],
            must_not_skip=["preserve_frozen_target", "structural_check_after_repair"],
            generator_authorized=True,
        )

    if unsolved_hit:
        return explorer_then_lovasz(
            prompt=text,
            reason=f"unsolved/open guard matched {unsolved_hit!r}; Lovasz must run immediately after Explorer triage",
            mode=mode,
            worker_policy=worker_policy,
            include_generator=bool(artifact_hit),
        )

    if named_hit:
        return explorer_then_lovasz(
            prompt=text,
            reason=f"named open/problem-list guard matched {named_hit!r}; Lovasz must run immediately after Explorer triage",
            mode=mode,
            worker_policy=worker_policy,
            include_generator=bool(artifact_hit),
        )

    if olympiad_hit:
        chain = [EXPLORER, OLYMPIAD_FAST, EXPLORER]
        must_not_skip = [EXPLORER, OLYMPIAD_FAST, "explorer_review_after_fast_lane"]
        if artifact_hit:
            chain.append(GENERATOR)
            must_not_skip.append("generator_after_explorer_authorization")
        return with_common_fields(
            prompt=text,
            route_name=EXPLORER,
            announcement=f"Using witsoc with {EXPLORER} -> {OLYMPIAD_FAST} -> {EXPLORER}.",
            reason=f"olympiad/competition guard matched {olympiad_hit!r}; Explorer freezes the "
                   "target, then the local olympiad fast lane attempts bounded kernel-gated "
                   "closure before falling back to Lovasz solved-class mode",
            chain=chain,
            research_mode_value="deep" if mode == "quick" else mode,
            worker_policy="local-first fast lane; if it fails, Lovasz solved-class campaign with 8-20 agents by default",
            confidence="high",
            blockers=[],
            must_not_skip=must_not_skip,
            conditional_followup=LOVASZ,
            conditional_followup_when="olympiad fast lane returns OBLIGATION_OPEN, BUDGET_EXHAUSTED, GAP, or non-kernel status",
            requires_explorer_review_after_lovasz=False,
            generator_after_explorer_authorization=bool(artifact_hit),
            completion_guard="fast-lane closure must be kernel-gated; otherwise Explorer must dispatch Lovasz solved-class mode and review its return before final reporting",
        )

    if lovasz_direct_hit:
        return explorer_then_lovasz(
            prompt=text,
            reason=f"direct Lovasz/skip-exploration guard matched {lovasz_direct_hit!r}; Explorer must still freeze the target before Lovasz",
            mode="deep",
            worker_policy=worker_policy,
            include_generator=bool(artifact_hit),
        )

    if hard_proof_hit and substance_hit:
        return explorer_then_lovasz(
            prompt=text,
            reason=f"serious-proof guard matched {hard_proof_hit!r} with mathematical substance "
                   f"({substance_hit if isinstance(substance_hit, str) else 'long statement'}); "
                   "Lovasz directs the proof campaign after Explorer freezes the target",
            mode=mode,
            worker_policy=worker_policy,
            include_generator=bool(artifact_hit),
        )

    if artifact_hit:
        if existing_artifacts:
            return with_common_fields(
                prompt=text,
                route_name=GENERATOR,
                announcement=f"Using witsoc with {GENERATOR}.",
                reason=f"existing artifact path detected; Generator may inspect or repair the existing artifact",
                chain=[GENERATOR],
                research_mode_value="quick",
                worker_policy="no Lovasz spawning unless Generator finds a mathematical blocker",
                confidence="high",
                blockers=[],
                must_not_skip=["preserve_frozen_target", "structural_check_after_artifact_edit"],
                generator_authorized=True,
            )
        return with_common_fields(
            prompt=text,
            route_name=EXPLORER,
            announcement=f"Using witsoc with {EXPLORER} -> {GENERATOR}.",
            reason=f"new artifact guard matched {artifact_hit!r}; Explorer must freeze and accept the target before Generator",
            chain=[EXPLORER, GENERATOR],
            research_mode_value=mode,
            worker_policy=worker_policy,
            confidence="high",
            blockers=[],
            must_not_skip=["explorer_target_freeze", "generator_after_explorer_handoff"],
            requires_explorer_handoff=True,
            generator_authorized=False,
            completion_guard="new WIT/Lean artifacts require Explorer target freeze and handoff before Generator writes proof files",
        )

    if explorer_hit:
        return with_common_fields(
            prompt=text,
            route_name=EXPLORER,
            announcement=f"Using witsoc with {EXPLORER}.",
            reason=f"exploration guard matched {explorer_hit!r}",
            chain=[EXPLORER],
            research_mode_value=mode,
            worker_policy=worker_policy,
            confidence="high",
            blockers=[],
            must_not_skip=["explorer_target_freeze"],
        )

    if simple_hit:
        return with_common_fields(
            prompt=text,
            route_name=DIRECT,
            announcement="Using witsoc.",
            reason=f"simple/direct guard matched {simple_hit!r}",
            chain=[],
            research_mode_value="quick",
            worker_policy="no Lovasz spawning for simple direct answers",
            confidence="medium",
            blockers=[],
            must_not_skip=[],
        )

    return with_common_fields(
        prompt=text,
        route_name=EXPLORER,
        announcement=f"Using witsoc with {EXPLORER}.",
        reason="default nontrivial math route",
        chain=[EXPLORER],
        research_mode_value=mode,
        worker_policy=worker_policy,
        confidence="medium",
        blockers=[],
        must_not_skip=["explorer_target_freeze"],
    )


def default_state_path() -> Path | None:
    explicit = os.environ.get("WITSOC_ROUTE_STATE")
    if explicit:
        return Path(explicit)
    for env_name in ("PLANE_SESSION_DIR", "OSCI_SESSION_DIR", "KIMI_WORK_DIR"):
        value = os.environ.get(env_name)
        if value:
            return Path(value) / "witsoc_route_state.json"
    return None


def write_route_state(path: Path, result: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state = dict(result.get("route_state") or {})
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="*", help="Prompt text. If omitted, stdin is read.")
    parser.add_argument("--field", choices=["route", "announcement", "reason", "chain", "confidence", "state", "json"], default="json")
    parser.add_argument("--state-out", type=Path, default=None, help="Write route state JSON to this path.")
    parser.add_argument("--no-state", action="store_true", help="Do not write route state even when a session dir is available.")
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip()
    if not prompt:
        prompt = sys.stdin.read()

    result = route(prompt)
    state_path = args.state_out if args.state_out else (None if args.no_state else default_state_path())
    if state_path:
        write_route_state(state_path, result)
    if args.field == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.field == "chain":
        print(" -> ".join(result.get("chain") or []))
    elif args.field == "state":
        print(json.dumps(result.get("route_state") or {}, ensure_ascii=False, indent=2))
    else:
        print(result[args.field])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
