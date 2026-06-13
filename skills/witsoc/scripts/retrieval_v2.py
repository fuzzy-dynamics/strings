#!/usr/bin/env python3
"""Ω3 retrieval v2 — `witsoc retrieve`.

Tao: "a lot of the bottleneck now is actually lemma search." LeanSearch v2
measured the fix at a 4%→20% proving lift; Rethlas/Archon credit strong
theorem retrieval for their open-problem solve. This module brings the
validated recipe to witsoc:

  HIERARCHY-INFORMALIZED CORPUS  every declaration carries an informal
    description grounded in mathematics rather than identifiers, with
    dependency descriptions folded in where known (`build-corpus` merges the
    core atlas docs, the live lemma library, mined technique-atlas examples,
    and any Mathlib atlas; an optional fleet `informalize` pass enriches
    entries that lack descriptions);
  TWO-STAGE RETRIEVAL  stage 1 scores candidates lexically over
    name+statement+description (an optional `WITSOC_EMBED_CMD` cmd: embedder
    upgrades stage 1 to cached cosine similarity); stage 2 reranks the top-K
    via the sampler fleet (`rerank_premises`), falling back to the
    deterministic score offline;
  GLOBAL PREMISE SETS  `global` retrieves per sub-query (the goal's
    components and any sketch steps) and unions the results — the premise
    set a whole PROOF STRATEGY needs, not per-step keyword matches;
  SKETCH-RETRIEVE-REFLECT  `reflect` asks the fleet for a strategy sketch
    with named premise NEEDS, retrieves each, and reports which needs have NO
    library support — "retriever found nothing useful" is a first-class
    signal that revises the strategy (and feeds theory gaps).

The prover consumes this automatically: close_obligation routes premise
selection through retrieval_v2 whenever a corpus exists. All suggestions are
candidates; the kernel rejects wrong ones — retrieval only changes reach.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

CORPUS_NAME = "retrieval_corpus.jsonl"
_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_']*")
_STOP = {"the", "and", "for", "nat", "prop", "type", "of", "a", "an", "to", "is", "in"}


def corpus_path() -> Path:
    return witcore.witsoc_home() / "retrieval" / CORPUS_NAME


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")
            if len(t) > 2 and t.lower() not in _STOP}


# --- corpus build -----------------------------------------------------------------
def _core_atlas_entries() -> list[dict]:
    data = witcore.load_json(SCRIPT_DIR / "core_lemma_atlas.json", {})
    out = []
    for node in (data.get("nodes") or []) if isinstance(data, dict) else []:
        for sym in node.get("symbols") or []:
            out.append({"name": str(sym), "kind": "lemma", "statement": "",
                        "description": str(node.get("doc") or ""),
                        "imports": node.get("imports") or [], "source": "core_atlas"})
    return out


def _library_entries() -> list[dict]:
    db = witcore.global_library() / "lemmas.db"
    if not db.exists():
        return []
    out = []
    try:
        con = sqlite3.connect(db)
        for stmt, tier, prov in con.execute(
                "SELECT statement, tier, provenance FROM lemmas LIMIT 5000"):
            out.append({"name": f"library:{witcore.slug(str(stmt))[:40]}", "kind": "harvested_lemma",
                        "statement": str(stmt), "description": "",
                        "imports": [], "source": f"live_library({tier})",
                        "provenance": str(prov or "")})
        con.close()
    except Exception:
        return []
    return out


def _technique_entries() -> list[dict]:
    atlas = witcore.load_json(witcore.witsoc_home() / "technique_atlas.json", [])
    out = []
    for e in atlas if isinstance(atlas, list) else []:
        for ex in (e.get("examples") or [])[:2]:
            out.append({"name": f"technique:{e.get('move')}:{witcore.slug(str(ex))[:30]}",
                        "kind": "technique_example", "statement": str(ex),
                        "description": f"the '{e.get('move')}' move; proof skeleton: "
                                       f"{str(e.get('proof_skeleton') or '')[:120]}",
                        "imports": [], "source": "technique_atlas"})
    return out


def _informalize_with_fleet(entries: list[dict], limit: int) -> int:
    """Optional enrichment: the fleet writes grounded descriptions for entries
    that lack one. Hierarchy discipline: already-described entries are offered
    as context so new descriptions build on them."""
    import sampler_fleet as sf
    if not sf.samplers():
        return 0
    described = [e for e in entries if e["description"]][:20]
    todo = [e for e in entries if not e["description"]][:limit]
    enriched = 0
    for e in todo:
        results = sf.sample({
            "task": "informalize_declaration",
            "name": e["name"], "statement": e["statement"],
            "already_described_neighbors": [{"name": d["name"], "description": d["description"]}
                                            for d in described[:8]],
            "rules": "Return {description: \"...\"} — one sentence grounding this declaration in "
                     "mathematical concepts (not identifiers); mention what it is FOR.",
        }, per_sampler=1)
        for r in results:
            desc = str(r["reply"].get("description") or "").strip()
            if desc:
                e["description"] = desc[:300]
                enriched += 1
                break
    return enriched


def build_corpus(informalize: bool = False, informalize_limit: int = 50) -> dict:
    entries = _core_atlas_entries() + _library_entries() + _technique_entries()
    # dedup by name, prefer described entries
    by_name: dict[str, dict] = {}
    for e in entries:
        prior = by_name.get(e["name"])
        if prior is None or (not prior["description"] and e["description"]):
            by_name[e["name"]] = e
    entries = list(by_name.values())
    enriched = _informalize_with_fleet(entries, informalize_limit) if informalize else 0
    path = corpus_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    return {"schema": "witsoc.retrieval_corpus.v1", "corpus": str(path),
            "entries": len(entries), "fleet_informalized": enriched,
            "sources": {"core_atlas": sum(1 for e in entries if e["source"] == "core_atlas"),
                        "live_library": sum(1 for e in entries if e["source"].startswith("live_library")),
                        "technique_atlas": sum(1 for e in entries if e["source"] == "technique_atlas")}}


_CORPUS_CACHE: tuple[float, list[dict]] | None = None


def load_corpus() -> list[dict]:
    global _CORPUS_CACHE
    path = corpus_path()
    if not path.exists():
        return []
    mtime = path.stat().st_mtime
    if _CORPUS_CACHE and _CORPUS_CACHE[0] == mtime:
        return _CORPUS_CACHE[1]
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
            e["_tokens"] = _tokens(f"{e['name']} {e['statement']} {e['description']}")
            entries.append(e)
        except Exception:
            continue
    _CORPUS_CACHE = (mtime, entries)
    return entries


# --- two-stage retrieval -----------------------------------------------------------
def _stage1(query: str, entries: list[dict], k: int = 50) -> list[tuple[float, dict]]:
    import os
    embed_cmd = os.environ.get("WITSOC_EMBED_CMD")
    if embed_cmd:
        scored = _stage1_embed(embed_cmd, query, entries)
        if scored is not None:
            return scored[:k]
    q = _tokens(query)
    if not q:
        return []
    scored = []
    for e in entries:
        overlap = len(q & e["_tokens"])
        if overlap:
            scored.append((overlap / (len(q | e["_tokens"]) ** 0.5), e))
    scored.sort(key=lambda x: -x[0])
    return scored[:k]


def _stage1_embed(embed_cmd: str, query: str, entries: list[dict]) -> list[tuple[float, dict]] | None:
    """Optional cmd: embedder (request {texts: [...]} -> {vectors: [[...], ...]});
    corpus vectors are cached beside the corpus."""
    cache_file = corpus_path().with_suffix(".vectors.json")
    cache = witcore.load_json(cache_file, {})
    texts, missing = [], []
    for e in entries:
        if e["name"] not in cache:
            missing.append(e["name"])
            texts.append(f"{e['name']}: {e['statement']} — {e['description']}")
    reply = witcore.run_sampler(embed_cmd, {"task": "embed", "texts": [query] + texts}, timeout=300)
    if not (isinstance(reply, dict) and isinstance(reply.get("vectors"), list)
            and len(reply["vectors"]) == 1 + len(texts)):
        return None
    qvec = reply["vectors"][0]
    for name, vec in zip(missing, reply["vectors"][1:]):
        cache[name] = vec
    witcore.save_json(cache_file, cache)

    def cos(a, b):
        num = sum(x * y for x, y in zip(a, b))
        da = sum(x * x for x in a) ** 0.5
        db = sum(y * y for y in b) ** 0.5
        return num / (da * db) if da and db else 0.0

    scored = [(cos(qvec, cache[e["name"]]), e) for e in entries if e["name"] in cache]
    scored.sort(key=lambda x: -x[0])
    return scored


def _stage2_rerank(query: str, candidates: list[tuple[float, dict]], k: int) -> list[dict]:
    """Fleet rerank of the stage-1 shortlist; deterministic order offline."""
    import sampler_fleet as sf
    fleet = sf.samplers()
    shortlist = [e for _, e in candidates]
    if fleet and len(shortlist) > 1:
        reply = witcore.run_sampler(fleet[0]["command"], {
            "task": "rerank_premises", "query": query,
            "candidates": [{"name": e["name"], "statement": e["statement"],
                            "description": e["description"]} for e in shortlist[:20]],
            "rules": "Return {ranking: [names best-first]} — rank by usefulness for PROVING the "
                     "query, weighting definitions and exact-match lemmas highly.",
        })
        names = (reply or {}).get("ranking")
        if isinstance(names, list) and names:
            order = {str(n): i for i, n in enumerate(names)}
            shortlist.sort(key=lambda e: order.get(e["name"], 999))
    return shortlist[:k]


def query(text: str, k: int = 6) -> list[dict]:
    entries = load_corpus()
    if not entries:
        return []
    out = _stage2_rerank(text, _stage1(text, entries), k)
    return [{key: e[key] for key in ("name", "kind", "statement", "description", "imports", "source")}
            for e in out]


def global_premises(goal: str, sketch_steps: list[str] | None = None, k_per_query: int = 4,
                    cap: int = 14) -> dict:
    """The proof-strategy-level premise set: retrieve per sub-query (the goal
    plus each sketch step / goal component) and union — premises 'linked not
    by shared vocabulary but by the logical architecture of a proof strategy'."""
    sub_queries = [goal]
    for step in sketch_steps or []:
        if step.strip():
            sub_queries.append(step.strip())
    # goal components as sub-queries (implication sides, conjuncts)
    for part in re.split(r"→|∧|↔", goal):
        part = part.strip()
        if len(part) > 8 and part != goal:
            sub_queries.append(part)
    seen: dict[str, dict] = {}
    per_query = {}
    for q in sub_queries[:8]:
        hits = query(q, k=k_per_query)
        per_query[q[:60]] = [h["name"] for h in hits]
        for h in hits:
            seen.setdefault(h["name"], h)
    premises = list(seen.values())[:cap]
    return {"schema": "witsoc.global_premises.v1", "goal": goal,
            "sub_queries": len(sub_queries), "per_query": per_query,
            "premises": premises,
            "premise_symbols": [p["name"] for p in premises if not p["name"].startswith(("library:", "technique:"))]}


