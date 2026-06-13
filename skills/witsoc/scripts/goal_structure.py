#!/usr/bin/env python3
"""Structural analysis of Lean goals — the shared substrate for obligation
minimization, conjunction splitting, and gap-granularity assessment.

Three consumers, one parser:
  * close_obligation: OBLIGATION MINIMIZATION — drop hypotheses (the pruned goal
    is STRONGER, so a proof of it proves the original by weakening; sound by
    construction) and wrap the pruned proof back onto the full goal.
  * lovasz_prover_dispatch: CONJUNCTION SPLITTING — a node whose conclusion is
    `P ∧ Q` is two obligations; prove each, recombine with ⟨_, _⟩ (the combined
    proof is kernel-re-checked against the ORIGINAL statement).
  * sketch_tournament / dispatch: GAP GRANULARITY — flag nodes whose
    lean_statement spans multiple reasoning steps (the "miracle sorry" check).

Everything here only PROPOSES candidate statements/proofs; the kernel remains
the sole judge — a wrong prune or recombination simply fails to check.
"""

from __future__ import annotations

import re

_OPEN = "([{⟨"
_CLOSE = ")]}⟩"


def split_top(text: str, seps: tuple[str, ...]) -> list[str]:
    """Split `text` on any of `seps` occurring at bracket depth 0."""
    parts: list[str] = []
    depth = 0
    i = 0
    start = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in _OPEN:
            depth += 1
        elif c in _CLOSE:
            depth = max(0, depth - 1)
        elif depth == 0:
            for sep in seps:
                if text.startswith(sep, i):
                    parts.append(text[start:i].strip())
                    i += len(sep)
                    start = i
                    break
            else:
                i += 1
                continue
            continue
        i += 1
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def strip_foralls(statement: str) -> tuple[str, str]:
    """Peel leading `∀ <binders>,` groups. Returns (forall_prefix, body); the
    prefix keeps its trailing comma+space so `prefix + new_body` is well-formed."""
    s = statement.strip()
    prefix = ""
    while True:
        m = re.match(r"^\s*∀", s)
        if not m:
            break
        # find the binder-terminating comma at depth 0
        depth = 0
        comma = -1
        for i in range(m.end(), len(s)):
            c = s[i]
            if c in _OPEN:
                depth += 1
            elif c in _CLOSE:
                depth = max(0, depth - 1)
            elif c == "," and depth == 0:
                comma = i
                break
        if comma < 0:
            break
        prefix += s[: comma + 1] + " "
        s = s[comma + 1:].strip()
    return prefix, s


def implication_chain(statement: str) -> dict:
    """Parse `∀ …, H1 → H2 → C` into {prefix, hypotheses, conclusion}."""
    prefix, body = strip_foralls(statement)
    segs = split_top(body, ("→", "->"))
    if len(segs) < 2:
        return {"prefix": prefix, "hypotheses": [], "conclusion": body}
    return {"prefix": prefix, "hypotheses": segs[:-1], "conclusion": segs[-1]}


def pruned_variants(statement: str, max_variants: int = 4) -> list[dict]:
    """Hypothesis-pruned variants of a goal, strongest first.

    Dropping a hypothesis STRENGTHENS the goal, so any pruned variant that the
    prover discharges yields the original by weakening — the sound direction.
    Returns [{statement, dropped}] (empty when the goal has no hypotheses)."""
    chain = implication_chain(statement)
    hyps = chain["hypotheses"]
    if not hyps or len(hyps) > 4:
        return []
    prefix, concl = chain["prefix"], chain["conclusion"]

    def rebuild(keep: list[str]) -> str:
        return (prefix + " → ".join(keep + [concl])).strip()

    out: list[dict] = [{"statement": rebuild([]), "dropped": list(hyps)}]
    if len(hyps) >= 2:
        for i, h in enumerate(hyps):
            out.append({"statement": rebuild(hyps[:i] + hyps[i + 1:]), "dropped": [h]})
    seen: set[str] = set()
    uniq = [v for v in out if not (v["statement"] in seen or seen.add(v["statement"]))]
    return uniq[:max_variants]


