#!/usr/bin/env python3
"""SKETCH TOURNAMENT: N competing decompositions per target, ranked by a
good-gaps judge BEFORE any prover budget is spent.

decompose_problem emits exactly ONE static DAG, and the whole worker budget
rides on it — a wrong decomposition wastes the run. This generates several
genuinely different decomposition strategies (template, concept/induction-first,
barrier-first, optional LLM-proposed, plus the population incumbent and its
small-diff mutant), scores each on the GOOD-GAPS rubric, optionally consults an
LLM tournament judge (full AlphaProof-style rater prompt, `"2 > 1 = 3"` final
ranking) and crowns a winner whose nodes get the dispatch budget. Rankings feed
Elo + P-UCB parent selection in the SQLite-backed population
(sketch_population.py); every tournament (ranking, winner, raw rater judgment)
is logged to the populations.sqlite3 history table.

The judge's rubric (deterministic, transparent):
  * lean coverage    — gaps the Prover can actually attack (has lean_statement)
  * gap atomicity    — one reasoning step per gap; conjunctive gaps are
                       splittable (half credit), multi-step gaps are bad gaps
  * miracle penalty  — a node that merely RESTATES the target is a miracle
                       sorry, not a decomposition
  * dependency shape — nodes know their path to the target
  * type diversity   — multiple lines of attack survive ranking

CALIBRATION: the tournament ALLOCATES EFFORT ONLY. Every node in every sketch
must be OPEN/OPEN_UNFALSIFIED (structural assert); ranks and Elo never touch a
claim's status — trust still enters exclusively via the kernel dispatch gates.

Usage:
  sketch_tournament.py --target "..." [--lean-target "..."] [--target-hash H]
      [--domain D] [--run-dir RUN --write] [--sampler cmd:CMD] [--rater cmd:CMD]
      [--population-dir DIR | --no-population] [--out tournament.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
import goal_structure as gs  # noqa: E402
import sketch_population as sp  # noqa: E402
import decompose_problem as dp  # noqa: E402
import concept_generator as cg  # noqa: E402
import domain_barrier_lemmas as dbl  # noqa: E402

ATOMICITY_CREDIT = {"atomic": 1.0, "conjunctive": 0.6, "multi_step": 0.3}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tok(s: str) -> Counter:
    return Counter(re.findall(r"[A-Za-z0-9_]+", (s or "").lower()))


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0) for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


# --- sketch generators (each returns {sketch_id, strategy, nodes, lemmas}) ----
def sketch_template(target: str, target_hash: str) -> dict:
    nodes, lemmas = dp.decompose(target, target_hash)
    return {"sketch_id": "template", "strategy": "template_decomposition",
            "nodes": nodes, "lemmas": lemmas}


def sketch_concepts(target: str, lean_target: str | None, target_hash: str, domain: str) -> dict | None:
    goal = lean_target or target
    cands = [c for c in cg.deterministic_candidates(goal, domain)]
    if not any(c.get("lean_statement") for c in cands):
        return None
    nodes = []
    for i, c in enumerate(cands, start=1):
        nid = f"K{i}"
        nodes.append({"node_id": nid, "statement": c["form"], "type": c["kind"],
                      "lean_statement": c.get("lean_statement"), "status": "OPEN",
                      "target_hash": target_hash, "dependencies": ["T"],
                      "dependency_path_to_target": [nid, "T"], "priority": 78 - i})
    return {"sketch_id": "concepts", "strategy": "concept_stepping_stones",
            "nodes": nodes, "lemmas": []}


def sketch_barriers(target: str, lean_target: str | None, target_hash: str, domain: str,
                    failure_memory: list[dict] | None = None) -> dict:
    lemmas = dbl.generate_barrier_lemmas(target, lean_target=lean_target, domain=domain,
                                         target_hash=target_hash,
                                         failure_memory=failure_memory, max_lemmas=8)
    nodes = [{"node_id": l["node_id"], "statement": l["statement"], "type": l["barrier_type"],
              "lean_statement": l.get("lean_statement"), "status": "OPEN",
              "target_hash": target_hash, "dependencies": ["T"],
              "dependency_path_to_target": l.get("dependency_path_to_target") or [l["node_id"], "T"],
              "priority": l.get("priority", 80)} for l in lemmas]
    return {"sketch_id": "barriers", "strategy": "barrier_lemmas",
            "nodes": nodes, "lemmas": lemmas}


def sketch_llm(target: str, lean_target: str | None, domain: str, sampler: str,
               prior_attempts: list[dict] | None = None, theory: dict | None = None) -> dict | None:
    reply = witcore.run_sampler(sampler, {
        "task": "propose_decomposition", "target": target, "lean_target": lean_target,
        "domain": domain, "k": 6, "prior_attempts": prior_attempts or [],
        "problem_theory": theory or {},
        "rules": "one reasoning step per node; routine gaps only — never sorry the "
                 "core insight; lean_statement when safely formalizable, else null"})
    if not isinstance(reply, dict):
        return None
    nodes = []
    for i, n in enumerate(reply.get("nodes") or [], start=1):
        if not isinstance(n, dict) or not n.get("statement"):
            continue
        lean = n.get("lean_statement")
        if lean and any(t in str(lean) for t in dbl.FORBIDDEN_LEAN):
            lean = None  # never accept a proposed Lean goal smuggling a proof hole
        nid = f"M{i}"
        nodes.append({"node_id": nid, "statement": str(n["statement"]),
                      "type": str(n.get("kind") or "lemma"), "lean_statement": lean,
                      "status": "OPEN", "target_hash": sha(str(n["statement"])),
                      "dependencies": ["T"], "dependency_path_to_target": [nid, "T"],
                      "priority": 76 - i, "source": "llm"})
    if not nodes:
        return None
    return {"sketch_id": "llm", "strategy": "llm_proposed", "nodes": nodes, "lemmas": []}


# --- the good-gaps judge -------------------------------------------------------
def judge_sketch(sketch: dict, target: str) -> dict:
    nodes = [n for n in (sketch.get("nodes") or [])
             if n.get("type") != "target" and n.get("node_id") != "T"]
    if not nodes:
        return {"score": 0.0, "nodes": 0}
    lean_nodes = [n for n in nodes if n.get("lean_statement")]
    coverage = len(lean_nodes) / len(nodes)
    if lean_nodes:
        atomicity = sum(ATOMICITY_CREDIT.get(gs.granularity(str(n["lean_statement"]))["flag"], 0.0)
                        for n in lean_nodes) / len(lean_nodes)
    else:
        atomicity = 0.0
    tvec = _tok(target)
    miracles = sum(1 for n in nodes
                   if _cosine(_tok(str(n.get("lean_statement") or n.get("statement"))), tvec) > 0.9)
    miracle_frac = miracles / len(nodes)
    dep_quality = sum(1 for n in nodes if n.get("dependency_path_to_target")) / len(nodes)
    diversity = len({n.get("type") for n in nodes}) / len(nodes)
    score = (0.30 * coverage + 0.30 * atomicity + 0.15 * dep_quality
             + 0.10 * diversity + 0.15 * (1.0 - miracle_frac))
    return {"score": round(score, 4), "nodes": len(nodes),
            "lean_coverage": round(coverage, 3), "gap_atomicity": round(atomicity, 3),
            "miracle_fraction": round(miracle_frac, 3), "dependency_quality": round(dep_quality, 3),
            "type_diversity": round(diversity, 3)}


# --- LLM rater (optional), AlphaProof-tournament ranking format ---------------
RATER_PROMPT = """You are a discerning tournament judge and an expert in formal proof strategies, specializing in Lean. Your task is to serve as the arbiter between competing proof sketches for a given theorem. Each sketch decomposes the target into subgoals (gaps) that witsoc's kernel-gated Prover will attempt to close.

