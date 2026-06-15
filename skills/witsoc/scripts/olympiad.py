#!/usr/bin/env python3
"""Olympiad fast lane for Witsoc.

Local-first solved-problem path:
  profile  -> classify domain/style cheaply
  prove    -> run the existing kernel-gated prover with profile-tuned budgets
  eval     -> run a small olympiad benchmark suite with calibration sentinels

This script never verifies mathematics itself. `prove` delegates acceptance to
close_obligation.py / Lean and reports honest OPEN/BUDGET_EXHAUSTED otherwise.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

DOMAIN_KEYWORDS = {
    "number_theory": ["divisible", "congruence", "mod", "prime", "integer", "nat", "%", "gcd", "lcm"],
    "combinatorics": ["graph", "set", "color", "pigeonhole", "extremal", "matching", "partition"],
    "geometry": ["triangle", "circle", "angle", "point", "line", "parallel", "incidence", "coordinate"],
    "inequalities": ["≤", ">=", "≥", "<=", "inequality", "positive real", "nonnegative", "sum"],
    "algebra": ["polynomial", "group", "ring", "field", "factor", "root"],
    "functional_equations": ["function", "f(", "functional equation", "maps", "->"],
}

STYLE_KEYWORDS = {
    "induction": ["∀ n", "forall n", "recurrence", "sequence", "induction"],
    "modular": ["mod", "%", "congruence", "divisible", "∣"],
    "divisibility": ["divisible", "gcd", "lcm", "prime"],
    "extremal": ["maximum", "minimum", "at most", "at least", "extremal"],
    "pigeonhole": ["pigeonhole", "boxes", "colors", "coloring"],
    "invariant": ["invariant", "operation", "game", "move"],
    "coordinate_geometry": ["coordinate", "slope", "distance", "circle", "triangle"],
    "factorization": ["factor", "polynomial", "^", "*"],
    "inequality_normalization": ["≤", "≥", "inequality", "positive real", "nonnegative"],
    "functional_substitution": ["function", "f(", "functional equation"],
}


def _score_keywords(text: str, table: dict[str, list[str]]) -> list[dict[str, Any]]:
    lower = text.lower()
    rows = []
    for label, kws in table.items():
        hits = [kw for kw in kws if kw.lower() in lower]
        if hits:
            rows.append({"label": label, "score": len(hits), "evidence": hits[:5]})
    rows.sort(key=lambda r: (-r["score"], r["label"]))
    return rows


def profile(statement: str, preamble: str = "", domain: str = "auto") -> dict[str, Any]:
    text = f"{preamble}\n{statement}".strip()
    domains = _score_keywords(text, DOMAIN_KEYWORDS)
    styles = _score_keywords(text, STYLE_KEYWORDS)
    primary = domain if domain != "auto" else (domains[0]["label"] if domains else "other")
    difficulty = "D3" if any(s["label"] in {"induction", "extremal", "functional_substitution"} for s in styles) else "D2"
    if primary == "geometry" and "coordinate_geometry" not in [s["label"] for s in styles]:
        difficulty = "D3"
    return {
        "schema": "witsoc.olympiad_profile.v1",
        "domain": primary,
        "domain_candidates": domains,
        "styles": [s["label"] for s in styles] or ["direct"],
        "style_evidence": styles,
        "difficulty": difficulty,
        "recommended_path": "local_fast_lane_then_lovasz_on_failure",
        "trust": "classification_only",
    }


def _run_json(cmd: list[str], timeout: int = 600) -> dict[str, Any]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        data = json.loads(r.stdout) if r.stdout.strip() else {}
        data["_returncode"] = r.returncode
        if r.stderr.strip():
            data["_stderr"] = r.stderr[-1000:]
        return data
    except Exception as exc:
        return {"_error": str(exc), "_returncode": 2}


def prove(statement: str, preamble: str = "", domain: str = "auto", lake_dir: str | None = None,
          max_nodes: int = 180, workers: int | None = None) -> dict[str, Any]:
    prof = profile(statement, preamble, domain)
    workers = witcore.local_prover_worker_count(workers)
    # Keep the fast lane bounded. D3 induction/function/combinatorics gets a bit
    # more search; simple D2 goals should close early or fail quickly.
    styles = set(prof["styles"])
    budget = max_nodes
    if styles & {"induction", "functional_substitution", "extremal", "coordinate_geometry"}:
        budget = max(max_nodes, 260)
    cmd = [sys.executable, str(SCRIPT_DIR / "close_obligation.py"),
           "--lean-statement", statement, "--name", "olympiad_fast_lane",
           "--out-ledger", "/dev/null", "--search",
           "--search-max-nodes", str(budget), "--workers", str(workers)]
    if preamble:
        cmd += ["--imports", preamble]
    if lake_dir:
        cmd += ["--lake-dir", lake_dir]
    started = time.time()
    result = _run_json(cmd, timeout=900)
    elapsed = round(time.time() - started, 3)
    discharged = bool(result.get("discharged"))
    return {
        "schema": "witsoc.olympiad_prove.v1",
        "profile": prof,
        "status": "VERIFIED_LEAN" if discharged else result.get("label", "OBLIGATION_OPEN"),
        "discharged": discharged,
        "proof": result.get("proof") if discharged else None,
        "label": result.get("label"),
        "search_nodes": result.get("search_nodes") or result.get("nodes") or 0,
        "budget": {"max_nodes": budget, "workers": workers, "local_first": True},
        "elapsed_sec": elapsed,
        "fallback": None if discharged else "route_to_lovasz_solved_class_with_profile_and_failure_trace",
        "trace": result.get("search_trace") or result.get("trace"),
    }


def eval_suite(suite: Path, mode: str, out: Path | None = None) -> dict[str, Any]:
    data = json.loads(suite.read_text(encoding="utf-8"))
    rows = []
    violations = []
    for item in data.get("problems", []):
        kind = item.get("kind", "lean")
        if kind not in {"lean", "expected_open"}:
            rows.append({"id": item.get("id"), "status": "UNSUPPORTED_KIND", "passed": False})
            continue
        if mode == "profile":
            res = {"profile": profile(item["statement"], item.get("preamble", ""), item.get("domain", "auto")),
                   "discharged": False, "status": "PROFILE_ONLY", "search_nodes": 0}
        else:
            res = prove(item["statement"], item.get("preamble", ""), item.get("domain", "auto"))
        if kind == "expected_open":
            passed = not res.get("discharged")
            if res.get("discharged"):
                violations.append(item.get("id"))
        else:
            passed = bool(res.get("discharged")) if item.get("oracle") == "provable" else False
        rows.append({"id": item.get("id"), "kind": kind, "passed": passed,
                     "status": res.get("status"), "domain": res.get("profile", {}).get("domain"),
                     "styles": res.get("profile", {}).get("styles"),
                     "search_nodes": res.get("search_nodes", 0),
                     "elapsed_sec": res.get("elapsed_sec", 0.0)})
    graded = [r for r in rows if r["kind"] != "expected_open"]
    solved = sum(1 for r in graded if r["passed"])
    nodes = [int(r.get("search_nodes") or 0) for r in graded if r["passed"]]
    report = {
        "schema": "witsoc.olympiad_eval.v1",
        "suite": str(suite),
        "mode": mode,
        "graded": len(graded),
        "solved": solved,
        "score": round(solved / len(graded), 4) if graded else 0.0,
        "mean_search_nodes": round(sum(nodes) / len(nodes), 2) if nodes else 0.0,
        "calibration_clean": not violations,
        "calibration_violations": violations,
        "rows": rows,
    }
    if out:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_prof = sub.add_parser("profile")
    p_prof.add_argument("--statement", required=True)
    p_prof.add_argument("--preamble", default="")
    p_prof.add_argument("--domain", default="auto")
    p_prove = sub.add_parser("prove")
    p_prove.add_argument("--statement", required=True)
    p_prove.add_argument("--preamble", default="")
    p_prove.add_argument("--domain", default="auto")
    p_prove.add_argument("--lake-dir", default=None)
    p_prove.add_argument("--max-nodes", type=int, default=180)
    p_prove.add_argument("--workers", type=int, default=None,
                         help="local prover thread fanout (default: WITSOC_PROVER_WORKERS or 4; capped at 10)")
    p_eval = sub.add_parser("eval")
    p_eval.add_argument("--suite", type=Path, default=SCRIPT_DIR.parent / "benchmarks" / "olympiad_suite.json")
    p_eval.add_argument("--mode", choices=["profile", "fast"], default="fast")
    p_eval.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    if args.cmd == "profile":
        out = profile(args.statement, args.preamble, args.domain)
    elif args.cmd == "prove":
        out = prove(args.statement, args.preamble, args.domain, args.lake_dir, args.max_nodes, args.workers)
    else:
        out = eval_suite(args.suite, args.mode, args.out)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("calibration_clean", True) and out.get("status") != "UNCHECKED_NO_TOOLCHAIN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
