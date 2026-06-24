#!/usr/bin/env python3
"""A6 cluster campaigns — `witsoc cluster`.

Open problems rarely fall in isolation: counterexamples to nearby variants
prune dead approaches (Tao), proved weaker rungs become stepping stones, and
the same enemy haunts a whole family. A cluster campaign attacks the frozen
target TOGETHER WITH its posed variants under ONE shared problem theory:

  init      pose stronger/weaker/boundary variants of the run's lean target
            (pose_variants) and record the cluster in cluster.json + theory
  run       dispatch the kernel prover (and the Nexus fleet when configured)
            on each variant with a small budget; every outcome transfers:
              proved weaker rung  -> positive example + library harvest
              refuted stronger    -> enemy constraint (which hypothesis is
                                     load-bearing) + negative example
              boundary stress     -> example zoo
  status    the cluster scoreboard

Transfer is the point: nothing here touches the frozen target's status — the
cluster informs the THEORY that the main attack reads.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import problem_theory as pt  # noqa: E402
import witcore  # noqa: E402

CLUSTER_NAME = "cluster.json"


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def init_cluster(run: Path, lean_target: str = "", bound: int = 32) -> dict:
    if not lean_target:
        manifest = _load(run / "lovasz_run.json", {})
        lean_target = str(manifest.get("source_target_text") or "")
    import pose_variants as pv
    doc = pv.generate(lean_target, bound=bound)
    variants = []
    for role, bucket in (("stronger", "stronger"), ("weaker", "weaker"), ("boundary", "boundary")):
        for v in doc.get(bucket, []) or []:
            variants.append({"variant_id": f"{role[0]}{len(variants) + 1}",
                             "role": role, "lean": v.get("lean_statement"),
                             "why": v.get("why"), "kind": v.get("kind"),
                             "status": "OPEN"})
    cluster = {"schema": "witsoc.cluster.v1", "run_dir": str(run),
               "target": lean_target, "variants": variants,
               "note": "cluster outcomes inform the THEORY; the frozen target's status is untouched"}
    witcore.save_json(run / CLUSTER_NAME, cluster)
    pt.init_theory(run)
    pt.update_theory(run, {"add_technique": {
        "technique": "cluster campaign", "source": "pose_variants",
        "outcome": f"{len(variants)} variants posed (stronger/weaker/boundary)"}},
        why="cluster initialized")
    return cluster


def run_cluster(run: Path, limit: int = 6, search: bool = False,
                use_nexus: bool = False) -> dict:
    cluster = _load(run / CLUSTER_NAME, None)
    if not isinstance(cluster, dict):
        raise SystemExit(f"no cluster.json in {run}; run `witsoc cluster init` first")
    import close_obligation as co
    theory_ctx = pt.prompt_context(run) if pt.theory_path(run).exists() else None

    attempted = 0
    transfers = []
    for v in cluster["variants"]:
        if attempted >= limit or v["status"] != "OPEN" or not v.get("lean"):
            continue
        attempted += 1
        result = co.close_goal(str(v["lean"]), name=f"cluster_{v['variant_id']}",
                               search=search, record_library=True)
        if not result.get("discharged") and use_nexus:
            try:
                import nexus_loop as nx
                fleet_result = nx.fleet_prove(str(v["lean"]), theory=theory_ctx,
                                              deterministic_first=False)
                if fleet_result.get("discharged"):
                    result = {"discharged": True, "proof": fleet_result["proof"],
                              "label": "PROOF_DISCHARGED", "via": fleet_result["via"]}
            except Exception:
                pass
        if result.get("discharged"):
            v["status"] = "PROVED"
            v["proof"] = result.get("proof")
            patch = {"add_positive_example": {
                "object": v["lean"], "why": f"{v['role']} variant kernel-proved ({v['kind']})"}}
            if v["role"] == "stronger":
                # a PROVED stronger variant supersedes the target outright — flag loudly
                patch["set_enemy_verdict"] = "STRONGER_VARIANT_PROVED_REVIEW_TARGET"
            transfers.append({"variant": v["variant_id"], "transfer": "positive_example"})
        else:
            v["status"] = "OPEN_AFTER_ATTEMPT"
            v["last_label"] = result.get("label")
            if v["role"] == "stronger":
                # stronger variants are TRY-TO-BREAK targets; route to the
                # dialectic rather than recording mere failure-to-prove.
                transfers.append({"variant": v["variant_id"],
                                  "transfer": "stronger-variant open; counterexample search is the next move"})
                continue
            patch = None
        if patch:
            pt.update_theory(run, patch, why=f"cluster transfer from {v['variant_id']}")
    witcore.save_json(run / CLUSTER_NAME, cluster)
    counts: dict[str, int] = {}
    for v in cluster["variants"]:
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    return {"schema": "witsoc.cluster_run.v1", "attempted": attempted,
            "counts": counts, "transfers": transfers}


def status(run: Path) -> dict:
    cluster = _load(run / CLUSTER_NAME, None)
    if not isinstance(cluster, dict):
        raise SystemExit(f"no cluster.json in {run}")
    counts: dict[str, int] = {}
    for v in cluster["variants"]:
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    return {"target": cluster["target"], "variants": len(cluster["variants"]),
            "counts": counts,
            "proved": [{"id": v["variant_id"], "role": v["role"], "lean": v["lean"]}
                       for v in cluster["variants"] if v["status"] == "PROVED"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("run_dir", type=Path)
    p_init.add_argument("--lean-target", default="")
    p_init.add_argument("--bound", type=int, default=32)
    p_run = sub.add_parser("run")
    p_run.add_argument("run_dir", type=Path)
    p_run.add_argument("--limit", type=int, default=6)
    p_run.add_argument("--search", action="store_true")
    p_run.add_argument("--nexus", action="store_true")
    p_st = sub.add_parser("status")
    p_st.add_argument("run_dir", type=Path)
    args = ap.parse_args()

    if args.cmd == "init":
        result = init_cluster(args.run_dir, args.lean_target, args.bound)
        result = {"variants": len(result["variants"]), "cluster": str(args.run_dir / CLUSTER_NAME)}
    elif args.cmd == "run":
        result = run_cluster(args.run_dir, args.limit, args.search, args.nexus)
    else:
        result = status(args.run_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
