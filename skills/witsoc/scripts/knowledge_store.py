#!/usr/bin/env python3
"""R4 knowledge substrate — `witsoc memory`.

The single cross-run store at `~/.witsoc/knowledge.sqlite3`, delivering the
two pieces of the original roadmap that were doc-only until now:

  L4 GLOBAL FAILURE MEMORY — per-run `lovasz.soc` failures used to die with
  the run; `sync-run` lifts them into the global table, and
  `query` (token-overlap matching, same semantics as the per-run `.soc`
  check) lets any future run see that an approach already failed elsewhere.
  lovasz_worker_dispatch consults it automatically alongside the local soc.

  L5 BANDIT PRIORS BY GOAL SIGNATURE — campaign outcomes are recorded per
  (goal signature, approach); a new target with a familiar structure starts
  from informed priors instead of uniform. engine_dispatch reads/writes this
  automatically inside campaigns.

Both are ATTENTION machinery: a prior or a failure match changes what gets
tried first, never what counts as proved.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

_SCHEMA = """
CREATE TABLE IF NOT EXISTS failures (
  fid TEXT, run_dir TEXT, method TEXT, statement TEXT, blocker TEXT,
  do_not_repeat TEXT, created INTEGER, PRIMARY KEY (fid, run_dir));
CREATE TABLE IF NOT EXISTS priors (
  goal_signature TEXT, approach TEXT, tries INTEGER, reward REAL,
  PRIMARY KEY (goal_signature, approach));
CREATE TABLE IF NOT EXISTS memory_flow (
  kind TEXT PRIMARY KEY, count INTEGER);
"""


def store_path() -> Path:
    return witcore.witsoc_home() / "knowledge.sqlite3"


def connect() -> sqlite3.Connection:
    store_path().parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(store_path())
    con.executescript(_SCHEMA)
    return con


def goal_signature(target: str) -> str:
    try:
        from value_function import featurize_goal
        sig = ",".join(sorted(featurize_goal(target)))
    except Exception:
        sig = " ".join(sorted(set(re.findall(r"[a-zA-Z0-9_]+", target.lower()))))
    import hashlib
    return hashlib.sha256(sig.encode("utf-8")).hexdigest()[:16]


# --- L4: global failure memory ---------------------------------------------------
def sync_run(run: Path) -> dict:
    """Lift a run's failure memory (lovasz.soc + failure_memory.jsonl) into the
    global store. Idempotent: (fid, run_dir) is the key."""
    con = connect()
    now = int(time.time())
    count = 0
    soc = run / "lovasz.soc"
    if soc.exists():
        try:
            from lovasz_soc_memory import parse_failed_entries
            for f in parse_failed_entries(soc.read_text(encoding="utf-8")):
                if not f.get("id"):
                    continue
                con.execute("INSERT OR REPLACE INTO failures (fid, run_dir, method, statement,"
                            " blocker, do_not_repeat, created) VALUES (?,?,?,?,?,?,?)",
                            (str(f["id"]), str(run), str(f.get("method") or ""),
                             str(f.get("statement") or ""), str(f.get("blocker") or ""),
                             str(f.get("do_not_repeat") or ""), now))
                count += 1
        except Exception:
            pass
    jsonl = run / "failure_memory.jsonl"
    if jsonl.exists():
        for i, line in enumerate(jsonl.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            con.execute("INSERT OR REPLACE INTO failures (fid, run_dir, method, statement,"
                        " blocker, do_not_repeat, created) VALUES (?,?,?,?,?,?,?)",
                        (str(item.get("id") or f"jsonl{i}"), str(run),
                         str(item.get("method_family") or item.get("method") or ""),
                         str(item.get("statement") or ""),
                         str(item.get("blocker_or_counterexample") or item.get("blocker") or ""),
                         str(item.get("retry_condition") or ""), now))
            count += 1
    con.commit()
    con.close()
    return {"synced": count, "run_dir": str(run), "store": str(store_path())}


def query_failures(statement: str, method: str = "", limit: int = 5) -> list[dict]:
    """Token-overlap matching, mirroring the per-run `.soc` semantics: a match
    needs a method match AND statement overlap (or either alone when the other
    is unspecified)."""
    con = connect()
    rows = con.execute("SELECT fid, run_dir, method, statement, blocker, do_not_repeat"
                       " FROM failures ORDER BY created DESC LIMIT 1000").fetchall()
    con.close()
    tokens = {t for t in re.findall(r"[a-zA-Z0-9_]+", statement.lower()) if len(t) > 4}
    method_l = method.lower()
    required = 2 if len(tokens) < 8 else 3
    out = []
    for fid, run_dir, fmethod, fstatement, blocker, dnr in rows:
        method_match = bool(method_l and method_l == fmethod.lower())
        overlap = sum(1 for t in tokens if t in fstatement.lower())
        statement_match = bool(tokens and overlap >= required)
        hit = (method_match and statement_match) if (method_l and tokens) else \
              (method_match or statement_match)
        if hit:
            out.append({"id": fid, "run_dir": run_dir, "method": fmethod,
                        "statement": fstatement, "blocker": blocker, "do_not_repeat": dnr})
        if len(out) >= limit:
            break
    return out


# --- L5: bandit priors by goal signature -----------------------------------------
def record_outcome(target: str, approach: str, reward: float) -> None:
    sig = goal_signature(target)
    con = connect()
    con.execute("INSERT INTO priors (goal_signature, approach, tries, reward)"
                " VALUES (?,?,1,?) ON CONFLICT(goal_signature, approach)"
                " DO UPDATE SET tries = tries + 1, reward = reward + excluded.reward",
                (sig, approach, float(reward)))
    con.commit()
    con.close()


def priors_for(target: str) -> dict[str, float]:
    """Mean reward per approach for this goal's signature — fed straight into
    research_state.select_approach's `priors` bonus."""
    sig = goal_signature(target)
    con = connect()
    rows = con.execute("SELECT approach, tries, reward FROM priors WHERE goal_signature = ?",
                       (sig,)).fetchall()
    con.close()
    return {a: round(r / t, 4) for a, t, r in rows if t > 0}


