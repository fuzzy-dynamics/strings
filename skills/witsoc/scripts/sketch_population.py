#!/usr/bin/env python3
"""Per-target SKETCH POPULATION: artifact inheritance for decompositions.

The research director (research_state) remembers which APPROACH failed; nothing
remembered the ARTIFACTS. Every new decomposition attempt regenerated from
scratch, so a sketch that closed 3 of 5 nodes was thrown away with its failures.
This is the population database: per frozen-target attempts, each carrying its
sketch (DAG nodes), an end-of-attempt summary, its dispatch outcome, and an Elo
rating updated from sketch-tournament rankings. Parents are selected P-UCB style
(Elo + exploration bonus) and mutated by SMALL DIFFS — drop the node the kernel
refuted, split the conjunctive node, keep what progressed — instead of starting
over.

CALIBRATION: a population entry is an allocation artifact. Every node it stores
must be OPEN/OPEN_UNFALSIFIED (`assert_no_trust`); Elo and selection NEVER touch
a claim's status — trust enters only via the kernel dispatch gates.

State: SQLite at <dir>/populations.sqlite3 (dir defaults to the witsoc home).
Tables: populations (per-target tournament counter), attempts (sketch rows with
Elo/games/outcome), tournaments (ranking history + raw rater judgments). Legacy
<dir>/populations/<target_hash>.json files are read once and migrated on the
next save.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
import goal_structure as gs  # noqa: E402

ALLOWED_STATUS = {None, "", "OPEN", "OPEN_UNFALSIFIED", "DRAFT"}
START_ELO = 1000.0
ELO_K = 32.0
# Worker failure classes that mark a node as a refuted/dead direction worth
# dropping in a child sketch (vs. merely not-yet-closed).
DEAD_FAILURE_CLASSES = {"genuine_mathematical_barrier"}
DEAD_STATUSES = {"REJECTED", "FAILED_ATTEMPT"}
PROGRESS_STATUSES = {"CHECKED", "VERIFIED_LEAN"}

DB_NAME = "populations.sqlite3"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS populations (
    target_hash TEXT PRIMARY KEY,
    tournaments INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS attempts (
    target_hash TEXT NOT NULL,
    attempt_id  TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    sketch_id   TEXT,
    strategy    TEXT,
    parent_id   TEXT,
    nodes       TEXT NOT NULL,
    lemmas      TEXT NOT NULL,
    summary     TEXT,
    mutations   TEXT NOT NULL,
    elo         REAL NOT NULL,
    games       INTEGER NOT NULL,
    outcome     TEXT,
    PRIMARY KEY (target_hash, attempt_id)
);
CREATE TABLE IF NOT EXISTS tournaments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    target_hash      TEXT NOT NULL,
    ranking          TEXT NOT NULL,
    winner_attempt   TEXT,
    llm_ranking_used INTEGER NOT NULL DEFAULT 0,
    rater_judgment   TEXT
);
CREATE INDEX IF NOT EXISTS idx_attempts_hash ON attempts (target_hash, seq);
CREATE INDEX IF NOT EXISTS idx_tournaments_hash ON tournaments (target_hash, id);
"""


def assert_no_trust(nodes: list[dict]) -> None:
    """Structural calibration guard: the population stores PROPOSALS only."""
    for n in nodes:
        if n.get("status") not in ALLOWED_STATUS:
            raise AssertionError(
                f"calibration violation: population node {n.get('node_id')!r} carries "
                f"status {n.get('status')!r}; populations may hold only open proposals")


def population_path(target_hash: str, directory: Path | None = None) -> Path:
    """Path of the population store (one SQLite DB shared by all targets)."""
    base = Path(directory) if directory else witcore.witsoc_home()
    return base / DB_NAME


def _legacy_json_path(target_hash: str, directory: Path | None = None) -> Path:
    base = Path(directory) if directory else witcore.witsoc_home()
    return base / "populations" / f"{target_hash}.json"


