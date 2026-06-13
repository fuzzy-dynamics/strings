#!/usr/bin/env python3
"""Phase 6: autonomous campaigns — the flywheel at SCALE.

The top-level self-improving loop. Over a PORTFOLIO of problems, each iteration runs the
research director (engine_dispatch) on every problem; verified proofs are harvested into a
shared lemma library and the value model is retrained, so the next iteration is stronger
(reach and/or efficiency compound). The runner tracks a capability curve, per-problem rung
progress, library growth, and — at every iteration — that the frozen-calibration problems
stay unsolved. Honest by construction: a campaign reaches SOLVED only at a kernel-verified
L6, and one calibration violation fails the whole campaign.

The compounding wiring: the dispatcher's prover is library-aware (`--use-library`
+ `--record-library`), so closures from earlier problems/iterations are reused on later
ones, and the value model (trained from the closure ledger) reorders candidates.

Usage:
  autonomous_campaign.py --portfolio portfolio.json --iterations 2 [--library DIR]
      [--max-steps 6] [--lake-dir DIR] [--out campaign.json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import engine_dispatch as ed  # noqa: E402
import research_state as rs   # noqa: E402
import witcore                # noqa: E402

RUNG_VALUE = rs.RUNG_REWARD


def _train_value_model(library: Path, closure_ledger: Path) -> None:
    if not closure_ledger.exists():
        return
    subprocess.run([sys.executable, str(SCRIPT_DIR / "value_function.py"), "train",
                    "--from-closures", str(closure_ledger),
                    "--out", str(library / "value_model.json")],
                   capture_output=True, text=True, timeout=60, check=False)


def _library_size(library: Path) -> int:
    try:
        r = subprocess.run([sys.executable, str(SCRIPT_DIR / "lemma_library.py"),
                            "--library", str(library), "stats"], capture_output=True, text=True, timeout=20, check=False)
        return json.loads(r.stdout).get("total", 0)
    except Exception:
        return 0


def run(portfolio: list[dict], library: Path, iterations: int, max_steps: int,
        lake_dir: Path | None = None, make_prover=None, closure_ledger: Path | None = None) -> dict:
    """`make_prover(library)` builds the prover for an iteration (injectable for tests);
    the default is the library-aware real prover."""
    library.mkdir(parents=True, exist_ok=True)
    if make_prover is None:
        def make_prover(lib):
            return ed.real_prover(lake_dir, library=lib)

    log: list[dict] = []
    violations: list[str] = []
    solve_claims_required: list[dict] = []
    best_rung_seen: dict[str, str] = {p["id"]: "L0" for p in portfolio}

    for it in range(1, iterations + 1):
        prover = make_prover(library)
        per_problem = []
        for p in portfolio:
            disp = ed.EngineDispatcher(p["lean_target"], p.get("preamble", ""), p.get("imports", ""),
                                       lake_dir, p.get("domain", "other"), prover=prover)
            st = ed.campaign(disp, p["lean_target"], max_steps=max_steps)
            rung = st["best_rung"]
            if RUNG_VALUE.get(rung, 0.0) > RUNG_VALUE.get(best_rung_seen[p["id"]], 0.0):
                best_rung_seen[p["id"]] = rung
            # CALIBRATION: a frozen-calibration problem must never reach a solve.
            if p.get("tier") == "frozen_calibration" and rung == "L6":
                violations.append(f"iter{it}:{p['id']}")
            # FRONTIER: an L6 on a frontier_attack problem is not a violation,
            # but it is reportable as a solve ONLY through the solve-claim
            # protocol (math-solve audit + independent re-derivation + novelty
            # + human gate). Until SOLVE_ACCEPTED it stays an internal result.
            elif p.get("tier") == "frontier_attack" and rung == "L6":
                solve_claims_required.append({
                    "iteration": it, "id": p["id"],
                    "required": "solve_claim_protocol: open -> add-rederivation -> add-novelty -> human-gate",
                })
            per_problem.append({"id": p["id"], "rung": rung, "status": st["status"],
                                "tier": p.get("tier", "open")})

        if closure_ledger:
            _train_value_model(library, closure_ledger)

        graded = [r for r in per_problem if r["tier"] != "frozen_calibration"]
        solved = sum(1 for r in graded if r["rung"] == "L6")
        mean_rung = round(sum(RUNG_VALUE.get(r["rung"], 0.0) for r in graded) / len(graded), 4) if graded else 0.0
        log.append({
            "iteration": it, "solved": solved, "graded": len(graded),
            "mean_rung_value": mean_rung, "library_size": _library_size(library),
            "calibration_clean": not violations, "per_problem": per_problem,
        })

    caps = [r["solved"] for r in log]
    means = [r["mean_rung_value"] for r in log]
    turned = (len(caps) >= 2 and (caps[-1] > caps[0] or means[-1] > means[0]))
    return {
        "schema": "witsoc.autonomous_campaign.v1",
        "iterations": iterations,
        "portfolio_size": len(portfolio),
        "log": log,
        "best_rung_per_problem": best_rung_seen,
        "verdict": "FLYWHEEL_TURNS" if turned else "PLATEAU",
        "calibration_clean": not violations,
        "calibration_violations": violations,
        "solve_claims_required": solve_claims_required,
        "note": ("a campaign reaches SOLVED only at a kernel-verified L6; one calibration violation "
                 "fails the whole campaign. A frontier_attack L6 is reportable as a solve only after "
                 "solve_claim_protocol reaches SOLVE_ACCEPTED. PLATEAU is honest (corpus at ceiling); "
                 "the library and value model still compound underneath."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--portfolio", type=Path, required=True, help="JSON list of {id, lean_target, preamble?, domain?, tier?}")
    ap.add_argument("--iterations", type=int, default=2)
    ap.add_argument("--max-steps", type=int, default=6)
    ap.add_argument("--library", type=Path, default=None)
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--lovasz-run", type=Path, default=None,
                    help="Lovasz run dir (with lovasz_run.json) this campaign belongs to")
    ap.add_argument("--standalone", action="store_true",
                    help="explicit opt-out of the Lovasz run context (recorded in output)")
    args = ap.parse_args()

    # Ownership gate (references/core/services.md): the flywheel is SOLVER
    # machinery — it runs inside a Lovasz campaign context, not bare.
    # research_campaign (the scheduler) creates per-problem contexts itself.
    if args.lovasz_run is None and not args.standalone:
        print(json.dumps({"error": "autonomous_campaign is Lovasz-owned: pass --lovasz-run <dir> "
                                   "(with lovasz_run.json) or an explicit --standalone"}), file=sys.stderr)
        return 2
    if args.lovasz_run is not None and not (args.lovasz_run / "lovasz_run.json").exists():
        print(json.dumps({"error": f"no lovasz_run.json in {args.lovasz_run}; "
                                   "run lovasz_run_manifest.py first"}), file=sys.stderr)
        return 2

    portfolio = json.loads(args.portfolio.read_text(encoding="utf-8"))
    if isinstance(portfolio, dict):
        portfolio = portfolio.get("problems", [])
    # Deep runs push into the LIVE knowledge store and prove in MATHLIB MODE by
    # default (knowledge-stores.md): results compound across runs and the
    # prover gets ring/nlinarith reach. Override with --library/--lake-dir;
    # WITSOC_CORE_ONLY=1 forces core Lean.
    library = args.library or witcore.global_library()
    lake_dir = witcore.enable_mathlib_mode(args.lake_dir)
    closure_ledger = library / "closures.json"
    report = run(portfolio, library, args.iterations, args.max_steps, lake_dir,
                 closure_ledger=closure_ledger)
    report["lovasz_run"] = str(args.lovasz_run) if args.lovasz_run else None
    report["standalone"] = bool(args.standalone)
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "log"} |
                     {"log": [{kk: vv for kk, vv in r.items() if kk != "per_problem"} for r in report["log"]]},
                     indent=2, ensure_ascii=False))
    return 0 if report["calibration_clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