# --- P4: the compounding surface ---------------------------------------------------
def _track_flow(kind: str, n: int = 1) -> None:
    if n <= 0:
        return
    con = connect()
    con.execute("INSERT INTO memory_flow (kind, count) VALUES (?,?)"
                " ON CONFLICT(kind) DO UPDATE SET count = count + excluded.count", (kind, n))
    con.commit()
    con.close()


def _soc_failures(run_dir: Path, statement: str, limit: int = 3) -> list[dict]:
    """Per-run .soc FAILED_APPROACHES that token-match the statement."""
    soc = Path(run_dir) / "lovasz.soc"
    if not soc.exists():
        return []
    try:
        from lovasz_soc_memory import parse_failed_entries
        entries = parse_failed_entries(soc.read_text(encoding="utf-8"))
    except Exception:
        return []
    tokens = {t for t in re.findall(r"[a-zA-Z0-9_]+", statement.lower()) if len(t) > 4}
    out = []
    for e in entries:
        overlap = sum(1 for t in tokens if t in str(e.get("statement") or "").lower())
        if overlap >= 2:
            out.append({"method": e.get("method"), "blocker": e.get("blocker"),
                        "do_not_repeat": e.get("do_not_repeat"), "scope": "run"})
        if len(out) >= limit:
            break
    return out


def _library_lemmas(statement: str, limit: int = 3) -> list[dict]:
    """Token-overlap matches from the global lemma library (lemmas.db)."""
    db = witcore.global_library() / "lemmas.db"
    if not db.exists():
        return []
    try:
        con = sqlite3.connect(db)
        rows = con.execute("SELECT statement, trust_tier, tokens FROM lemmas LIMIT 2000").fetchall()
        con.close()
    except Exception:
        return []
    tokens = {t for t in re.findall(r"[a-zA-Z0-9_]+", statement.lower()) if len(t) > 3}
    scored = []
    for stmt, tier, toks in rows:
        overlap = sum(1 for t in tokens if t in str(toks or stmt).lower())
        if overlap >= 2:
            scored.append((overlap, {"statement": stmt, "trust_tier": tier}))
    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored[:limit]]