def _connect(directory: Path | None = None) -> sqlite3.Connection:
    path = population_path("", directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(_SCHEMA)
    return con


def _row_to_attempt(row: tuple) -> dict:
    (attempt_id, sketch_id, strategy, parent_id, nodes, lemmas,
     summary, mutations, elo, games, outcome) = row
    return {"attempt_id": attempt_id, "sketch_id": sketch_id, "strategy": strategy,
            "parent_id": parent_id, "nodes": json.loads(nodes),
            "lemmas": json.loads(lemmas), "summary": summary,
            "mutations": json.loads(mutations), "elo": elo, "games": games,
            "outcome": json.loads(outcome) if outcome else None}


def load_population(target_hash: str, directory: Path | None = None) -> dict:
    con = _connect(directory)
    try:
        row = con.execute("SELECT tournaments FROM populations WHERE target_hash = ?",
                          (target_hash,)).fetchone()
        if row is None:
            legacy = witcore.load_json(_legacy_json_path(target_hash, directory), None)
            if isinstance(legacy, dict) and legacy.get("schema") == "witsoc.sketch_population.v1":
                return legacy  # migrated into SQLite on the next save
            return {"schema": "witsoc.sketch_population.v1", "target_hash": target_hash,
                    "attempts": [], "tournaments": 0}
        attempts = [_row_to_attempt(r) for r in con.execute(
            "SELECT attempt_id, sketch_id, strategy, parent_id, nodes, lemmas, summary,"
            " mutations, elo, games, outcome FROM attempts WHERE target_hash = ? ORDER BY seq",
            (target_hash,))]
        return {"schema": "witsoc.sketch_population.v1", "target_hash": target_hash,
                "attempts": attempts, "tournaments": row[0]}
    finally:
        con.close()


def save_population(pop: dict, directory: Path | None = None) -> Path:
    con = _connect(directory)
    try:
        h = pop["target_hash"]
        con.execute("INSERT INTO populations (target_hash, tournaments) VALUES (?, ?)"
                    " ON CONFLICT(target_hash) DO UPDATE SET tournaments = excluded.tournaments",
                    (h, pop.get("tournaments", 0)))
        # The in-memory attempts list is authoritative for this target.
        con.execute("DELETE FROM attempts WHERE target_hash = ?", (h,))
        con.executemany(
            "INSERT INTO attempts (target_hash, attempt_id, seq, sketch_id, strategy,"
            " parent_id, nodes, lemmas, summary, mutations, elo, games, outcome)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(h, a["attempt_id"], seq, a.get("sketch_id"), a.get("strategy"),
              a.get("parent_id"), json.dumps(a.get("nodes") or [], ensure_ascii=False),
              json.dumps(a.get("lemmas") or [], ensure_ascii=False), a.get("summary"),
              json.dumps(a.get("mutations") or [], ensure_ascii=False),
              a.get("elo", START_ELO), a.get("games", 0),
              json.dumps(a["outcome"], ensure_ascii=False) if a.get("outcome") else None)
             for seq, a in enumerate(pop.get("attempts") or [])])
        con.commit()
    finally:
        con.close()
    return population_path(pop["target_hash"], directory)


def log_tournament(target_hash: str, ranking: list[list[str]], winner_attempt: str | None,
                   llm_ranking_used: bool, rater_judgment: str | None,
                   directory: Path | None = None) -> int:
    """Append one tournament to the history table; returns its row id."""
    con = _connect(directory)
    try:
        cur = con.execute(
            "INSERT INTO tournaments (target_hash, ranking, winner_attempt,"
            " llm_ranking_used, rater_judgment) VALUES (?, ?, ?, ?, ?)",
            (target_hash, json.dumps(ranking, ensure_ascii=False), winner_attempt,
             int(bool(llm_ranking_used)), rater_judgment))
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def tournament_history(target_hash: str, directory: Path | None = None,
                       limit: int = 20) -> list[dict]:
    con = _connect(directory)
    try:
        return [{"id": rid, "ranking": json.loads(ranking), "winner_attempt": winner,
                 "llm_ranking_used": bool(used), "rater_judgment": judgment}
                for rid, ranking, winner, used, judgment in con.execute(
                    "SELECT id, ranking, winner_attempt, llm_ranking_used, rater_judgment"
                    " FROM tournaments WHERE target_hash = ? ORDER BY id DESC LIMIT ?",
                    (target_hash, limit))]
    finally:
        con.close()


def record_attempt(pop: dict, sketch: dict, parent_id: str | None = None,
                   summary: str | None = None) -> dict:
    """Add a sketch as a population attempt (born at START_ELO, no games)."""
    assert_no_trust(sketch.get("nodes") or [])
    attempt = {
        "attempt_id": f"a{len(pop['attempts']) + 1}",
        "sketch_id": sketch.get("sketch_id") or f"sketch-{len(pop['attempts']) + 1}",
        "strategy": sketch.get("strategy", "unknown"),
        "parent_id": parent_id,
        "nodes": sketch.get("nodes") or [],
        "lemmas": sketch.get("lemmas") or [],
        "summary": summary,
        "mutations": sketch.get("mutations") or [],
        "elo": START_ELO,
        "games": 0,
        "outcome": None,
    }
    pop["attempts"].append(attempt)
    return attempt


