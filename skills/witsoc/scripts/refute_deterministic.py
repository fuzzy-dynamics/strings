#!/usr/bin/env python3
"""Item 8: deterministic adversarial refutation pass for an accepted claim/node.

Complements the LLM skeptic panel (skeptic_refute.py) with checks that need no
model and can only DEMOTE:

  * target_drift     node target_hash != frozen target hash        -> REJECTED
  * circular         node depends on itself / repeats in its path   -> REJECTED
  * counterexample   an explicit witness was found/supplied         -> REJECTED
  * precondition_gap a cited lemma does not resolve in Lean         -> GAP (demote)
  * vacuous          conclusion is `False`/`True` with no real content -> REJECTED/GAP

Never upgrades; on any hard refutation the claim is demoted. Degrades gracefully
(no Lean -> precondition audit is UNCHECKED, never a silent pass).

Usage:
  refute_deterministic.py --node node.json [--frozen-hash H] [--imports I] [--out J]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

HARD = "REJECTED"


def cited_names(node: dict) -> list[str]:
    """Lemma names a node/proof cites (for the precondition audit)."""
    text = " ".join(str(node.get(k, "")) for k in ("lean_statement", "proof", "evidence"))
    if isinstance(node.get("evidence"), list):
        text += " " + " ".join(str(x) for x in node["evidence"])
    # qualified identifiers like Nat.mul_comm / List.reverse_reverse
    return sorted(set(re.findall(r"\b([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\b", text)))


def refute(node: dict, frozen_hash: str | None, imports: str) -> dict:
    refutations: list[dict] = []
    demoted = None

    # target drift
    th = node.get("target_hash")
    if frozen_hash and th and th != frozen_hash:
        refutations.append({"check": "target_drift", "result": "REFUTED",
                            "detail": f"node hash {th[:12]}… != frozen {frozen_hash[:12]}…"})
        demoted = HARD

    # circular dependency
    nid = node.get("node_id")
    deps = node.get("dependencies") or []
    path = node.get("dependency_path_to_target") or []
    if nid and (nid in deps or path.count(nid) > 1):
        refutations.append({"check": "circular", "result": "REFUTED", "detail": f"{nid} depends on itself"})
        demoted = HARD

    # explicit counterexample supplied
    if node.get("counterexample"):
        refutations.append({"check": "counterexample", "result": "REFUTED",
                            "detail": f"witness {node['counterexample']}"})
        demoted = HARD

    # vacuous / trivial conclusion
    ls = str(node.get("lean_statement") or "")
    if re.search(r",\s*False\s*$", ls) and "→" not in ls and "->" not in ls:
        refutations.append({"check": "vacuous", "result": "REFUTED", "detail": "bare False conclusion"})
        demoted = HARD

    # precondition audit: cited lemmas must resolve in Lean (else search target)
    names = cited_names(node)
    precond = {"checked": False, "known": [], "unresolved": []}
    if names:
        for nm in names:
            verdict = witcore.lean_verify_cached((f"{imports}\n" if imports else "") + f"#check @{nm}\n", None)
            if not verdict.get("checked"):
                precond = {"checked": False, "known": [], "unresolved": []}
                break
            precond["checked"] = True
            (precond["known"] if verdict.get("build_ok") else precond["unresolved"]).append(nm)
        if precond["checked"] and precond["unresolved"]:
            refutations.append({"check": "precondition_gap", "result": "DEMOTE",
                                "detail": f"unresolved citations: {precond['unresolved']}"})
            if demoted is None:
                demoted = "GAP"

    return {
        "schema": "witsoc.deterministic_refutation.v1",
        "node_id": node.get("node_id"),
        "refuted": demoted == HARD,
        "demoted_status": demoted,           # None = survived; REJECTED/GAP otherwise
        "refutations": refutations,
        "precondition_audit": precond,
        "is_solve": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--node", type=Path, required=True)
    ap.add_argument("--frozen-hash", default=None)
    ap.add_argument("--imports", default="")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    node = witcore.load_json(args.node, {})
    result = refute(node, args.frozen_hash, args.imports)
    if args.out:
        witcore.save_json(args.out, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result["demoted_status"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
