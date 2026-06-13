#!/usr/bin/env python3
"""P0 Intelligence Bus — `witsoc bus`.

Witsoc engines need model intelligence (ideation, sketch mutation, skeptic
panels, Nexus proof rounds, narrative steps...). Instead of calling a model
API, an engine EMITS a typed request to this bus and returns; the
ORCHESTRATOR running witsoc (any harness: theater, Claude Code, codex, a
scheduled agent) fulfills the pending requests — inline for single
judgments, fanned out to subagents for batches — and re-runs the command.
On the re-run the engine finds its replies and proceeds. No credentials,
no network code, harness-agnostic.

The bus plugs into the existing sampler protocol as a backend:
  - `witcore.run_sampler` treats the pseudo-command `bus:` as
    emit-or-consume against this queue (reply dict if fulfilled, else None —
    exactly how a failing cmd-sampler already behaves, so every consumer
    degrades gracefully on the emitting turn).
  - `sampler_fleet.samplers()` falls back to a single `orchestrator` bus
    sampler when no cmd fleet is configured and the bus is enabled.

Enablement: WITSOC_BUS_DIR=<dir> (per-run: the campaign driver sets
<run>/bus) or WITSOC_BUS=1 (dir defaults to <witsoc home>/bus).
WITSOC_BUS=0 force-disables. Ceiling: WITSOC_BUS_CEILING pending requests
(default 500) — a runaway-loop backstop, not a budget; emits beyond it are
DROPPED and counted honestly.

Trust contract (non-negotiable): every reply enters the system as
OPEN_UNFALSIFIED candidate material. Fulfillment never upgrades a status;
the kernel/checker/skeptic gates remain the only filters.

CLI (the fulfiller surface):
  status [--dir D]                    counts + ceiling state
  pending [--dir D] [--role R]        list pending requests (ids + roles)
  next-batch [--dir D] [--role R] [--max N]
                                      one fulfillment packet: standing rules
                                      + up to N self-describing requests
  fulfill --id ID (--reply-json J | --reply-file F) [--fulfiller NAME]
  fulfill-batch --file F.jsonl        bulk: lines of {"id":..., "reply":{...}}
  gc [--max-age-hours H]              drop stale pending requests (default 48h)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

DEFAULT_CEILING = 500

# Known roles get an extra reply-shape hint in fulfillment packets. Any role
# string is legal — requests are self-describing (they carry `instructions`).
ROLE_HINTS = {
    "ideate": "reply {\"ideas\": [{\"move_class\", \"idea\", \"lean_statement\"?, \"falsification_test\"?}]}",
    "prove_sketch": ("ITERATE BEFORE SUBMITTING: you have shell access — check each candidate "
                     "yourself with `witsoc prove --lean-statement '<goal>' [--imports I] "
                     "[--lake-dir D]`, read the REAL compiler diagnostics, revise, repeat (up to "
                     "~8 rounds). Submit only your best kernel-checked attempt (or your best "
                     "sketch with honest open gaps). The whole refinement loop belongs in THIS "
                     "fulfillment, not across bus turns"),
    "mutate": "reply with mutated candidate(s) in the requested JSON shape; change exactly what the operator asks",
    "skeptic": "adversarial: try to REFUTE; reply {\"refuted\": bool, \"reasoning\": str}; uncertainty => refuted=true",
    "formalize": ("reply {\"lean_statement\": str, \"imports\": str?, \"notes\": str?}; "
                  "lean_statement is a BARE Lean PROPOSITION (a term of type Prop), NOT a "
                  "declaration. It must be usable directly as `(fun h : <lean_statement> => h)` "
                  "— so DO NOT wrap it in `theorem`/`lemma`/`def`/`example`, give it a name, "
                  "or append `:= <proof>`. Fold any hypotheses into the Prop with `∀`/`→`. "
                  "GOOD: `∀ (G : SimpleGraph (Fin n)), G.CliqueFree 3 → Real.sqrt n ≤ k`. "
                  "BAD: `theorem foo (G : ...) : ... := by ...`. It must elaborate in Lean and "
                  "must not include a proof, axiom, sorry, or a stronger/weaker target hidden "
                  "without notes. (Declaration-shaped replies are auto-normalized when "
                  "unambiguous, but a bare Prop avoids the round-trip.)"),
    "conjecture": "reply with conjecture candidates in the requested JSON shape; bold is fine, they are born unfalsified",
    "rerank": "reply with the requested ranking/scoring JSON over the given candidates only",
    "literature_search": "use your own search/browse access; reply {\"findings\": [{\"claim\", \"source\", \"relevance\"}]}",
    "theorem_extract": ("READ the cited source; reply {\"exact_statement\": str, "
                        "\"hypotheses\": [str], \"conclusion\": str, "
                        "\"missing_preconditions\": [str], \"formal_availability\": "
                        "\"mathlib|literature|none|unknown\", \"source_locator\": str}. "
                        "exact_statement must be the real theorem, not a paraphrase or "
                        "PENDING placeholder; reply {\"exact_statement\": \"NONE\"} if the "
                        "source has no usable theorem — never invent one"),
}

STANDING_RULES = (
    "You are fulfilling witsoc Intelligence Bus requests. Rules: (1) each "
    "request is self-contained — answer from its own fields, chiefly "
    "`instructions`; (2) reply with EXACTLY ONE JSON object per request, no "
    "prose around it; (3) your replies are untrusted candidates — witsoc's "
    "kernel and gates do all verification, so prefer bold coverage over "
    "hedging; (4) batches of independent requests may be fanned out to "
    "parallel subagents (recommended ~10 per worker); (5) never fabricate "
    "verification verdicts — `skeptic` role refutes, it does not certify; "
    "(6) ITERATE INSIDE the fulfillment where the role allows it: for "
    "proving/formalizing roles you may run witsoc commands yourself (e.g. "
    "`witsoc prove`) and refine against real diagnostics before submitting — "
    "one bus turn should carry a whole refinement loop, not one step of it; "
    "(7) USE the attached memory_context: respect do_not_repeat warnings, "
    "build on proved lemmas, imitate the proof examples. "
    "Submit each reply with: witsoc bus --dir <bus-dir> fulfill --id <id> "
    "--reply-json '<json>' (or fulfill-batch --file replies.jsonl with lines "
    "{\"id\":...,\"reply\":{...}}). Then the orchestrator runs `witsoc bus-apply <run-dir>`."
)


# --- storage -------------------------------------------------------------------
def enabled() -> bool:
    if os.environ.get("WITSOC_BUS", "").strip() == "0":
        return False
    return bool(os.environ.get("WITSOC_BUS_DIR", "").strip()
                or os.environ.get("WITSOC_BUS", "").strip() == "1")


def bus_dir(explicit: Path | str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("WITSOC_BUS_DIR", "").strip()
    if env:
        return Path(env)
    return witcore.witsoc_home() / "bus"


def _requests_path(d: Path) -> Path:
    return d / "requests.jsonl"


def _responses_path(d: Path) -> Path:
    return d / "responses.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    try:
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
        return out
    except Exception:
        return []


def _append_jsonl(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def request_id(role: str, payload: dict) -> str:
    """Content-hash id: the same (role, payload) is the same request — emits
    dedup, and a re-run after fulfillment finds its reply by recomputing."""
    blob = json.dumps({"role": role, "payload": payload}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# --- core API (engines call these) ----------------------------------------------
def responses_by_id(d: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for rec in _read_jsonl(_responses_path(d)):
        if rec.get("id") and isinstance(rec.get("reply"), dict):
            out[str(rec["id"])] = rec
    return out


def requests_by_id(d: Path) -> dict[str, dict]:
    return {str(r["id"]): r for r in _read_jsonl(_requests_path(d)) if r.get("id")}


# Roles whose requests get the memory context attached at queue time — the
# P4 compounding surface: failure warnings, proved lemmas, proof examples,
# and approach priors travel WITH the request to whoever fulfills it.
ENRICH_ROLES = {"ideate", "prove_sketch", "formalize", "mutate", "conjecture", "rerank",
                "evolve_program", "mutate_decomposition", "pose_frontier_conjectures"}

_STATEMENT_KEYS = ("statement", "target", "goal", "lean_target", "seed_statement", "claim")


def _memory_context_for(payload: dict, d: Path) -> dict | None:
    """Assemble the memory context for a payload (best statement-ish field).
    Attached OUTSIDE the content hash: enrichment may evolve between turns
    without orphaning fulfilled requests."""
    stmt = next((str(payload[k]) for k in _STATEMENT_KEYS if payload.get(k)), "")
    if not stmt:
        return None
    try:
        import knowledge_store as ks
        run_dir = d.parent if (d.parent / "lovasz.soc").exists() else None
        ctx = ks.memory_context(stmt, run_dir)
        return ctx or None
    except Exception:
        return None


def emit(payload: dict, *, role: str | None = None, priority: int = 5,
         d: Path | None = None) -> dict:
    """Queue a request (idempotent by content hash of the RAW payload — the
    attached memory context never affects identity). Returns
    {id, status: queued|already_pending|fulfilled|dropped_ceiling, reply?}."""
    d = bus_dir(d)
    role = str(role or payload.get("task") or payload.get("role") or "sample")
    rid = request_id(role, payload)
    responses = responses_by_id(d)
    if rid in responses:
        return {"id": rid, "status": "fulfilled", "reply": responses[rid]["reply"]}
    existing = requests_by_id(d)
    if rid in existing:
        return {"id": rid, "status": "already_pending"}
    ceiling = int(os.environ.get("WITSOC_BUS_CEILING", DEFAULT_CEILING))
    pending_now = len([r for r in existing.values() if r["id"] not in responses])
    if pending_now >= ceiling:
        _append_jsonl(d / "dropped.jsonl", {"id": rid, "role": role,
                                            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                            "reason": f"ceiling {ceiling} reached"})
        return {"id": rid, "status": "dropped_ceiling", "ceiling": ceiling}
    record = {
        "schema": "witsoc.bus_request.v1",
        "id": rid, "role": role, "priority": int(priority),
        "payload": payload,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if role in ENRICH_ROLES:
        ctx = _memory_context_for(payload, d)
        if ctx:
            record["memory_context"] = ctx
    _append_jsonl(_requests_path(d), record)
    return {"id": rid, "status": "queued"}


def consume(payload: dict, *, role: str | None = None, d: Path | None = None) -> dict | None:
    """The reply for this exact (role, payload) if fulfilled, else None."""
    d = bus_dir(d)
    role = str(role or payload.get("task") or payload.get("role") or "sample")
    rec = responses_by_id(d).get(request_id(role, payload))
    return rec["reply"] if rec else None


def sample_via_bus(request: dict, *, d: Path | None = None) -> dict | None:
    """The `bus:` sampler backend (called from witcore.run_sampler):
    emit-or-consume in one call. Fulfilled -> reply dict; pending -> None,
    which every fleet consumer already treats as 'this sampler contributed
    nothing this round'."""
    if not enabled() and d is None:
        return None
    out = emit(request, d=d)
    if out["status"] == "fulfilled":
        return out["reply"]
    return None


