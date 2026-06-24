#!/usr/bin/env python3
"""Top-tier Lovasz control surface.

This is the deterministic checklist for plan items 2-12:

  2 barrier attacks are the core loop
  3 rungs are saturated and scored
  4 Lean generation is hole-free
  5 mathematical roles use strict packets
  6 failure memory blocks repeat routes
  7 novelty/literature discipline is present
  8 full-solve claims require the strict protocol
  9 search/computation engines are available and mapped
 10 each campaign loop learns or escalates
 11 rediscovery benchmark is runnable
 12 success is measured by honest, auditable criteria

The command never verifies mathematics. It prepares/audits the machinery that
keeps Lovasz ambitious without letting it report fake solves.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import barrier_attack  # noqa: E402
import lovasz_agent_packets as packets  # noqa: E402
import rung_saturation  # noqa: E402
import witcore  # noqa: E402

REQUIRED_ROLES = sorted(packets.ROLES)
FORBIDDEN_LEAN_TOKENS = ("sorry", "admit", "sorryAx", "axiom", "opaque", "unsafe", "constant")
ENGINE_ARMS = {
    "direct_prover": "kernel proof search",
    "premise_retrieval": "known theorem retrieval",
    "analogical_transfer": "technique priors",
    "speculative_arena": "bridge promotion",
    "conjecture_mining": "empirical lemma mining",
    "counterexample_search": "bounded falsification",
    "finite_reduction": "SAT/finite certificates",
    "construction_search": "object/construction search",
    "ontology_pivot": "encoding shift",
    "invention": "definition synthesis",
}


def _load(path: Path, default: Any) -> Any:
    return witcore.load_json(path, default)


def _manifest_context(run: Path) -> tuple[str, str, str | None, str]:
    manifest = _load(run / "lovasz_run.json", {})
    manifest = manifest if isinstance(manifest, dict) else {}
    target = str(manifest.get("source_target_text") or manifest.get("target") or "unspecified target")
    domain = str(manifest.get("domain") or "other")
    lean = manifest.get("lean_target") or manifest.get("frozen_lean_target")
    target_hash = str(manifest.get("target_hash") or rung_saturation.sha(target))
    return target, domain, str(lean) if lean else None, target_hash


def _check(name: str, ok: bool, detail: str, evidence: Any = None) -> dict[str, Any]:
    out = {"item": name, "ok": bool(ok), "detail": detail}
    if evidence is not None:
        out["evidence"] = evidence
    return out


def _lean_files(run: Path) -> list[Path]:
    return sorted(p for p in run.rglob("*.lean") if p.is_file())


def audit_hole_free_lean(run: Path) -> dict[str, Any]:
    offenders: list[dict[str, str]] = []
    for path in _lean_files(run):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for token in FORBIDDEN_LEAN_TOKENS:
            if re.search(rf"\b{re.escape(token)}\b", text):
                offenders.append({"file": str(path), "token": token})
                break
    return {
        "files_scanned": len(_lean_files(run)),
        "offenders": offenders,
        "ok": not offenders,
    }


def prepare(run: Path, *, target: str | None = None, domain: str | None = None,
            lean_target: str | None = None, top_rungs: int = 32) -> dict[str, Any]:
    """Materialize all planning artifacts needed for a top-tier open run."""
    run = Path(run)
    t, d, lean, _ = _manifest_context(run)
    t = target or t
    d = domain or d
    lean = lean_target or lean
    manifest = _load(run / "lovasz_run.json", {})
    if isinstance(manifest, dict):
        manifest.setdefault("source_target_text", t)
        manifest["domain"] = d
        if lean:
            manifest["lean_target"] = lean
        manifest.setdefault("target_hash", rung_saturation.sha(t))
        witcore.save_json(run / "lovasz_run.json", manifest)
    barrier = barrier_attack.prepare_run(run, target=t, domain=d, lean_target=lean, top_rungs=top_rungs)
    role_dir = run / "agent_packets"
    role_dir.mkdir(parents=True, exist_ok=True)
    role_files = []
    for role in REQUIRED_ROLES:
        path = role_dir / f"{role.lower()}.template.json"
        if not path.exists():
            witcore.save_json(path, packets.template(role))
        role_files.append(str(path))
    try:
        import lovasz_soc_memory as soc
        soc.ensure_soc(run)
    except Exception:
        pass
    witcore.save_json(run / "loop_learning_contract.json", {
        "schema": "witsoc.loop_learning_contract.v1",
        "rule": "each campaign loop must produce a theory diff, gap feedback, one-axis mutation, escalation, or honest stop",
        "enforced_by": ["campaign_driver.py", "problem_theory.py", "proof_gap_to_barrier_feedback.py", "barrier_attack.py"],
    })
    success = success_definition(run)
    witcore.save_json(run / "top_tier_success_definition.json", success)
    return {
        "schema": "witsoc.lovasz_top_tier.prepare.v1",
        "run_dir": str(run),
        "barrier_attack": barrier,
        "agent_packet_templates": role_files,
        "success_definition": str(run / "top_tier_success_definition.json"),
    }


def success_definition(run: Path) -> dict[str, Any]:
    return {
        "schema": "witsoc.lovasz_top_tier.success.v1",
        "run_dir": str(run),
        "top_tier_when": [
            "zero fake solves on frozen expected-open sentinels",
            "every claimed result has kernel/checkable evidence or an explicit open dependency",
            "every open problem run has barrier_attacks.json, rung_saturation.json, proof_dependency_dag.json, and actual_lemma_queue.json",
            "every failed route records gap_feedback plus local/global failure memory",
            "every repeated attack changes exactly one mutation axis",
            "every novelty claim has live-library, atlas, and literature/external-check evidence",
            "every solve claim passes audit, formal receipt when applicable, independent re-derivation, and NOVEL_CANDIDATE novelty",
            "rediscovery benchmark reports calibration_clean and soundness_clean",
            "campaign loops produce a theory diff, mutation, escalation, or honest stop",
        ],
        "metrics": {
            "false_solve_rate": "must be 0",
            "time_to_first_rung": "tracked by run ledger",
            "verified_lean_closures": "counted from worker_results/proof DAG",
            "useful_partial_products": "count CHECKED/PARTIAL/CONDITIONAL below full solve",
            "repeat_failed_method_blocks": "count BLOCKED_REPEAT_RISK/BLOCKED_NO_MUTATION",
            "rediscovery_score": "from rediscovery_benchmark.py",
        },
    }


def audit(run: Path) -> dict[str, Any]:
    run = Path(run)
    target, domain, lean, target_hash = _manifest_context(run)
    barrier_payload = _load(run / "barrier_attacks.json", {})
    barriers = barrier_payload.get("barriers") if isinstance(barrier_payload, dict) else []
    barriers = [b for b in barriers if isinstance(b, dict)]
    rung_payload = _load(run / "rung_saturation.json", {})
    rungs = rung_payload.get("rungs") if isinstance(rung_payload, dict) else []
    rungs = [r for r in rungs if isinstance(r, dict)]
    dag = witcore.records(run / "proof_dependency_dag.json")
    queue = witcore.records(run / "actual_lemma_queue.json")
    feedback = _load(run / "gap_feedback.json", {})
    mutation_ledger = witcore.records(run / "mutation_ledger.json")
    theory_log = witcore.records(run / "problem_theory_log.json")
    loop_contract = _load(run / "loop_learning_contract.json", {})
    solve_claim = _load(run / "solve_claim.json", {})
    literature = None
    try:
        import literature_engine as le
        literature = le.ledger_for(target)
    except Exception:
        literature = None
    lean_audit = audit_hole_free_lean(run)

    role_dir = run / "agent_packets"
    role_verdicts = []
    for role in REQUIRED_ROLES:
        path = role_dir / f"{role.lower()}.template.json"
        if path.exists():
            pkt = _load(path, {})
            verdict = packets.validate_packet(pkt if isinstance(pkt, dict) else {})
            role_verdicts.append({"role": role, "path": str(path), "ok": verdict["ok"], "errors": verdict["errors"]})
        else:
            role_verdicts.append({"role": role, "path": str(path), "ok": False, "errors": ["missing packet template"]})

    engine_map = []
    try:
        import engine_dispatch as ed
        for arm in ENGINE_ARMS:
            engine_map.append({"arm": arm, "mapped": hasattr(ed.EngineDispatcher, f"_a_{arm}"),
                               "purpose": ENGINE_ARMS[arm]})
    except Exception as exc:
        engine_map.append({"arm": "engine_dispatch", "mapped": False, "error": str(exc)})

    rediscovery_suite = SCRIPT_DIR.parent / "benchmarks" / "rediscovery_suite.json"
    checks = [
        _check("2_barrier_core", bool(barriers) and any(n.get("type") == "actual_barrier_lemma" for n in dag),
               "named barriers exist and are merged into the proof DAG",
               {"barriers": len(barriers), "dag_nodes": len(dag)}),
        _check("3_rung_saturation", len(rungs) >= 8 and all(r.get("status") == "OPEN_UNFALSIFIED" for r in rungs),
               "saturated rungs exist and remain open/untrusted",
               {"rungs": len(rungs)}),
        _check("4_hole_free_lean", lean_audit["ok"],
               "generated Lean artifacts contain no forbidden proof holes/declarations",
               lean_audit),
        _check("5_strict_roles", all(r["ok"] for r in role_verdicts),
               "all Lovasz mathematical roles have valid non-trust-upgrading packets",
               role_verdicts),
        _check("6_failure_memory", (run / "lovasz.soc").exists() or bool(feedback) or bool(mutation_ledger),
               "failed approaches are persisted locally and/or as one-axis mutations",
               {"gap_feedback": bool(feedback), "mutations": len(mutation_ledger), "soc": str(run / "lovasz.soc")}),
        _check("7_novelty_literature", literature is not None or os.environ.get("WITSOC_LITERATURE_OFFLINE") == "1",
               "literature ledger exists, or offline mode is explicit",
               {"literature_ledger": bool(literature), "offline": os.environ.get("WITSOC_LITERATURE_OFFLINE") == "1"}),
        _check("8_full_solve_protocol", not solve_claim or solve_claim.get("schema") == "witsoc.solve_claim.v1",
               "solve claims, if present, use solve_claim_protocol",
               {"solve_claim_present": bool(solve_claim), "status": solve_claim.get("status") if isinstance(solve_claim, dict) else None}),
        _check("9_engine_portfolio", all(e.get("mapped") for e in engine_map),
               "search/computation engine arms are mapped in engine_dispatch",
               engine_map),
        _check("10_self_improving_loop", bool(theory_log) or bool(feedback) or bool(mutation_ledger)
               or (isinstance(loop_contract, dict) and loop_contract.get("schema") == "witsoc.loop_learning_contract.v1"),
               "campaign has theory diffs, feedback, mutations, or a pre-loop learning contract",
               {"theory_events": len(theory_log), "feedback": bool(feedback),
                "mutations": len(mutation_ledger), "loop_contract": bool(loop_contract)}),
        _check("11_rediscovery", rediscovery_suite.exists(),
               "rediscovery benchmark suite exists and can be run",
               {"suite": str(rediscovery_suite)}),
        _check("12_success_definition", (run / "top_tier_success_definition.json").exists(),
               "top-tier success criteria are materialized for the run",
               {"path": str(run / "top_tier_success_definition.json")}),
    ]
    ok = all(c["ok"] for c in checks)
    return {
        "schema": "witsoc.lovasz_top_tier.audit.v1",
        "run_dir": str(run),
        "target": target,
        "domain": domain,
        "target_hash": target_hash,
        "lean_target_present": bool(lean),
        "ok": ok,
        "score": round(sum(1 for c in checks if c["ok"]) / len(checks), 4),
        "checks": checks,
        "required_next_actions": [c["item"] for c in checks if not c["ok"]],
    }


def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    out: dict[str, Any] = {"schema": "witsoc.lovasz_top_tier.benchmark.v1", "steps": []}
    try:
        import rediscovery_benchmark as rb
        red = rb.run_suite(args.rediscovery_suite, max_decisions=args.max_decisions,
                           search=args.search, use_nexus=args.nexus)
        out["steps"].append({"name": "rediscovery", "ok": red["calibration_clean"] and red["soundness_clean"],
                             "score": red.get("score"), "report": red})
    except Exception as exc:
        out["steps"].append({"name": "rediscovery", "ok": False, "error": str(exc)})
    out["ok"] = all(s["ok"] for s in out["steps"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--target", default=None)
    p.add_argument("--domain", default=None)
    p.add_argument("--lean-target", default=None)
    p.add_argument("--top-rungs", type=int, default=32)
    a = sub.add_parser("audit")
    a.add_argument("run_dir", type=Path)
    s = sub.add_parser("success-definition")
    s.add_argument("run_dir", type=Path)
    b = sub.add_parser("benchmark")
    b.add_argument("--rediscovery-suite", type=Path, default=SCRIPT_DIR.parent / "benchmarks" / "rediscovery_suite.json")
    b.add_argument("--max-decisions", type=int, default=300_000)
    b.add_argument("--search", action="store_true")
    b.add_argument("--nexus", action="store_true")
    args = ap.parse_args()
    if args.cmd == "prepare":
        out = prepare(args.run_dir, target=args.target, domain=args.domain,
                      lean_target=args.lean_target, top_rungs=args.top_rungs)
    elif args.cmd == "audit":
        out = audit(args.run_dir)
    elif args.cmd == "success-definition":
        out = success_definition(args.run_dir)
    else:
        out = benchmark(args)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