### Your Objective
Your goal is to deliver a professional comparative analysis. You will rank the sketches from best to worst and articulate the precise reasoning behind your decision. Your ranking allocates search effort only; it never certifies any sketch as proved.

### Target Theorem
{target}

### Proof Sketches to Review
The sketches below are labeled 1 to {n}.

{player_blocks}

### Core Judging Criteria & Priorities
Evaluate the sketches based on the following principles, which are listed in descending order of importance.

1. Strategic Robustness & Generalizability (Highest Priority)

Generalization over Specialization: Does the strategy scale to the full theorem? A plan that only handles small cases or special parameter values is weaker than one that addresses the general statement.

Avoid "Overfitting": Penalize strategies that rely on "brute force" computation, exhaustive enumeration, or tricks exploiting incidental features of the statement rather than its mathematical structure.

Diversity of Strategy: The goal is to explore multiple promising lines of reasoning. When sketches are otherwise comparable, prefer the one opening a genuinely different line of attack.

2. Quality of Decomposition
You must evaluate the quality of the gaps (sorries) left in the proof. Not all unproven subgoals are equal.

Good Gaps (Routine/Technical): It is acceptable to sorry standard mathematical tasks — routine algebraic manipulation, standard library lemmas, bookkeeping steps an automated prover can realistically close.

