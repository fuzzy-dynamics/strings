#!/usr/bin/env python3
"""Sustained research campaign — `witsoc research-campaign`. The nightly loop.

One invocation = one full pass of the discovery program over the curated
portfolio (benchmarks/research_portfolio.json):

  1. VALIDATE the portfolio (honesty contract; abort on violation).
  2. LEAN TRACK — autonomous_campaign over the kind=lean entries: research
     director per problem, MATHLIB MODE by default, harvest + value-model
     compounding into the LIVE library, frozen-calibration guard (one
     violation fails the run, exit 1).
  3. EXPERIMENTAL TRACK — backend adapters per kind=experimental entry:
       formula_synthesis  grammar-search witness families; whole-class lean
                          statement synthesized by exact residue substitution
                          and handed to the KERNEL-GATED prover; verified ->
                          KERNEL_VERIFIED family, else CONJECTURE with the
                          bounded evidence. All results -> discovery ledger
                          (novelty triage runs automatically).
       research_search    multiperfect/abundancy mining; each hit recorded as
                          a CHECKED arithmetic certificate (never kernel-grade).
     Entries whose backend has no adapter yet are reported `backend_pending`
     — never silently dropped.
  4. REPORT — <witsoc home>/campaigns/<stamp>/report.json: rung movement,
     library growth, ledger additions, calibration status, publishable set.

The chat agent's job is to READ the report and steer the portfolio; the loop
itself is script-driven (the miniF2F lesson: turn discipline, not math, is
what fails long campaigns).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import autonomous_campaign as ac  # noqa: E402
import campaign_budget_gate as bg  # noqa: E402
import discovery_ledger as dl     # noqa: E402
import formula_synthesis as fs    # noqa: E402
import lovasz_run_manifest as lrm  # noqa: E402
import novelty_triage as nt       # noqa: E402
import portfolio as pf            # noqa: E402
import witcore                    # noqa: E402


# --- formula_synthesis adapter -------------------------------------------------
_EXPR_FORMS = [
    (re.compile(r"^(\d+)$"), lambda m, a, b: (0, int(m.group(1)))),
    (re.compile(r"^n$"), lambda m, a, b: (a, b)),
    (re.compile(r"^(\d+)\*n$"), lambda m, a, b: (int(m.group(1)) * a, int(m.group(1)) * b)),
    (re.compile(r"^n\+(\d+)$"), lambda m, a, b: (a, b + int(m.group(1)))),
    # floor/ceil of (a*t+b)/c are exactly linear in t whenever c | a:
    # floor -> (a/c)t + floor(b/c), ceil -> (a/c)t + ceil(b/c).
    (re.compile(r"^n/(\d+)$"), lambda m, a, b: (a // int(m.group(1)), b // int(m.group(1)))
        if a % int(m.group(1)) == 0 else None),
    (re.compile(r"^ceil\(n/(\d+)\)$"), lambda m, a, b: (a // int(m.group(1)), (b + int(m.group(1)) - 1) // int(m.group(1)))
        if a % int(m.group(1)) == 0 else None),
]


def _subst(expr: str, a: int, b: int) -> tuple[int, int] | None:
    """Substitute n = a*t + b into a grammar expression; return (a', b') with
    value a'*t + b', or None when a division is not exact on the class."""
    expr = expr.replace(" ", "")
    for rx, fn in _EXPR_FORMS:
        m = rx.match(expr)
        if m:
            return fn(m, a, b)
    return None


def _poly(ab: tuple[int, int]) -> str:
    a, b = ab
    if a == 0:
        return str(b)
    base = f"{a} * t" if a != 1 else "t"
    return f"({base} + {b})" if b else f"({base})"


def family_to_lean(fam: dict) -> str | None:
    """Whole-class Lean identity for a witness family on n ≡ r (mod m), via
    n = m*t + (m + r) (t ranges over Nat; the shift keeps every witness
    positive and skips only the finitely many n < m+r, which the bounded
    check already covered)."""
    rc = fam.get("residue_class")
    if not isinstance(rc, dict):
        m, r = 1, 0
    else:
        m, r = rc["mod"], rc["rem"]
    a, b = m, m + r
    parts = [_subst(fam[k], a, b) for k in ("x", "y", "z")]
    if any(p is None for p in parts):
        return None
    if any(p[0] <= 0 and p[1] <= 0 for p in parts):
        return None  # a non-positive witness would make the family vacuous/false
    x, y, z = (_poly(p) for p in parts)
    n = _poly((a, b))
    return (f"∀ t : Nat, 4 * ({x} * ({y} * {z})) = "
            f"{n} * ({y} * {z} + {x} * {z} + {x} * {y})")


def _prove(statement: str, lake_dir: Path | None, timeout: int = 600) -> dict:
    cmd = [sys.executable, str(SCRIPT_DIR / "close_obligation.py"),
           "--lean-statement", statement, "--search", "--out-ledger", "/dev/null",
           "--imports", "import Mathlib.Tactic",
           "--use-library", "--record-library"]
    if lake_dir:
        cmd += ["--lake-dir", str(lake_dir)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {}


def run_formula_synthesis(entry: dict, lake_dir: Path | None) -> dict:
    spec = entry["spec"]
    relation = fs.PROBLEMS[spec["problem"]]
    fams = fs.synthesize(relation, spec["moduli"], spec["nmax"], spec.get("consts", [1, 2, 3, 4, 6]))
    results = []
    for fam in fams:
        rc = fam.get("residue_class")
        cls = f"n ≡ {rc['rem']} (mod {rc['mod']})" if isinstance(rc, dict) else "all n"
        claim = (f"Erdős–Straus witness family on {cls}: "
                 f"(x,y,z) = ({fam['x']}, {fam['y']}, {fam['z']})")
        lean = family_to_lean(fam)
        tier, statement, proof = "CONJECTURE", lean or fam["verified_on"], None
        # Novelty BEFORE proving: the prover harvests the statement into the
        # live library (--record-library), so a post-hoc triage would always
        # self-match as KNOWN_INTERNAL and under-report novelty.
        novelty = nt.triage(statement, keywords=claim.split()[:8])
        if lean:
            res = _prove(lean, lake_dir)
            if res.get("discharged"):
                tier, proof = "KERNEL_VERIFIED", res.get("proof")
        rec = dl.add_entry(
            claim=claim, kind="family", trust_tier=tier, statement=statement,
            problem_id=entry["id"],
            repro=(f"witsoc prove --search --lake-dir <mathlib4> --imports 'import Mathlib.Tactic' "
                   f"--lean-statement '{lean}'") if lean else
                  f"formula_synthesis bounded check: {fam['verified_on']}",
            evidence={"family": {k: fam[k] for k in ('x', 'y', 'z')},
                      "bounded": fam["verified_on"], "kernel_proof": proof},
            novelty=novelty)
        results.append({"class": cls, "tier": tier, "ledger": rec})
    return {"backend": "formula_synthesis", "families": len(fams), "results": results}


def run_research_search(entry: dict) -> dict:
    spec = entry["spec"]
    cmd = [sys.executable, str(SCRIPT_DIR / "research_search.py"), "number-theory",
           "--mode", spec.get("mode", "multiperfect"), "--limit", str(spec.get("limit", 100000))]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
        data = json.loads(r.stdout)
    except Exception:
        return {"backend": "research_search", "status": "backend_error"}
    rows = data.get("multiperfect", []) if isinstance(data, dict) else []
    results = []
    for row in rows:
        n, k = row.get("n"), row.get("k") or row.get("ratio")
        rec = dl.add_entry(
            claim=f"sigma({n}) = {k}*{n} (multiperfect witness)", kind="certificate",
            trust_tier="CHECKED", statement=f"sigma({n}) = {k}*{n}", problem_id=entry["id"],
            repro=f"python3 research_search.py number-theory --mode multiperfect --limit {spec.get('limit')}",
            sequence=[n] if isinstance(n, int) else None, evidence=row)
        results.append({"n": n, "ledger": rec})
    return {"backend": "research_search", "hits": len(rows), "results": results}


ADAPTERS = {
    "formula_synthesis": lambda entry, lake: run_formula_synthesis(entry, lake),
    "research_search": lambda entry, lake: run_research_search(entry),
}


# --- the campaign -------------------------------------------------------------
def run_campaign(portfolio_path: Path, iterations: int, max_steps: int,
                 lake_dir: Path | None, out_dir: Path | None, stamp: str | None = None) -> dict:
    data = pf.load(portfolio_path)
    errors = pf.validate(data)
    if errors:
        return {"status": "INVALID_PORTFOLIO", "errors": errors}

    lake = witcore.enable_mathlib_mode(lake_dir)
    library = witcore.global_library()
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    out = out_dir or (witcore.witsoc_home() / "campaigns" / stamp)
    out.mkdir(parents=True, exist_ok=True)
    before = dl.load_entries()

    # Phase 0 boundary: the scheduler prepares a persistent Lovasz run context
    # per lean problem (lovasz_run.json whose campaign block — budget,
    # escalation ladder, stall counters — survives across nightly passes) and
    # launches the campaign inside it. A problem at HONEST_STOP is skipped and
    # reported, never silently dropped. Calibration sentinels are exempt from
    # charging and escalation: their honesty role is permanent, so they are
    # always attacked.
    runs_root = witcore.witsoc_home() / "lovasz-runs"
    lean_problems = pf.emit_campaign(data)
    lovasz_runs: dict[str, dict] = {}
    active: list[dict] = []
    for p in lean_problems:
        run_dir = runs_root / p["id"]
        run_dir.mkdir(parents=True, exist_ok=True)
        handoff = run_dir / "handoff_v1.json"
        new_context = not handoff.exists()
        if new_context:
            witcore.save_json(handoff, {"frozen_target": p["lean_target"],
                                        "target_hash": lrm.sha256_text(p["lean_target"])})
        m = lrm.manifest(run_dir, lrm.infer_phase(run_dir), p["lean_target"], lrm.sha256_text(p["lean_target"]))
        witcore.save_json(run_dir / "lovasz_run.json", m)
        frontier = p.get("tier") == "frontier_attack"
        if new_context and frontier:
            # Frontier attacks are week-scale programs, not nightly slots: 10x
            # the default run budget. The per-barrier cap (three loops ->
            # obstruction) stays — it is doctrine, not budget.
            bg.set_budget(run_dir, max_attempts=600, max_time_minutes=4800.0)
        sentinel = p.get("tier") == "frozen_calibration"
        level = bg.load_campaign(run_dir)["escalation_level"]
        lovasz_runs[p["id"]] = {"run_dir": str(run_dir), "escalation_level": level,
                                "calibration_sentinel": sentinel,
                                "frontier_attack": frontier}
        if sentinel or level != "HONEST_STOP":
            active.append(p)
        else:
            lovasz_runs[p["id"]]["status"] = "SKIPPED_HONEST_STOP"

    lean_track = ac.run(active, library, iterations, max_steps, lake,
                        closure_ledger=library / "closures.json")

    # Charge each problem's run budget and walk the escalation ladder when the
    # gate recommends it (3 stalled passes) — the script-driven part of nightly
    # steering the docs used to leave to the chat agent.
    best_rungs = lean_track.get("best_rung_per_problem", {})
    for p in active:
        if p.get("tier") == "frozen_calibration":
            continue
        run_dir = Path(lovasz_runs[p["id"]]["run_dir"])
        bg.charge(run_dir, attempts=iterations)
        rung = best_rungs.get(p["id"])
        if rung:
            progress = bg.record_progress(run_dir, rung)
            lovasz_runs[p["id"]]["best_rung"] = progress["best_rung"]
            if progress["escalation_recommended"]:
                esc = bg.escalate(run_dir, reason=f"{progress['stall_count']} stalled passes at {progress['best_rung']}")
                lovasz_runs[p["id"]]["escalation_level"] = esc.get("escalation_level",
                                                                   lovasz_runs[p["id"]]["escalation_level"])
                lovasz_runs[p["id"]]["escalated"] = esc.get("reason")

    # A frontier_attack L6 is only an INTERNAL result until the solve-claim
    # protocol reaches SOLVE_ACCEPTED; surface what each claim still needs.
    solve_claims = []
    for req in lean_track.get("solve_claims_required", []):
        pid = req.get("id")
        entry = lovasz_runs.get(pid)
        record = {**req, "claim_status": "NOT_OPENED",
                  "next": "witsoc solve-claim open <run_dir> --problem-id " + str(pid)}
        if entry:
            entry["solve_claim_required"] = True
            claim = {}
            try:
                claim = json.loads((Path(entry["run_dir"]) / "solve_claim.json").read_text(encoding="utf-8"))
            except Exception:
                pass
            if isinstance(claim, dict) and claim.get("schema") == "witsoc.solve_claim.v1":
                record["claim_status"] = claim.get("status", "CLAIMED")
                record.pop("next", None)
            entry["solve_claim_status"] = record["claim_status"]
        solve_claims.append(record)

    experiments = []
    for entry in pf.emit_experiments(data):
        full = next(p for p in data["problems"] if p["id"] == entry["id"])
        adapter = ADAPTERS.get(full["backend"])
        if adapter is None:
            experiments.append({"id": entry["id"], "backend": full["backend"],
                                "status": "backend_pending",
                                "note": "no adapter yet; entry NOT silently dropped"})
            continue
        res = adapter(full, lake)
        experiments.append({"id": entry["id"], **res})

    after = dl.load_entries()
    new_ids = {e["id"] for e in after} - {e["id"] for e in before}
    new_entries = [e for e in after if e["id"] in new_ids]
    report = {
        "schema": "witsoc.research_campaign.v1",
        "stamp": stamp,
        "mathlib_mode": bool(lake),
        "library": str(library),
        "lovasz_runs": lovasz_runs,
        "solve_claims": solve_claims,
        "lean_track": {k: v for k, v in lean_track.items() if k != "log"},
        "lean_log": lean_track.get("log", []),
        "experiments": experiments,
        "ledger_additions": [{"id": e["id"], "kind": e["kind"], "claim": e["claim"],
                              "trust_tier": e["trust_tier"],
                              "novelty": e.get("novelty", {}).get("novelty")} for e in new_entries],
        "calibration_clean": lean_track.get("calibration_clean", False),
        "publishable": [{"id": e["id"], "claim": e["claim"]} for e in after if dl.publishable(e)],
        "note": ("Read this report, then steer the portfolio. SOLVED only ever means a "
                 "kernel-verified L6 on the stated rung; calibration sentinels must stay open. "
                 "A frontier_attack L6 is reportable as a solve of the named problem only after "
                 "solve_claim_protocol reaches SOLVE_ACCEPTED."),
    }
    witcore.save_json(out / "report.json", report)
    report["report_path"] = str(out / "report.json")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--portfolio", type=Path, default=pf.DEFAULT_PORTFOLIO)
    ap.add_argument("--iterations", type=int, default=1)
    ap.add_argument("--max-steps", type=int, default=6)
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()
    report = run_campaign(args.portfolio, args.iterations, args.max_steps, args.lake_dir, args.out_dir)
    print(json.dumps({k: v for k, v in report.items() if k != "lean_log"}, indent=2, ensure_ascii=False))
    if report.get("status") == "INVALID_PORTFOLIO":
        return 2
    return 0 if report.get("calibration_clean") else 1


if __name__ == "__main__":
    raise SystemExit(main())
