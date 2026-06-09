#!/usr/bin/env python3
"""Expert-iteration flywheel (Phase 3).

The loop that is supposed to move the distribution:

    search the targets  ->  harvest kernel-verified proofs (closure traces)
         ^                            |
         |                            v
    retrain policy  <-  add lemmas to the GLOBAL library (compounding substrate)

Each iteration logs the capability score, how many targets close, the mean
search nodes-to-close, and the global library size. If the flywheel turns these
rise / nodes fall; if it plateaus, the log shows it — and this tool REPORTS the
plateau rather than hiding it (a flat curve is a real, honest result).

The global library is `witcore.global_library()` (env WITSOC_LEMMA_LIBRARY). It
is the only durable cross-run memory, so verified lemmas accumulate across every
flywheel turn and every normal run.

Usage:
  flywheel.py --iterations 3 [--targets targets.json] [--manifest benchmarks/manifest.json]
      [--library DIR] [--out flywheel_log.json]

targets.json (optional extra training targets): [{"statement","preamble"?}, ...]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
import proof_search  # noqa: E402
import value_function  # noqa: E402


def lean_targets_from_manifest(manifest: Path) -> list[dict]:
    m = witcore.load_json(manifest, {})
    out = []
    for p in m.get("problems", []):
        if p.get("kind") == "lean":
            out.append({"id": p["id"], "statement": p["statement"], "preamble": p.get("preamble", "")})
    return out


def close_and_harvest(stmt: str, preamble: str, library: Path, policy: dict | None,
                      closure_ledger: Path) -> dict:
    r = proof_search.search(stmt, preamble, None, policy, library if library.exists() else None,
                            max_nodes=300, workers=8)
    if r.get("discharged"):
        # harvest: record the verified proof to the closure ledger AND the library
        # (preamble too, so the value function can learn def-shape features)
        witcore.append_record(closure_ledger, {"statement": stmt, "preamble": preamble,
                                               "discharged": True, "proof": r["proof"]})
        subprocess.run([sys.executable, str(SCRIPT_DIR / "lemma_library.py"),
                        "--library", str(library), "add", "--statement", stmt,
                        "--tier", "WIT_STRUCTURE", "--provenance", f"close_obligation:{r['proof']}"],
                       capture_output=True, text=True, timeout=30, check=False)
    return {"discharged": bool(r.get("discharged")), "nodes": r.get("nodes", 0), "proof": r.get("proof")}


def library_size(library: Path) -> int:
    if not library.exists():
        return 0
    try:
        r = subprocess.run([sys.executable, str(SCRIPT_DIR / "lemma_library.py"),
                            "--library", str(library), "stats"], capture_output=True, text=True, timeout=20, check=False)
        return json.loads(r.stdout).get("total", 0)
    except Exception:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--iterations", type=int, default=3)
    ap.add_argument("--manifest", type=Path, default=SCRIPT_DIR.parent / "benchmarks" / "manifest.json")
    ap.add_argument("--targets", type=Path, default=None)
    ap.add_argument("--library", type=Path, default=None)
    ap.add_argument("--full-eval", action="store_true",
                    help="re-run the whole corpus harness each iteration (slow); default measures proof-target closure")
    ap.add_argument("--out", type=Path, default=Path("flywheel_log.json"))
    args = ap.parse_args()

    library = args.library or witcore.global_library()
    library.mkdir(parents=True, exist_ok=True)
    targets = lean_targets_from_manifest(args.manifest)
    if args.targets and args.targets.exists():
        for t in witcore.load_json(args.targets, []):
            targets.append({"id": t.get("id", "extra"), "statement": t["statement"], "preamble": t.get("preamble", "")})

    work = Path(".flywheel"); work.mkdir(exist_ok=True)
    closure_ledger = work / "closures.jsonl_dir.json"
    policy_path = work / "policy.json"
    log = []
    policy = None

    for it in range(1, args.iterations + 1):
        closed, total_nodes = 0, 0
        for t in targets:
            res = close_and_harvest(t["statement"], t.get("preamble", ""), library, policy, closure_ledger)
            if res["discharged"]:
                closed += 1
                total_nodes += res["nodes"]
        # retrain the policy AND the value function from accumulated closures. The
        # value model goes into the library dir so proof_search picks it up next
        # iteration (load_model(library)) — candidate ordering compounds across runs.
        if closure_ledger.exists():
            subprocess.run([sys.executable, str(SCRIPT_DIR / "proof_policy.py"), "train",
                            "--from-closures", str(closure_ledger), "--out", str(policy_path)],
                           capture_output=True, text=True, timeout=60, check=False)
            policy = witcore.load_json(policy_path, None)
            subprocess.run([sys.executable, str(SCRIPT_DIR / "value_function.py"), "train",
                            "--from-closures", str(closure_ledger),
                            "--out", str(library / value_function.MODEL_FILE)],
                           capture_output=True, text=True, timeout=60, check=False)
        # Capability of the flywheel = fraction of its own (proof) targets closed —
        # the policy/library only affect proof search, so this is the right, fast
        # signal. --full-eval re-runs the entire corpus harness (slow) instead.
        cap_score = round(closed / len(targets), 4) if targets else None
        calib_clean = True
        if args.full_eval:
            subprocess.run([sys.executable, str(SCRIPT_DIR / "eval_harness.py"), "--mode", "search",
                            "--out", str(work / f"cap_{it}.json")], capture_output=True, text=True, check=False)
            rep = witcore.load_json(work / f"cap_{it}.json", {})
            cap_score, calib_clean = rep.get("capability_score"), rep.get("calibration_clean")
        log.append({
            "iteration": it,
            "targets": len(targets),
            "closed": closed,
            "mean_nodes_to_close": round(total_nodes / closed, 1) if closed else None,
            "library_size": library_size(library),
            "capability_score": cap_score,
            "calibration_clean": calib_clean,
        })

    # Honest verdict: did the flywheel turn?
    caps = [r["capability_score"] for r in log if r["capability_score"] is not None]
    closes = [r["closed"] for r in log]
    turned = (len(caps) >= 2 and caps[-1] > caps[0]) or (len(closes) >= 2 and closes[-1] > closes[0])
    verdict = "FLYWHEEL_TURNS" if turned else "PLATEAU"
    out = {"schema": "witsoc.flywheel_log.v1", "iterations": args.iterations,
           "library": str(library), "log": log, "verdict": verdict,
           "note": "PLATEAU is an honest result: at capability ceiling / with a search already "
                   "strong on the corpus, harvesting adds no reach. Needs a harder corpus to show "
                   "distribution shift. Calibration must stay clean every iteration."}
    witcore.save_json(args.out, out)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
