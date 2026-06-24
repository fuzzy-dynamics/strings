#!/usr/bin/env python3
"""Ω2 lemma pool — `witsoc pool`.

Seed-Prover's core paradigm (99.6% miniF2F, 331 Putnam problems): proving is
LEMMA-STYLE — a dynamic pool of proposed bridging lemmas evolves across
attempts; proved ones are cached and REUSED everywhere, intractable ones are
abandoned with their evidence, and failed proof attempts are the main source
of new proposals. Witsoc had the storage (the library) and the loops (Nexus,
dispatch); the pool makes them one compounding object per campaign:

  propose        add a candidate lemma (origin: a node's failure, a fleet
                 idea, residual-goal mining, a human) — deduped by statement
  mine           Prover-Agent's trick, kernel-grounded: probe a hard goal
                 with structural openers (intro/constructor/cases), parse the
                 REAL Lean "unsolved goals ⊢ ..." diagnostics, and propose
                 each residual goal as a bridging lemma
  prove-pending  budgeted pass over PROPOSED entries through the in-process
                 prover (Nexus fleet optional): PROVED entries harvest into
                 the global library (so every later close_goal --use-library
                 sees them) and join prompts; entries failing
                 `abandon_after` attempts become INTRACTABLE with evidence
  status         the pool scoreboard

Trust: pool statuses are workflow states; PROVED means a kernel verdict
(close_goal), nothing less. The driver runs mine + prove-pending each loop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

POOL_NAME = "lemma_pool.json"
ABANDON_AFTER = 3
_UNSOLVED_RE = re.compile(r"unsolved goals\s*\n(.*?)(?:\n\n|\Z)", re.DOTALL)
_GOAL_LINE_RE = re.compile(r"⊢\s*(.+)")
FORBIDDEN = ("sorry", "admit", "axiom")
OPENERS = ("intro", "intros", "constructor", "intro n", "intro x h", "refine ⟨?_, ?_⟩")


def pool_path(run: Path) -> Path:
    return run / POOL_NAME


def load_pool(run: Path) -> dict:
    data = witcore.load_json(pool_path(run), None)
    if isinstance(data, dict) and data.get("schema") == "witsoc.lemma_pool.v1":
        return data
    return {"schema": "witsoc.lemma_pool.v1", "run_dir": str(run), "lemmas": {}}


def save_pool(run: Path, pool: dict) -> None:
    witcore.save_json(pool_path(run), pool)


def _lemma_id(statement: str) -> str:
    return "lp_" + hashlib.sha256(statement.encode("utf-8")).hexdigest()[:12]


def propose(run: Path, statement: str, origin: str, imports: str = "") -> dict:
    statement = re.sub(r"\s+", " ", statement).strip()
    if not statement or any(t in statement for t in FORBIDDEN):
        return {"proposed": False, "reason": "empty or forbidden-token statement"}
    pool = load_pool(run)
    lid = _lemma_id(statement)
    if lid in pool["lemmas"]:
        entry = pool["lemmas"][lid]
        if origin not in entry["origins"]:
            entry["origins"].append(origin)
        save_pool(run, pool)
        return {"proposed": False, "reason": "duplicate", "lemma_id": lid,
                "status": entry["status"]}
    pool["lemmas"][lid] = {"lemma_id": lid, "statement": statement, "imports": imports,
                           "origins": [origin], "status": "PROPOSED",
                           "attempts": 0, "proof": None, "last_failure": None, "uses": 0}
    save_pool(run, pool)
    return {"proposed": True, "lemma_id": lid}


def mine_residual_goals(goal: str, imports: str = "", lake_dir: Path | None = None,
                        max_probes: int = 4) -> list[str]:
    """Kernel-grounded bridging-lemma mining: apply structural openers to the
    goal, read the REAL compiler's residual `⊢` goals, and return each as a
    candidate lemma statement. The probe build is expected to fail — the
    diagnostics are the product."""
    import close_obligation as co
    residuals: list[str] = []
    for opener in OPENERS[:max_probes]:
        src = co.lean_source("pool_probe", goal, imports, f"by {opener}")
        with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as fh:
            fh.write(src)
            tmp = Path(fh.name)
        try:
            verdict = witcore.lean_verify(tmp, lake_dir)
        finally:
            tmp.unlink(missing_ok=True)
        build = verdict.get("build", {}) or {}
        blob = str(build.get("stdout", "")) + "\n" + str(build.get("stderr", ""))
        for block in _UNSOLVED_RE.findall(blob):
            for m in _GOAL_LINE_RE.finditer(block):
                residual = re.sub(r"\s+", " ", m.group(1)).strip()
                # a residual identical to the goal teaches nothing
                if residual and residual not in residuals and residual not in goal:
                    residuals.append(residual)
    return residuals[:6]


def mine_into_pool(run: Path, goal: str, origin_node: str, imports: str = "",
                   lake_dir: Path | None = None) -> dict:
    residuals = mine_residual_goals(goal, imports, lake_dir)
    proposed = 0
    for r in residuals:
        # residual goals are open-term contexts; close over obvious free nat vars
        statement = r if r.startswith("∀") else f"∀ n : Nat, {r}" if re.search(r"\bn\b", r) else r
        out = propose(run, statement, origin=f"residual_of:{origin_node}", imports=imports)
        proposed += int(bool(out.get("proposed")))
    return {"mined": len(residuals), "proposed": proposed, "residuals": residuals}


def prove_pending(run: Path, limit: int = 4, search: bool = False,
                  use_nexus: bool = False, lake_dir: Path | None = None) -> dict:
    pool = load_pool(run)
    import close_obligation as co
    theory_ctx = None
    try:
        import problem_theory as pt
        if pt.theory_path(run).exists():
            theory_ctx = pt.prompt_context(run)
    except Exception:
        pass
    attempted, proved, abandoned = 0, [], []
    pending = sorted((e for e in pool["lemmas"].values() if e["status"] == "PROPOSED"),
                     key=lambda e: e["attempts"])
    for entry in pending:
        if attempted >= limit:
            break
        attempted += 1
        entry["attempts"] += 1
        result = co.close_goal(entry["statement"], name=f"pool_{entry['lemma_id']}",
                               imports=entry.get("imports") or "", search=search,
                               lake_dir=lake_dir, record_library=True)
        if not result.get("discharged") and use_nexus:
            try:
                import nexus_loop as nx
                fr = nx.fleet_prove(entry["statement"], imports=entry.get("imports") or "",
                                    theory=theory_ctx, deterministic_first=False)
                if fr.get("discharged"):
                    result = {"discharged": True, "proof": fr["proof"], "label": "PROOF_DISCHARGED"}
            except Exception:
                pass
        if result.get("discharged"):
            entry["status"] = "PROVED"
            entry["proof"] = result.get("proof")
            proved.append(entry["lemma_id"])
            try:
                import proof_bank
                banked = proof_bank.bank(entry["statement"], str(entry["proof"]),
                                         entry.get("imports") or "", lake_dir)
                if banked.get("compressed"):
                    entry["proof"] = banked["proof"]  # keep the simplified form
            except Exception:
                pass
        else:
            entry["last_failure"] = result.get("label")
            if entry["attempts"] >= ABANDON_AFTER:
                entry["status"] = "INTRACTABLE"
                abandoned.append(entry["lemma_id"])
    save_pool(run, pool)
    return {"attempted": attempted, "proved": proved, "abandoned": abandoned, **stats(pool)}


def proved_statements(run: Path, k: int = 8) -> list[dict]:
    """The reuse surface: PROVED pool lemmas for prompts and premises (the
    library harvest already feeds close_goal --use-library)."""
    pool = load_pool(run)
    rows = [e for e in pool["lemmas"].values() if e["status"] == "PROVED"]
    rows.sort(key=lambda e: -e["uses"])
    return [{"statement": e["statement"], "proof": e["proof"]} for e in rows[:k]]


def stats(pool: dict) -> dict:
    counts: dict[str, int] = {}
    for e in pool["lemmas"].values():
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    return {"pool_size": len(pool["lemmas"]), "by_status": counts}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_p = sub.add_parser("propose")
    p_p.add_argument("run_dir", type=Path)
    p_p.add_argument("--statement", required=True)
    p_p.add_argument("--origin", default="manual")
    p_p.add_argument("--imports", default="")
    p_m = sub.add_parser("mine")
    p_m.add_argument("run_dir", type=Path)
    p_m.add_argument("--goal", required=True)
    p_m.add_argument("--origin-node", default="manual")
    p_m.add_argument("--imports", default="")
    p_v = sub.add_parser("prove-pending")
    p_v.add_argument("run_dir", type=Path)
    p_v.add_argument("--limit", type=int, default=4)
    p_v.add_argument("--search", action="store_true")
    p_v.add_argument("--nexus", action="store_true")
    p_s = sub.add_parser("status")
    p_s.add_argument("run_dir", type=Path)
    args = ap.parse_args()

    if args.cmd == "propose":
        result: Any = propose(args.run_dir, args.statement, args.origin, args.imports)
    elif args.cmd == "mine":
        result = mine_into_pool(args.run_dir, args.goal, args.origin_node, args.imports)
    elif args.cmd == "prove-pending":
        result = prove_pending(args.run_dir, args.limit, args.search, args.nexus)
    else:
        pool = load_pool(args.run_dir)
        result = {**stats(pool),
                  "proved": [e["statement"] for e in pool["lemmas"].values()
                             if e["status"] == "PROVED"][:10],
                  "intractable": [e["statement"] for e in pool["lemmas"].values()
                                  if e["status"] == "INTRACTABLE"][:5]}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