def _expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))


def update_elo(pop: dict, ranking: list[list[str]], k: float = ELO_K) -> None:
    """Apply a tournament result: `ranking` is an ordered list of GROUPS of
    attempt_ids, best first; ids in the same group drew. Standard pairwise Elo."""
    by_id = {a["attempt_id"]: a for a in pop["attempts"]}
    flat = [(aid, gi) for gi, group in enumerate(ranking) for aid in group if aid in by_id]
    deltas = {aid: 0.0 for aid, _ in flat}
    for i, (aid, gi) in enumerate(flat):
        for bid, gj in flat[i + 1:]:
            sa = 0.5 if gi == gj else (1.0 if gi < gj else 0.0)
            ea = _expected(by_id[aid]["elo"], by_id[bid]["elo"])
            deltas[aid] += k * (sa - ea)
            deltas[bid] += k * ((1.0 - sa) - (1.0 - ea))
    for aid, d in deltas.items():
        by_id[aid]["elo"] = round(by_id[aid]["elo"] + d, 2)
        by_id[aid]["games"] += len(flat) - 1
    pop["tournaments"] += 1


def record_outcome(pop: dict, attempt_id: str, packets: list[dict]) -> dict | None:
    """Attach a dispatch outcome (worker-result packets) to an attempt: which
    nodes progressed, which died, per-node failure classes. This is the failure
    context the NEXT attempt mutates against."""
    attempt = next((a for a in pop["attempts"] if a["attempt_id"] == attempt_id), None)
    if attempt is None:
        return None
    failed, progressed, statuses = [], [], {}
    for p in packets:
        nid = str(p.get("node_id"))
        statuses[nid] = p.get("status")
        if p.get("status") in PROGRESS_STATUSES:
            progressed.append(nid)
        elif p.get("status") in DEAD_STATUSES or p.get("failure_class") in DEAD_FAILURE_CLASSES:
            failed.append(nid)
    attempt["outcome"] = {"statuses": statuses, "failed_nodes": failed,
                          "progressed_nodes": progressed}
    return attempt["outcome"]


def select_parent(pop: dict, c: float = 80.0) -> dict | None:
    """P-UCB-style parent selection on the Elo scale: rating plus an exploration
    bonus (`c` in Elo units) for under-played attempts. Selection allocates the
    next mutation's parent — it never assigns trust."""
    attempts = pop.get("attempts") or []
    if not attempts:
        return None
    total = sum(a["games"] for a in attempts) + 2
    return max(attempts, key=lambda a: a["elo"] + c * math.sqrt(math.log(total) / (a["games"] + 1)))


def mutate_sketch(attempt: dict, max_drops: int = 2) -> dict:
    """SMALL-DIFF mutation of a parent sketch using its recorded outcome:
      * drop nodes the dispatch marked dead (bounded; never below 2 nodes),
      * split a conjunctive lean_statement into its conjunct nodes,
      * bump the priority of nodes that progressed (keep what worked).
    The child records its parent and the mutation log — the heredity the
    fresh-regeneration flow never had."""
    outcome = attempt.get("outcome") or {}
    dead = set(outcome.get("failed_nodes") or [])
    progressed = set(outcome.get("progressed_nodes") or [])
    nodes = copy.deepcopy(attempt.get("nodes") or [])
    mutations: list[str] = []
    out: list[dict] = []
    drops = 0
    for n in nodes:
        nid = str(n.get("node_id"))
        if nid in dead and drops < max_drops and len(nodes) - drops > 2:
            drops += 1
            mutations.append(f"drop:{nid}")
            continue
        ls = n.get("lean_statement")
        subs = gs.conjunction_split(str(ls)) if ls else []
        if len(subs) >= 2:
            for j, s in enumerate(subs, start=1):
                child = copy.deepcopy(n)
                child["node_id"] = f"{nid}s{j}"
                child["lean_statement"] = s
                child["statement"] = f"{n.get('statement', nid)} (conjunct {j})"
                out.append(child)
            mutations.append(f"split:{nid}->{len(subs)}")
            continue
        if nid in progressed:
            n["priority"] = int(n.get("priority") or 80) + 5
            mutations.append(f"keep+boost:{nid}")
        out.append(n)
    child = {
        "sketch_id": f"{attempt.get('sketch_id', 'sketch')}+m{len(mutations)}",
        "strategy": f"mutated:{attempt.get('strategy', 'unknown')}",
        "nodes": out,
        "lemmas": copy.deepcopy(attempt.get("lemmas") or []),
        "mutations": mutations,
        "parent_attempt": attempt["attempt_id"],
    }
    assert_no_trust(child["nodes"])
    return child


