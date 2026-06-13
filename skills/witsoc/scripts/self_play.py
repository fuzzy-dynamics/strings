#!/usr/bin/env python3
"""Ω5+Ω9 self-play — `witsoc self-play`.

Two coupled games, both grounded in the kernel:

  frontier-round (Ω5, the STP lesson): the conjecturer is most useful when it
    generates statements at the prover's FRONTIER — "barely provable". Each
    round: generate candidates (pose_variants structural moves + the fleet,
    prompted with the current solve-rate band and examples of barely-solved
    statements), prove each at light tier, and record outcomes per goal
    signature in the knowledge store. The band statistics steer the next
    round toward the 30–70% solve-rate edge; everything proved harvests into
    the library and proof bank (the curriculum climbs instead of scattering).

  game (Ω9, the adversarial-formalization suggestion from the Buzzard/
    Kontorovich/Lauter panel): PROVER vs ATTACKER on generated statements —
    the prover formalizes-and-proves, the attacker runs kernel-gated instance
    refutation (lemma_repair.falsify) against the statement. A refuted
    statement is the attacker's win (discarded, witnesses recorded); a proved
    survivor is a verified (goal, proof) pair banked as synthetic Lean corpus
    for prompts and expert iteration.

Trust: candidates are OPEN until the kernel speaks; refutations and proofs
are both kernel verdicts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

FORBIDDEN = ("sorry", "admit", "axiom")
FRONTIER_LOW, FRONTIER_HIGH = 0.3, 0.7


def _frontier_table():
    import knowledge_store as ks
    con = ks.connect()
    con.execute("CREATE TABLE IF NOT EXISTS frontier ("
                " signature TEXT PRIMARY KEY, attempts INTEGER, solved INTEGER, updated INTEGER)")
    return con


def _record_outcome(goal: str, solved: bool) -> None:
    import knowledge_store as ks
    con = _frontier_table()
    sig = ks.goal_signature(goal)
    con.execute("INSERT INTO frontier (signature, attempts, solved, updated) VALUES (?,?,?,?)"
                " ON CONFLICT(signature) DO UPDATE SET attempts = attempts + 1,"
                " solved = solved + excluded.solved, updated = excluded.updated",
                (sig, 1, int(solved), int(time.time())))
    con.commit()
    con.close()


def band_stats() -> dict:
    con = _frontier_table()
    rows = con.execute("SELECT attempts, solved FROM frontier").fetchall()
    con.close()
    attempts = sum(a for a, _ in rows)
    solved = sum(s for _, s in rows)
    rate = round(solved / attempts, 3) if attempts else None
    return {"signatures": len(rows), "attempts": attempts, "solved": solved, "solve_rate": rate,
            "frontier_band": [FRONTIER_LOW, FRONTIER_HIGH],
            "steer": ("harder" if rate is not None and rate > FRONTIER_HIGH else
                      "easier" if rate is not None and rate < FRONTIER_LOW else "hold")}


def _structural_candidates(seed: str, bound: int) -> list[str]:
    try:
        import pose_variants as pv
        doc = pv.generate(seed, bound=bound)
        out = []
        for bucket in ("weaker", "stronger", "boundary"):
            for v in doc.get(bucket, []) or []:
                lean = v.get("lean_statement")
                if lean and not any(t in lean for t in FORBIDDEN):
                    out.append(str(lean))
        return out
    except Exception:
        return []


def _fleet_candidates(seed: str, stats: dict, barely_solved: list[dict], n: int) -> list[str]:
    import sampler_fleet as sf
    out: list[str] = []
    for result in sf.sample({
        "task": "pose_frontier_conjectures",
        "seed_statement": seed,
        "band_stats": stats,
        "barely_solved_examples": barely_solved[:4],
        "count": n,
        "rules": "Return {conjectures: [Lean 4 Prop strings]} — variants of the seed at the "
                 "prover's FRONTIER (the band stats say whether to go harder or easier). "
                 "True-looking, decidable-leaning, one idea each. Never sorry/admit/axiom.",
    }, per_sampler=1):
        for c in result["reply"].get("conjectures", []) or []:
            c = re.sub(r"\s+", " ", str(c)).strip()
            if c and not any(t in c for t in FORBIDDEN) and c not in out:
                out.append(c)
    return out[:n]


def frontier_round(seed: str, *, n: int = 6, bound: int = 24, tier: str = "light") -> dict:
    import prover_tiers
    import proof_bank
    stats = band_stats()
    barely = []
    try:
        barely = proof_bank.examples_for(seed, k=4)
    except Exception:
        pass
    candidates = _structural_candidates(seed, bound) + _fleet_candidates(seed, stats, barely, n)
    seen: list[str] = []
    rows = []
    for goal in candidates:
        if goal in seen or len(rows) >= n:
            continue
        seen.append(goal)
        record = prover_tiers.prove(goal, tier=tier, name="frontier")
        solved = bool(record.get("discharged"))
        _record_outcome(goal, solved)
        if solved:
            try:
                proof_bank.bank(goal, str(record["proof"]))
            except Exception:
                pass
        rows.append({"goal": goal[:100], "solved": solved,
                     "via": record.get("via"), "label": record.get("label")})
    return {"schema": "witsoc.frontier_round.v1", "seed": seed,
            "band_before": stats, "band_after": band_stats(),
            "candidates": len(rows), "solved": sum(1 for r in rows if r["solved"]),
            "rows": rows,
            "note": "proved candidates banked + harvested; the band steers the next round"}


def game(seed: str, *, rounds: int = 4, bound: int = 24, instance_bound: int = 8) -> dict:
    """PROVER vs ATTACKER: each candidate first faces the attacker's
    kernel-gated instance refutation; survivors face the prover. Both sides'
    verdicts are kernel verdicts; survivors' proofs become banked corpus."""
    import lemma_repair as lr
    import prover_tiers
    import proof_bank
    candidates = (_structural_candidates(seed, bound)
                  + _fleet_candidates(seed, band_stats(), [], rounds))[: rounds * 2]
    attacker_wins, prover_wins, undecided = [], [], 0
    for goal in candidates[:rounds * 2]:
        parsed = lr.parse_wish(goal)
        if parsed:
            fal = lr.falsify(parsed["body"], parsed["var"], list(range(instance_bound + 1)), "", None)
            if fal.get("witnesses"):
                attacker_wins.append({"goal": goal[:100], "witnesses": fal["witnesses"][:3]})
                continue
        record = prover_tiers.prove(goal, tier="light", name="game")
        if record.get("discharged"):
            try:
                proof_bank.bank(goal, str(record["proof"]))
            except Exception:
                pass
            prover_wins.append({"goal": goal[:100], "proof": record["proof"][:80]})
        else:
            undecided += 1
    return {"schema": "witsoc.formalization_game.v1", "seed": seed,
            "attacker_wins": attacker_wins, "prover_wins": prover_wins,
            "undecided": undecided,
            "corpus_added": len(prover_wins),
            "note": ("survivors are verified (goal, proof) corpus in the bank; refuted candidates "
                     "are recorded negative knowledge — both sides are kernel verdicts")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_f = sub.add_parser("frontier-round")
    p_f.add_argument("--seed", required=True, help="Lean statement to vary around")
    p_f.add_argument("-n", type=int, default=6)
    p_f.add_argument("--tier", choices=("light", "medium", "heavy"), default="light")
    p_g = sub.add_parser("game")
    p_g.add_argument("--seed", required=True)
    p_g.add_argument("--rounds", type=int, default=4)
    sub.add_parser("band")
    args = ap.parse_args()
    if args.cmd == "frontier-round":
        result = frontier_round(args.seed, n=args.n, tier=args.tier)
    elif args.cmd == "game":
        result = game(args.seed, rounds=args.rounds)
    else:
        result = band_stats()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