def reflect(goal: str, rounds: int = 2) -> dict:
    """Sketch-retrieve-reflect: the fleet sketches a strategy with named
    premise NEEDS; unsupported needs (no retrieval hit) are first-class
    signals that revise the strategy — and are returned as theory-gap
    candidates for the campaign."""
    import sampler_fleet as sf
    fleet = sf.samplers()
    if not fleet:
        gp = global_premises(goal)
        return {"mode": "no_fleet", "premises": gp["premises"],
                "unsupported_needs": [], "note": "global premise union only (no fleet to sketch)"}
    feedback = ""
    last = None
    for rnd in range(1, rounds + 1):
        reply = witcore.run_sampler(fleet[0]["command"], {
            "task": "sketch_premises", "goal": goal, "round": rnd,
            "previous_unsupported": feedback,
            "rules": "Return {strategy: \"...\", needs: [short descriptions of the lemmas/definitions "
                     "the strategy requires]}. If previous needs were unsupported by the library, "
                     "revise the strategy to avoid them.",
        })
        if not isinstance(reply, dict) or not reply.get("needs"):
            break
        needs = [str(n) for n in reply["needs"]][:8]
        supported, unsupported = [], []
        for need in needs:
            hits = query(need, k=2)
            (supported if hits else unsupported).append(
                {"need": need, "hits": [h["name"] for h in hits]})
        last = {"mode": "reflect", "round": rnd, "strategy": str(reply.get("strategy") or ""),
                "supported": supported, "unsupported_needs": [u["need"] for u in unsupported],
                "premises": [h for s in supported for h in query(s["need"], k=2)][:12]}
        if not unsupported:
            break
        feedback = "; ".join(u["need"] for u in unsupported)
    return last or {"mode": "reflect_failed", "premises": [], "unsupported_needs": []}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_b = sub.add_parser("build-corpus")
    p_b.add_argument("--informalize", action="store_true", help="fleet-enrich missing descriptions")
    p_b.add_argument("--informalize-limit", type=int, default=50)
    p_q = sub.add_parser("query")
    p_q.add_argument("--text", required=True)
    p_q.add_argument("-k", type=int, default=6)
    p_g = sub.add_parser("global")
    p_g.add_argument("--goal", required=True)
    p_g.add_argument("--sketch-step", action="append", default=[])
    p_r = sub.add_parser("reflect")
    p_r.add_argument("--goal", required=True)
    args = ap.parse_args()

    if args.cmd == "build-corpus":
        result: Any = build_corpus(args.informalize, args.informalize_limit)
    elif args.cmd == "query":
        result = {"hits": query(args.text, args.k)}
    elif args.cmd == "global":
        result = global_premises(args.goal, args.sketch_step)
    else:
        result = reflect(args.goal)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