# F2: LLM mutation operators (AlphaEvolve-style). The small-diff mutator above
# explores template-space; these explore PROOF-space — directed rewrites of the
# parent decomposition proposed by the untrusted sampler fleet and validated
# structurally before entering the population. Effort allocation only.
MUTATION_OPERATORS = [
    "strengthen_node: replace one node's statement with a stronger intermediate invariant that would make its proof routine",
    "replace_node_strategy: keep a failed node's goal but attack it via a different method family (induction/extremal/algebraic/probabilistic/reduction)",
    "import_technique: rewrite one node to apply a suggested technique from the atlas to this goal",
    "add_bridge_lemma: insert one new node supplying the missing bridge between a progressed node and a failed one",
    "drop_and_reroute: remove a dead node and reroute its dependents through an alternative decomposition step",
]


def select_inspiration(pop: dict, exclude_strategy: str | None) -> dict | None:
    """A second, structurally DIFFERENT parent for cross-pollination (the
    AlphaProof-Nexus inspiration-sampling pattern): the highest-Elo attempt
    whose strategy differs from the mutation parent's. Attention only."""
    attempts = pop.get("attempts") or []
    if isinstance(attempts, dict):
        attempts = list(attempts.values())
    best = None
    for a in attempts:
        if exclude_strategy and a.get("strategy") == exclude_strategy:
            continue
        if best is None or float(a.get("elo") or 0) > float(best.get("elo") or 0):
            best = a
    return best


def llm_mutants(attempt: dict, target: str, lean_target: str | None, domain: str,
                limit: int = 2, technique_hints: list[dict] | None = None,
                theory: dict | None = None, inspiration: dict | None = None) -> list[dict]:
    """Ask the sampler fleet for operator-directed mutations of a parent sketch.
    Every proposal is validated like sketch_llm output: statements required,
    FORBIDDEN_LEAN screened, status forced OPEN, then assert_no_trust. Invalid
    or absent replies contribute nothing. Returns up to `limit` children."""
    import hashlib
    import sampler_fleet as sf
    try:
        from domain_barrier_lemmas import FORBIDDEN_LEAN
    except Exception:
        FORBIDDEN_LEAN = ("sorry", "admit", "axiom ")
    if not sf.samplers():
        return []
    hints = technique_hints
    if hints is None:
        try:
            from analogical_transfer import suggest
            hints = [{"technique": h.get("technique"), "construction": h.get("construction")}
                     for h in suggest(lean_target or target, domain, k=3)]
        except Exception:
            hints = []
    outcome = attempt.get("outcome") or {}
    request = {
        "task": "mutate_decomposition",
        "target": target, "lean_target": lean_target, "domain": domain,
        "problem_theory": theory or {},
        "operators": MUTATION_OPERATORS,
        "parent": {"strategy": attempt.get("strategy"),
                   "nodes": [{k: n.get(k) for k in ("node_id", "statement", "lean_statement", "type")}
                             for n in attempt.get("nodes") or []],
                   "failed_nodes": outcome.get("failed_nodes") or [],
                   "progressed_nodes": outcome.get("progressed_nodes") or [],
                   "prior_mutations": attempt.get("mutations") or []},
        "technique_suggestions": hints,
        "inspiration": ({"strategy": inspiration.get("strategy"),
                         "nodes": [{k: n.get(k) for k in ("statement", "type")}
                                   for n in (inspiration.get("nodes") or [])[:6]],
                         "note": "a structurally different high-rated sketch — graft its ideas "
                                 "into the parent where they fit; do not copy it wholesale"}
                        if inspiration else None),
        "rules": "Apply EXACTLY ONE operator. Return {operator, mutations: [what changed], nodes: "
                 "[{node_id?, statement, kind?, lean_statement?}]} — the FULL mutated node list, "
                 "2-12 nodes, one reasoning step per node; lean_statement only when safely "
                 "formalizable, else null. Never weaken or change the target.",
    }
    children: list[dict] = []
    for result in sf.sample(request, per_sampler=1):
        reply = result["reply"]
        raw_nodes = reply.get("nodes") or []
        nodes = []
        for i, n in enumerate(raw_nodes, start=1):
            if not (isinstance(n, dict) and n.get("statement")):
                continue
            lean = n.get("lean_statement")
            if lean and any(t in str(lean) for t in FORBIDDEN_LEAN):
                lean = None  # never accept a proposed Lean goal smuggling a proof hole
            nid = str(n.get("node_id") or f"LM{i}")
            nodes.append({"node_id": nid, "statement": str(n["statement"]),
                          "type": str(n.get("kind") or "lemma"), "lean_statement": lean,
                          "status": "OPEN",
                          "target_hash": hashlib.sha256(str(n["statement"]).encode()).hexdigest(),
                          "dependencies": ["T"], "dependency_path_to_target": [nid, "T"],
                          "priority": 76 - i, "source": f"llm-mutation:{result['sampler_id']}"})
        if not 2 <= len(nodes) <= 12:
            continue
        child = {
            "sketch_id": f"{attempt.get('sketch_id', 'sketch')}+llm:{result['sampler_id']}",
            "strategy": f"llm-mutated:{reply.get('operator') or 'unspecified'}",
            "nodes": nodes,
            "lemmas": copy.deepcopy(attempt.get("lemmas") or []),
            "mutations": [f"llm:{m}" for m in (reply.get("mutations") or ["unspecified"])],
            "parent_attempt": attempt.get("attempt_id"),
        }
        try:
            assert_no_trust(child["nodes"])
        except AssertionError:
            continue
        children.append(child)
        if len(children) >= limit:
            break
    return children


