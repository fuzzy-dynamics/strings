#!/usr/bin/env python3
"""F4 literature engine — `witsoc literature`.

Knowing the frontier is half of open-problem work: without it Explorer cannot
write a truthful barrier packet, novelty verdicts degrade to
LOCALLY_NEW_UNCHECKED, and the discovery ledger's `publishable` bar is
structurally unreachable. This engine gives witsoc its first live literature
loop:

  search          query the arXiv Atom API (urllib, no dependencies); network
                  failure is an honest `network_unavailable`, never a guess
  triage          build/refresh a per-problem SOURCE LEDGER
                  (~/.witsoc/literature/<slug>.json): query, checked_at,
                  sources with title/authors/year/arxiv_id — the dated trail
                  literature_triage.md mandates but nothing implemented
  staleness       flag ledgers older than --max-age-days (default 90) — the
                  re-triage gate before re-running a campaign on a problem
  novelty-probe   keyword search for a statement; matches are CANDIDATE PRIOR
                  WORK to read, an empty result is recorded probe evidence —
                  never a novelty verdict by itself

novelty_triage uses the probe as its default external checker when
WITSOC_NOVELTY_CMD is unset: matches -> KNOWN (with the sources to check);
no matches -> still LOCALLY_NEW_UNCHECKED, with the probe recorded as
evidence. A keyword search missing a paper is common; absence of matches is
never NOVEL_CANDIDATE.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
from witcore import slug  # noqa: E402

ARXIV_API = "http://export.arxiv.org/api/query"
_ATOM = "{http://www.w3.org/2005/Atom}"
DEFAULT_MAX_AGE_DAYS = 90

# Injectable fetcher (tests replace this; the arXiv path needs no dependencies).
def _fetch(url: str, timeout: float) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


FETCH = _fetch


def ledger_dir() -> Path:
    return witcore.witsoc_home() / "literature"


def parse_atom(xml_text: str) -> list[dict]:
    sources = []
    root = ET.fromstring(xml_text)
    for entry in root.findall(f"{_ATOM}entry"):
        arxiv_id = (entry.findtext(f"{_ATOM}id") or "").rsplit("/", 1)[-1]
        published = entry.findtext(f"{_ATOM}published") or ""
        sources.append({
            "title": re.sub(r"\s+", " ", entry.findtext(f"{_ATOM}title") or "").strip(),
            "authors": [a.findtext(f"{_ATOM}name") or ""
                        for a in entry.findall(f"{_ATOM}author")][:6],
            "year": published[:4],
            "arxiv_id": arxiv_id,
            "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
            "summary_excerpt": re.sub(r"\s+", " ", entry.findtext(f"{_ATOM}summary") or "").strip()[:300],
            "source_type": "arxiv_preprint",
        })
    return sources


def search(query: str, max_results: int = 10, timeout: float = 20.0) -> dict:
    url = (f"{ARXIV_API}?search_query={urllib.parse.quote(f'all:{query}')}"
           f"&max_results={max_results}&sortBy=relevance")
    try:
        xml_text = FETCH(url, timeout)
    except Exception as exc:
        return {"status": "network_unavailable", "query": query,
                "reason": f"{type(exc).__name__}: {str(exc)[:120]}",
                "note": "no literature evidence gathered; status claims stay unconfirmed"}
    try:
        sources = parse_atom(xml_text)
    except Exception as exc:
        return {"status": "parse_error", "query": query, "reason": str(exc)[:120]}
    return {"status": "ok", "query": query, "sources": sources, "count": len(sources)}


def triage(problem_id: str, queries: list[str], max_results: int, timeout: float) -> dict:
    """Build/refresh the per-problem source ledger. Pointer discipline: arXiv
    entries are dated, findable leads — status claims still need the primary
    source actually read (literature_triage.md)."""
    results, sources, failures = [], [], []
    for q in queries:
        r = search(q, max_results, timeout)
        results.append({"query": q, "status": r["status"], "count": r.get("count", 0)})
        if r["status"] == "ok":
            for s in r["sources"]:
                if s["arxiv_id"] not in {x["arxiv_id"] for x in sources}:
                    sources.append(s)
        else:
            failures.append(r)
    ledger = {
        "schema": "witsoc.literature_ledger.v1",
        "problem_id": problem_id,
        "queries": results,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "checked_epoch": int(time.time()),
        "sources": sources,
        "network_failures": failures,
        "note": ("arXiv entries are POINTER sources: dated, findable leads for triage. "
                 "A status claim still requires the primary source read (literature_triage.md)."),
    }
    path = ledger_dir() / f"{slug(problem_id)}.json"
    witcore.save_json(path, ledger)
    return {**ledger, "ledger_path": str(path)}


def staleness(max_age_days: int) -> dict:
    now = int(time.time())
    rows = []
    for path in sorted(ledger_dir().glob("*.json")):
        ledger = witcore.load_json(path, {})
        if not isinstance(ledger, dict) or ledger.get("schema") != "witsoc.literature_ledger.v1":
            continue
        age_days = (now - int(ledger.get("checked_epoch", 0))) / 86400
        rows.append({"problem_id": ledger.get("problem_id"), "ledger": str(path),
                     "age_days": round(age_days, 1), "stale": age_days > max_age_days,
                     "sources": len(ledger.get("sources", []))})
    return {"schema": "witsoc.literature_staleness.v1", "max_age_days": max_age_days,
            "ledgers": rows, "stale": [r["problem_id"] for r in rows if r["stale"]],
            "gate": "re-run `witsoc literature triage` for stale problems before campaigning on them"}


def ledger_for(problem_id: str) -> dict | None:
    data = witcore.load_json(ledger_dir() / f"{slug(problem_id)}.json", None)
    if isinstance(data, dict) and data.get("schema") == "witsoc.literature_ledger.v1":
        return data
    wanted = {t for t in re.findall(r"[a-z0-9]+", problem_id.lower()) if len(t) >= 4}
    best = None
    best_score = 0
    for path in ledger_dir().glob("*.json"):
        cand = witcore.load_json(path, None)
        if not isinstance(cand, dict) or cand.get("schema") != "witsoc.literature_ledger.v1":
            continue
        hay = " ".join([
            str(cand.get("problem_id") or ""),
            " ".join(str(q.get("query") or "") for q in cand.get("queries", []) if isinstance(q, dict)),
            " ".join(str(s.get("title") or "") for s in cand.get("sources", []) if isinstance(s, dict)),
        ]).lower()
        have = set(re.findall(r"[a-z0-9]+", hay))
        score = len(wanted & have)
        if score > best_score:
            best, best_score = cand, score
    return best if best_score >= 2 else None


def _row_id(source: str, candidate: str) -> str:
    import hashlib
    return hashlib.sha256(f"{source}|{candidate}".encode("utf-8")).hexdigest()[:16]


EXTRACT_INSTRUCTIONS = (
    "Read the cited source and EXTRACT the exact theorem most relevant to the "
    "target subgoal. Do NOT paraphrase a vague claim. Reply shape: "
    "{\"exact_statement\": \"verbatim or faithful formal statement\", "
    "\"hypotheses\": [\"each precondition as a separate item\"], "
    "\"conclusion\": \"the asserted conclusion\", "
    "\"missing_preconditions\": [\"preconditions the target subgoal does NOT "
    "establish\"], \"formal_availability\": \"mathlib|literature|none|unknown\", "
    "\"source_locator\": \"theorem number / page / url anchor\"}. If the source "
    "does not contain a usable theorem for this subgoal, reply "
    "{\"exact_statement\": \"NONE\", \"reason\": \"...\"} — never invent one."
)


def theorem_audit(problem_id: str, target: str, out: Path | None = None,
                  limit: int = 8, bus_dir: Path | None = None) -> dict:
    """Turn a source ledger into theorem-precondition audit rows.

    This is deliberately conservative: arXiv hits become candidate theorem
    sources to read, not known usable theorems. The value is that Researcher now
    emits the exact artifact Lovasz needs: candidate source, missing exact
    statement, missing preconditions, formal availability, and use decision.

    When `bus_dir` is given, each candidate row also EMITS a `theorem_extract`
    Intelligence Bus request so the orchestrator/fleet can read the source and
    return the exact statement + hypotheses + conclusion + missing preconditions.
    `bus_apply_replies` validates and merges those extractions, flipping a row
    from PENDING to EXTRACTED — the gated path off pointer-level research.
    """
    ledger = ledger_for(problem_id)
    rows = []
    emitted = []
    if ledger:
        for src in (ledger.get("sources") or [])[:limit]:
            if not isinstance(src, dict):
                continue
            source = src.get("url") or src.get("arxiv_id") or ""
            candidate = src.get("title") or "untitled source"
            rid = _row_id(source, candidate)
            row = {
                "row_id": rid,
                "extraction_status": "PENDING",
                "target_subgoal": target,
                "candidate_theorem": candidate,
                "exact_statement": "PENDING_READ: extract exact theorem statement from the cited source before use",
                "source": source,
                "source_type": src.get("source_type") or "unknown",
                "year": src.get("year") or "",
                "authors": src.get("authors") or [],
                "required_preconditions": [],
                "missing_preconditions": [
                    "exact theorem statement not extracted",
                    "preconditions not compared with target subgoal",
                    "Lean/mathlib availability not checked",
                ],
                "formal_availability": "unknown",
                "use_decision": "read_source_before_use",
                "relevance": "candidate_prior_work",
            }
            if bus_dir is not None:
                try:
                    import request_bus as rb
                    payload = {
                        "task": "theorem_extract",
                        "row_id": rid,
                        "candidate_theorem": candidate,
                        "source": source,
                        "target": target,
                        "problem_id": problem_id,
                        "instructions": EXTRACT_INSTRUCTIONS,
                    }
                    res = rb.emit(payload, role="theorem_extract", priority=6, d=bus_dir)
                    row["extract_bus_request"] = res.get("id")
                    emitted.append(res.get("id"))
                except Exception as exc:  # pragma: no cover - emit best-effort
                    row["extract_bus_request"] = {"status": "emit_failed", "error": str(exc)}
            rows.append(row)

    # No source ledger and no network triage available here: rather than a silent
    # dead-end (0 rows, 0 requests), emit a `literature_search` bus request so the
    # ORCHESTRATOR (which has web access; witsoc does not) can supply sources. Its
    # reply is merged into a ledger by bus_apply, after which a re-run of
    # theorem-audit finds the ledger and emits the theorem_extract requests.
    search_request = None
    if not ledger and bus_dir is not None:
        try:
            import request_bus as rb
            payload = {
                "task": "literature_search",
                "problem_id": problem_id,
                "target": target,
                "instructions": (
                    "Find the key papers/theorems bearing on this target. Reply "
                    "{\"findings\": [{\"title\": str, \"claim\": str, \"source\": "
                    "\"url or arXiv id\", \"year\": str?, \"relevance\": str}]}. "
                    "Prefer the primary results and best-known bounds."),
            }
            res = rb.emit(payload, role="literature_search", priority=7, d=bus_dir)
            search_request = res.get("id")
        except Exception as exc:  # pragma: no cover - emit best-effort
            search_request = {"status": "emit_failed", "error": str(exc)}

    result = {
        "schema": "witsoc.theorem_precondition_audit.v1",
        "problem_id": problem_id,
        "target_subgoal": target,
        "source_ledger_found": bool(ledger),
        "rows": rows,
        "extracted": sum(1 for r in rows if r.get("extraction_status") == "EXTRACTED"),
        "pending": sum(1 for r in rows if r.get("extraction_status") == "PENDING"),
        "emitted_extract_requests": [e for e in emitted if e],
        "emitted_literature_search": search_request,
        "action_required": (
            None if ledger else
            "NO_SOURCE_LEDGER: fulfil the literature_search bus request (web access), "
            "then `witsoc bus-apply` and re-run theorem-audit"),
        "note": "candidate rows are not theorem evidence until exact statements and preconditions are extracted",
    }
    if out:
        witcore.save_json(out, rows)
        result["out"] = str(out)
    return result


def novelty_probe(statement: str, keywords: list[str], max_results: int = 8,
                  timeout: float = 20.0) -> dict:
    """The default external novelty checker (novelty_triage falls back here).
    Honesty contract: matches = candidate prior work that MUST be read;
    no matches NEVER establishes novelty (keyword search misses things)."""
    query = " AND ".join(f"all:{k}" for k in keywords[:6]) if keywords else statement[:80]
    r = search(query, max_results, timeout)
    if r["status"] != "ok":
        return {"status": r["status"], "known": None, "reason": r.get("reason"),
                "note": "probe unavailable; novelty stays UNCHECKED"}
    matches = r.get("sources", [])
    return {"status": "ok", "known": bool(matches),
            "matches": [{k: s[k] for k in ("title", "year", "arxiv_id")} for s in matches[:5]],
            "source": matches[0]["url"] if matches else None,
            "note": ("matches are CANDIDATE prior work to read before any priority claim"
                     if matches else
                     "no keyword match found — recorded probe evidence, NOT a novelty verdict")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_s = sub.add_parser("search")
    p_s.add_argument("--query", required=True)
    p_s.add_argument("--max-results", type=int, default=10)
    p_t = sub.add_parser("triage")
    p_t.add_argument("--problem-id", required=True)
    p_t.add_argument("--query", action="append", required=True, dest="queries")
    p_t.add_argument("--max-results", type=int, default=10)
    p_t.add_argument("--timeout", type=float, default=20.0)
    p_st = sub.add_parser("staleness")
    p_st.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    p_a = sub.add_parser("theorem-audit")
    p_a.add_argument("--problem-id", required=True)
    p_a.add_argument("--target", required=True)
    p_a.add_argument("--out", type=Path, default=None)
    p_a.add_argument("--limit", type=int, default=8)
    p_a.add_argument("--bus-dir", type=Path, default=None,
                     help="emit theorem_extract bus requests into this dir")
    p_n = sub.add_parser("novelty-probe")
    p_n.add_argument("--statement", required=True)
    p_n.add_argument("--keyword", action="append", default=[], dest="keywords")
    args = ap.parse_args()

    if args.cmd == "search":
        result = search(args.query, args.max_results)
    elif args.cmd == "triage":
        result = triage(args.problem_id, args.queries, args.max_results, args.timeout)
    elif args.cmd == "staleness":
        result = staleness(args.max_age_days)
    elif args.cmd == "theorem-audit":
        result = theorem_audit(args.problem_id, args.target, args.out, args.limit,
                               bus_dir=args.bus_dir)
    else:
        result = novelty_probe(args.statement, args.keywords)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") in ("ok", None) or "ledgers" in result or "sources" in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