def pending(d: Path | None = None, role: str | None = None) -> list[dict]:
    d = bus_dir(d)
    responses = responses_by_id(d)
    reqs = [r for r in requests_by_id(d).values() if r["id"] not in responses]
    if role:
        reqs = [r for r in reqs if r.get("role") == role]
    return sorted(reqs, key=lambda r: (-int(r.get("priority", 5)), r.get("created", "")))


def status(d: Path | None = None) -> dict:
    d = bus_dir(d)
    responses = responses_by_id(d)
    reqs = requests_by_id(d)
    pend = [r for r in reqs.values() if r["id"] not in responses]
    by_role: dict[str, int] = {}
    for r in pend:
        by_role[str(r.get("role"))] = by_role.get(str(r.get("role")), 0) + 1
    return {
        "schema": "witsoc.bus_status.v1",
        "dir": str(d),
        "enabled": enabled(),
        "pending": len(pend),
        "pending_by_role": by_role,
        "fulfilled": len([i for i in reqs if i in responses]),
        "dropped": len(_read_jsonl(d / "dropped.jsonl")),
        "ceiling": int(os.environ.get("WITSOC_BUS_CEILING", DEFAULT_CEILING)),
        "next": ("fulfill pending requests (witsoc bus next-batch), then re-run "
                 "the command that reported them" if pend else "nothing pending"),
    }