def prior_context(pop: dict, k: int = 3) -> list[dict]:
    """Compact prior-attempt context for proposers (LLM samplers / raters):
    what was tried, how it rated, and where it failed."""
    ranked = sorted(pop.get("attempts") or [], key=lambda a: -a["elo"])[:k]
    return [{"attempt_id": a["attempt_id"], "strategy": a["strategy"], "elo": a["elo"],
             "summary": a.get("summary"),
             "failed_nodes": (a.get("outcome") or {}).get("failed_nodes") or [],
             "progressed_nodes": (a.get("outcome") or {}).get("progressed_nodes") or []}
            for a in ranked]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target-hash", required=True)
    ap.add_argument("--dir", type=Path, default=None, help="population base dir (default: witsoc home)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    p_hist = sub.add_parser("history")
    p_hist.add_argument("--limit", type=int, default=20)
    p_sel = sub.add_parser("select")
    p_sel.add_argument("--c", type=float, default=80.0)
    p_mut = sub.add_parser("mutate")
    p_mut.add_argument("--attempt", default=None, help="attempt_id (default: P-UCB-selected parent)")
    p_out = sub.add_parser("record-outcome")
    p_out.add_argument("--attempt", required=True)
    p_out.add_argument("--worker-results", type=Path, required=True)
    args = ap.parse_args()

    pop = load_population(args.target_hash, args.dir)
    if args.cmd == "show":
        print(json.dumps({"target_hash": pop["target_hash"], "tournaments": pop["tournaments"],
                          "attempts": prior_context(pop, k=len(pop["attempts"]) or 1)},
                         indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "history":
        print(json.dumps(tournament_history(args.target_hash, args.dir, args.limit),
                         indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "select":
        parent = select_parent(pop, args.c)
        print(json.dumps({"selected": parent and parent["attempt_id"],
                          "elo": parent and parent["elo"]}, indent=2))
        return 0
    if args.cmd == "mutate":
        parent = (next((a for a in pop["attempts"] if a["attempt_id"] == args.attempt), None)
                  if args.attempt else select_parent(pop))
        if parent is None:
            print(json.dumps({"error": "no parent attempt found"}))
            return 1
        child = mutate_sketch(parent)
        print(json.dumps(child, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "record-outcome":
        packets = witcore.load_json(args.worker_results, [])
        outcome = record_outcome(pop, args.attempt, packets if isinstance(packets, list) else [])
        save_population(pop, args.dir)
        print(json.dumps({"attempt": args.attempt, "outcome": outcome}, indent=2, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
