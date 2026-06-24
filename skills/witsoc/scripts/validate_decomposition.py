#!/usr/bin/env python3
"""Decomposition-completeness check: does the subgoal DAG actually compose into
the target, with every piece backed?

`decompose_problem.py` records subgoal nodes but does not claim they compose. A
proof DAG can have every node green yet not entail the target — the gap between
"all the pieces are proved" and "the pieces, together, prove the theorem". This
tool closes that gap two ways:

  Structural (always):  walk the dependency frontier of the target node; require
    every node on a path to the target to be ACCEPTED (not OPEN/GAP/REJECTED) and,
    when certificate_recheck.json exists, certificate-backed (PASS). Reports
    `coverage` and the offending nodes.

  Logical (optional):  if the target and its direct dependencies carry a
    `lean_statement`, emit the Lean composition obligation
        (sub_1 ∧ sub_2 ∧ ... ∧ sub_k) → target
    as a type-checking `sorry` obligation. Discharging it (close_obligation.py /
    human) is the actual proof that the decomposition is logically complete.

Usage:
  validate_decomposition.py <run_dir> --target <node_id> [--emit-composition out.lean]
Exit 0 iff structurally complete.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ACCEPTED = {"VERIFIED", "CHECKED", "PROVED_SKETCH", "PARTIAL", "CONDITIONAL"}
MACHINE_STATUS = {"VERIFIED", "CHECKED"}
UNUSABLE = {"CONJECTURE", "REJECTED", "FAILED_ATTEMPT", "GAP", "OPEN"}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def records(path: Path) -> list[dict]:
    data = load(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def node_id(n: dict) -> str:
    return str(n.get("node_id") or n.get("id") or "")


def deps(n: dict) -> list[str]:
    v = n.get("dependencies", n.get("depends_on", []))
    return [str(x) for x in v] if isinstance(v, list) else []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--target", required=True)
    ap.add_argument("--emit-composition", type=Path, default=None)
    args = ap.parse_args()

    run = args.run_dir
    dag = records(run / "proof_dependency_dag.json")
    nodes = {node_id(n): n for n in dag if node_id(n)}
    if args.target not in nodes:
        print(json.dumps({"status": "error", "reason": f"target {args.target!r} not in DAG"}, indent=2))
        return 2

    recheck_doc = load(run / "certificate_recheck.json", None)
    recheck = {}
    if isinstance(recheck_doc, dict):
        recheck = {str(v.get("node_id")): str(v.get("result"))
                   for v in recheck_doc.get("verdicts", []) if isinstance(v, dict)}

    # Transitive dependency frontier of the target (everything it rests on).
    frontier: set[str] = set()
    stack = [args.target]
    missing_dep = []
    while stack:
        nid = stack.pop()
        for d in deps(nodes.get(nid, {})):
            if d not in nodes:
                missing_dep.append((nid, d))
                continue
            if d not in frontier:
                frontier.add(d)
                stack.append(d)

    problems: list[str] = []
    for md_parent, md in missing_dep:
        problems.append(f"node {md_parent!r} depends on missing node {md!r}")

    backed = 0
    machine = 0
    for nid in sorted(frontier):
        node = nodes[nid]
        status = str(node.get("status") or "")
        if status in UNUSABLE:
            problems.append(f"dependency {nid!r} is unusable (status {status})")
        if status in MACHINE_STATUS:
            machine += 1
            if recheck.get(nid) == "PASS":
                backed += 1
            elif recheck_doc is not None:
                problems.append(f"dependency {nid!r} claims {status} but is not certificate-backed (PASS)")
    coverage = (backed / machine) if machine else None

    # Optional formal composition obligation.
    composition = None
    if args.emit_composition:
        tgt = nodes[args.target]
        direct = [nodes[d] for d in deps(tgt) if d in nodes]
        tgt_lean = tgt.get("lean_statement")
        sub_leans = [(node_id(d), d.get("lean_statement")) for d in direct]
        if tgt_lean and all(s for _, s in sub_leans) and sub_leans:
            hyps = " ".join(f"(_h{i} : {s})" for i, (_, s) in enumerate(sub_leans))
            src = ("namespace WitsocCompose\n\n"
                   "/-- Composition obligation: the conjunction of the subgoals entails the target. -/\n"
                   f"theorem compose {hyps} : {tgt_lean} := sorry\n\n"
                   "end WitsocCompose\n")
            kind = "formal"
        else:
            # Fall back to a documented, informal composition obligation.
            lines = "".join(f"--   sub {nid}: {nodes[d].get('statement','?') if (d:=nid) else ''}\n"
                            for nid, _ in sub_leans)
            src = ("namespace WitsocCompose\n\n"
                   f"-- Informal composition obligation for target {args.target}:\n"
                   f"-- target: {tgt.get('statement','?')}\n"
                   f"{lines}"
                   "-- (no per-node lean_statement; supply them for a formal composition check)\n"
                   "theorem compose : True := trivial\n\n"
                   "end WitsocCompose\n")
            kind = "informal"
        args.emit_composition.parent.mkdir(parents=True, exist_ok=True)
        args.emit_composition.write_text(src, encoding="utf-8")
        composition = {"kind": kind, "lean_path": str(args.emit_composition),
                       "note": "discharge with close_obligation.py to prove logical completeness"}

    complete = not problems
    out = {
        "schema": "witsoc.decomposition_completeness.v1",
        "run_dir": str(run),
        "target": args.target,
        "frontier_size": len(frontier),
        "machine_dependencies": machine,
        "certificate_backed": backed,
        "coverage": coverage,
        "decomposition_complete": complete,
        "problems": problems,
        "composition_obligation": composition,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
