#!/usr/bin/env python3
"""F0 solve-claim protocol — `witsoc solve-claim`.

The maximum-scrutiny gate between "a campaign believes it solved a
frontier_attack problem" and "witsoc reports a solve". A frontier solve is an
extraordinary claim; this protocol replaces the calibration-sentinel rule
(where any solve fails the run) for the frontier_attack tier with four
independent requirements, ALL mandatory:

  1. AUDIT          the primary run passes validate_mathematical_solve
                    (stage MATHEMATICAL_SOLVE), plus a recorded Lean receipt
                    for stage FORMAL_SOLVE;
  2. REDERIVATION   at least one independent re-derivation: a DIFFERENT run
                    directory, same frozen target hash, passing its own
                    mathematical-solve audit (a fresh fleet with no access to
                    the original proof);
  3. NOVELTY        a recorded novelty verdict; NOVEL_CANDIDATE is required —
                    KNOWN/KNOWN_INTERNAL rejects the claim (priority), and
                    LOCALLY_NEW_UNCHECKED is insufficient at frontier stakes;
  4. FORMAL RECEIPT for FORMAL_SOLVE claims, validated by
                    validate_lean_receipt.py so environment-only placeholder
                    Lean output cannot support a solve.

Claim state lives in <run_dir>/solve_claim.json; every mutation also appends
an event to the durable ledger <witsoc home>/solve_claims.jsonl. Status is
computed from satisfied requirements, never stored as a free-form label:
CLAIMED -> SOLVE_ACCEPTED only when all machine-verification requirements hold;
REJECTED is terminal. Human review can be recorded as optional evidence, but is
not required for the default machine-verified solve label.

Only SOLVE_ACCEPTED may ever be reported as a solve of the named problem.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import validate_mathematical_solve as vms
import validate_lean_receipt as vlr
import witcore

STAGES = ("MATHEMATICAL_SOLVE", "FORMAL_SOLVE")
NOVELTY_VERDICTS = ("NOVEL_CANDIDATE", "KNOWN", "KNOWN_INTERNAL", "LOCALLY_NEW_UNCHECKED")


def claim_path(run: Path) -> Path:
    return run / "solve_claim.json"


def ledger_path() -> Path:
    return witcore.witsoc_home() / "solve_claims.jsonl"


def load_claim(run: Path) -> dict:
    try:
        data = json.loads(claim_path(run).read_text(encoding="utf-8"))
    except Exception:
        raise SystemExit(f"no solve_claim.json in {run}; run `solve-claim open` first")
    if not isinstance(data, dict) or data.get("schema") != "witsoc.solve_claim.v1":
        raise SystemExit(f"{claim_path(run)} is not a witsoc.solve_claim.v1 record")
    return data


def save_claim(run: Path, claim: dict, event: str, detail: dict) -> None:
    claim["status"] = computed_status(claim)
    claim_path(run).write_text(json.dumps(claim, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ledger = ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event,
                             "problem_id": claim.get("problem_id"), "run_dir": claim.get("run_dir"),
                             "status": claim["status"], **detail}, ensure_ascii=False) + "\n")


def computed_status(claim: dict) -> str:
    if claim.get("rejected_reason"):
        return "REJECTED"
    requirements = missing_requirements(claim)
    return "SOLVE_ACCEPTED" if not requirements else "CLAIMED"


def missing_requirements(claim: dict) -> list[str]:
    missing = []
    if not claim.get("audit_passed"):
        missing.append("primary run must pass validate_mathematical_solve")
    if claim.get("stage") == "FORMAL_SOLVE" and not claim.get("lean_receipt"):
        missing.append("FORMAL_SOLVE stage requires a recorded Lean receipt")
    if not [r for r in claim.get("rederivations", []) if r.get("verified")]:
        missing.append("at least one verified independent re-derivation")
    if claim.get("novelty", {}).get("verdict") != "NOVEL_CANDIDATE":
        missing.append("novelty verdict NOVEL_CANDIDATE")
    return missing


def open_claim(args: argparse.Namespace) -> dict:
    run = args.run_dir
    if claim_path(run).exists():
        raise SystemExit(f"{claim_path(run)} already exists; one claim per run")
    audit = vms.audit(run, args.min_skeptics)
    if audit["verdict"] != "MATHEMATICAL_SOLVE_READY":
        return {"error": "cannot open a solve claim: the mathematical-solve audit fails",
                "failures": audit["failures"]}
    lean_receipt = ""
    lean_receipt_validation = {}
    if args.stage == "FORMAL_SOLVE":
        if not args.lean_receipt or not Path(args.lean_receipt).exists():
            return {"error": "FORMAL_SOLVE claims require --lean-receipt pointing to an existing receipt"}
        lean_receipt_validation = vlr.validate(args.lean_receipt, audit["target_hash"])
        if not lean_receipt_validation["valid"]:
            return {"error": "FORMAL_SOLVE Lean receipt failed validation",
                    "failures": lean_receipt_validation["errors"]}
        lean_receipt = str(args.lean_receipt)
    claim = {
        "schema": "witsoc.solve_claim.v1",
        "problem_id": args.problem_id,
        "tier": "frontier_attack",
        "stage": args.stage,
        "run_dir": str(run),
        "target_hash": audit["target_hash"],
        "audit_passed": True,
        "audit": {"min_skeptics": audit["min_skeptics"], "counts": audit["counts"]},
        "lean_receipt": lean_receipt,
        "lean_receipt_validation": lean_receipt_validation,
        "rederivations": [],
        "novelty": {},
        "human_gate": {},
        "rejected_reason": "",
    }
    save_claim(run, claim, "claim_opened", {"stage": args.stage})
    return claim


def add_rederivation(args: argparse.Namespace) -> dict:
    claim = load_claim(args.run_dir)
    if claim["status"] == "REJECTED":
        return {"error": f"claim is REJECTED ({claim['rejected_reason']}); no further evidence accepted"}
    reder = args.rederivation_run
    if reder.resolve() == args.run_dir.resolve():
        return {"error": "a re-derivation must be a DIFFERENT run directory (independent fleet)"}
    audit = vms.audit(reder, args.min_skeptics)
    entry = {"run_dir": str(reder), "target_hash": audit["target_hash"],
             "verified": False, "failures": audit["failures"][:5]}
    if audit["verdict"] != "MATHEMATICAL_SOLVE_READY":
        claim["rederivations"].append(entry)
        save_claim(args.run_dir, claim, "rederivation_failed_audit", {"rederivation": str(reder)})
        return {"error": "re-derivation run fails its own mathematical-solve audit",
                "failures": audit["failures"]}
    if audit["target_hash"] != claim["target_hash"]:
        claim["rederivations"].append(entry)
        save_claim(args.run_dir, claim, "rederivation_target_mismatch", {"rederivation": str(reder)})
        return {"error": f"re-derivation target hash {audit['target_hash']!r} does not match "
                         f"the claimed target {claim['target_hash']!r}"}
    entry.update(verified=True, failures=[])
    claim["rederivations"].append(entry)
    save_claim(args.run_dir, claim, "rederivation_verified", {"rederivation": str(reder)})
    return {"rederivations": claim["rederivations"], "status": claim["status"]}


def add_novelty(args: argparse.Namespace) -> dict:
    claim = load_claim(args.run_dir)
    if claim["status"] == "REJECTED":
        return {"error": f"claim is REJECTED ({claim['rejected_reason']}); no further evidence accepted"}
    claim["novelty"] = {"verdict": args.verdict, "details": args.details,
                        "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if args.verdict in ("KNOWN", "KNOWN_INTERNAL"):
        claim["rejected_reason"] = f"novelty check returned {args.verdict}: the result was already known"
    save_claim(args.run_dir, claim, "novelty_recorded", {"verdict": args.verdict})
    return {"novelty": claim["novelty"], "status": claim["status"],
            "rejected_reason": claim["rejected_reason"]}


def human_gate(args: argparse.Namespace) -> dict:
    claim = load_claim(args.run_dir)
    if claim["status"] == "REJECTED":
        return {"error": f"claim is REJECTED ({claim['rejected_reason']}); no further evidence accepted"}
    claim["human_gate"] = {"reviewer": args.reviewer, "decision": args.decision,
                           "notes": args.notes, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if args.decision == "reject":
        claim["rejected_reason"] = f"human gate rejected by {args.reviewer}: {args.notes or 'no notes'}"
    save_claim(args.run_dir, claim, "human_gate", {"reviewer": args.reviewer, "decision": args.decision})
    return {"human_gate": claim["human_gate"], "status": claim["status"]}


def status(args: argparse.Namespace) -> dict:
    claim = load_claim(args.run_dir)
    return {
        "problem_id": claim["problem_id"],
        "stage": claim["stage"],
        "status": claim["status"],
        "target_hash": claim["target_hash"],
        "missing_requirements": missing_requirements(claim) if claim["status"] != "REJECTED" else [],
        "rejected_reason": claim["rejected_reason"],
        "reportable_as_solve": claim["status"] == "SOLVE_ACCEPTED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_open = sub.add_parser("open")
    p_open.add_argument("run_dir", type=Path)
    p_open.add_argument("--problem-id", required=True)
    p_open.add_argument("--stage", choices=STAGES, default="MATHEMATICAL_SOLVE")
    p_open.add_argument("--lean-receipt", type=Path, default=None)
    p_open.add_argument("--min-skeptics", type=int, default=3)

    p_reder = sub.add_parser("add-rederivation")
    p_reder.add_argument("run_dir", type=Path)
    p_reder.add_argument("--rederivation-run", type=Path, required=True)
    p_reder.add_argument("--min-skeptics", type=int, default=3)

    p_novel = sub.add_parser("add-novelty")
    p_novel.add_argument("run_dir", type=Path)
    p_novel.add_argument("--verdict", choices=NOVELTY_VERDICTS, required=True)
    p_novel.add_argument("--details", default="")

    p_human = sub.add_parser("human-gate")
    p_human.add_argument("run_dir", type=Path)
    p_human.add_argument("--reviewer", required=True)
    p_human.add_argument("--decision", choices=("approve", "reject"), required=True)
    p_human.add_argument("--notes", default="")

    p_status = sub.add_parser("status")
    p_status.add_argument("run_dir", type=Path)

    args = parser.parse_args()
    handler = {"open": open_claim, "add-rederivation": add_rederivation,
               "add-novelty": add_novelty, "human-gate": human_gate, "status": status}[args.cmd]
    result = handler(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
