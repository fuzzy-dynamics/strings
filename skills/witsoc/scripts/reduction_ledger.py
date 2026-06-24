#!/usr/bin/env python3
"""Reduction / obligation ledger — the conjecture-distance substrate (P1).

The progress grader used to measure `closed / total` over the SEEDED proof DAG.
That rewards closing whatever was seeded: discharge two trivial special cases of
Erdős–Straus and the closure ratio looks great even though the conjecture is
untouched. The seeded DAG is the wrong unit. The right unit is the gap between
what is proved and what the conjecture asks.

This module makes that gap a first-class, auditable artifact:

    target  ⟸  (every obligation discharged)  ∧  (open_core empty)

An obligation is a sub-claim that, together with the others, would imply the
target. The `open_core` is the explicitly-named residual that the current
obligations DO NOT cover — the hard part nobody has reduced yet (for
Erdős–Straus: the primes n ≡ 1 (mod 24) that resist the elementary families).

Honesty contract (this is the whole point):
  * Progress toward the TARGET is bounded LOW while the open_core has any open
    entry or the reduction is unjustified — because closing easy obligations is
    NOT progress on the conjecture if the hard core is still open.
  * Only when every obligation is discharged AND the open_core is empty AND the
    reduction is justified does the target count as reduced (progress uncapped).
  * This module never proves anything and never upgrades a status. It records
    statuses set by the kernel/checker gates elsewhere and computes an honest
    cap from them.

Statuses (obligations and open_core entries share this lattice):
    OPEN          — stated, not discharged
    FORMALIZED    — elaborates in Lean, dispatchable, still not proved
    DISCHARGED    — kernel/verifier-closed (CHECKED/VERIFIED/PROOF_DISCHARGED)
    REFUTED       — shown false (kills the whole reduction; surfaced loudly)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

LEDGER_NAME = "reduction_ledger.json"
SCHEMA = "witsoc.reduction_ledger.v1"

# A discharged obligation/core entry is one closed by a kernel/verifier gate.
DISCHARGED_STATUSES = {"DISCHARGED", "CHECKED", "VERIFIED", "LEAN_VERIFIED",
                       "PROOF_DISCHARGED", "RECEIPT_ACCEPTED"}
REFUTED_STATUSES = {"REFUTED", "DISPROVEN", "FALSE"}
JUSTIFIED = {"ASSERTED", "KERNEL_CHECKED"}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ledger_path(run: Path) -> Path:
    return run / LEDGER_NAME


# --- target discovery (mirror decompose_problem.infer_target) -------------------
def infer_target(run: Path, explicit: str = "") -> tuple[str, str]:
    if explicit:
        return explicit, _hash(explicit)
    handoff = _load(run / "handoff_v1.json", {}) or {}
    for key in ("frozen_target", "target", "statement"):
        if handoff.get(key):
            t = str(handoff[key])
            return t, str(handoff.get("target_hash") or handoff.get("frozen_target_hash") or _hash(t))
    manifest = _load(run / "lovasz_run.json", {}) or {}
    if manifest.get("source_target_text"):
        t = str(manifest["source_target_text"])
        return t, str(manifest.get("target_hash") or _hash(t))
    return "UNSPECIFIED_TARGET", "UNKNOWN_TARGET_HASH"


# --- applicability (P3) ---------------------------------------------------------
_PLACEHOLDER = {"", "n/a", "na", "none", "tbd", "todo", "pending", "applies",
                "applicable", "relevant", "see above", "-", "."}


def applicability_ok(obligation: dict, target: str) -> tuple[bool, str]:
    """P3: an obligation only enters the reduction if it carries a SUBSTANTIVE
    justification of why it bears on THIS target. This is structural, not a
    string match on the problem name — the bug it prevents is the old
    `"erdos" in target` template that injected Erdős–Straus arithmetic into
    every Erdős problem. A bare `applies_because` (or a placeholder) is rejected,
    so an unrelated template cannot smuggle a node into the ledger.

    The check is deliberately permissive about CONTENT (the kernel judges the
    math; we cannot adjudicate relevance) but strict about PRESENCE: the
    fulfiller must have written a real reason. As a weak corroborating signal we
    also accept obligations whose statement shares a salient token with the
    target, but a written reason is always required."""
    reason = str(obligation.get("applies_because") or "").strip()
    if reason.lower() in _PLACEHOLDER:
        return False, "missing or placeholder `applies_because` (P3 applicability gate)"
    if len(reason) < 12:
        return False, "`applies_because` too short to be a real justification"
    # Reject the degenerate case where the 'reason' is just the statement echoed.
    stmt = str(obligation.get("statement") or obligation.get("lean_statement") or "").strip()
    if stmt and reason == stmt:
        return False, "`applies_because` merely echoes the statement, no relevance argument"
    return True, "ok"


# --- ledger construction --------------------------------------------------------
def _norm_status(s: Any) -> str:
    return str(s or "OPEN").upper()


def init(target: str, target_hash: str | None = None, *, domain: str = "",
         justification: str = "", justification_status: str = "UNJUSTIFIED") -> dict:
    return {
        "schema": SCHEMA,
        "target": target,
        "target_hash": target_hash or _hash(target),
        "domain": domain,
        "reduction": {
            "claim": "target ⟸ (all obligations discharged) ∧ (open_core empty)",
            "justification": justification,
            "justification_status": justification_status if justification_status in JUSTIFIED
            else "UNJUSTIFIED",
        },
        "obligations": [],
        "open_core": [],
        "notes": [],
    }


def load_or_init(run: Path, target: str = "", **kw) -> dict:
    existing = _load(ledger_path(run), None)
    if isinstance(existing, dict) and existing.get("schema") == SCHEMA:
        return existing
    t, h = infer_target(run, target)
    return init(t, h, **kw)


def _next_id(items: list[dict], prefix: str) -> str:
    n = len(items) + 1
    used = {str(i.get("id")) for i in items}
    while f"{prefix}{n}" in used:
        n += 1
    return f"{prefix}{n}"


def add_obligation(ledger: dict, statement: str, *, applies_because: str,
                   lean_statement: str = "", kind: str = "lemma",
                   covers: str = "", status: str = "OPEN",
                   source: str = "manual", oid: str = "") -> dict:
    """Add an obligation. Applicability (P3) is enforced by the caller via
    `applicability_ok`; this records what the gate accepted. Returns the row."""
    row = {
        "id": oid or _next_id(ledger["obligations"], "O"),
        "statement": statement,
        "lean_statement": lean_statement,
        "kind": kind,
        "covers": covers,
        "applies_because": applies_because,
        "status": _norm_status(status),
        "source": source,
        "discharged_by": None,
    }
    ledger["obligations"].append(row)
    return row


def add_open_core(ledger: dict, description: str, *, why_hard: str = "",
                  status: str = "OPEN", cid: str = "") -> dict:
    row = {
        "id": cid or _next_id(ledger["open_core"], "C"),
        "description": description,
        "why_hard": why_hard,
        "status": _norm_status(status),
    }
    ledger["open_core"].append(row)
    return row


def set_status(ledger: dict, oid: str, status: str, *, discharged_by: str = "") -> bool:
    for row in ledger["obligations"]:
        if str(row.get("id")) == oid:
            row["status"] = _norm_status(status)
            if discharged_by:
                row["discharged_by"] = discharged_by
            return True
    for row in ledger["open_core"]:
        if str(row.get("id")) == oid:
            row["status"] = _norm_status(status)
            return True
    return False


def set_justification(ledger: dict, justification: str, status: str = "ASSERTED") -> None:
    ledger["reduction"]["justification"] = justification
    ledger["reduction"]["justification_status"] = status if status in JUSTIFIED else "UNJUSTIFIED"


def set_reduction_goal(ledger: dict, lean_goal: str, imports: str = "") -> None:
    """Record the FORMAL reduction lemma — the Lean Prop stating
    `obligations ⟹ target`. Discharging it (verify_reduction) is what upgrades the
    reduction from ASSERTED to KERNEL_CHECKED."""
    ledger["reduction"]["lean_goal"] = lean_goal
    if imports:
        ledger["reduction"]["lean_imports"] = imports


def verify_reduction(ledger: dict, proof: str, *, lean_goal: str = "",
                     imports: str = "", lake_dir=None) -> dict:
    """Phase-1 honesty upgrade: kernel-check a PROOF of the reduction lemma
    (`obligations ⟹ target`). On a green, sorry/axiom-free proof, set the
    justification to KERNEL_CHECKED — the reduction step is no longer a fleet
    claim but a kernel fact. Sound by construction: the kernel is the only judge.
    Returns {ok, status, error?}."""
    goal = lean_goal or ledger.get("reduction", {}).get("lean_goal") or ""
    imp = imports or ledger.get("reduction", {}).get("lean_imports") or ""
    if not goal.strip():
        return {"ok": False, "error": "no reduction lean_goal set (set_reduction_goal first)"}
    if not (isinstance(proof, str) and proof.strip()):
        return {"ok": False, "error": "empty proof"}
    try:
        import close_obligation as co
        import witcore
        src = co.lean_source("reduction", goal, imp, proof)
        verdict = witcore.lean_verify_cached(src, lake_dir)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if verdict.get("verified"):
        ledger["reduction"]["justification_status"] = "KERNEL_CHECKED"
        ledger["reduction"]["reduction_proof"] = proof
        return {"ok": True, "status": "KERNEL_CHECKED"}
    # honest env classification: a Mathlib-only tactic that core Lean can't run is
    # an environment blocker, not a bad reduction.
    try:
        import witcore
        blk = witcore.classify_lean_env_blocker(verdict, src)
    except Exception:
        blk = None
    return {"ok": False, "status": "ENV_BLOCKED" if blk else "FAILED",
            "env_blocker": blk, "error": "reduction proof failed kernel verification"}


# --- completeness auditor (Phase 1): hunt for coverage holes --------------------
COVERAGE_AUDIT_INSTRUCTIONS = (
    "ADVERSARIAL completeness audit of a reduction. You are given the target and "
    "the list of cases it is decomposed into: the `covers` of each obligation plus "
    "the `open_core` descriptions. Try to exhibit a concrete instance that "
    "satisfies the target's hypotheses but is covered by NEITHER an obligation NOR "
    "an open_core item — a coverage hole that would make the decomposition unsound. "
    "Reply {\"hole_found\": bool, \"uncovered_case\": str, \"reasoning\": str}. If "
    "the cases provably tile the whole space, reply {\"hole_found\": false}. Do not "
    "invent a hole; default to false when the cover looks exhaustive.")


def coverage_summary(ledger: dict) -> dict:
    """The claimed coverage of the target: every obligation's `covers` + the
    open_core descriptions. This is what the auditor checks for exhaustiveness."""
    return {
        "target": ledger.get("target"),
        "obligation_covers": [{"id": o.get("id"), "covers": o.get("covers") or o.get("statement")}
                              for o in ledger.get("obligations", [])],
        "open_core": [{"id": c.get("id"), "description": c.get("description")}
                      for c in ledger.get("open_core", [])],
    }


def set_coverage_hole(ledger: dict, uncovered_case: str, reasoning: str = "") -> None:
    ledger["reduction"]["coverage_hole"] = {"uncovered_case": uncovered_case, "reasoning": reasoning}


def clear_coverage_hole(ledger: dict) -> None:
    ledger["reduction"].pop("coverage_hole", None)


def coverage_audit_done(run: Path) -> bool:
    """True once a coverage_audit bus request exists (pending/fulfilled) for this
    run — so `witsoc next` does not re-request it every turn."""
    try:
        import request_bus as rb
        return any(r.get("role") == "coverage_audit"
                   for r in rb.requests_by_id(run / "bus").values())
    except Exception:
        return False


def needs_coverage_audit(run: Path) -> bool:
    """After obligations are seeded, the reduction should be completeness-audited
    once: obligations exist, no audit emitted yet, no verdict recorded."""
    led = _load(ledger_path(run), None)
    if not (isinstance(led, dict) and led.get("obligations")):
        return False
    if led.get("reduction", {}).get("coverage_audit_verdict") is not None:
        return False
    return not coverage_audit_done(run)


def request_coverage_audit(run: Path, *, bus_dir: Path | None = None) -> dict:
    """Emit one coverage_audit bus request carrying the claimed coverage."""
    led = _load(ledger_path(run), None)
    if not (isinstance(led, dict) and led.get("obligations")):
        return {"status": "no_obligations"}
    if coverage_audit_done(run):
        return {"status": "already_requested"}
    try:
        import request_bus as rb
        res = rb.emit({"task": "coverage_audit", "target": led.get("target"),
                       "coverage": coverage_summary(led),
                       "instructions": COVERAGE_AUDIT_INSTRUCTIONS},
                      role="coverage_audit", priority=7, d=bus_dir or (run / "bus"))
        return {"status": "coverage_audit_emitted", "request_id": res.get("id")}
    except Exception as exc:
        return {"status": "emit_failed", "error": str(exc)}


# --- orchestrator wiring: make the ledger a first-class step of the loop --------
SEED_INSTRUCTIONS = (
    "Decompose THIS target into a problem-specific reduction. Reply "
    "{\"obligations\": [{\"statement\", \"lean_statement\"?, \"applies_because\", "
    "\"covers\"?, \"kind\"?}], \"open_core\": [{\"description\", \"why_hard\"?}], "
    "\"reduction_justification\"}. Each obligation needs a REAL relevance argument "
    "(applies_because) or it is rejected. Be HONEST about open_core — naming the "
    "hard residual you cannot reduce is the point; an empty open_core claims the "
    "obligations fully reduce the target. Obligations enter OPEN/FORMALIZED, never "
    "proved.")


def seed_request_exists(run: Path) -> bool:
    """True if a seed_lemmas bus request has already been emitted for this run
    (pending or fulfilled) — so seeding is not re-triggered every turn."""
    try:
        import request_bus as rb
        return any(r.get("role") == "seed_lemmas"
                   for r in rb.requests_by_id(run / "bus").values())
    except Exception:
        return False


def has_obligations(run: Path) -> bool:
    led = _load(ledger_path(run), None)
    return bool(isinstance(led, dict) and led.get("obligations"))


def needs_seeding(run: Path) -> bool:
    """The orchestrator should seed the reduction when the run has a frozen
    target but neither obligations nor an outstanding seed_lemmas request."""
    manifest = _load(run / "lovasz_run.json", {}) or {}
    if not manifest:
        return False
    return not has_obligations(run) and not seed_request_exists(run)


def seed_request(run: Path, *, domain: str = "", bus_dir: Path | None = None) -> dict:
    """Initialize the reduction ledger (if absent) and emit ONE seed_lemmas bus
    request so the orchestrator/fleet supplies the problem-specific obligations +
    honest open_core. Idempotent: a second call with a request already present is
    a no-op. This is the seam that connects the keystone to `witsoc next`."""
    target, target_hash = infer_target(run)
    if _load(ledger_path(run), None) is None:
        _save(ledger_path(run), init(target, target_hash, domain=domain))
    if seed_request_exists(run):
        return {"status": "already_seeded", "target": target}
    bus = bus_dir or (run / "bus")
    try:
        import request_bus as rb
        res = rb.emit({"task": "seed_lemmas", "target": target, "domain": domain,
                       "instructions": SEED_INSTRUCTIONS},
                      role="seed_lemmas", priority=8, d=bus)
        return {"status": "seed_request_emitted", "request_id": res.get("id"), "target": target}
    except Exception as exc:
        return {"status": "emit_failed", "error": str(exc)}


# --- assessment (the honesty engine) --------------------------------------------
def assess(ledger: dict) -> dict:
    obs = ledger.get("obligations", []) or []
    core = ledger.get("open_core", []) or []

    n_ob = len(obs)
    discharged = [o for o in obs if _norm_status(o.get("status")) in DISCHARGED_STATUSES]
    refuted = [o for o in obs if _norm_status(o.get("status")) in REFUTED_STATUSES]
    open_ob = [o for o in obs if o not in discharged and o not in refuted]

    n_core = len(core)
    core_discharged = [c for c in core if _norm_status(c.get("status")) in DISCHARGED_STATUSES]
    core_open = [c for c in core if c not in core_discharged]

    coverage = (len(discharged) / n_ob) if n_ob else 0.0
    jstatus = ledger.get("reduction", {}).get("justification_status")
    justified = jstatus in JUSTIFIED
    kernel_checked = jstatus == "KERNEL_CHECKED"
    # A coverage hole (Phase-1 completeness auditor): the fleet's obligations ∪
    # open_core do NOT cover the target's whole case space — a case was found that
    # neither handles. That makes the decomposition UNSOUND, not merely incomplete.
    coverage_hole = ledger.get("reduction", {}).get("coverage_hole")

    # "complete" = the decomposition leaves nothing open (every obligation
    # discharged, no open_core open, nothing refuted). Genuinely "reduced" (the
    # target is solved modulo a sound reduction) requires complete AND the
    # reduction step itself kernel-checked.
    complete = bool(n_ob) and not open_ob and not core_open and not refuted
    reduced = complete and kernel_checked and not coverage_hole

    # --- the honest progress cap toward the TARGET ---
    if refuted:
        cap, band = 5.0, "REFUTED_OBLIGATION"
        note = ("an obligation was REFUTED — the reduction is broken; "
                "fix the decomposition before claiming progress")
    elif coverage_hole:
        cap, band = 5.0, "COVERAGE_HOLE"
        note = ("completeness audit found a case covered by NEITHER an obligation "
                f"nor open_core: {str(coverage_hole.get('uncovered_case'))[:120]} — "
                "the decomposition is unsound until the hole is closed")
    elif complete and kernel_checked:
        cap, band = 100.0, "REDUCED"
        note = ("target REDUCED: all obligations discharged, open_core empty, and the "
                "reduction obligations⟹target is KERNEL-CHECKED")
    elif complete and justified:
        # everything discharged and the reduction is ASSERTED (fleet claim) but not
        # kernel-proven — real, but the implication itself is unverified.
        cap, band = 85.0, "REDUCED_ASSERTED"
        note = ("all obligations discharged + open_core empty, but the reduction "
                "obligations⟹target is only ASSERTED — kernel-check it to reach REDUCED")
    elif complete and not justified:
        cap, band = 45.0, "UNJUSTIFIED_REDUCTION"
        note = ("all obligations and core discharged but the reduction is "
                "UNJUSTIFIED — assert/kernel-check that they imply the target")
    elif not core_open:
        # The hard core is covered/closed; remaining work is the named obligations.
        cap, band = 40.0 + 40.0 * coverage, "CORE_CLOSED_OBLIGATIONS_OPEN"
        note = (f"open_core fully addressed; {len(discharged)}/{n_ob} obligations "
                "discharged — genuine reduction progress, target not yet closed")
    else:
        # The hard core is still OPEN — closing easy obligations is not progress on
        # the conjecture. The Erdős–Straus lesson made mechanical.
        cap, band = 8.0 + 12.0 * coverage, "OPEN_CORE_OPEN"
        note = (f"{len(core_open)} open_core item(s) OPEN: closing the "
                f"{len(discharged)}/{n_ob} easy obligations is NOT progress on the "
                "conjecture while the hard core is open")

    return {
        "schema": "witsoc.reduction_assessment.v1",
        "target_hash": ledger.get("target_hash"),
        "obligations_total": n_ob,
        "obligations_discharged": len(discharged),
        "obligations_open": len(open_ob),
        "obligations_refuted": len(refuted),
        "open_core_total": n_core,
        "open_core_open": len(core_open),
        "coverage": round(coverage, 3),
        "justified": justified,
        "justification_status": jstatus or "UNJUSTIFIED",
        "kernel_checked": kernel_checked,
        "coverage_hole": bool(coverage_hole),
        "complete": complete,
        "reduced": reduced,
        "progress_cap": round(cap, 2),
        "band": band,
        "cap_note": note,
    }


def solve_ready(ledger: dict) -> bool:
    """STANDALONE substrate gate the orchestrator/Explorer calls to decide
    solve-readiness without the grader. True only when the target is genuinely
    REDUCED: complete, kernel-checked reduction, no coverage hole. An open_core,
    an only-ASSERTED reduction, or a coverage hole all return False."""
    return bool(assess(ledger)["reduced"])


def auto_discharge(ledger: dict, *, lake_dir=None, search: bool = False,
                   max_obligations: int = 50) -> dict:
    """Phase-3 autonomy bet: witsoc discharges its OWN formalized obligations,
    with NO fleet. For each obligation carrying a lean_statement, run the
    in-process prover (close_obligation: learned portfolio + premise retrieval +
    optional compound search), and on a kernel-checked, sorry/axiom-free proof
    flip it to DISCHARGED. Honest about reach: in a core-only environment only
    goals provable without Mathlib close (rfl/decide/omega/simp/grind); harder
    goals stay open and are reported as such, not silently failed. With a Mathlib
    toolchain the same call closes much more — this is the fuel-gated frontier.

    Returns {attempted, discharged, env_blocked, results}. Mutates the ledger."""
    try:
        import close_obligation as co
    except Exception as exc:
        return {"error": f"prover unavailable: {exc}", "attempted": 0, "discharged": 0}
    results = []
    attempted = discharged = env_blocked = 0
    for ob in ledger.get("obligations", []):
        if _norm_status(ob.get("status")) in DISCHARGED_STATUSES:
            continue
        goal = str(ob.get("lean_statement") or "").strip()
        if not goal:
            results.append({"id": ob.get("id"), "discharged": False, "reason": "informal (no lean_statement)"})
            continue
        if attempted >= max_obligations:
            break
        attempted += 1
        imports = str(ob.get("lean_imports") or "")
        try:
            rec = co.close_goal(goal, imports=imports, lake_dir=lake_dir, search=search,
                                out_ledger=None)
        except Exception as exc:
            results.append({"id": ob.get("id"), "discharged": False, "error": str(exc)})
            continue
        if rec.get("discharged"):
            ob["status"] = "DISCHARGED"
            ob["discharged_by"] = f"auto_prover:{rec.get('proof')}"
            discharged += 1
            results.append({"id": ob.get("id"), "discharged": True, "proof": rec.get("proof")})
        else:
            label = rec.get("label")
            if label == "UNCHECKED_NO_TOOLCHAIN":
                env_blocked += 1
            results.append({"id": ob.get("id"), "discharged": False, "label": label})
    return {"schema": "witsoc.auto_discharge.v1", "attempted": attempted,
            "discharged": discharged, "env_blocked": env_blocked,
            "no_fleet": True, "results": results}


# --- CLI ------------------------------------------------------------------------
def _cmd_init(args) -> dict:
    led = load_or_init(args.run_dir, args.target, domain=args.domain)
    _save(ledger_path(args.run_dir), led)
    return {"created": str(ledger_path(args.run_dir)), "target": led["target"]}


def _cmd_add_obligation(args) -> dict:
    led = load_or_init(args.run_dir)
    ok, why = applicability_ok({"statement": args.statement,
                                "applies_because": args.applies_because}, led["target"])
    if not ok:
        return {"rejected": True, "reason": why}
    row = add_obligation(led, args.statement, applies_because=args.applies_because,
                         lean_statement=args.lean_statement or "", kind=args.kind,
                         covers=args.covers or "", status=args.status, source="cli")
    _save(ledger_path(args.run_dir), led)
    return {"added_obligation": row["id"]}


def _cmd_add_core(args) -> dict:
    led = load_or_init(args.run_dir)
    row = add_open_core(led, args.description, why_hard=args.why_hard or "", status=args.status)
    _save(ledger_path(args.run_dir), led)
    return {"added_open_core": row["id"]}


def _cmd_set_status(args) -> dict:
    led = load_or_init(args.run_dir)
    ok = set_status(led, args.id, args.status, discharged_by=args.discharged_by or "")
    _save(ledger_path(args.run_dir), led)
    return {"updated": ok, "id": args.id, "status": args.status}


def _cmd_auto_discharge(args) -> dict:
    led = load_or_init(args.run_dir)
    out = auto_discharge(led, search=args.search)
    _save(ledger_path(args.run_dir), led)
    out["assessment"] = assess(led)
    return out


def _cmd_assess(args) -> dict:
    led = load_or_init(args.run_dir)
    return assess(led)


def _cmd_verify(args) -> dict:
    led = load_or_init(args.run_dir)
    if args.lean_goal:
        set_reduction_goal(led, args.lean_goal, args.imports)
    out = verify_reduction(led, args.proof, lean_goal=args.lean_goal, imports=args.imports)
    _save(ledger_path(args.run_dir), led)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--target", default="")
    p.add_argument("--domain", default="")
    p.set_defaults(fn=_cmd_init)

    p = sub.add_parser("add-obligation")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--statement", required=True)
    p.add_argument("--applies-because", required=True)
    p.add_argument("--lean-statement", default="")
    p.add_argument("--kind", default="lemma")
    p.add_argument("--covers", default="")
    p.add_argument("--status", default="OPEN")
    p.set_defaults(fn=_cmd_add_obligation)

    p = sub.add_parser("add-open-core")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--description", required=True)
    p.add_argument("--why-hard", default="")
    p.add_argument("--status", default="OPEN")
    p.set_defaults(fn=_cmd_add_core)

    p = sub.add_parser("set-status")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--discharged-by", default="")
    p.set_defaults(fn=_cmd_set_status)

    p = sub.add_parser("assess")
    p.add_argument("run_dir", type=Path)
    p.set_defaults(fn=_cmd_assess)

    p = sub.add_parser("seed", help="init the ledger + emit a seed_lemmas bus request")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--domain", default="")
    p.add_argument("--bus-dir", type=Path, default=None)
    p.set_defaults(fn=lambda a: seed_request(a.run_dir, domain=a.domain, bus_dir=a.bus_dir))

    p = sub.add_parser("audit-coverage", help="emit an adversarial coverage_audit bus request")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--bus-dir", type=Path, default=None)
    p.set_defaults(fn=lambda a: request_coverage_audit(a.run_dir, bus_dir=a.bus_dir))

    p = sub.add_parser("verify", help="kernel-check a proof of the reduction lemma (obligations⟹target)")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--lean-goal", default="")
    p.add_argument("--imports", default="")
    p.add_argument("--proof", required=True)
    p.set_defaults(fn=lambda a: _cmd_verify(a))

    p = sub.add_parser("auto-discharge",
                       help="witsoc's OWN prover attacks formalized obligations (no fleet)")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--search", action="store_true", help="escalate to compound proof search")
    p.set_defaults(fn=_cmd_auto_discharge)

    args = ap.parse_args()
    print(json.dumps(args.fn(args), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