def memory_context(statement: str, run_dir: Path | str | None = None, k: int = 3) -> dict:
    """Everything witsoc REMEMBERS that bears on this statement, assembled
    from the real substrates (.soc + sqlite) for embedding into bus requests
    and fleet prompts — the cross-problem compounding surface. Each section
    is attention only; nothing here is trust.

    Sections: failure_warnings (L4 global + per-run .soc), proved_lemmas
    (global library), proof_examples (proof bank few-shots), priors (L5)."""
    ctx: dict = {}
    failures = query_failures(statement, limit=k)
    if run_dir:
        failures = _soc_failures(Path(run_dir), statement, limit=k) + failures
    if failures:
        ctx["failure_warnings"] = [{"method": f.get("method"), "blocker": f.get("blocker"),
                                    "do_not_repeat": f.get("do_not_repeat")}
                                   for f in failures[:k]]
    lemmas = _library_lemmas(statement, limit=k)
    if lemmas:
        ctx["proved_lemmas"] = lemmas
    try:
        import proof_bank
        examples = proof_bank.examples_for(statement, k=k)
        if examples:
            ctx["proof_examples"] = examples
    except Exception:
        pass
    priors = priors_for(statement)
    if priors:
        ctx["approach_priors"] = priors
    for kind, key in (("failure_warnings", "failure_warnings"), ("proved_lemmas", "proved_lemmas"),
                      ("proof_examples", "proof_examples"), ("approach_priors", "approach_priors")):
        _track_flow(f"attached:{kind}", len(ctx.get(key) or []))
    if ctx:
        ctx["calibration"] = "memory is attention, never trust; warnings advise, lemmas/examples are candidates"
        _track_flow("contexts_assembled")
    return ctx


def flow_report() -> dict:
    """The compounding gauge: store sizes + how much memory actually reaches
    prompts (attachment counters) + how much the decision loop has learned.
    A growing store with zero attachments means the flywheel is NOT turning."""
    con = connect()
    flow = dict(con.execute("SELECT kind, count FROM memory_flow"))
    base = {
        "failures_stored": con.execute("SELECT COUNT(*) FROM failures").fetchone()[0],
        "prior_rows": con.execute("SELECT COUNT(*) FROM priors").fetchone()[0],
    }
    con.close()
    try:
        db = witcore.global_library() / "lemmas.db"
        if db.exists():
            lc = sqlite3.connect(db)
            base["library_lemmas"] = lc.execute("SELECT COUNT(*) FROM lemmas").fetchone()[0]
            lc.close()
    except Exception:
        pass
    try:
        import proof_bank
        base["proof_bank"] = proof_bank.stats().get("banked", proof_bank.stats().get("rows", 0))
    except Exception:
        pass
    try:
        import decision_ledger
        base["decisions"] = decision_ledger.stats()
    except Exception:
        pass
    return {"schema": "witsoc.memory_flow.v1", "stores": base, "attachments": flow,
            "verdict": ("flywheel turning" if flow.get("contexts_assembled") else
                        "stores exist but nothing attached to prompts yet")}


def stats() -> dict:
    con = connect()
    out = {
        "store": str(store_path()),
        "failures": con.execute("SELECT COUNT(*) FROM failures").fetchone()[0],
        "runs_synced": con.execute("SELECT COUNT(DISTINCT run_dir) FROM failures").fetchone()[0],
        "prior_signatures": con.execute("SELECT COUNT(DISTINCT goal_signature) FROM priors").fetchone()[0],
        "prior_rows": con.execute("SELECT COUNT(*) FROM priors").fetchone()[0],
    }
    con.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_sync = sub.add_parser("sync-run")
    p_sync.add_argument("run_dir", type=Path)
    p_q = sub.add_parser("query")
    p_q.add_argument("--statement", default="")
    p_q.add_argument("--method", default="")
    p_rec = sub.add_parser("record-outcome")
    p_rec.add_argument("--target", required=True)
    p_rec.add_argument("--approach", required=True)
    p_rec.add_argument("--reward", type=float, required=True)
    p_pri = sub.add_parser("priors")
    p_pri.add_argument("--target", required=True)
    p_ctx = sub.add_parser("context")
    p_ctx.add_argument("--statement", required=True)
    p_ctx.add_argument("--run-dir", type=Path, default=None)
    sub.add_parser("flow")
    sub.add_parser("stats")
    args = ap.parse_args()

    if args.cmd == "sync-run":
        result = sync_run(args.run_dir)
    elif args.cmd == "query":
        result = {"matches": query_failures(args.statement, args.method)}
    elif args.cmd == "record-outcome":
        record_outcome(args.target, args.approach, args.reward)
        result = {"recorded": True, "signature": goal_signature(args.target)}
    elif args.cmd == "priors":
        result = {"signature": goal_signature(args.target), "priors": priors_for(args.target)}
    elif args.cmd == "context":
        result = memory_context(args.statement, args.run_dir)
    elif args.cmd == "flow":
        result = flow_report()
    else:
        result = stats()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