def wrapper_candidates(pruned_statement: str, pruned_proof: str) -> list[str]:
    """Proof candidates for the ORIGINAL goal given a kernel-verified proof of a
    pruned (stronger) variant. `apply hmin <;> assumption` re-derives the original:
    apply unifies the conclusion and any kept hypotheses become goals closed from
    context. All candidates are kernel-gated by the caller."""
    have = f"have hmin : {pruned_statement} := ({pruned_proof})"
    return [
        f"by {have}; intros; apply hmin <;> assumption",
        f"by {have}; intros; exact hmin",
        f"by {have}; intros; simp_all",
        f"by {have}; simp [hmin]",
    ]


def conjunction_split(statement: str) -> list[str]:
    """Split a goal whose CONCLUSION is a top-level conjunction into one subgoal
    per conjunct (each keeps the full ∀-prefix and hypothesis chain). Returns []
    when the conclusion is not conjunctive."""
    chain = implication_chain(statement)
    conjuncts = split_top(chain["conclusion"], ("∧",))
    if len(conjuncts) < 2:
        return []
    pre, hyps = chain["prefix"], chain["hypotheses"]

    def strip_outer_parens(s: str) -> str:
        s = s.strip()
        while s.startswith("(") and s.endswith(")") and not split_top(s[1:-1], (",",)) == []:
            inner = s[1:-1].strip()
            # only strip when the parens really wrap the whole expression
            depth = 0
            for i, c in enumerate(inner):
                if c in _OPEN:
                    depth += 1
                elif c in _CLOSE:
                    depth -= 1
                    if depth < 0:
                        return s
            s = inner
        return s

    return [(pre + " → ".join(hyps + [strip_outer_parens(c)])).strip() for c in conjuncts]


def recombination_candidates(subgoals: list[str], proofs: list[str]) -> list[str]:
    """Proof candidates for the ORIGINAL conjunctive goal from per-conjunct
    proofs: inline each as a `have`, then recombine with the anonymous
    constructor under a small family of binder/hypothesis intro patterns.
    Kernel-gated by the caller — a wrong arity pattern just fails."""
    haves = "; ".join(f"have h{i + 1} : {s} := ({p})" for i, (s, p) in enumerate(zip(subgoals, proofs)))
    k = len(subgoals)

    def tup(args: str) -> str:
        return "⟨" + ", ".join(f"h{i + 1}{args}" for i in range(k)) + "⟩"

    cands = [f"by {haves}; exact {tup('')}"]
    for intro, args in (("intro x", " x"), ("intro x y", " x y"),
                        ("intro x h", " x h"), ("intro x y h", " x y h")):
        cands.append(f"by {haves}; {intro}; exact {tup(args)}")
    cands.append(f"by {haves}; intros; constructor <;> simp_all")
    cands.append(f"by {haves}; constructor <;> simp_all")
    return cands


def granularity(statement: str | None) -> dict:
    """Gap-granularity assessment of a node's lean_statement — the constructive
    twin of the rater's good-gaps/bad-gaps rubric. A `sorry`-shaped node should
    be ONE reasoning step; a conjunctive or deeply-chained statement is flagged
    (and the dispatcher can auto-split conjunctions). Flags only — this NEVER
    changes a claim's status."""
    if not statement:
        return {"conjuncts": 0, "hypotheses": 0, "flag": "no_lean_statement", "atomic": False}
    chain = implication_chain(statement)
    conjuncts = len(split_top(chain["conclusion"], ("∧",)))
    hyps = len(chain["hypotheses"])
    if conjuncts >= 2:
        flag = "conjunctive"
    elif hyps > 2:
        flag = "multi_step"
    else:
        flag = "atomic"
    return {"conjuncts": conjuncts, "hypotheses": hyps, "flag": flag, "atomic": flag == "atomic"}


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("statement")
    args = ap.parse_args()
    print(json.dumps({
        "granularity": granularity(args.statement),
        "implication_chain": implication_chain(args.statement),
        "conjunction_split": conjunction_split(args.statement),
        "pruned_variants": pruned_variants(args.statement),
    }, indent=2, ensure_ascii=False))
