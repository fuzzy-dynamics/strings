#!/usr/bin/env python3
"""Ideation phase — the mandatory divergent step before any DAG freeze.

A working mathematician generates many candidate directions before filtering;
witsoc's pipeline previously went straight from barrier mapping to decomposition,
so every attack was template-shaped. This module produces a quota of ideas across
distinct cognitive move classes (examples_first, wishful_lemma, strengthen_to_prove,
find_the_enemy, dualize_reformulate, invent_concept, vary_problem), merging
deterministic generators with an optional untrusted `cmd:` sampler, then ranks by
novelty+specificity under a move-class diversity constraint.

GENERATION vs JUDGEMENT (the calibration spine, same as concept_generator):
  * every idea is born `status = OPEN_UNFALSIFIED`, `arena = SPECULATIVE`;
  * `assert_no_upgrade` raises if anything carries trust — ideation structurally
    cannot manufacture a solve; ranking allocates attention only;
  * ideas exit the arena only through the kernel gate (witsoc prove /
    lovasz-prover-dispatch -> validate_prover_result).

SERENDIPITY LANE: a capped fraction of ideas may carry `lane = "serendipity"` —
high-novelty stepping stones with no recorded dependency path to the target.
They are dispatchable and harvest into the library, but are never reported as
target progress (dependency_path_to_target says so explicitly).

Usage:
  ideate.py --target "<informal frozen statement>" [--lean-target "<Lean>"]
      [--domain D] [--barrier B ...] [--quota 15] [--sampler cmd:CMD]
      [--serendipity-fraction 0.2] [--library DIR]
      [--out ideation.json] [--run-dir RUNS/<task> --write]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
import goal_structure as gs  # noqa: E402

OPEN = "OPEN_UNFALSIFIED"
ARENA = "SPECULATIVE"
FORBIDDEN = ("sorry", "admit", "axiom", "native_decide")

MOVE_CLASSES = (
    "examples_first",
    "wishful_lemma",
    "strengthen_to_prove",
    "find_the_enemy",
    "dualize_reformulate",
    "invent_concept",
    "vary_problem",
)

# Move classes whose ideas are exploratory by nature: eligible for the
# serendipity lane (no dependency path to the target is required of them).
SERENDIPITY_ELIGIBLE = {"examples_first", "invent_concept"}

MIN_DISTINCT_CLASSES = 4


def tok(s: str) -> Counter:
    return Counter(re.findall(r"[A-Za-z0-9_]+", (s or "").lower()))


from witcore import cosine  # noqa: E402  -- shared substrate, was a local copy

def force_open(idea: dict) -> dict:
    """Single chokepoint: an idea leaves the generator only as
    OPEN_UNFALSIFIED / SPECULATIVE. No exceptions, no upgrades."""
    idea["status"] = OPEN
    idea["arena"] = ARENA
    return idea


def assert_no_upgrade(ideas: list[dict]) -> None:
    for i in ideas:
        if i.get("status") != OPEN or i.get("arena") != ARENA:
            raise AssertionError(
                f"calibration violation: ideation emitted status={i.get('status')!r} "
                f"arena={i.get('arena')!r}; must be {OPEN}/{ARENA}")


def _clean_lean(stmt) -> str | None:
    if not stmt or not isinstance(stmt, str):
        return None
    if any(t in stmt for t in FORBIDDEN):
        return None
    return stmt.strip() or None


def _idea(move: str, text: str, *, lean: str | None = None, follow_up: str = "",
          falsification: str = "", lane: str = "target", source: str = "template") -> dict:
    return force_open({
        "move_class": move,
        "idea": text,
        "lean_statement": _clean_lean(lean),
        "follow_up_engine": follow_up,
        "falsification_test": falsification,
        "lane": lane if move in SERENDIPITY_ELIGIBLE else "target",
        "source": source,
    })


# --- Deterministic move-class generators -------------------------------------
def gen_examples_first(target: str, domain: str) -> list[dict]:
    plans = {
        "number_theory": ("tabulate the relevant arithmetic invariant for n up to 10^4 and inspect "
                          "residue classes, growth rate, and where near-misses cluster",
                          "empirical_miner.py --domain number_theory"),
        "graph_theory": ("enumerate all graphs up to n=7 (and the standard families: cycles, Mycielski, "
                         "Kneser) and tabulate the invariant; look for the smallest near-violator",
                         "empirical_miner.py --domain graphs"),
        "combinatorics": ("exhaust the smallest instances and the symmetric/extremal candidates; record "
                          "where the bound is tight", "research_search.py finite-model"),
        "additive_combinatorics": ("compute the invariant on intervals, arithmetic progressions, Sidon "
                                   "sets, and random sets of matching density", "research_search.py finite-model"),
    }
    plan, engine = plans.get(domain, ("compute the statement's key quantity on the smallest instances and "
                                      "the most symmetric instances; record exactly where intuition and data "
                                      "diverge", "empirical_miner.py"))
    out = [_idea("examples_first", f"Before theorizing: {plan}.", follow_up=engine,
                 falsification="a single computed instance violating the pattern")]
    out.append(_idea("examples_first",
                     "Mine the computed table for stable invariants and implications, then push survivors "
                     "through the conjecture-to-lemma pipeline.",
                     follow_up="conjecture_to_lemma_pipeline.py", lane="serendipity",
                     falsification="pattern breaks at larger bounds"))
    return out


def gen_wishful_lemma(target: str, lean_target: str | None) -> list[dict]:
    out = [_idea("wishful_lemma",
                 f"State the dream lemma: the single statement H that would make '{target}' a two-line "
                 "corollary, even if H looks too strong. Then kernel-test H → target in the arena.",
                 follow_up="speculative_arena.py",
                 falsification="counterexample to H (then repair H, do not discard the wish)")]
    if lean_target:
        chain = gs.implication_chain(lean_target)
        if chain["hypotheses"]:
            pruned = gs.pruned_variants(lean_target, max_variants=2)
            for v in pruned:
                out.append(_idea("wishful_lemma",
                                 f"Wish the hypotheses away: prove the stronger hypothesis-free form "
                                 f"(dropped: {', '.join(v['dropped'])[:80]}).",
                                 lean=v["statement"], follow_up="speculative_arena.py",
                                 falsification="counterexample exploiting a dropped hypothesis"))
        out.append(_idea("wishful_lemma",
                         "Wish for an equivalence: find a simpler statement S with S ↔ target; proving "
                         "either direction is progress, and S may live in a better-tooled domain.",
                         follow_up="speculative_arena.py",
                         falsification="one direction of the equivalence fails on small cases"))
    return out


def gen_strengthen_to_prove(target: str, lean_target: str | None) -> list[dict]:
    out = [_idea("strengthen_to_prove",
                 "Inductive loading: replace the goal by a stronger, more uniform statement whose induction "
                 "hypothesis is strong enough to close the inductive step (generalize constants to "
                 "parameters, add the accumulator, strengthen the invariant).",
                 follow_up="close_obligation.py --search (generalization candidates)",
                 falsification="the strengthened statement is false on a small case")]
    if lean_target:
        nums = sorted({m for m in re.findall(r"\b\d+\b", lean_target) if m not in ("0", "1")})
        if nums:
            out.append(_idea("strengthen_to_prove",
                             f"Anti-unify the literals {', '.join(nums[:4])} into universally quantified "
                             "parameters; the parametric statement is often the provable one.",
                             follow_up="proof_autopsy.py / close_obligation.py",
                             falsification="parametric form fails for some parameter value"))
    return out


def gen_find_the_enemy(target: str, domain: str) -> list[dict]:
    return [
        _idea("find_the_enemy",
              "Assume a minimal counterexample M and derive forced local structure: what must M look like "
              "near its smallest/densest part? Each forced property is a lemma candidate.",
              follow_up="counterexample_search.py",
              falsification="the forced structure admits an explicit construction (a real counterexample)"),
        _idea("find_the_enemy",
              "Search for near-violators: objects that almost break the claim reveal the true threshold and "
              "the shape of the extremal configuration.",
              follow_up="construction_search.py / discovery_evaluators.py",
              falsification="a near-violator extends to a full violator"),
    ]


def gen_dualize(target: str, domain: str) -> list[dict]:
    out = []
    try:
        import ontology_pivot as op
        for p in op.pivots(target, domain, k=2):
            out.append(_idea("dualize_reformulate",
                             f"Pivot to {p.get('target_domain', 'an orthogonal domain')}: "
                             f"{p.get('encoding', 'structure-preserving encoding')} — unlocks "
                             f"{', '.join(p.get('unlocks', [])[:3]) or 'a different theorem family'}.",
                             follow_up="ontology_pivot.py",
                             falsification="the encoding fails to preserve the obstruction"))
    except Exception:
        pass
    if not out:
        out.append(_idea("dualize_reformulate",
                         "Translate the target into a dual language (cuts/flows, colorings/independent sets, "
                         "additive/Fourier, combinatorial/spectral) where the blocked operation is native.",
                         follow_up="ontology_pivot.py",
                         falsification="the dual statement is provably weaker than the original"))
    return out


def gen_invent_concept(target: str, domain: str) -> list[dict]:
    return [_idea("invent_concept",
                  "Name the missing invariant: what single quantity, monotone under the problem's moves and "
                  "extremal exactly on the conjectured objects, would make the proof trivial? Emit a "
                  "grammar-search record and search for it instead of inventing it by prose.",
                  follow_up="definition_synthesis.py", lane="serendipity",
                  falsification="no expression in the grammar separates the positive and negative examples")]


def gen_vary_problem(target: str, lean_target: str | None) -> list[dict]:
    out = [_idea("vary_problem",
                 "Pose the neighbors: one strictly stronger variant (try to break it), one strictly weaker "
                 "variant (try to prove it), and the boundary case where the statement almost fails.",
                 follow_up="pose_variants.py / curriculum_portfolio.py",
                 falsification="the stronger variant has a counterexample (keep it as an obstruction)")]
    if lean_target:
        conjs = gs.conjunction_split(lean_target)
        for c in conjs[:2]:
            out.append(_idea("vary_problem", "Isolate one conjunct as a standalone lemma.",
                             lean=c, follow_up="lovasz_prover_dispatch.py",
                             falsification="the conjunct fails independently"))
        f = re.match(r"^\s*∀\s*([A-Za-z_][A-Za-z0-9_']*)\s*:\s*(Nat|ℕ)\s*,\s*(.+)$", lean_target.strip())
        if f:
            v, body = f.group(1), f.group(3)
            out.append(_idea("vary_problem", f"Bounded version: settle the statement for all {v} ≤ 32 first.",
                             lean=f"∀ {v} : Nat, {v} ≤ 32 → ({body})",
                             follow_up="lovasz_prover_dispatch.py",
                             falsification="bounded search finds a witness below the bound"))
    return out


# --- LLM sampler fleet (untrusted) ---------------------------------------------
def sampler_ideas(target: str, lean_target: str | None, domain: str,
                  barriers: list[str], quota: int, sampler: str | None,
                  fleet_rounds: int = 1, theory: dict | None = None) -> list[dict]:
    """F2 fleet-wide generation: every configured sampler (sampler_fleet) plus
    the explicit --sampler argument is queried `fleet_rounds` times. Quantity
    before quality is the design — the falsification/kernel stack is the filter,
    so generation should be as wide as the fleet allows. Everything returned is
    born OPEN_UNFALSIFIED with a per-sampler source tag."""
    import sampler_fleet as sf
    request = {
        "task": "ideate", "target": target, "lean_target": lean_target, "domain": domain,
        "barriers": barriers, "move_classes": list(MOVE_CLASSES), "quota": quota,
        "problem_theory": theory or {},
        "instructions": "Generate diverse mathematical research ideas. Quantity before quality; no "
                        "filtering. Build on the problem_theory: respect refuted candidates and "
                        "recorded failure mechanisms. Each idea: {move_class, idea, lean_statement?, "
                        "falsification_test?}.",
    }
    out = []
    for result in sf.sample(request, per_sampler=max(1, fleet_rounds), extra=sampler):
        for c in result["reply"].get("ideas", []) or []:
            if not (isinstance(c, dict) and c.get("idea")):
                continue
            move = str(c.get("move_class") or "wishful_lemma")
            if move not in MOVE_CLASSES:
                move = "wishful_lemma"
            out.append(_idea(move, str(c["idea"]), lean=c.get("lean_statement"),
                             falsification=str(c.get("falsification_test") or ""),
                             follow_up=str(c.get("follow_up_engine") or ""),
                             source=f"llm:{result['sampler_id']}"))
    return sf.dedup(out, "idea")


# --- Ranking + diversity-constrained selection --------------------------------
def library_statements(library: Path | None) -> list[str]:
    if not library or not library.exists():
        return []
    try:
        import subprocess
        r = subprocess.run([sys.executable, str(SCRIPT_DIR / "lemma_library.py"),
                            "--library", str(library), "search", "--query", "lemma", "--limit", "50"],
                           capture_output=True, text=True, timeout=30, check=False)
        return [m.get("statement", "") for m in json.loads(r.stdout).get("matches", [])]
    except Exception:
        return []


def score_ideas(ideas: list[dict], lib: list[str]) -> None:
    lib_vecs = [tok(s) for s in lib]
    seen_vecs: list[Counter] = []
    for i in ideas:
        text = (i.get("lean_statement") or "") + " " + i.get("idea", "")
        v = tok(text)
        nov_lib = 1.0 - max((cosine(v, lv) for lv in lib_vecs), default=0.0)
        nov_intra = 1.0 - max((cosine(v, sv) for sv in seen_vecs), default=0.0)
        novelty = round(0.6 * nov_lib + 0.4 * nov_intra, 3)
        specificity = 1.0 if i.get("lean_statement") else (0.6 if i.get("falsification_test") else 0.3)
        i["novelty"] = novelty
        i["specificity"] = specificity
        i["score"] = round(0.5 * novelty + 0.5 * specificity, 4)
        seen_vecs.append(v)


def select(ideas: list[dict], quota: int, serendipity_fraction: float) -> list[dict]:
    """Round-robin across move classes (diversity first), then best-score fill.
    Serendipity-lane ideas are capped at ceil(fraction*quota)."""
    by_class: dict[str, list[dict]] = {}
    for i in sorted(ideas, key=lambda x: -x.get("score", 0)):
        by_class.setdefault(i["move_class"], []).append(i)
    cap = max(0, math.ceil(serendipity_fraction * quota))
    chosen: list[dict] = []
    seren = 0
    classes = [c for c in MOVE_CLASSES if c in by_class]
    # round-robin until quota or exhaustion
    idx = {c: 0 for c in classes}
    while len(chosen) < quota and any(idx[c] < len(by_class[c]) for c in classes):
        for c in classes:
            if len(chosen) >= quota:
                break
            while idx[c] < len(by_class[c]):
                cand = by_class[c][idx[c]]
                idx[c] += 1
                if cand.get("lane") == "serendipity":
                    if seren >= cap:
                        continue  # over serendipity cap: skip, try next of this class
                    seren += 1
                chosen.append(cand)
                break
    for n, i in enumerate(chosen):
        i["id"] = f"idea-{n + 1}"
    return chosen


# --- Run-dir merge -------------------------------------------------------------
def queue_entry(idea: dict, target: str) -> dict:
    """actual_lemma_queue entry with the honest non-empty defaults
    validate_open_problem_run requires."""
    serendip = idea.get("lane") == "serendipity"
    return {
        "statement": idea.get("lean_statement") or idea["idea"],
        "lean_statement": idea.get("lean_statement"),
        "why_it_matters": (f"ideation ({idea['move_class']}): " + idea["idea"])[:300],
        "unlocks": ("library stepping stone (serendipity lane; NOT target progress)"
                    if serendip else f"a direct attack route on: {target[:160]}"),
        "known_counterexamples_or_boundary_cases": ["none recorded yet (fresh ideation candidate)"],
        "failed_approaches": ["none yet"],
        "next_mutation": idea.get("falsification_test") or "falsify on small cases, then dispatch the Prover",
        "smallest_formalizable_subcase": idea.get("lean_statement") or "needs formalization first",
        "status": OPEN,
        "arena": ARENA,
        "priority": int(round(50 + 40 * idea.get("score", 0))),
        "lane": idea.get("lane", "target"),
        "dependency_path_to_target": (["serendipity_lane", target] if serendip
                                      else ["ideation", target]),
        "source": f"ideate:{idea['move_class']}",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True, help="frozen informal target statement")
    ap.add_argument("--lean-target", default=None)
    ap.add_argument("--domain", default="other")
    ap.add_argument("--barrier", action="append", dest="barriers", default=[])
    ap.add_argument("--quota", type=int, default=15)
    ap.add_argument("--sampler", default=os.environ.get("WITSOC_IDEATION_SAMPLER"))
    ap.add_argument("--fleet-rounds", type=int, default=1,
                    help="rounds per fleet sampler (WITSOC_SAMPLER_FLEET multiplies generation)")
    ap.add_argument("--serendipity-fraction", type=float, default=0.2)
    ap.add_argument("--library", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("ideation.json"))
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument("--write", action="store_true", help="merge dispatchable ideas into the run's actual_lemma_queue")
    args = ap.parse_args()

    # Infer the domain from the target when the caller did not pin one. Without
    # this every generator runs under 'other' (generic empirical engine, and the
    # dualize pivot misfires on a stray keyword), so ideas don't engage the real
    # subject. An explicit, non-'other' --domain is always respected.
    if args.domain in ("", "other"):
        try:
            import ontology_pivot as _op
            args.domain = _op.infer_domain(args.target)
        except Exception:
            pass

    raw: list[dict] = []
    raw += gen_examples_first(args.target, args.domain)
    raw += gen_wishful_lemma(args.target, args.lean_target)
    raw += gen_strengthen_to_prove(args.target, args.lean_target)
    raw += gen_find_the_enemy(args.target, args.domain)
    raw += gen_dualize(args.target, args.domain)
    raw += gen_invent_concept(args.target, args.domain)
    raw += gen_vary_problem(args.target, args.lean_target)
    theory = None
    if args.run_dir is not None:
        try:
            import problem_theory as pt
            if pt.theory_path(args.run_dir).exists():
                theory = pt.prompt_context(args.run_dir)
        except Exception:
            theory = None
    raw += sampler_ideas(args.target, args.lean_target, args.domain, args.barriers,
                         args.quota, args.sampler, args.fleet_rounds, theory)

    score_ideas(raw, library_statements(args.library))
    chosen = select(raw, args.quota, args.serendipity_fraction)

    # CALIBRATION GUARD (structural): nothing left the arena with trust.
    assert_no_upgrade(chosen)

    classes_present = sorted({i["move_class"] for i in chosen})
    shortfall = max(0, args.quota - len(chosen))
    diversity_met = len(classes_present) >= min(MIN_DISTINCT_CLASSES, len(MOVE_CLASSES))

    out = {
        "schema": "witsoc.ideation.v1",
        "target": args.target,
        "lean_target": args.lean_target,
        "domain": args.domain,
        "quota": args.quota,
        "generated": len(raw),
        "selected": len(chosen),
        "shortfall": shortfall,
        "move_classes_present": classes_present,
        "diversity_met": diversity_met,
        "serendipity_count": sum(1 for i in chosen if i.get("lane") == "serendipity"),
        "ideas": chosen,
        "reservoir": [i for i in raw if i not in chosen],
        "sampler_used": bool(args.sampler),
        "fleet_size": len(__import__("sampler_fleet").samplers(args.sampler)),
        "llm_idea_count": sum(1 for i in raw if str(i.get("source", "")).startswith("llm")),
        "calibration": f"every idea is {OPEN}/{ARENA}; ideation allocates attention only and cannot "
                       "assign trust. Exit the arena only via the kernel gate.",
    }
    witcore.save_json(args.out, out)

    if args.write and args.run_dir:
        qpath = args.run_dir / "actual_lemma_queue.json"
        queue = witcore.load_json(qpath, [])
        if not isinstance(queue, list):
            queue = []
        existing = {e.get("statement") for e in queue if isinstance(e, dict)}
        added = 0
        for idea in chosen:
            e = queue_entry(idea, args.target)
            if e["statement"] not in existing:
                queue.append(e)
                added += 1
        witcore.save_json(qpath, queue)
        witcore.save_json(args.run_dir / "ideation.json", out)
        out["queue_added"] = added

    print(json.dumps({k: v for k, v in out.items() if k not in ("ideas", "reservoir")}
                     | {"top": [{"id": i["id"], "move_class": i["move_class"],
                                 "idea": i["idea"][:90], "score": i["score"], "lane": i["lane"]}
                                for i in chosen[:8]]},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