def fulfill(rid: str, reply: dict, *, fulfiller: str = "orchestrator",
            d: Path | None = None) -> dict:
    d = bus_dir(d)
    if not isinstance(reply, dict):
        return {"ok": False, "error": "reply must be a JSON object"}
    reqs = requests_by_id(d)
    if rid not in reqs:
        return {"ok": False, "error": f"unknown request id {rid!r}"}
    if rid in responses_by_id(d):
        return {"ok": True, "id": rid, "note": "already fulfilled; duplicate ignored"}
    _append_jsonl(_responses_path(d), {
        "schema": "witsoc.bus_response.v1",
        "id": rid, "reply": reply, "fulfiller": fulfiller,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    return {"ok": True, "id": rid}


def next_batch(d: Path | None = None, role: str | None = None, max_n: int = 10) -> dict:
    """A self-contained fulfillment packet for the orchestrator/subagent."""
    batch = pending(d, role)[:max_n]
    return {
        "schema": "witsoc.bus_batch.v1",
        "standing_rules": STANDING_RULES,
        "count": len(batch),
        "requests": [{
            "id": r["id"], "role": r.get("role"), "priority": r.get("priority", 5),
            "reply_shape_hint": ROLE_HINTS.get(str(r.get("role")),
                                               "reply with the JSON object the payload's instructions describe"),
            "payload": r.get("payload"),
            **({"memory_context": r["memory_context"]} if r.get("memory_context") else {}),
        } for r in batch],
    }


def gc(d: Path | None = None, max_age_hours: float = 48.0) -> dict:
    """Rewrite requests.jsonl without stale pending entries (fulfilled history
    is kept — it is the dedup/memoization surface)."""
    d = bus_dir(d)
    responses = responses_by_id(d)
    cutoff = time.time() - max_age_hours * 3600
    kept, dropped = [], 0
    for r in _read_jsonl(_requests_path(d)):
        try:
            created = time.mktime(time.strptime(str(r.get("created")), "%Y-%m-%dT%H:%M:%S"))
        except Exception:
            created = time.time()
        if r.get("id") in responses or created >= cutoff:
            kept.append(r)
        else:
            dropped += 1
    if dropped:
        _requests_path(d).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
    return {"dropped": dropped, "kept": len(kept)}


# --- CLI -------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=None, help="bus dir (default: WITSOC_BUS_DIR or <witsoc home>/bus)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p_pending = sub.add_parser("pending")
    p_pending.add_argument("--role", default=None)
    p_batch = sub.add_parser("next-batch")
    p_batch.add_argument("--role", default=None)
    p_batch.add_argument("--max", type=int, default=10)
    p_fulfill = sub.add_parser("fulfill")
    p_fulfill.add_argument("--id", required=True)
    p_fulfill.add_argument("--reply-json", default=None)
    p_fulfill.add_argument("--reply-file", type=Path, default=None)
    p_fulfill.add_argument("--fulfiller", default="orchestrator")
    p_bulk = sub.add_parser("fulfill-batch")
    p_bulk.add_argument("--file", type=Path, required=True)
    p_bulk.add_argument("--fulfiller", default="orchestrator")
    p_gc = sub.add_parser("gc")
    p_gc.add_argument("--max-age-hours", type=float, default=48.0)
    args = ap.parse_args()

    d = args.dir
    if args.cmd == "status":
        print(json.dumps(status(d), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "pending":
        for r in pending(d, args.role):
            print(json.dumps({"id": r["id"], "role": r.get("role"),
                              "priority": r.get("priority"), "created": r.get("created")}))
        return 0
    if args.cmd == "next-batch":
        print(json.dumps(next_batch(d, args.role, args.max), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "fulfill":
        if (args.reply_json is None) == (args.reply_file is None):
            print(json.dumps({"ok": False, "error": "exactly one of --reply-json/--reply-file"}))
            return 2
        try:
            reply: Any = (json.loads(args.reply_json) if args.reply_json is not None
                          else json.loads(args.reply_file.read_text(encoding="utf-8")))
        except Exception as exc:
            print(json.dumps({"ok": False, "error": f"invalid JSON reply: {exc}"}))
            return 1
        result = fulfill(args.id, reply, fulfiller=args.fulfiller, d=d)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if args.cmd == "fulfill-batch":
        ok = bad = 0
        for line in args.file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                result = fulfill(str(rec["id"]), rec["reply"], fulfiller=args.fulfiller, d=d)
            except Exception:
                result = {"ok": False}
            ok, bad = ok + bool(result.get("ok")), bad + (not result.get("ok"))
        print(json.dumps({"fulfilled": ok, "failed": bad}))
        return 0 if bad == 0 else 1
    if args.cmd == "gc":
        print(json.dumps(gc(d, args.max_age_hours)))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
