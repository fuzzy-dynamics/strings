#!/usr/bin/env python3
"""A7 rediscovery benchmark — `witsoc rediscovery`.

"Top tier" is a measured claim or it is nothing. This benchmark grades Lovasz
on REDISCOVERY: problems whose answers are known (some once open for decades)
are presented to the solving machinery WITHOUT their answers; the hidden
answer is used only for grading, oracle-style — it never reaches any solver
input by construction (the calibration discipline of portfolio
verify-truth).

Suite entries (benchmarks/rediscovery_suite.json) by kind:
  sat_bracket   reduction_hunt scans the instance family; grade SOLVED_MATCH
                when the witness/refutation bracket pins the hidden value
  sat_decision  one verified SAT instance; grade against the hidden verdict
  prove         the kernel prover (+--nexus fleet) attacks a hidden-provable
                Lean target
  expected_open calibration rows: genuinely-open or out-of-reach statements
                where anything but OPEN is a calibration FAILURE

Score = weighted fraction over graded rows, with calibration violations
failing the whole run (the sentinel discipline at benchmark level). Run it
every release; the published bar to compare against is AlphaProof Nexus's
9/353 open Erdős problems (2026).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

DEFAULT_SUITE = SCRIPT_DIR.parent / "benchmarks" / "rediscovery_suite.json"


def grade_sat_bracket(entry: dict, max_decisions: int) -> dict:
    import reduction_hunt as rh
    family = {"encoder": entry["encoder"], "params": entry.get("params", {}),
              "scan": entry["scan"], "rationale": "rediscovery"}
    result = rh.run_family(family, max_decisions, int(entry.get("scan_cap", 10)))
    bracket = result.get("bracket", {})
    flip = "first_sat" if str(entry["scan"].get("until", "unsat")) == "sat" else "first_unsat"
    found = bracket.get(flip, {}).get(entry["scan"]["param"])
    hidden = entry["hidden_answer"]
    if found == hidden:
        verdict = "SOLVED_MATCH"
    elif found is not None:
        verdict = "WRONG_VALUE"  # a bracket that disagrees with truth is a soundness alarm
    elif bracket.get("last_sat"):
        verdict = "BRACKETED_PARTIAL"
    else:
        verdict = "OPEN"
    return {"verdict": verdict, "found": found, "bracket": bracket}


def grade_sat_decision(entry: dict, max_decisions: int) -> dict:
    import sat_backend as sb
    if entry["encoder"] == "covering":
        enc = sb.encode_covering(entry["params"]["moduli"])
    else:
        return {"verdict": "UNSUPPORTED_ENCODER"}
    out = sb.solve_internal(enc["num_vars"], enc["clauses"], max_decisions)
    if out["result"] == "SAT" and not sb.verify_witness(enc["clauses"], out.get("witness") or {}):
        return {"verdict": "WRONG_VALUE", "found": "SAT_UNVERIFIED"}
    found = out["result"] if out["result"] in ("SAT", "UNSAT") else None
    hidden = entry["hidden_answer"]
    return {"verdict": "SOLVED_MATCH" if found == hidden
            else ("OPEN" if found is None else "WRONG_VALUE"), "found": found}


def grade_prove(entry: dict, search: bool, use_nexus: bool) -> dict:
    import close_obligation as co
    from witcore import slug
    result = co.close_goal(entry["lean_target"], name=f"rd_{slug(entry['id']).replace('-', '_')}",
                           imports=str(entry.get("imports") or ""), search=search)
    if not result.get("discharged") and use_nexus:
        try:
            import nexus_loop as nx
            fr = nx.fleet_prove(entry["lean_target"], imports=str(entry.get("imports") or ""),
                                deterministic_first=False)
            if fr.get("discharged"):
                result = {"discharged": True, "proof": fr["proof"]}
        except Exception:
            pass
    if result.get("discharged"):
        return {"verdict": "SOLVED_MATCH", "proof": result.get("proof")}
    return {"verdict": "OPEN", "label": result.get("label")}


def grade_expected_open(entry: dict, search: bool) -> dict:
    import close_obligation as co
    from witcore import slug
    result = co.close_goal(entry["lean_target"], name=f"cal_{slug(entry['id']).replace('-', '_')}",
                           imports=str(entry.get("imports") or ""), search=search,
                           search_max_nodes=60)
    if result.get("discharged"):
        return {"verdict": "CALIBRATION_VIOLATION",
                "detail": "an expected-open statement was 'proved' — audit immediately",
                "proof": result.get("proof")}
    return {"verdict": "CALIBRATED_OPEN"}


def run_suite(suite_path: Path, *, max_decisions: int, search: bool,
              use_nexus: bool, only: list[str] | None = None) -> dict:
    suite = witcore.load_json(suite_path, None)
    if not isinstance(suite, dict) or not isinstance(suite.get("entries"), list):
        raise SystemExit(f"no rediscovery suite at {suite_path}")
    rows = []
    for entry in suite["entries"]:
        if only and entry.get("id") not in only:
            continue
        kind = entry.get("kind")
        if kind == "sat_bracket":
            graded = grade_sat_bracket(entry, max_decisions)
        elif kind == "sat_decision":
            graded = grade_sat_decision(entry, max_decisions)
        elif kind == "prove":
            graded = grade_prove(entry, search, use_nexus)
        elif kind == "expected_open":
            graded = grade_expected_open(entry, search)
        else:
            graded = {"verdict": "UNKNOWN_KIND"}
        rows.append({"id": entry.get("id"), "kind": kind,
                     "track": entry.get("track", "competition"),
                     "once_open_years": entry.get("once_open_years"),
                     **graded})

    graded_rows = [r for r in rows if r["kind"] != "expected_open"]
    # Ω7 (SorryDB): score per TRACK — competition numbers must never mask the
    # real-world gap, which is the one that matters for research mathematics.
    tracks: dict[str, dict] = {}
    for r in graded_rows:
        t = tracks.setdefault(r["track"], {"graded": 0, "solved": 0})
        t["graded"] += 1
        t["solved"] += int(r["verdict"] == "SOLVED_MATCH")
    for t in tracks.values():
        t["score"] = round(t["solved"] / t["graded"], 4) if t["graded"] else 0.0
    solved = sum(1 for r in graded_rows if r["verdict"] == "SOLVED_MATCH")
    wrong = sum(1 for r in rows if r["verdict"] == "WRONG_VALUE")
    violations = [r["id"] for r in rows if r["verdict"] == "CALIBRATION_VIOLATION"]
    return {
        "schema": "witsoc.rediscovery.v1",
        "suite": str(suite_path),
        "rows": rows,
        "graded": len(graded_rows),
        "solved_match": solved,
        "bracketed_partial": sum(1 for r in graded_rows if r["verdict"] == "BRACKETED_PARTIAL"),
        "open": sum(1 for r in graded_rows if r["verdict"] == "OPEN"),
        "wrong_value": wrong,
        "score": round(solved / len(graded_rows), 4) if graded_rows else 0.0,
        "track_scores": tracks,
        "calibration_clean": not violations,
        "calibration_violations": violations,
        "soundness_clean": wrong == 0,
        "note": ("hidden answers grade only — they never reach a solver input. WRONG_VALUE is a "
                 "soundness alarm, CALIBRATION_VIOLATION fails the run. Published bar: "
                 "AlphaProof Nexus 9/353 open Erdős problems (2026)."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    ap.add_argument("--max-decisions", type=int, default=300_000)
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--nexus", action="store_true")
    ap.add_argument("--only", action="append", default=[], help="run only these entry ids")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    report = run_suite(args.suite, max_decisions=args.max_decisions, search=args.search,
                       use_nexus=args.nexus, only=args.only or None)
    if args.out:
        witcore.save_json(args.out, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["calibration_clean"] and report["soundness_clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
