#!/usr/bin/env python3
"""F1 reduction hunt — `witsoc reduction-hunt`.

The campaign mode whose only goal is the historically decisive step: find a
FINITE statement family relevant to the target and check it with verified
computation. Detection is deterministic (signature scan over the frozen
target / barrier text for finite-reducible shapes), execution walks each
family's parameter upward — every SAT instance is a re-verified
witness/lower-bound, the first UNSAT is a checked refutation/upper-bound —
producing a BRACKET plus the next escalation instance when the budget stops
the scan.

Detected shapes (all backed by sat_backend encoders):
  ramsey      "R(s,t)" / "ramsey"            -> scan n: witness bracket for R(s,t)
  vdw         "W(k)" / "van der waerden"     -> scan n: bracket for W(2,k)
  schur       "schur"                        -> scan n: bracket for S(2)
  chromatic   "chromatic"/"coloring" (+ grotzsch/mycielski/triangle-free,
              cycle, complete)               -> scan k: chromatic-number bracket
  covering    "covering system" + a moduli list {m1, m2, ...} -> single instance

Output: reduction_hunt.json with per-family instance certificates, the
bracket, a `dag_node_draft` per checked fact (type computational_certificate,
`proposed_status` only — the acceptance layer assigns real statuses), and
`next_escalation` for bound growth. Everything is CHECKED-grade bounded
evidence; nothing here upgrades a claim.

The `finite_reduction` engine arm self-seeds from `detect()` when the
campaign context carries no explicit encoding.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import sat_backend as sb  # noqa: E402

DEFAULT_SCAN_CAP = 10
DEFAULT_MAX_DECISIONS = 200_000


def detect(text: str) -> list[dict]:
    """Deterministic signature scan -> finite instance families."""
    t = text.lower()
    families: list[dict] = []

    m = re.search(r"r\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", t)
    if m or "ramsey" in t:
        s, tt = (int(m.group(1)), int(m.group(2))) if m else (3, 3)
        families.append({"encoder": "ramsey", "params": {"s": s, "t": tt},
                         "scan": {"param": "n", "start": max(s, tt)},
                         "rationale": f"Ramsey signature: bracket R({s},{tt}) by witness/refutation scan over n"})

    m = re.search(r"w\s*\(\s*(?:2\s*,\s*)?(\d+)\s*\)", t)
    if "van der waerden" in t or "vdw" in t or (m and "waerden" in t):
        k = int(m.group(1)) if m else 3
        families.append({"encoder": "vdw", "params": {"k": k},
                         "scan": {"param": "n", "start": k + 1},
                         "rationale": f"van der Waerden signature: bracket W(2,{k}) over n"})

    if "schur" in t:
        families.append({"encoder": "schur", "params": {},
                         "scan": {"param": "n", "start": 2},
                         "rationale": "Schur signature: bracket S(2) over n"})

    if "chromatic" in t or "coloring" in t or "colouring" in t:
        if "grotzsch" in t or "grötzsch" in t or "mycielski" in t or "triangle-free" in t:
            family, n = "grotzsch", 0
        elif "complete" in t:
            family, n = "complete", _first_int(t, default=4)
        else:
            family, n = "cycle", _first_int(t, default=5)
        families.append({"encoder": "graph-coloring", "params": {"family": family, "n": n},
                         "scan": {"param": "k", "start": 2, "until": "sat"},
                         "rationale": f"chromatic signature: bracket chi({family}) over k "
                                      "(UNSAT below chi, first SAT at chi)"})

    m = re.search(r"covering[^{]*\{\s*([\d\s,]+)\}", t)
    if m:
        moduli = [int(x) for x in re.findall(r"\d+", m.group(1))]
        if len(moduli) >= 2:
            families.append({"encoder": "covering", "params": {"moduli": moduli},
                             "scan": None,
                             "rationale": f"covering-system signature: decide existence for moduli {moduli}"})
    return families


def _first_int(text: str, default: int) -> int:
    m = re.search(r"\b(\d+)\b", text)
    return int(m.group(1)) if m else default


def _encode(encoder: str, params: dict) -> dict:
    if encoder == "ramsey":
        return sb.encode_ramsey(params["n"], params["s"], params["t"])
    if encoder == "vdw":
        return sb.encode_vdw(params["n"], params["k"])
    if encoder == "schur":
        return sb.encode_schur(params["n"])
    if encoder == "graph-coloring":
        n, edges = sb.GRAPH_FAMILIES[params["family"]](params.get("n", 0))
        label = params["family"] if params["family"] == "grotzsch" else f"{params['family']}({params.get('n')})"
        return sb.encode_graph_coloring(n, edges, params["k"], label)
    if encoder == "covering":
        return sb.encode_covering(params["moduli"])
    raise ValueError(f"unknown encoder {encoder!r}")


def _run_one(encoder: str, params: dict, max_decisions: int) -> dict:
    enc = _encode(encoder, params)
    outcome = sb.solve_internal(enc["num_vars"], enc["clauses"], max_decisions)
    record = {"params": dict(params), "result": outcome["result"]}
    if outcome["result"] == "SAT":
        record["witness_verified"] = sb.verify_witness(enc["clauses"], outcome.get("witness") or {})
        record["meaning"] = enc["sat_means"]
    elif outcome["result"] == "UNSAT":
        record["refutation"] = outcome.get("refutation")
        record["meaning"] = enc["unsat_means"]
    else:
        record["reason"] = outcome.get("reason")
    return record


def run_family(family: dict, max_decisions: int, scan_cap: int) -> dict:
    """Walk the scan parameter upward: SAT instances are verified lower-bound
    witnesses; the first UNSAT closes the bracket; budget stops are honest."""
    encoder = family["encoder"]
    instances: list[dict] = []
    bracket: dict[str, Any] = {}
    next_escalation = None

    if family.get("scan") is None:
        instances.append(_run_one(encoder, family["params"], max_decisions))
    else:
        scan_param, value = family["scan"]["param"], family["scan"]["start"]
        # scan direction: witness families go SAT..SAT,UNSAT (until=unsat,
        # default); threshold families like chromatic number go
        # UNSAT..UNSAT,SAT (until=sat) — the bracket closes on the flip.
        until = str(family["scan"].get("until", "unsat"))
        for _ in range(scan_cap):
            params = {**family["params"], scan_param: value}
            record = _run_one(encoder, params, max_decisions)
            instances.append(record)
            if record["result"] == "SAT" and record.get("witness_verified"):
                if until == "sat":
                    bracket["first_sat"] = {scan_param: value, "meaning": record["meaning"]}
                    break
                bracket["last_sat"] = {scan_param: value, "meaning": record["meaning"]}
            elif record["result"] == "UNSAT":
                if until == "unsat":
                    bracket["first_unsat"] = {scan_param: value, "meaning": record["meaning"]}
                    break
                bracket["last_unsat"] = {scan_param: value, "meaning": record["meaning"]}
            elif record["result"] == "UNKNOWN":
                next_escalation = {**family["params"], scan_param: value,
                                   "note": "budget exhausted here; rerun with a real SAT solver or higher --max-decisions"}
                break
            value += 1
        else:
            next_escalation = {**family["params"], scan_param: value,
                               "note": f"scan cap {scan_cap} reached; the next instance to try"}

    drafts = []
    for record in instances:
        if record["result"] == "UNSAT" or (record["result"] == "SAT" and record.get("witness_verified")):
            drafts.append({
                "node_id": f"finite_{encoder}_" + "_".join(f"{k}{v}" for k, v in sorted(record["params"].items())
                                                           if not isinstance(v, list)),
                "type": "computational_certificate",
                "statement": record["meaning"],
                "proposed_status": "CHECKED_BOUNDED",
                "evidence": [f"sat_backend {encoder} {record['params']}: {record['result']}"
                             + (f" ({record.get('refutation')})" if record.get("refutation") else " (witness re-verified)")],
                "note": "draft node: the acceptance layer assigns real statuses",
            })

    return {"encoder": encoder, "rationale": family["rationale"], "instances": instances,
            "bracket": bracket, "next_escalation": next_escalation, "dag_node_drafts": drafts}


def hunt(text: str, max_decisions: int, scan_cap: int) -> dict:
    families = detect(text)
    results = [run_family(f, max_decisions, scan_cap) for f in families]
    return {
        "schema": "witsoc.reduction_hunt.v1",
        "target_excerpt": text[:300],
        "families_detected": len(families),
        "results": results,
        "checked_facts": sum(len(r["dag_node_drafts"]) for r in results),
        "note": ("CHECKED-grade bounded evidence only. Drafts carry proposed_status; merge into the "
                 "proof DAG through the normal acceptance layer. SAT brackets are witness lower bounds; "
                 "UNSAT entries are checked refutations of the stated finite instance."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default="", help="frozen target / barrier text to scan")
    ap.add_argument("--run-dir", type=Path, default=None,
                    help="Lovasz run dir: read the frozen target from lovasz_run.json, write reduction_hunt.json")
    ap.add_argument("--max-decisions", type=int, default=DEFAULT_MAX_DECISIONS)
    ap.add_argument("--scan-cap", type=int, default=DEFAULT_SCAN_CAP)
    ap.add_argument("--detect-only", action="store_true", help="report detected families without solving")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    text = args.target
    if args.run_dir is not None:
        try:
            manifest = json.loads((args.run_dir / "lovasz_run.json").read_text(encoding="utf-8"))
            text = (text + " " + str(manifest.get("source_target_text") or "")).strip()
        except Exception:
            pass
    if not text:
        raise SystemExit("nothing to scan: pass --target text and/or --run-dir with a lovasz_run.json")

    if args.detect_only:
        report = {"schema": "witsoc.reduction_hunt.v1", "detect_only": True, "families": detect(text)}
    else:
        report = hunt(text, args.max_decisions, args.scan_cap)
    out = args.out or (args.run_dir / "reduction_hunt.json" if args.run_dir else None)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
