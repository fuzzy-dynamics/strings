#!/usr/bin/env python3
"""Automated decomposition proposer (Tier F).

Finding the right lemma graph is the creative heart of a proof and is not solved
here. What this does is propose a *structured* subgoal DAG along standard schemas
(case split, induction, reduction) — or via a model (`--schema cmd:CMD`) — and
write it as proof_dependency_dag.json nodes so the rest of the spine can act on
it: validate_decomposition checks the pieces compose, close_obligation tries to
discharge each, recheck_certificates re-checks them.

A proposal is NOT a claim that the decomposition is correct or complete. It earns
that only when validate_decomposition's composition obligation is discharged and
every subgoal is certificate-backed.

Schemas:
  case_split  --mod K   : target restricted to each residue class mod K
  case_split            : target on the even case and the odd case
  induction             : base case + successor step
  reduction --to "L"    : target reduced to a single lemma L
  cmd:CMD               : model proposes {"subgoals":[{statement,lean_statement?}], ...}

Usage:
  auto_decompose.py --target "4/n = 1/x+1/y+1/z for n>=2" --schema case_split --mod 4 \
      --target-lean "P n" --out proof_dependency_dag.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402


def node(nid: str, statement: str, deps: list[str], lean: str | None, status: str = "OPEN") -> dict:
    n = {"node_id": nid, "status": status, "statement": statement,
         "dependencies": deps, "dependency_path_to_target": "decomposition"}
    if lean:
        n["lean_statement"] = lean
    return n


def propose(target: str, target_lean: str | None, schema: str, mod: int,
            reduce_to: str | None) -> list[dict]:
    nodes: list[dict] = []
    sub_ids: list[str] = []
    if schema == "case_split" and mod and mod > 1:
        for r in range(mod):
            sid = f"sub_res_{r}_mod_{mod}"
            sub_ids.append(sid)
            nodes.append(node(sid, f"{target}  (restricted to n ≡ {r} mod {mod})", [], None))
    elif schema == "case_split":
        for label in ("even", "odd"):
            sid = f"sub_{label}"
            sub_ids.append(sid)
            nodes.append(node(sid, f"{target}  (restricted to n {label})", [], None))
    elif schema == "induction":
        nodes.append(node("sub_base", f"base case of: {target}", [], None))
        nodes.append(node("sub_step", f"successor step of: {target}", [], None))
        sub_ids = ["sub_base", "sub_step"]
    elif schema == "reduction":
        lemma = reduce_to or "the key lemma"
        nodes.append(node("sub_lemma", f"lemma: {lemma}", [], None))
        sub_ids = ["sub_lemma"]
    else:
        raise SystemExit(f"unknown schema {schema!r}")
    nodes.append(node("target", target, sub_ids, target_lean))
    return nodes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True)
    ap.add_argument("--target-lean", default=None)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--mod", type=int, default=0)
    ap.add_argument("--to", dest="reduce_to", default=None)
    ap.add_argument("--out", type=Path, default=Path("proof_dependency_dag.json"))
    args = ap.parse_args()

    if args.schema.startswith("cmd:"):
        reply = witcore.run_sampler(args.schema, {"target": args.target, "target_lean": args.target_lean,
                                                  "instructions": "Return {\"subgoals\":[{\"statement\":...,"
                                                                  "\"lean_statement\":...}], \"composition\":...}."})
        subs = (reply or {}).get("subgoals") or []
        nodes = []
        sub_ids = []
        for i, s in enumerate(subs):
            sid = f"sub_{i}"
            sub_ids.append(sid)
            nodes.append(node(sid, str(s.get("statement", f"subgoal {i}")), [], s.get("lean_statement")))
        nodes.append(node("target", args.target, sub_ids, args.target_lean))
    else:
        nodes = propose(args.target, args.target_lean, args.schema, args.mod, args.reduce_to)

    # Merge into an existing DAG if present (preserve unrelated nodes).
    existing = witcore.records(args.out)
    keep = [n for n in existing if str(n.get("node_id")) not in {str(x["node_id"]) for x in nodes}]
    witcore.save_json(args.out, keep + nodes)
    print(json.dumps({"status": "proposed", "schema": args.schema,
                      "subgoals": [n["node_id"] for n in nodes if n["node_id"] != "target"],
                      "target_depends_on": nodes[-1]["dependencies"], "out": str(args.out),
                      "note": "proposal only; prove subgoals + discharge the composition obligation to validate"},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
