#!/usr/bin/env python3
"""P2 decision ledger + option tables — `witsoc decide`.

Options-not-orders, made executable. Strategy choices belong to the agent;
this module makes each choice INFORMED and makes the system LEARN from it:

  options   assemble a live option table for a decision point: candidate
            techniques (analogical transfer), historical mean reward for this
            goal signature (L5 priors), known failures that match (L4 global
            failure memory), and this decision point's own track record —
            with a recommended default so an undecided agent still moves.
  record    log the choice (options considered, chosen, reason) -> decision id.
  resolve   attach the outcome later; reward feeds the L5 priors, so future
            option tables rank by what actually worked, not by static prose.
  stats     win rates per decision point / per chosen option.

Attention machinery only: a decision record never upgrades a status, and the
recommended default is advice — departing from it is legitimate and exactly
what the ledger is for. Contracts (claim acceptance, freeze, sentinels) are
never decision points.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import knowledge_store as ks  # noqa: E402

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
  did TEXT PRIMARY KEY, run_dir TEXT, decision_point TEXT, statement TEXT,
  options TEXT, chosen TEXT, reason TEXT, outcome TEXT, reward REAL,
  created INTEGER, resolved INTEGER);
"""


def _connect():
    con = ks.connect()
    con.executescript(_SCHEMA)
    return con


# --- the option table -------------------------------------------------------------
def _applicability(s: dict) -> str:
    """Compose a human-readable applicability note from the fields the technique
    suggester returns (construction = what it does, matched_concepts = why it fit
    here, unlocks = when it pays). Falls back to any explicit field."""
    explicit = s.get("why") or s.get("applicability")
    if explicit:
        return str(explicit)
    parts: list[str] = []
    if s.get("construction"):
        parts.append(str(s["construction"]))
    matched = s.get("matched_concepts") or []
    if matched:
        parts.append("fits here via: " + ", ".join(map(str, matched)))
    unlocks = s.get("unlocks") or []
    if unlocks:
        parts.append("unlocks: " + ", ".join(map(str, unlocks)))
    return " — ".join(parts)


def option_table(statement: str, domain: str = "", decision_point: str = "technique",
                 k: int = 4) -> dict:
    """A live decision-support table: candidates with applicability, evidence,
    and a recommended default. Evidence is drawn from the real stores at call
    time — never from static doctrine prose."""
    # Infer the domain from the statement when the caller did not pin one, so the
    # suggester matches domain-appropriate techniques (consistency with ideate).
    if domain in ("", "other"):
        try:
            import ontology_pivot as _op
            domain = _op.infer_domain(statement)
        except Exception:
            pass

    candidates: list[dict] = []
    try:
        import analogical_transfer as at
        for s in at.suggest(statement, domain, k):
            matched = s.get("matched_concepts") or []
            # Atlas-harvested tactic moves match only the generic 'g:other'
            # bucket and carry a raw Lean proof skeleton; flag them so they read
            # as generic and never out-rank a domain-matched research technique.
            generic = bool(matched) and all(str(m).startswith("g:") for m in matched)
            candidates.append({
                "candidate": s.get("technique"),
                # the suggester does not emit a `why`; build applicability from
                # the fields it DOES return so the option is not content-free.
                "applicability": _applicability(s),
                "source": "grown_atlas" if generic else "kb_analogy",
                "generic": generic,
                "evidence": {"relevance": s.get("relevance"),
                             "matched_concepts": matched,
                             "unlocks": s.get("unlocks") or []},
                "status": s.get("status"),
            })
    except Exception:
        pass

    priors = ks.priors_for(statement)
    for c in candidates:
        if c["candidate"] in priors:
            c["evidence"]["prior_mean_reward"] = priors[c["candidate"]]
    # priors may know approaches the suggester did not surface
    for approach, reward in sorted(priors.items(), key=lambda kv: -kv[1])[:k]:
        if not any(c["candidate"] == approach for c in candidates):
            candidates.append({"candidate": approach,
                               "applicability": "informed prior: this goal signature responded to it before",
                               "evidence": {"prior_mean_reward": reward}})

    warnings = ks.query_failures(statement)
    for c in candidates:
        hits = [w for w in warnings if w.get("method") and w["method"].lower() in str(c["candidate"]).lower()]
        if hits:
            c["evidence"]["failure_warnings"] = [
                {"blocker": h["blocker"], "do_not_repeat": h["do_not_repeat"]} for h in hits[:2]]

    # this decision point's own track record (the learning loop closing)
    con = _connect()
    rows = con.execute(
        "SELECT chosen, COUNT(*), AVG(COALESCE(reward, 0)) FROM decisions"
        " WHERE decision_point = ? AND resolved IS NOT NULL GROUP BY chosen",
        (decision_point,)).fetchall()
    con.close()
    track = {chosen: {"resolved": n, "mean_reward": round(r or 0.0, 3)} for chosen, n, r in rows}
    for c in candidates:
        if c["candidate"] in track:
            c["evidence"]["decision_track_record"] = track[c["candidate"]]

    def score(c: dict) -> float:
        ev = c["evidence"]
        s = float(ev.get("relevance") or 0.0)
        s += 2.0 * float(ev.get("prior_mean_reward") or 0.0)
        s += float(ev.get("decision_track_record", {}).get("mean_reward") or 0.0)
        s -= 0.5 * len(ev.get("failure_warnings") or [])
        return s

    # A generic atlas tactic-move is a kernel-harvested FALLBACK, not a research
    # strategy, and its relevance is scored on a different (inflated) scale than
    # the domain-matched KB techniques — so rank all non-generic candidates
    # strictly ahead of generic ones, then by score within each band.
    candidates.sort(key=lambda c: (0 if c.get("generic") else 1, score(c)), reverse=True)
    for i, c in enumerate(candidates):
        c["recommended_default"] = i == 0
    return {
        "schema": "witsoc.option_table.v1",
        "decision_point": decision_point,
        "statement": statement,
        "options": candidates[:max(2, k)],
        "calibration": ("candidates and the default are ADVICE assembled from live stores; "
                        "the agent chooses and records the choice (witsoc decide record). "
                        "Contracts are never decision points."),
    }


