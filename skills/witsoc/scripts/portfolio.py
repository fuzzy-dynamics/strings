#!/usr/bin/env python3
"""Research-portfolio tooling for sustained Lovász campaigns — `witsoc portfolio`.

The portfolio (benchmarks/research_portfolio.json) is the curated list of
attackable open problems and their rungs. This tool keeps it honest and turns
it into campaign inputs:

  validate          schema + honesty checks (calibration sentinels present,
                    open entries carry honest_statuses, no trust claims)
  verify-truth      kernel-check every reachable_research entry's oracle_proof
                    (portfolio hygiene: a FALSE rung would poison campaigns).
                    Oracle proofs are NEVER given to the campaign prover.
  emit-campaign     kind=lean entries -> autonomous_campaign portfolio JSON
  emit-experiments  kind=experimental entries -> backend dispatch list
  ladder            difficulty-graded curriculum ladder for one lean entry

Tier semantics (the honesty contract, also in the portfolio _comment):
  frozen_calibration  genuinely open; a solve FAILS the campaign
  research_target     open; expected honest OPEN/BUDGET_EXHAUSTED
  frontier_attack     genuinely open AND a solve is the goal; a campaign solve
                      is NOT a calibration violation but is reportable ONLY
                      through the solve-claim protocol (math-solve audit +
                      independent re-derivation + novelty + human gate;
                      solve_claim_protocol.py)
  reachable_research  TRUE rung toward an open problem; closing it is library
                      growth, never a solve of the named problem
  experimental        computation-backend search; outputs are conjectures or
                      certificates routed through novelty triage
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

DEFAULT_PORTFOLIO = SCRIPT_DIR.parent / "benchmarks" / "research_portfolio.json"
TIERS = {"frozen_calibration", "research_target", "frontier_attack", "reachable_research", "experimental"}
KINDS = {"lean", "experimental"}


def load(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("problems"), list):
        raise SystemExit("portfolio must be an object with a `problems` list")
    return data


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    calibration = 0
    for p in data["problems"]:
        pid = p.get("id", "<missing id>")
        if pid in seen:
            errors.append(f"{pid}: duplicate id")
        seen.add(pid)
        for field in ("id", "tier", "kind", "domain", "title", "informal", "status",
                      "relation_to_open_problem"):
            if not p.get(field):
                errors.append(f"{pid}: missing `{field}`")
        if p.get("tier") not in TIERS:
            errors.append(f"{pid}: unknown tier {p.get('tier')!r}")
        if p.get("kind") not in KINDS:
            errors.append(f"{pid}: unknown kind {p.get('kind')!r}")
        if p.get("kind") == "lean" and not p.get("lean_target"):
            errors.append(f"{pid}: kind=lean requires lean_target")
        if p.get("kind") == "experimental" and not (p.get("backend") and p.get("spec")):
            errors.append(f"{pid}: kind=experimental requires backend + spec")
        if p.get("tier") == "frozen_calibration":
            calibration += 1
            if p.get("status") != "OPEN":
                errors.append(f"{pid}: calibration sentinel must have status OPEN")
        if p.get("tier") in ("frozen_calibration", "research_target", "frontier_attack"):
            if p.get("oracle_proof"):
                errors.append(f"{pid}: open entry must not carry an oracle_proof")
            if not p.get("honest_statuses"):
                errors.append(f"{pid}: open entry needs honest_statuses")
        if p.get("tier") == "frontier_attack" and p.get("status") != "OPEN":
            errors.append(f"{pid}: frontier_attack entry must have status OPEN "
                          "(a solve is reportable only via the solve-claim protocol)")
        if p.get("tier") == "reachable_research" and not p.get("oracle_proof"):
            errors.append(f"{pid}: reachable_research needs an oracle_proof (truth hygiene)")
        # No entry may pre-claim trust: status is a research label, never a verdict.
        if str(p.get("status", "")).upper() in ("VERIFIED", "CHECKED", "SOLVED", "VERIFIED_LEAN"):
            errors.append(f"{pid}: portfolio entries must not claim trust statuses")
    if calibration < 2:
        errors.append("portfolio needs >=2 frozen_calibration sentinels")
    return errors


def _theorem_source(p: dict) -> str:
    name = "t_" + p["id"].replace("-", "_")
    imports = p.get("imports", "") or "import Mathlib.Tactic"
    preamble = p.get("preamble", "")
    return "\n\n".join(s for s in (
        imports, preamble,
        f"theorem {name} : {p['lean_target']} := {p['oracle_proof']}") if s) + "\n"


def verify_truth(data: dict, lake_dir: Path | None) -> dict:
    """Kernel-check oracle proofs of reachable rungs. This validates the
    PORTFOLIO (the statements are true), not the system (the campaign prover
    never sees these proofs)."""
    results = {}
    for p in data["problems"]:
        if p.get("tier") != "reachable_research":
            continue
        verdict = witcore.lean_verify_cached(_theorem_source(p), lake_dir)
        results[p["id"]] = {"verified": bool(verdict.get("verified")),
                            "reason": verdict.get("reason")}
    return results


def emit_campaign(data: dict) -> list[dict]:
    out = []
    for p in data["problems"]:
        if p.get("kind") != "lean":
            continue
        out.append({"id": p["id"], "lean_target": p["lean_target"],
                    "preamble": p.get("preamble", ""), "imports": p.get("imports", ""),
                    "domain": p.get("domain", "other"), "tier": p["tier"]})
    return out


def emit_experiments(data: dict) -> list[dict]:
    return [{"id": p["id"], "backend": p["backend"], "spec": p["spec"],
             "domain": p.get("domain", "other"), "title": p.get("title", "")}
            for p in data["problems"] if p.get("kind") == "experimental"]


def ladder(data: dict, pid: str) -> dict:
    import curriculum_portfolio as cp
    p = next((x for x in data["problems"] if x["id"] == pid), None)
    if not p or p.get("kind") != "lean":
        raise SystemExit(f"no lean entry {pid!r}")
    return {"id": pid, "portfolio": cp.build_portfolio(
        p["lean_target"], [], p.get("preamble", ""), p.get("domain", "other"))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--portfolio", type=Path, default=DEFAULT_PORTFOLIO)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    p_vt = sub.add_parser("verify-truth")
    p_vt.add_argument("--lake-dir", type=Path, default=None)
    p_ec = sub.add_parser("emit-campaign")
    p_ec.add_argument("--out", type=Path, default=None)
    p_ee = sub.add_parser("emit-experiments")
    p_ee.add_argument("--out", type=Path, default=None)
    p_l = sub.add_parser("ladder")
    p_l.add_argument("--id", required=True)
    args = ap.parse_args()

    data = load(args.portfolio)
    if args.cmd == "validate":
        errors = validate(data)
        print(json.dumps({"status": "ok" if not errors else "invalid",
                          "problems": len(data["problems"]), "errors": errors}, indent=2))
        return 0 if not errors else 1
    if args.cmd == "verify-truth":
        lake = witcore.enable_mathlib_mode(args.lake_dir)
        res = verify_truth(data, lake)
        ok = all(r["verified"] for r in res.values())
        print(json.dumps({"status": "ok" if ok else "FALSE_RUNG_DETECTED", "results": res}, indent=2))
        return 0 if ok else 1
    if args.cmd in ("emit-campaign", "emit-experiments"):
        payload = emit_campaign(data) if args.cmd == "emit-campaign" else emit_experiments(data)
        if args.out:
            witcore.save_json(args.out, payload)
        print(json.dumps({"count": len(payload), "out": str(args.out) if args.out else None,
                          "ids": [x["id"] for x in payload]}, indent=2))
        return 0
    if args.cmd == "ladder":
        print(json.dumps(ladder(data, args.id), indent=2, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