Bad Gaps (Miracles/Strategic): It is unacceptable to sorry the core insight of the proof. A gap that merely restates the target, or hides the whole difficulty in one step, destroys the decomposition's value.

The Rule: A sketch with good gaps (even if the Prover fails to close them) > A sketch with no gaps (but a dead-end strategy).

3. Logical Correctness:

Is the plan valid? Each step must be mathematically sound, and the composition of all steps must actually imply the target.

Coherence: Do the steps build upon each other logically towards the final goal?

### Feedback and Evaluation Analysis
You will receive execution feedback, but you must interpret this carefully:

Prover Failure != Bad Sketch: the Prover failing to close a routine gap does not make the sketch bad; judge the strategy, not the subsolver.

System Errors: Ignore timeouts or service errors.

### Critical Flaws & Red Flags
Be vigilant for these issues, which severely undermine a sketch's quality:

Asserting a Falsehood: a step that states something false (sanity-check small cases mentally).

Trivial or Circular Reasoning: a step that assumes the target or a trivial restatement of it.

Strategic Dead Ends: locally valid steps that cannot compose into a proof of the target.

### Feedback and Evaluation error:
You will receive execution feedback and/or evaluation errors for each sketch. Treat evaluation errors (timeouts, infrastructure failures) as neutral — they say nothing about sketch quality.

### Required Output Format
Provide your judgment in the following structured format.

1. Summary of Strategies

Briefly summarize the approach taken in each sketch.

2. Comparative Analysis

Scalability: which strategies address the general statement vs. special cases.

Decomposition Quality: which sketches leave good (routine) gaps vs. bad (miracle) gaps.

Logical Soundness: any invalid, false, or circular steps.

Strategic Approach: the diversity and promise of the lines of attack.

Progress & Feasibility: what the execution feedback actually supports.

3. Final Judgment

Ranking: Provide a ranking of the sketches from best to worst, using '>' for 'better than' and '=' for 'equal in quality'.

Rationale: Provide a concluding paragraph that crisply summarizes the primary reasons for your ranking, focusing on the most significant differences in quality based on the judging criteria.

