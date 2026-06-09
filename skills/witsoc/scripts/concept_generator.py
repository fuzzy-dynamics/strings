#!/usr/bin/env python3
"""Layer 2: the idea-GENERATOR (concept / stepping-stone proposer).

witsoc's trust root only FILTERS; it never PRODUCES the new lemma/construction
that closes an open problem. This is the quarantined generation arena: it
proposes candidate auxiliary objects (stepping-stone lemmas, invariants, base/
inductive splits, strengthened hypotheses) for a decomposed subproblem, and hands
them to the existing kernel/faithfulness gates.

GENERATION vs JUDGEMENT separation (the calibration spine):
  * Every candidate is born `status = OPEN_UNFALSIFIED`, `arena = SPECULATIVE`.
  * This module has NO authority to assign trust. `force_open()` coerces status,
    and `assert_no_upgrade()` raises if anything is above OPEN_UNFALSIFIED — so the
    generator structurally cannot manufacture a solve.
  * A candidate exits the arena ONLY by being proved through the existing gate
    (`witsoc prove` / `lovasz_prover_dispatch` -> `validate_prover_result`). The
    generator never marks anything proved.

Sources of candidates: an optional `cmd:` LLM sampler (untrusted), plus a
deterministic domain-aware template fallback so it works with no model present.

Usage:
  concept_generator.py --goal "<Lean goal>" [--domain D] [--k N]
      [--sampler cmd:CMD] [--library DIR] [--out candidate_lemmas.json]
      [--queue-out actual_lemma_queue.json]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

OPEN = "OPEN_UNFALSIFIED"
ARENA = "SPECULATIVE"

_FORALL_RE = re.compile(r"^\s*∀\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^,]+?)\s*,\s*(.+)$")


def parse_forall(goal: str):
    m = _FORALL_RE.match(goal.strip())
    if not m:
        return None
    return {"var": m.group(1), "type": m.group(2).strip(), "body": m.group(3).strip()}


def tok(s: str) -> Counter:
    return Counter(re.findall(r"[A-Za-z0-9_]+", (s or "").lower()))


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0) for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def force_open(cand: dict) -> dict:
    """The single chokepoint: a candidate can only ever be OPEN_UNFALSIFIED /
    SPECULATIVE coming out of the generator. No exceptions, no upgrades."""
    cand["status"] = OPEN
    cand["arena"] = ARENA
    return cand


def assert_no_upgrade(cands: list[dict]) -> None:
    """Structural calibration guard — raises if the generator ever emits trust."""
    for c in cands:
        if c.get("status") != OPEN or c.get("arena") != ARENA:
            raise AssertionError(
                f"calibration violation: generator emitted status={c.get('status')!r} "
                f"arena={c.get('arena')!r}; must be {OPEN}/{ARENA}")


def deterministic_candidates(goal: str, domain: str) -> list[dict]:
    """Domain-agnostic structural stepping-stones, plus a couple of domain hints.
    lean_statement is best-effort; if it does not type-check, the kernel gate
    reports it OPEN honestly (no harm — the generator never claims it holds)."""
    cands: list[dict] = []
    f = parse_forall(goal)
    if f and f["type"] in ("Nat", "ℕ"):
        v, body = f["var"], f["body"]
        base = re.sub(rf"\b{re.escape(v)}\b", "0", body)
        cands.append({"kind": "base_case", "form": f"base case: {body} at {v}=0",
                      "lean_statement": base})
        cands.append({"kind": "inductive_step",
                      "form": f"inductive step: assume body at {v}, show at {v}+1",
                      "lean_statement": f"∀ {v} : Nat, ({body}) → ({re.sub(rf'\b{re.escape(v)}\b', f'({v}+1)', body)})"})
        cands.append({"kind": "even_case", "form": f"restrict to even {v}",
                      "lean_statement": f"∀ {v} : Nat, (∃ k : Nat, {v} = 2*k) → ({body})"})
        cands.append({"kind": "odd_case", "form": f"restrict to odd {v}",
                      "lean_statement": f"∀ {v} : Nat, (∃ k : Nat, {v} = 2*k+1) → ({body})"})
    # generic strengthening / reduction stepping-stones (no lean_statement: needs
    # formalization — the dispatcher records these as needing a lean goal, honestly)
    cands.append({"kind": "strengthened_invariant",
                  "form": "propose a strengthened invariant Q with Q -> goal", "lean_statement": None})
    if domain in ("number_theory", "additive_combinatorics"):
        cands.append({"kind": "bound", "form": "propose an explicit bound / growth-rate lemma", "lean_statement": None})
    if domain in ("graph_theory", "combinatorics"):
        cands.append({"kind": "extremal_config", "form": "propose the extremal configuration to rule out", "lean_statement": None})
    return cands


def llm_candidates(goal: str, domain: str, k: int, sampler: str | None) -> list[dict]:
    if not sampler:
        return []
    reply = witcore.run_sampler(sampler, {"task": "propose_stepping_stone_lemmas",
                                          "goal": goal, "domain": domain, "k": k})
    if not isinstance(reply, dict):
        return []
    out = []
    for c in reply.get("candidates", []) or []:
        if isinstance(c, dict) and c.get("form"):
            out.append({"kind": str(c.get("kind") or "lemma"), "form": str(c["form"]),
                        "lean_statement": c.get("lean_statement"), "source": "llm"})
    return out


def is_trivial(cand: dict) -> str | None:
    ls = (cand.get("lean_statement") or "").strip()
    form = cand.get("form", "")
    # tautologies / vacuous shapes
    if re.search(r"\bTrue\b\s*$", ls) or ls == "True":
        return "tautology (-> True)"
    m = re.match(r"^∀.+?,\s*\((.+)\)\s*→\s*\(\1\)\s*$", ls)
    if m:
        return "tautology (P -> P)"
    if form.strip() in ("", "P -> P"):
        return "empty/tautological form"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goal", required=True, help="the (Lean) goal being decomposed")
    ap.add_argument("--domain", default="other")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--sampler", default=None, help="optional cmd:<command> LLM mutation sampler")
    ap.add_argument("--library", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("candidate_lemmas.json"))
    ap.add_argument("--queue-out", type=Path, default=None, help="also write an actual_lemma_queue projection")
    ap.add_argument("--dag-out", type=Path, default=None, help="also write a proof_dependency_dag.json the Prover dispatcher can attack")
    args = ap.parse_args()

    raw = deterministic_candidates(args.goal, args.domain) + llm_candidates(args.goal, args.domain, args.k, args.sampler)

    # JUDGEMENT: novelty vs library + trivial kill (ordering/pruning only).
    lib = []
    if args.library and args.library.exists():
        try:
            import subprocess
            r = subprocess.run([sys.executable, str(SCRIPT_DIR / "lemma_library.py"),
                                "--library", str(args.library), "search", "--query", args.goal, "--limit", "50"],
                               capture_output=True, text=True, timeout=30, check=False)
            lib = [m.get("statement", "") for m in json.loads(r.stdout).get("matches", [])]
        except Exception:
            lib = []
    lib_vecs = [tok(s) for s in lib]

    kept, killed = [], []
    for i, c in enumerate(raw):
        reason = is_trivial(c)
        if reason:
            killed.append({"form": c.get("form"), "reason": reason})
            continue
        novelty = 1.0 - max((cosine(tok(c.get("lean_statement") or c.get("form", "")), v) for v in lib_vecs), default=0.0)
        c = force_open(c)
        c["id"] = f"cand-{i}"
        c["novelty"] = round(novelty, 3)
        kept.append(c)

    kept.sort(key=lambda c: -c["novelty"])

    # CALIBRATION GUARD (structural): nothing left the arena.
    assert_no_upgrade(kept)

    out = {"schema": "witsoc.concept_candidates.v1", "goal": args.goal, "domain": args.domain,
           "candidates": kept, "killed": killed,
           "calibration": f"every candidate is {OPEN}/{ARENA}; the generator cannot assign trust. "
                          "Exit the arena only via the kernel gate (witsoc prove / lovasz-prover-dispatch).",
           "sampler_used": bool(args.sampler)}
    witcore.save_json(args.out, out)

    if args.queue_out:
        queue = [{"statement": c["form"], "lean_statement": c.get("lean_statement"),
                  "priority": round(c["novelty"], 3), "status": OPEN, "arena": ARENA,
                  "kind": c["kind"], "source": c.get("source", "template")}
                 for c in kept]
        witcore.save_json(args.queue_out, queue)

    if args.dag_out:
        import hashlib
        dag = [{"node_id": c["id"], "type": "lemma", "statement": c["form"],
                "lean_statement": c.get("lean_statement"), "arena": ARENA, "status": OPEN,
                "target_hash": hashlib.sha256((c.get("lean_statement") or c["form"]).encode()).hexdigest(),
                "dependency_path_to_target": ["concept_generator", args.goal]}
               for c in kept]
        witcore.save_json(args.dag_out, dag)

    print(json.dumps({k: v for k, v in out.items() if k != "candidates"}
                     | {"kept": len(kept), "killed_count": len(killed),
                        "top": [{"kind": c["kind"], "form": c["form"], "novelty": c["novelty"]} for c in kept[:5]]},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
