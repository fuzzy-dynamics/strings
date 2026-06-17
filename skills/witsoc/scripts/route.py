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


UNSOLVED_PATTERNS = [
    r"\bunsolved\b",
    r"\bopen problem\b",
    r"\bopen (question|conjecture|target|case|problem)\b",
    r"\bstill open\b",
    r"\bremains open\b",
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


def rh_problem_context(text: str) -> bool:
    if not re.search(r"\bRH\b", text):
        return False
    return bool(re.search(
        r"\b(riemann|hypothesis|prove|disprove|solve|formaliz(e|ation)|lean|wit|conjecture)\b",
        text,
        flags=re.IGNORECASE,
    ))


def short_title(text: str, limit: int = 72) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def deep_run_spec(prompt: str, *, mode: str, include_generator: bool = False) -> dict[str, object]:
    menu: list[dict[str, object]] = [
        {
            "name": "statement-freeze",
            "lane": "intake",
            "suggested_agent": "scout",
            "value": "Freeze exact statement, variants, definitions, sources, and target hashes.",
            "risk": "Freezing the wrong variant wastes downstream work.",
            "expected_outputs": ["statement-ledger.md", "lovasz_run.json"],
            "validators": ["validate-route-state"],
        },
        {
            "name": "literature-barriers",
            "lane": "retrieval",
            "suggested_agent": "scout",
            "value": "Separate known results, theorem preconditions, failed methods, and source status.",
            "risk": "Source coverage can be stale or informal; do not promote without exact statements.",
            "expected_outputs": ["theorem_precondition_audit.json", "novelty-ledger.md"],
            "validators": ["validate-open-problem"],
        },
        {
            "name": "counterexample-pressure",
            "lane": "disproof",
            "suggested_agent": "worker",
            "value": "Try definitions, variants, boundary cases, bounded searches, and obstruction families.",
            "risk": "No bounded witness is not proof.",
            "expected_outputs": ["disproof_first.json", "computational-search.md"],
            "validators": ["validate-open-problem"],
        },
        {
            "name": "barrier-dag",
            "lane": "decomposition",
            "suggested_agent": "worker",
            "value": "Name actual barrier lemmas and dependency paths back to the frozen target.",
            "risk": "A side lemma without a dependency path is not progress on the target.",
            "expected_outputs": ["proof_dependency_dag.json", "actual_lemma_queue.json", "barrier_attacks.json"],
            "validators": ["validate-dag-integrity", "validate-open-problem"],
        },
        {
            "name": "idea-generation",
            "lane": "creative",
            "suggested_agent": "worker",
            "value": "Use analogy, conjecture mining, construction search, speculative bridges, and technique transfer.",
            "risk": "Ideas enter only as OPEN_UNFALSIFIED candidates until checked.",
            "expected_outputs": ["worker_results.json", "lemma_pool.json"],
            "validators": ["validate-lovasz-worker-quality"],
        },
        {
            "name": "formalizable-rungs",
            "lane": "verification",
            "suggested_agent": "worker",
            "value": "Select special cases, reductions, conditionals, computations, or counterexamples for checking.",
            "risk": "A formalizable subgoal can still miss the original target.",
            "expected_outputs": ["product_selection.json", "formalization_feasibility.json"],
            "validators": ["validate-explorer-review"],
        },
        {
            "name": "skeptic-synthesis",
            "lane": "review",
            "suggested_agent": "reviewer",
            "value": "Demote weak claims, classify gaps, record one-axis mutations, and decide reportability.",
            "risk": "Skeptic review may invalidate attractive but unsupported products.",
            "expected_outputs": ["gap_feedback.json", "mutation_ledger.json", "explorer_return_packet.json"],
            "validators": ["validate-explorer-review", "validate-lovasz-run"],
        },
    ]
    if include_generator:
        menu.append({
            "name": "artifact-package",
            "lane": "artifact",
            "suggested_agent": "worker",
            "value": "After Explorer authorization, package accepted narrow products into WIT/Lean artifacts and receipts.",
            "risk": "Generator packages mathematics; it does not certify unsupported claims.",
            "expected_outputs": ["handoff_v1.json", "witsoc_artifacts.json", "generator_artifact_receipt.json"],
            "validators": ["generator-receipt"],
        })
    return {
        "schema": "witsoc.deep_run_spec.v2",
        "title": f"Witsoc: {short_title(prompt, 54)}",
        "prompt": prompt,
        "mode": mode,
        "orchestrator_authority": (
            "The orchestrator owns strategy, fanout, ordering, budget, agent assignment, "
            "reframing, and which Witsoc recommendations to use. Witsoc gates only police claim honesty."
        ),
        "mission_menu": menu,
        "recommended_start": "statement-freeze",
        "alternative_strategies": [
            "counterexample-first",
            "literature-and-barrier-scouting",
            "formalization-feasibility-first",
            "creative-idea-generation",
            "parallel-lane-tournament",
        ],
        "composition_hints": [
            "Run counterexample pressure early when definitions or variants are fragile.",
            "Run literature/barrier scouting in parallel with formalization feasibility on named problems.",
            "Use idea-generation when current barriers have stale method families.",
            "Run skeptic review before promoting products into a report.",
            "Artifact packaging is useful only after an accepted narrow product exists.",
        ],
        "hard_gates": [
            "target_freeze_before_serious_claims",
            "no_status_upgrade_without_evidence",
            "open_solve_requests_need_barrier_or_gap_evidence",
            "generator_does_not_arbitrate_truth",
        ],
        "required_artifacts": [
            "statement-ledger.md",
            "lovasz_run.json",
            "proof_dependency_dag.json",
            "actual_lemma_queue.json",
            "barrier_attacks.json",
            "worker_results.json",
            "gap_feedback.json",
            "mutation_ledger.json",
            "explorer_return_packet.json",
        ],
    }


def research_mode(text: str, *, open_style: bool) -> tuple[str, str]:
    if any_match(CAMPAIGN_PATTERNS, text):
        return "campaign", "orchestrator decides fanout and budget; Witsoc supplies candidate lanes and gates"
    if any_match(DEEP_RUN_PATTERNS, text) or open_style:
        return "deep", "orchestrator decides fanout and ordering; Witsoc supplies candidate lanes and gates"
    return "quick", "orchestrator may spawn workers when useful; no fixed Witsoc fanout"


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
        "deep_run_spec": result.get("deep_run_spec"),
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
            deep_run_spec=deep_run_spec(prompt, mode=mode, include_generator=include_generator),
            completion_guard="status-only report is incomplete; Explorer must dispatch Lovasz immediately after triage, then Explorer must review Lovasz output before Generator or final reporting unless the target is solved/false/routine or Lovasz is operationally blocked",
        )
    }


def route(prompt: str) -> dict[str, object]:
    text = prompt.strip()
    lower = text.lower()
    artifacts = artifact_paths(text)
    existing_artifacts = [p for p in artifacts if p.get("exists")]

    unsolved_hit = any_match(UNSOLVED_PATTERNS, lower)
    named_hit = any_match(NAMED_OPEN_PATTERNS, lower) or ("bare_RH_math_context" if rh_problem_context(text) else None)
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

    if lovasz_direct_hit:
        return explorer_then_lovasz(
            prompt=text,
            reason=f"direct Lovasz/skip-exploration guard matched {lovasz_direct_hit!r}; Explorer must still freeze the target before Lovasz",
            mode="deep",
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