# --- the ledger --------------------------------------------------------------------
def record(decision_point: str, statement: str, options: list[str], chosen: str,
           reason: str, run_dir: str = "") -> dict:
    did = hashlib.sha256(f"{decision_point}|{statement}|{chosen}|{time.time()}"
                         .encode("utf-8")).hexdigest()[:12]
    con = _connect()
    con.execute("INSERT INTO decisions (did, run_dir, decision_point, statement, options,"
                " chosen, reason, created) VALUES (?,?,?,?,?,?,?,?)",
                (did, run_dir, decision_point, statement,
                 json.dumps(options, ensure_ascii=False), chosen, reason, int(time.time())))
    con.commit()
    con.close()
    return {"did": did, "decision_point": decision_point, "chosen": chosen}


def resolve(did: str, outcome: str, reward: float) -> dict:
    con = _connect()
    row = con.execute("SELECT statement, chosen FROM decisions WHERE did = ?", (did,)).fetchone()
    if not row:
        con.close()
        return {"ok": False, "error": f"unknown decision id {did!r}"}
    con.execute("UPDATE decisions SET outcome = ?, reward = ?, resolved = ? WHERE did = ?",
                (outcome, float(reward), int(time.time()), did))
    con.commit()
    con.close()
    # feed the L5 priors: the chosen approach earned this reward on this goal
    ks.record_outcome(row[0], row[1], float(reward))
    return {"ok": True, "did": did, "outcome": outcome, "reward": reward,
            "priors_updated": True}


def stats(decision_point: str | None = None) -> dict:
    con = _connect()
    where, params = ("WHERE decision_point = ?", (decision_point,)) if decision_point else ("", ())
    total = con.execute(f"SELECT COUNT(*) FROM decisions {where}", params).fetchone()[0]
    resolved = con.execute(
        f"SELECT COUNT(*) FROM decisions {where}{' AND' if where else ' WHERE'} resolved IS NOT NULL",
        params).fetchone()[0]
    by_point = dict(con.execute(
        "SELECT decision_point, COUNT(*) FROM decisions GROUP BY decision_point"))
    con.close()
    return {"decisions": total, "resolved": resolved, "unresolved": total - resolved,
            "by_decision_point": by_point}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_opt = sub.add_parser("options")
    p_opt.add_argument("--statement", required=True)
    p_opt.add_argument("--domain", default="")
    p_opt.add_argument("--decision-point", default="technique")
    p_opt.add_argument("-k", type=int, default=4)
    p_rec = sub.add_parser("record")
    p_rec.add_argument("--decision-point", required=True)
    p_rec.add_argument("--statement", required=True)
    p_rec.add_argument("--option", action="append", default=[], help="an option considered (repeatable)")
    p_rec.add_argument("--chosen", required=True)
    p_rec.add_argument("--reason", required=True)
    p_rec.add_argument("--run-dir", default="")
    p_res = sub.add_parser("resolve")
    p_res.add_argument("--did", required=True)
    p_res.add_argument("--outcome", required=True)
    p_res.add_argument("--reward", type=float, required=True,
                       help="1.0 closed/advanced, 0 no effect, negative for wasted budget")
    p_st = sub.add_parser("stats")
    p_st.add_argument("--decision-point", default=None)
    args = ap.parse_args()

    if args.cmd == "options":
        result = option_table(args.statement, args.domain, args.decision_point, args.k)
    elif args.cmd == "record":
        result = record(args.decision_point, args.statement, args.option, args.chosen,
                        args.reason, args.run_dir)
    elif args.cmd == "resolve":
        result = resolve(args.did, args.outcome, args.reward)
        if not result.get("ok"):
            print(json.dumps(result, ensure_ascii=False))
            return 1
    else:
        result = stats(args.decision_point)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
