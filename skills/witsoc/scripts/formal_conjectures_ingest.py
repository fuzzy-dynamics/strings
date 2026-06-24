#!/usr/bin/env python3
"""P2 breadth intake: ingest google-deepmind/formal-conjectures — `witsoc fc-ingest`.

The Nexus lesson: attack EVERY community-formalized problem and let
tractability emerge, instead of hand-curating a handful. This tool turns a
checkout of https://github.com/google-deepmind/formal-conjectures (441 Erdős
problems + more, each a Lean `theorem ... := by sorry` tagged
`@[category research open|solved, AMS ...]`) into:

  index <repo_dir>      benchmarks/formal_conjectures_index.json — every
                        research-tagged theorem with statement, docstring,
                        source URL, AMS areas, open/solved status, whether it
                        needs repo-local context, and a deterministic
                        attackability score (attention only).
  to-portfolio --id ... emit selected entries in research-portfolio schema
                        (tier frontier_attack, status OPEN) for the agent to
                        review and merge — NEVER auto-merged: portfolio edits
                        are deliberate and `witsoc portfolio validate` gated.

Honesty notes baked into every entry: `solved` here means solved IN THE
LITERATURE (the repo formalizes the statement, not a proof); statements that
reference repo-local definitions (`requires_context`) cannot be attacked as
standalone Mathlib goals — they need the repo's lake project as the Lean
context. Scores allocate attention; they never claim tractability.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

DEFAULT_OUT = SCRIPT_DIR.parent / "benchmarks" / "formal_conjectures_index.json"

_THEOREM_RE = re.compile(
    r"(?:/--(?P<doc>.*?)-/\s*)?"
    r"@\[category\s+research\s+(?P<status>open|solved)\s*(?:,\s*AMS\s+(?P<ams>[0-9 ]+))?\]\s*"
    r"theorem\s+(?P<name>[A-Za-z0-9_.«»']+)"
    r"(?P<binders>[^:]*?):\s*(?P<statement>.*?)\s*:=\s*by\b",
    re.DOTALL)
_REF_RE = re.compile(r"\[(?:erdosproblems\.com/(\d+)|Wikipedia)\]\(([^)]+)\)")
_LOCAL_DEF_RE = re.compile(r"^\s*(?:noncomputable\s+)?(?:abbrev|def|structure|inductive|class)\s+([A-Za-z0-9_']+)",
                           re.MULTILINE)

# AMS top-level codes -> witsoc domain labels (the common ones in the repo).
AMS_DOMAINS = {
    "5": "combinatorics", "11": "number_theory", "51": "geometry",
    "52": "discrete_geometry", "28": "measure_theory", "26": "analysis",
    "60": "probability", "3": "logic", "20": "group_theory",
}


def parse_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    source = ""
    m = _REF_RE.search(text)
    if m:
        source = m.group(2)
    local_defs = set(_LOCAL_DEF_RE.findall(text))
    out = []
    for tm in _THEOREM_RE.finditer(text):
        statement = re.sub(r"\s+", " ", tm.group("statement")).strip()
        binders = re.sub(r"\s+", " ", tm.group("binders") or "").strip()
        doc = re.sub(r"\s+", " ", (tm.group("doc") or "")).strip()
        ams = [a for a in (tm.group("ams") or "").split() if a]
        uses_local = sorted(d for d in local_defs
                            if re.search(rf"\b{re.escape(d)}\b", binders + " " + statement))
        out.append({
            "name": tm.group("name"),
            "file": str(path),
            "status": tm.group("status"),
            "ams": ams,
            "domains": sorted({AMS_DOMAINS.get(a, f"ams_{a}") for a in ams}),
            "doc": doc[:400],
            "binders": binders[:400],
            "statement": statement[:1200],
            "source": source,
            "answer_unknown": "answer(sorry)" in statement,
            "requires_context": bool(uses_local),
            "local_defs_used": uses_local,
        })
    return out


def attackability(entry: dict) -> float:
    """Deterministic attention score in [0,1]: shorter standalone statements in
    domains where witsoc has machinery rank higher. Never a tractability claim."""
    s = 0.5
    n = len(entry["statement"])
    s += 0.2 if n < 200 else (0.1 if n < 400 else -0.1)
    if not entry["requires_context"]:
        s += 0.2  # attackable against plain Mathlib today
    if entry["answer_unknown"]:
        s -= 0.15  # open-ANSWER problems need the answer found, not just a proof
    if {"number_theory", "combinatorics"} & set(entry["domains"]):
        s += 0.1  # witsoc's strongest tooling (SAT/ILP/miners/predicates)
    return round(max(0.0, min(1.0, s)), 3)


def build_index(repo: Path, out: Path) -> dict:
    roots = [repo / "FormalConjectures"]
    entries: list[dict] = []
    files = 0
    for root in roots:
        for path in sorted(root.rglob("*.lean")):
            files += 1
            try:
                entries.extend(parse_file(path))
            except Exception:
                continue
    for e in entries:
        e["attackability"] = attackability(e)
        e["id"] = re.sub(r"[^a-z0-9_.-]+", "-", e["name"].lower()).strip("-")
    entries.sort(key=lambda e: (-(e["status"] == "open"), -e["attackability"]))
    index = {
        "schema": "witsoc.formal_conjectures_index.v1",
        "repo": str(repo),
        "files_scanned": files,
        "theorems": len(entries),
        "open": sum(1 for e in entries if e["status"] == "open"),
        "solved_in_literature": sum(1 for e in entries if e["status"] == "solved"),
        "standalone_open": sum(1 for e in entries
                               if e["status"] == "open" and not e["requires_context"]),
        "note": ("'solved' = solved in the literature (statement formalized, proof not included). "
                 "requires_context entries need the repo's lake project as Lean context; "
                 "attackability allocates attention only."),
        "entries": entries,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {k: v for k, v in index.items() if k != "entries"} | {"out": str(out)}


def to_portfolio(index_path: Path, ids: list[str]) -> dict:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in index["entries"]}
    out = []
    for i in ids:
        e = by_id.get(i)
        if not e:
            return {"error": f"unknown id {i!r}"}
        if e["status"] != "open":
            return {"error": f"{i} is solved in the literature — not a frontier_attack target"}
        out.append({
            "id": f"fc-{e['id']}"[:64],
            "tier": "frontier_attack",
            "kind": "lean",
            "domain": (e["domains"] or ["other"])[0],
            "title": (e["doc"][:80] or e["name"]),
            "informal": e["doc"] or e["statement"][:200],
            "status": "OPEN",
            "relation_to_open_problem": "is the open problem (community formalization)",
            "honest_statuses": ["OPEN", "PARTIAL", "CONDITIONAL", "CONJECTURE", "FAILED_ATTEMPT"],
            "lean_target": (e["binders"] + " : " if e["binders"] else "") + e["statement"],
            "source": e["source"],
            "formal_conjectures_file": e["file"],
            "requires_context": e["requires_context"],
            "note": ("requires the formal-conjectures lake project as Lean context"
                     if e["requires_context"] else "standalone against Mathlib"),
        })
    return {"entries": out,
            "next": "review, then merge into the portfolio and run `witsoc portfolio validate`"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_idx = sub.add_parser("index")
    p_idx.add_argument("repo", type=Path)
    p_idx.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p_top = sub.add_parser("top")
    p_top.add_argument("--index", type=Path, default=DEFAULT_OUT)
    p_top.add_argument("-k", type=int, default=15)
    p_top.add_argument("--standalone-only", action="store_true")
    p_pf = sub.add_parser("to-portfolio")
    p_pf.add_argument("--index", type=Path, default=DEFAULT_OUT)
    p_pf.add_argument("--id", action="append", dest="ids", required=True)
    args = ap.parse_args()

    if args.cmd == "index":
        result = build_index(args.repo, args.out)
    elif args.cmd == "top":
        index = json.loads(args.index.read_text(encoding="utf-8"))
        rows = [e for e in index["entries"] if e["status"] == "open"
                and (not args.standalone_only or not e["requires_context"])]
        result = {"top": [{"id": e["id"], "attackability": e["attackability"],
                           "domains": e["domains"], "requires_context": e["requires_context"],
                           "doc": e["doc"][:100]} for e in rows[:args.k]]}
    else:
        result = to_portfolio(args.index, args.ids)
        if "error" in result:
            print(json.dumps(result, ensure_ascii=False))
            return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
