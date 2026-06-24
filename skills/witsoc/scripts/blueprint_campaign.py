#!/usr/bin/env python3
"""F3 blueprint formalization campaign — `witsoc blueprint`.

The bridge from MATHEMATICAL_SOLVE to FORMAL_SOLVE: a proof DAG becomes a
Lean BLUEPRINT — a persistent, resumable ledger of formalization obligations
ground down over days by parallel workers, exactly how large formalizations
(PFR, FLT-blueprint projects) actually work. Without this, the two-stage
success rule has no operational second stage.

State lives in <run_dir>/blueprint.json:
  obligations   one per DAG node: lean_statement, dependencies, status
                  PENDING       not yet attempted (or unblocked again)
                  READY         all dependencies VERIFIED — dispatchable now
                  VERIFIED      kernel-verified (proof recorded)
                  FAILED        attempted, honest failure recorded
                  THEORY_GAP    blocked on missing theory (unknown identifiers)
  theory_gaps   F3 library-campaign mode: unknown-identifier diagnostics from
                failed attempts become PREREQUISITE THEORY obligations (define
                the identifier + its API lemmas). A node with open theory gaps
                stays THEORY_GAP; closing the last gap re-opens it to PENDING.

Commands:
  init <run>          build the blueprint from proof_dependency_dag.json
                      (nodes already VERIFIED_LEAN enter as VERIFIED)
  status <run>        progress: counts, ready frontier, gap list
  next <run>          the READY obligations (dependency-ordered), for workers
  record <run> --node N --status VERIFIED|FAILED [--proof P] [--failure TEXT]
                      record a worker result; unknown-identifier failures
                      auto-create theory gaps
  record-theory <run> --gap ID --status VERIFIED [--evidence E]
                      close a theory obligation; dependents may unblock
  dispatch <run> [--limit K] run the kernel prover on up to K ready
                      obligations and record results automatically

Statuses here are blueprint workflow states, not claim statuses; the claim
lattice is untouched. A finished blueprint (all obligations VERIFIED) is the
evidence a FORMAL_SOLVE claim needs — reported through solve_claim_protocol,
never from here.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

_UNKNOWN_ID_RE = re.compile(r"unknown (?:identifier|constant) '([^']+)'")
VERIFIED_DAG_STATUSES = {"VERIFIED", "VERIFIED_LEAN", "VERIFIED_WIT", "VERIFIED_EXTERNAL"}


def blueprint_path(run: Path) -> Path:
    return run / "blueprint.json"


def load_blueprint(run: Path) -> dict:
    data = witcore.load_json(blueprint_path(run), None)
    if not (isinstance(data, dict) and data.get("schema") == "witsoc.blueprint.v1"):
        raise SystemExit(f"no blueprint.json in {run}; run `blueprint init` first")
    return data


def save_blueprint(run: Path, bp: dict) -> None:
    refresh_ready(bp)
    witcore.save_json(blueprint_path(run), bp)
    try:
        import run_ledger
        run_ledger.auto_ingest(run)  # R1.5: the unified ledger stays fresh
    except Exception:
        pass


def refresh_ready(bp: dict) -> None:
    """PENDING -> READY when every dependency is VERIFIED; THEORY_GAP -> PENDING
    when every referenced theory gap is closed."""
    obligations = bp["obligations"]
    gaps = bp.get("theory_gaps", {})
    for ob in obligations.values():
        if ob["status"] == "THEORY_GAP":
            if all(gaps.get(g, {}).get("status") == "VERIFIED" for g in ob.get("blocked_on_gaps", [])):
                ob["status"] = "PENDING"
                ob["blocked_on_gaps"] = []
    for ob in obligations.values():
        if ob["status"] == "PENDING":
            deps = ob.get("dependencies", [])
            if all(obligations.get(d, {}).get("status") == "VERIFIED" for d in deps if d in obligations):
                ob["status"] = "READY"


def init_blueprint(run: Path) -> dict:
    dag = witcore.load_json(run / "proof_dependency_dag.json", [])
    dag = [n for n in dag if isinstance(n, dict)] if isinstance(dag, list) else []
    if not dag:
        raise SystemExit(f"no proof_dependency_dag.json in {run}")
    manifest = witcore.load_json(run / "lovasz_run.json", {})
    obligations: dict[str, dict] = {}
    for i, node in enumerate(dag):
        nid = str(node.get("node_id") or node.get("id") or f"node{i}")
        status = "VERIFIED" if str(node.get("status") or "") in VERIFIED_DAG_STATUSES else "PENDING"
        obligations[nid] = {
            "node_id": nid,
            "statement": str(node.get("statement") or ""),
            "lean_statement": node.get("lean_statement"),
            "lean_imports": str(node.get("lean_imports") or ""),
            # Ω7 (the SorryDB lesson): provers do far better WITH a sketch —
            # carry the node's informal proof sketch into the obligation.
            "sketch": str(node.get("informal_sketch") or node.get("proof_idea") or ""),
            "dependencies": [str(d) for d in (node.get("dependencies") or [])],
            "status": status,
            "attempts": 0,
            "proof": node.get("proof") if status == "VERIFIED" else None,
            "last_failure": None,
            "blocked_on_gaps": [],
        }
    bp = {
        "schema": "witsoc.blueprint.v1",
        "run_dir": str(run),
        "target_hash": str(manifest.get("target_hash") or "") if isinstance(manifest, dict) else "",
        "obligations": obligations,
        "theory_gaps": {},
        "note": ("blueprint workflow states, not claim statuses; an all-VERIFIED blueprint is "
                 "FORMAL_SOLVE evidence reported only through solve_claim_protocol"),
    }
    save_blueprint(run, bp)
    return bp


def stats(bp: dict) -> dict:
    counts: dict[str, int] = {}
    for ob in bp["obligations"].values():
        counts[ob["status"]] = counts.get(ob["status"], 0) + 1
    gaps = bp.get("theory_gaps", {})
    total = len(bp["obligations"])
    return {
        "obligations": total,
        "counts": counts,
        "verified_fraction": round(counts.get("VERIFIED", 0) / total, 4) if total else 0.0,
        "ready_frontier": sorted(n for n, ob in bp["obligations"].items() if ob["status"] == "READY"),
        "theory_gaps_open": sorted(g for g, e in gaps.items() if e.get("status") != "VERIFIED"),
        "complete": counts.get("VERIFIED", 0) == total,
    }


def ready_obligations(bp: dict) -> tuple[list[dict], list[str]]:
    out = [ob for ob in bp["obligations"].values() if ob["status"] == "READY" and ob.get("lean_statement")]
    unformalized = [ob["node_id"] for ob in bp["obligations"].values()
                    if ob["status"] == "READY" and not ob.get("lean_statement")]
    out.sort(key=lambda ob: ob["attempts"])
    return out, unformalized


def record_result(run: Path, bp: dict, node_id: str, status: str,
                  proof: str | None, failure: str | None) -> dict:
    ob = bp["obligations"].get(node_id)
    if ob is None:
        return {"error": f"unknown obligation {node_id!r}"}
    ob["attempts"] += 1
    if status == "VERIFIED":
        if not proof:
            return {"error": "recording VERIFIED requires --proof (the kernel-checked proof text)"}
        ob["status"] = "VERIFIED"
        ob["proof"] = proof
        ob["last_failure"] = None
    else:
        ob["last_failure"] = failure or "unspecified failure"
        # F3 library-campaign mode: unknown identifiers become prerequisite
        # THEORY obligations; the node waits on them instead of burning retries.
        missing = sorted(set(_UNKNOWN_ID_RE.findall(failure or "")))
        if missing:
            ob["status"] = "THEORY_GAP"
            ob["blocked_on_gaps"] = []
            for ident in missing:
                gid = f"theory:{ident}"
                bp.setdefault("theory_gaps", {})[gid] = bp["theory_gaps"].get(gid) or {
                    "gap_id": gid,
                    "identifier": ident,
                    "obligation": (f"define `{ident}` (or import/state its existing form) and prove the "
                                   "API lemmas the blocked nodes need; the definition file is itself a "
                                   "kernel-checked artifact"),
                    "status": "OPEN",
                    "blocked_nodes": [],
                }
                entry = bp["theory_gaps"][gid]
                if node_id not in entry["blocked_nodes"]:
                    entry["blocked_nodes"].append(node_id)
                ob["blocked_on_gaps"].append(gid)
        else:
            ob["status"] = "FAILED"
    save_blueprint(run, bp)
    return {"node_id": node_id, "status": ob["status"],
            "theory_gaps_created": ob.get("blocked_on_gaps", []), **stats(bp)}


def design_theory(run: Path, bp: dict, gap_id: str) -> dict:
    """Ω8 definition-first library campaigns (the Buzzard bottleneck:
    'definitions/library coverage are what block research formalization').
    For a theory gap, the fleet DESIGNS the missing definition plus its API
    lemmas; the definition is elaboration-probed by the real compiler, and
    the API lemmas enter the lemma pool as bridging targets. Without a fleet
    the obligation template is recorded for a human/worker."""
    gap = bp.get("theory_gaps", {}).get(gap_id)
    if gap is None:
        return {"error": f"unknown theory gap {gap_id!r}"}
    import sampler_fleet as sf
    fleet = sf.samplers()
    if not fleet:
        gap["design"] = {"designed": False,
                         "template": {"identifier": gap["identifier"],
                                      "needs": ["a Lean definition", "2-3 API lemmas the blocked "
                                                "nodes require", "kernel-checked definition file"]}}
        save_blueprint(run, bp)
        return {"designed": False, "reason": "no sampler fleet; obligation template recorded"}
    theory_ctx = None
    try:
        import problem_theory as pt
        if pt.theory_path(run).exists():
            theory_ctx = pt.prompt_context(run)
    except Exception:
        pass
    reply = witcore.run_sampler(fleet[0]["command"], {
        "task": "design_definition",
        "identifier": gap["identifier"],
        "blocked_nodes": gap.get("blocked_nodes", []),
        "problem_theory": theory_ctx or {},
        "rules": "Return {lean_definition: \"def ... \", api_lemmas: [Lean Prop strings the blocked "
                 "nodes need about this definition]}. Lean 4, no sorry/axiom.",
    })
    lean_def = str((reply or {}).get("lean_definition") or "").strip()
    if not lean_def or any(t in lean_def for t in ("sorry", "axiom")):
        return {"designed": False, "reason": "fleet returned no clean definition"}
    # elaboration probe: the definition must compile standalone
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as fh:
        fh.write(lean_def + "\n")
        tmp = Path(fh.name)
    try:
        verdict = witcore.lean_verify(tmp, None)
    finally:
        tmp.unlink(missing_ok=True)
    compiles = bool(verdict.get("build", {}).get("ok"))
    api = [str(a) for a in (reply.get("api_lemmas") or [])][:4]
    proposed = 0
    if compiles:
        try:
            import lemma_pool as lp
            for stmt in api:
                out = lp.propose(run, stmt, origin=f"theory_design:{gap_id}",
                                 imports="")
                proposed += int(bool(out.get("proposed")))
        except Exception:
            pass
    gap["design"] = {"designed": compiles, "lean_definition": lean_def,
                     "definition_compiles": compiles, "api_lemmas": api,
                     "api_proposed_to_pool": proposed}
    save_blueprint(run, bp)
    return {"designed": compiles, "definition_compiles": compiles,
            "api_lemmas": len(api), "api_proposed_to_pool": proposed}


def dispatch(run: Path, bp: dict, limit: int, search: bool, timeout: float) -> dict:
    """Run the kernel prover on up to `limit` READY obligations and record the
    results. Long-horizon by design: call repeatedly (or from cron) until the
    frontier is empty."""
    ready, unformalized = ready_obligations(bp)
    results = []
    for ob in ready[:limit]:
        # R3: in-process prover — shared imports and Lean cache across the batch.
        try:
            import close_obligation as co
            reply = co.close_goal(str(ob["lean_statement"]), name=f"bp_{ob['node_id']}",
                                  imports=str(ob.get("lean_imports") or ""), search=search)
        except Exception as exc:
            reply = {"discharged": False, "label": "DISPATCH_ERROR", "_error": str(exc)}
        if reply.get("discharged"):
            outcome = record_result(run, bp, ob["node_id"], "VERIFIED", str(reply.get("proof")), None)
        else:
            failure = f"{reply.get('label')}: {reply.get('_error') or 'portfolio/search did not close the goal'}"
            outcome = record_result(run, bp, ob["node_id"], "FAILED", None, failure)
        results.append({"node_id": ob["node_id"], "label": reply.get("label"),
                        "status": outcome.get("status")})
    return {"dispatched": len(results), "results": results,
            "unformalized_ready": unformalized, **stats(bp)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "status", "next"):
        p = sub.add_parser(name)
        p.add_argument("run_dir", type=Path)
    p_rec = sub.add_parser("record")
    p_rec.add_argument("run_dir", type=Path)
    p_rec.add_argument("--node", required=True)
    p_rec.add_argument("--status", choices=("VERIFIED", "FAILED"), required=True)
    p_rec.add_argument("--proof", default=None)
    p_rec.add_argument("--failure", default=None)
    p_th = sub.add_parser("record-theory")
    p_th.add_argument("run_dir", type=Path)
    p_th.add_argument("--gap", required=True)
    p_th.add_argument("--status", choices=("VERIFIED", "FAILED"), required=True)
    p_th.add_argument("--evidence", default="")
    p_dt = sub.add_parser("design-theory")
    p_dt.add_argument("run_dir", type=Path)
    p_dt.add_argument("--gap", required=True)
    p_disp = sub.add_parser("dispatch")
    p_disp.add_argument("run_dir", type=Path)
    p_disp.add_argument("--limit", type=int, default=4)
    p_disp.add_argument("--search", action="store_true")
    p_disp.add_argument("--timeout", type=float, default=900.0)
    args = ap.parse_args()

    if args.cmd == "init":
        bp = init_blueprint(args.run_dir)
        result: dict[str, Any] = {"initialized": True, **stats(bp)}
    elif args.cmd == "status":
        result = stats(load_blueprint(args.run_dir))
    elif args.cmd == "next":
        bp = load_blueprint(args.run_dir)
        ready, unformalized = ready_obligations(bp)
        result = {"ready": [{k: ob.get(k) for k in ("node_id", "lean_statement", "lean_imports",
                                                    "sketch", "attempts")}
                            for ob in ready],
                  "unformalized_ready": unformalized}
    elif args.cmd == "record":
        bp = load_blueprint(args.run_dir)
        result = record_result(args.run_dir, bp, args.node, args.status, args.proof, args.failure)
    elif args.cmd == "design-theory":
        bp = load_blueprint(args.run_dir)
        result = design_theory(args.run_dir, bp, args.gap)
    elif args.cmd == "record-theory":
        bp = load_blueprint(args.run_dir)
        gap = bp.get("theory_gaps", {}).get(args.gap)
        if gap is None:
            result = {"error": f"unknown theory gap {args.gap!r}"}
        else:
            gap["status"] = args.status
            if args.evidence:
                gap["evidence"] = args.evidence
            save_blueprint(args.run_dir, bp)
            result = {"gap": args.gap, "status": args.status, **stats(bp)}
    elif args.cmd == "dispatch":
        bp = load_blueprint(args.run_dir)
        result = dispatch(args.run_dir, bp, args.limit, args.search, args.timeout)
    else:
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