Provide a complete rank of the sketches from best to worst using '>' for 'better than' and '=' for 'equal in quality'. Your output must END with a line containing ONLY the final ranking in the format '2 > 1 = 3', containing a ranking of all {n} sketches presented.
"""

_RANK_RE = re.compile(r"^[\s\d>=]+$")


def parse_ranking(text: str, n: int) -> list[list[int]] | None:
    """Parse a `'2 > 1 = 3'` comparative ranking into ordered groups of 0-based
    sketch indices. Returns None unless EVERY sketch 1..n appears exactly once."""
    for line in reversed([l.strip() for l in (text or "").splitlines() if l.strip()]):
        if not _RANK_RE.match(line):
            continue
        groups: list[list[int]] = []
        ok = True
        for chunk in line.split(">"):
            members = []
            for tok in chunk.split("="):
                tok = tok.strip()
                if not tok.isdigit():
                    ok = False
                    break
                members.append(int(tok) - 1)
            if not ok or not members:
                ok = False
                break
            groups.append(members)
        flat = [i for g in groups for i in g]
        if ok and sorted(flat) == list(range(n)):
            return groups
    return None


def player_blocks(sketches: list[dict], scores: list[dict]) -> str:
    blocks = []
    for i, (sk, sc) in enumerate(zip(sketches, scores), start=1):
        lines = [f"Sketch {i} (strategy: {sk['strategy']}):"]
        for n in sk["nodes"][:10]:
            lines.append(f"  - [{n.get('type')}] {str(n.get('statement'))[:160]}"
                         + (f" | lean: {str(n['lean_statement'])[:120]}" if n.get("lean_statement") else " | (not formalized)"))
        lines.append(f"  execution_feedback: {json.dumps(sc)}")
        # Incumbents/mutants carry their prior dispatch outcome: what the
        # kernel-gated Prover progressed on vs. refuted last time around.
        if sk.get("dispatch_outcome"):
            lines.append(f"  prior_dispatch_outcome: {json.dumps(sk['dispatch_outcome'])}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def llm_ranking(sketches: list[dict], scores: list[dict], target: str,
                rater: str) -> tuple[list[list[int]] | None, str | None]:
    """Ask the tournament-judge LLM for a comparative ranking. Returns
    (ranking groups, raw judgment text); (None, None) when the rater fails or
    its final ranking is not a complete permutation."""
    prompt = RATER_PROMPT.format(target=target, n=len(sketches),
                                 player_blocks=player_blocks(sketches, scores))
    reply = witcore.run_sampler(rater, {
        "task": "rank_proof_sketches", "players": len(sketches), "prompt": prompt})
    if not isinstance(reply, dict):
        return None, None
    judgment = str(reply.get("ranking") or reply.get("text") or "")
    return parse_ranking(judgment, len(sketches)), judgment or None


def merge_rankings(det_order: list[int], llm_groups: list[list[int]] | None, n: int) -> list[list[int]]:
    """Combine the deterministic judge order with the optional LLM rater by mean
    rank position; the judge alone decides when no (valid) LLM ranking exists."""
    det_pos = {idx: p for p, idx in enumerate(det_order)}
    if not llm_groups:
        return [[i] for i in det_order]
    llm_pos = {idx: p for p, group in enumerate(llm_groups) for idx in group}
    combined = sorted(range(n), key=lambda i: (det_pos[i] + llm_pos.get(i, n)) / 2.0)
    out: list[list[int]] = []
    last_key = None
    for i in combined:
        key = (det_pos[i] + llm_pos.get(i, n)) / 2.0
        if out and key == last_key:
            out[-1].append(i)
        else:
            out.append([i])
            last_key = key
    return out


# --- the tournament ------------------------------------------------------------
def tournament(target: str, lean_target: str | None, target_hash: str, domain: str,
               sampler: str | None = None, rater: str | None = None,
               population_dir: Path | None = None, use_population: bool = True,
               failure_memory: list[dict] | None = None,
               theory: dict | None = None, kernel_probe: int = 0) -> dict:
    pop = sp.load_population(target_hash, population_dir) if use_population else None
    prior = sp.prior_context(pop) if pop else []

    sketches: list[dict] = [sketch_template(target, target_hash)]
    sc = sketch_concepts(target, lean_target, target_hash, domain)
    if sc:
        sketches.append(sc)
    sketches.append(sketch_barriers(target, lean_target, target_hash, domain, failure_memory))
    if sampler:
        sl = sketch_llm(target, lean_target, domain, sampler, prior, theory)
        if sl:
            sketches.append(sl)
    # population: the reigning incumbent competes, and so does its small-diff
    # mutant — this is the evolution loop (prior attempts as parents). With a
    # sampler fleet configured, operator-directed LLM mutants of the same parent
    # enter too (F2): small-diff explores template-space, LLM mutation explores
    # proof-space; the judge + Elo decide which survives.
    parent = sp.select_parent(pop) if pop and pop.get("attempts") else None
    if parent is not None:
        sketches.append({"sketch_id": f"incumbent:{parent['attempt_id']}",
                         "strategy": f"incumbent:{parent['strategy']}",
                         "nodes": parent["nodes"], "lemmas": parent.get("lemmas") or [],
                         "dispatch_outcome": parent.get("outcome")})
        mutant = sp.mutate_sketch(parent)
        mutant["dispatch_outcome"] = parent.get("outcome")
        sketches.append(mutant)
        inspiration = sp.select_inspiration(pop, parent.get("strategy"))
        for llm_child in sp.llm_mutants(parent, target, lean_target, domain, limit=2, theory=theory,
                                        inspiration=inspiration):
            llm_child["dispatch_outcome"] = parent.get("outcome")
            sketches.append(llm_child)

    # CALIBRATION (structural): every entrant holds open proposals only.
    for sk in sketches:
        sp.assert_no_trust(sk.get("nodes") or [])

    scores = [judge_sketch(sk, lean_target or target) for sk in sketches]

    # A3 kernel grounding (the Agent-D design): probe up to `kernel_probe`
    # formalizable nodes per sketch with a SMALL deterministic prover budget;
    # kernel-closed nodes raise the judge score, so Elo reflects kernel
    # reality instead of gap aesthetics alone. Effort allocation only — node
    # statuses are untouched; the real dispatch still decides everything.
    if kernel_probe > 0:
        import close_obligation as co
        for i, sk in enumerate(sketches):
            closed = 0
            probed = 0
            for node in sk.get("nodes") or []:
                if probed >= kernel_probe:
                    break
                lean = node.get("lean_statement")
                if not lean:
                    continue
                probed += 1
                try:
                    r = co.close_goal(str(lean), name="probe", max_candidates=8,
                                      no_minimize=True)
                    if r.get("discharged"):
                        closed += 1
                except Exception:
                    pass
            scores[i]["kernel_probe"] = {"probed": probed, "closed": closed}
            scores[i]["score"] = round(scores[i]["score"] + 0.5 * closed, 4)
    det_order = sorted(range(len(sketches)), key=lambda i: -scores[i]["score"])
    llm_groups, rater_judgment = llm_ranking(sketches, scores, target, rater) if rater else (None, None)
    ranking = merge_rankings(det_order, llm_groups, len(sketches))
    winner_idx = ranking[0][0]

    result = {
        "schema": "witsoc.sketch_tournament.v1",
        "target": target, "lean_target": lean_target, "target_hash": target_hash,
        "domain": domain,
        "entrants": [{"sketch_id": sk["sketch_id"], "strategy": sk["strategy"],
                      "judge": scores[i]} for i, sk in enumerate(sketches)],
        "deterministic_order": [sketches[i]["sketch_id"] for i in det_order],
        "llm_ranking_used": bool(llm_groups),
        "rater_judgment": rater_judgment,
        "ranking": [[sketches[i]["sketch_id"] for i in group] for group in ranking],
        "winner": sketches[winner_idx]["sketch_id"],
        "winner_sketch": sketches[winner_idx],
        "calibration": "tournament allocates dispatch effort only; every node stays "
                       "OPEN/OPEN_UNFALSIFIED until the kernel dispatch gates judge it",
    }

    if pop is not None:
        # record entrants as attempts (the mutant keeps its parent link), then
        # apply the tournament ranking as an Elo update.
        id_map: dict[int, str] = {}
        existing = {a["sketch_id"]: a["attempt_id"] for a in pop["attempts"]}
        for i, sk in enumerate(sketches):
            if sk["sketch_id"] in existing:  # incumbent re-enters under its old id
                id_map[i] = existing[sk["sketch_id"]]
                continue
            a = sp.record_attempt(pop, sk, parent_id=sk.get("parent_attempt"),
                                  summary=f"tournament entrant ({sk['strategy']}), "
                                          f"judge score {scores[i]['score']}")
            id_map[i] = a["attempt_id"]
        ranking_ids = [[id_map[i] for i in group] for group in ranking]
        sp.update_elo(pop, ranking_ids)
        sp.save_population(pop, population_dir)
        tournament_row = sp.log_tournament(pop["target_hash"], ranking_ids,
                                           id_map[winner_idx], bool(llm_groups),
                                           rater_judgment, population_dir)
        result["population"] = {"path": str(sp.population_path(target_hash, population_dir)),
                                "attempts": len(pop["attempts"]),
                                "winner_attempt": id_map[winner_idx],
                                "tournament_id": tournament_row}
    return result


def write_winner(run_dir: Path, result: dict) -> None:
    """Merge the WINNER's nodes/lemmas into the run's DAG + lemma queue (same
    merge discipline as decompose_problem) and persist the tournament record."""
    winner = result["winner_sketch"]
    dag_path = run_dir / "proof_dependency_dag.json"
    lemma_path = run_dir / "actual_lemma_queue.json"
    dp.dump(dag_path, dp.merge_by_id(dp.records(dag_path), winner.get("nodes") or [], "node_id"))
    lemmas = winner.get("lemmas") or []
    if lemmas:
        dp.dump(lemma_path, dp.merge_by_id(dp.records(lemma_path), lemmas, "lemma_id"))
    slim = {k: v for k, v in result.items() if k != "winner_sketch"}
    dp.dump(run_dir / "sketch_tournament.json", slim)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True)
    ap.add_argument("--lean-target", default=None)
    ap.add_argument("--target-hash", default=None)
    ap.add_argument("--domain", default="general")
    ap.add_argument("--sampler", default=None, help="cmd:CMD LLM decomposition proposer (optional)")
    ap.add_argument("--rater", default=None, help="cmd:CMD LLM comparative rater (optional)")
    ap.add_argument("--population-dir", type=Path, default=None)
    ap.add_argument("--no-population", action="store_true")
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument("--write", action="store_true", help="merge the winner into RUN_DIR's DAG/queue")
    ap.add_argument("--failure-memory", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    failure_memory = witcore.load_json(args.failure_memory, []) if args.failure_memory else None
    result = tournament(args.target, args.lean_target,
                        args.target_hash or sha(args.target), args.domain,
                        sampler=args.sampler, rater=args.rater,
                        population_dir=args.population_dir,
                        use_population=not args.no_population,
                        failure_memory=failure_memory)
    if args.out:
        witcore.save_json(args.out, result)
    if args.write:
        if not args.run_dir:
            print("--write requires --run-dir", file=sys.stderr)
            return 2
        write_winner(args.run_dir, result)
    print(json.dumps({k: v for k, v in result.items() if k != "winner_sketch"},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
