#!/usr/bin/env python3
"""Open-frontier workbench: novelty track + full-solve escalation.

This is an orchestrator over existing gates. It never upgrades truth:
novelty_triage owns novelty metadata, discovery_ledger records candidates,
validate_mathematical_solve audits full-target closure, and
solve_claim_protocol decides whether a solve is reportable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import discovery_ledger as dl  # noqa: E402
import novelty_triage as nt  # noqa: E402
import open_rungs  # noqa: E402
import solve_claim_protocol as scp  # noqa: E402
import validate_mathematical_solve as vms  # noqa: E402
import witcore  # noqa: E402


TRUST_RECORDABLE = {
    "CHECKED",
    "CHECKED_BOUNDED",
    "CHECKED_SYMBOLIC",
    "KERNEL_VERIFIED",
    "VERIFIED",
    "VERIFIED_LEAN",
    "LEAN_VERIFIED",
}

DISCOVERY_KIND = {
    "special_case_family": "family",
    "special_case": "lemma",
    "finite_certificate": "certificate",
    "computational_certificate": "certificate",
    "counterexample_search": "counterexample",
    "formula_synthesis": "family",
    "reduction": "reduction",
    "obstruction": "lemma",
}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def trust_from_rung(rung: dict[str, Any]) -> str:
    status = str(rung.get("status") or "").lower()
    if "verified" in status:
        return "VERIFIED_LEAN"
    if "checked" in status or "certificate" in status:
        return "CHECKED_BOUNDED"
    return "CONJECTURE"


def candidate_from_rung(rung: dict[str, Any], target_hash: str) -> dict[str, Any]:
    statement = str(rung.get("lean_statement") or rung.get("statement") or "")
    kind = str(rung.get("type") or "lemma")
    return {
        "id": str(rung.get("id") or witcore.slug(statement)[:40]),
        "statement": statement,
        "kind": kind,
        "trust_tier": str(rung.get("trust_tier") or trust_from_rung(rung)),
        "target_dependency": {
            "target_hash": target_hash,
            "dependency_path_to_target": [str(rung.get("id") or kind), "frozen_target"],
            "relation_to_target": rung.get("relation_to_target"),
        },
        "source": "open_rungs",
        "next_verification_step": rung.get("backend") or "formalize_or_dispatch",
        "repro_command": rung.get("repro_command") or "",
        "evidence": {"rung": rung},
    }


def normalize_extra_candidate(raw: dict[str, Any], target_hash: str) -> dict[str, Any]:
    statement = str(raw.get("statement") or raw.get("lean_statement") or raw.get("claim") or "")
    kind = str(raw.get("kind") or "lemma")
    return {
        "id": str(raw.get("id") or witcore.slug(statement)[:40]),
        "statement": statement,
        "kind": kind,
        "trust_tier": str(raw.get("trust_tier") or "CONJECTURE"),
        "target_dependency": raw.get("target_dependency") or {
            "target_hash": target_hash,
            "dependency_path_to_target": [str(raw.get("id") or kind), "frozen_target"],
            "relation_to_target": "candidate product toward frozen target",
        },
        "source": str(raw.get("source") or "external_candidate"),
        "next_verification_step": str(raw.get("next_verification_step") or "triage_or_verify"),
        "repro_command": str(raw.get("repro_command") or ""),
        "evidence": raw.get("evidence") or {},
    }


def novelty_track(target: str, domain: str, run_dir: Path,
                  extra_candidates: list[dict[str, Any]] | None = None,
                  register: bool = True) -> dict[str, Any]:
    target_hash = open_rungs._hash(target)
    rungs = open_rungs.build(target, domain)
    candidates = [candidate_from_rung(r, target_hash) for r in rungs["rungs"]]
    candidates += [normalize_extra_candidate(c, target_hash) for c in (extra_candidates or [])]

    rows = []
    bundles = []
    for cand in candidates:
        keywords = [w for w in cand["statement"].replace("∀", " ").replace("∃", " ").split()[:8]]
        novelty = nt.triage(cand["statement"], keywords=keywords)
        recordable = cand["trust_tier"] in TRUST_RECORDABLE
        ledger = None
        if register and recordable:
            kind = DISCOVERY_KIND.get(cand["kind"], "lemma")
            ledger = dl.add_entry(
                claim=cand["statement"][:240],
                kind=kind,
                trust_tier=cand["trust_tier"],
                statement=cand["statement"],
                problem_id=witcore.slug(target)[:80],
                repro=cand.get("repro_command", ""),
                evidence=cand.get("evidence"),
                novelty=novelty,
            )
        row = {
            **cand,
            "novelty_status": novelty.get("novelty"),
            "novelty": novelty,
            "recordable": recordable,
            "ledger": ledger,
            "publishable_now": bool(ledger and ledger.get("publishable")),
        }
        rows.append(row)
        bundles.append({
            "candidate_id": cand["id"],
            "statement": cand["statement"],
            "novelty_status": novelty.get("novelty"),
            "evidence": novelty.get("evidence", []),
            "statement_key": novelty.get("statement_key"),
            "note": novelty.get("note", ""),
        })

    result = {
        "schema": "witsoc.open_frontier_candidates.v1",
        "target": target,
        "target_sha256": target_hash,
        "domain": domain,
        "candidates": rows,
        "counts": {
            "total": len(rows),
            "recordable": sum(1 for r in rows if r["recordable"]),
            "novel_candidate": sum(1 for r in rows if r["novelty_status"] == "NOVEL_CANDIDATE"),
            "locally_new_unchecked": sum(1 for r in rows if r["novelty_status"] == "LOCALLY_NEW_UNCHECKED"),
            "known": sum(1 for r in rows if r["novelty_status"] in {"KNOWN", "KNOWN_INTERNAL"}),
        },
        "status_policy": "novelty is metadata; publishable requires kernel-grade trust, NOVEL_CANDIDATE, and human gate",
    }
    save(run_dir / "frontier_candidates.json", result)
    save(run_dir / "novelty_bundle.json", {
        "schema": "witsoc.novelty_bundle.v1",
        "target_sha256": target_hash,
        "bundles": bundles,
    })
    return result


def _claim_status_or_none(run_dir: Path) -> dict[str, Any] | None:
    try:
        return scp.status(argparse.Namespace(run_dir=run_dir))
    except SystemExit:
        return None
    except Exception:
        return None


def solve_escalation(target: str, run_dir: Path, problem_id: str,
                     min_skeptics: int = 3, open_claim: bool = True) -> dict[str, Any]:
    audit = vms.audit(run_dir, min_skeptics)
    existing = _claim_status_or_none(run_dir)
    opened = None
    if audit["verdict"] == "MATHEMATICAL_SOLVE_READY" and existing is None and open_claim:
        opened = scp.open_claim(argparse.Namespace(
            run_dir=run_dir,
            problem_id=problem_id,
            stage="MATHEMATICAL_SOLVE",
            lean_receipt=None,
            min_skeptics=min_skeptics,
        ))
        existing = _claim_status_or_none(run_dir)
    status = existing or {
        "status": "NOT_CLAIMED",
        "reportable_as_solve": False,
        "missing_requirements": ["primary run must pass validate_mathematical_solve"],
    }
    result = {
        "schema": "witsoc.solve_escalation.v1",
        "target": target,
        "problem_id": problem_id,
        "audit": audit,
        "claim_opened": bool(opened and not opened.get("error")),
        "claim": status,
        "reportable_as_solve": bool(status.get("reportable_as_solve")),
        "status": "SOLVE_ACCEPTED" if status.get("reportable_as_solve") else (
            "MATHEMATICAL_SOLVE_PENDING" if audit["verdict"] == "MATHEMATICAL_SOLVE_READY" else "NOT_READY"
        ),
        "missing_requirements": status.get("missing_requirements", []),
        "note": "Only solve_claim_protocol status SOLVE_ACCEPTED may be reported as a solve.",
    }
    save(run_dir / "solve_escalation.json", result)
    return result


def run(target: str, domain: str, run_dir: Path, mode: str,
        candidate_json: Path | None = None, register: bool = True,
        problem_id: str | None = None, min_skeptics: int = 3) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    extras = load(candidate_json, []) if candidate_json else []
    if isinstance(extras, dict):
        extras = extras.get("candidates", [])
    extras = [x for x in extras if isinstance(x, dict)] if isinstance(extras, list) else []

    novelty = None
    solve = None
    if mode in {"novelty", "both"}:
        novelty = novelty_track(target, domain, run_dir, extras, register=register)
    if mode in {"solve", "both"}:
        solve = solve_escalation(target, run_dir, problem_id or witcore.slug(target)[:80],
                                 min_skeptics=min_skeptics)
    report = {
        "schema": "witsoc.open_frontier_report.v1",
        "target": target,
        "domain": domain,
        "mode": mode,
        "frontier_candidates": str(run_dir / "frontier_candidates.json") if novelty else None,
        "novelty_bundle": str(run_dir / "novelty_bundle.json") if novelty else None,
        "solve_escalation": str(run_dir / "solve_escalation.json") if solve else None,
        "candidate_counts": novelty.get("counts") if novelty else None,
        "solve_status": solve.get("status") if solve else None,
        "reportable_as_solve": bool(solve and solve.get("reportable_as_solve")),
        "status_policy": "partials and novel candidates are not solves; full solve requires SOLVE_ACCEPTED",
    }
    save(run_dir / "frontier_report.json", report)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--target", required=True)
    p.add_argument("--domain", default="auto")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--mode", choices=["novelty", "solve", "both"], default="both")
    p.add_argument("--candidate-json", type=Path, default=None)
    p.add_argument("--problem-id", default=None)
    p.add_argument("--min-skeptics", type=int, default=3)
    p.add_argument("--no-register", action="store_true")
    args = ap.parse_args()
    result = run(args.target, args.domain, args.run_dir, args.mode,
                 args.candidate_json, register=not args.no_register,
                 problem_id=args.problem_id, min_skeptics=args.min_skeptics)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not result.get("reportable_as_solve") else 0


if __name__ == "__main__":
    raise SystemExit(main())
