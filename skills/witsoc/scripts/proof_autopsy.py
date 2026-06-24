#!/usr/bin/env python3
"""Proof autopsy — abstract kernel-verified proofs into reusable named techniques.

Mathematical taste is a compounding memory of which moves worked where. The
flywheel already harvests verified proofs for token-similarity reuse; this goes
one level up: after a closure, extract the load-bearing move, try to GENERALIZE
the statement (anti-unify integer literals into fresh universally quantified
parameters and re-prove — kernel-gated, so a false generalization is simply
rejected), fingerprint the technique, and store it in a global TECHNIQUE ATLAS
keyed by goal-structure signature. analogical_transfer then retrieves from the
atlas by signature overlap, so the curated analogy KB grows from actual runs.

CALIBRATION: the autopsy only ever records what the kernel re-verified. A
generalization without a kernel proof is not recorded as one; a closure that no
longer verifies is rejected (REJECTED_INPUT), not archived. Atlas entries are
retrieval hints (OPEN_UNFALSIFIED/SPECULATIVE on the suggestion side); they
never carry trust forward.

Usage:
  proof_autopsy.py --statement "<Lean stmt>" --proof "by ..." [--preamble P]
      [--imports I] [--lake-dir D] [--atlas PATH] [--out autopsy.json]
  proof_autopsy.py --closures closures.json [--max-records 20] ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
from value_function import featurize_goal  # noqa: E402

FORBIDDEN = ("sorry", "admit", "axiom", "native_decide")

# strategy fingerprints, checked in order — the first match names the move
_FINGERPRINTS: list[tuple[str, str]] = [
    ("generalization", r"\bhgen\b"),
    ("induction", r"\binduction\b"),
    ("library_premise", r"\b(exact|apply)\s+[A-Z][A-Za-z0-9_]*\."),
    ("conjunction_recombination", r"⟨.*⟩"),
    ("have_bridge", r"\bhave\b"),
    ("omega_arith", r"\bomega\b"),
    ("decide_finite", r"\bdecide\b"),
    ("ring_normalize", r"\bring\b"),
    ("simp_rewrite", r"\bsimp\b"),
]


def default_atlas() -> Path:
    return witcore.witsoc_home() / "technique_atlas.json"


def fingerprint(proof: str) -> str:
    for name, pat in _FINGERPRINTS:
        if re.search(pat, proof):
            return name
    return "direct"


def _verify(statement: str, proof: str, preamble: str, imports: str,
            lake_dir: Path | None) -> bool:
    if any(t in proof for t in FORBIDDEN) or any(t in statement for t in FORBIDDEN):
        return False
    header = (imports + "\n") if imports else ""
    pre = (preamble + "\n") if preamble else ""
    src = f"{header}{pre}theorem autopsy_check : {statement} := {proof}\n"
    return bool(witcore.lean_verify_cached(src, lake_dir).get("verified"))


def _fresh_var(statement: str) -> str:
    for v in ("m", "k", "j", "w"):
        if not re.search(rf"\b{v}\b", statement):
            return v
    return "m_autopsy"


def generalize(statement: str, proof: str, preamble: str, imports: str,
               lake_dir: Path | None, max_literals: int = 3) -> dict | None:
    """Anti-unify: replace one integer literal with a fresh ∀-bound parameter and
    re-prove. Kernel-gated — a false generalization (e.g. n+0=n ↛ ∀m, n+m=n) just
    fails every candidate and is NOT recorded. Returns the first verified
    generalization (most occurrences first = most uniform statement)."""
    literals = sorted({m for m in re.findall(r"\b\d+\b", statement)},
                      key=lambda c: -statement.count(c))[:max_literals]
    body = proof[2:].strip() if proof.strip().startswith("by") else proof.strip()
    for lit in literals:
        var = _fresh_var(statement)
        gen_stmt = f"∀ {var} : Nat, " + re.sub(rf"\b{re.escape(lit)}\b", var, statement)
        if gen_stmt == statement:
            continue
        candidates = [f"by intro {var}; {body}", "by intros; omega", "by intros; simp",
                      "by intros; simp_all", "by omega", "by simp"]
        for cand in candidates:
            if _verify(gen_stmt, cand, preamble, imports, lake_dir):
                return {"statement": gen_stmt, "proof": cand,
                        "generalized_literal": lit, "parameter": var,
                        "kernel_verified": True}
    return None


def _entry_key(name: str, signature: list[str]) -> str:
    return hashlib.sha256((name + "|" + ",".join(sorted(signature))).encode()).hexdigest()[:16]


def autopsy_one(statement: str, proof: str, *, preamble: str = "", imports: str = "",
                lake_dir: Path | None = None) -> dict:
    if not _verify(statement, proof, preamble, imports, lake_dir):
        return {"schema": "witsoc.proof_autopsy.v1", "statement": statement,
                "status": "REJECTED_INPUT",
                "reason": "closure does not kernel-verify (or carries forbidden tokens); "
                          "nothing is archived from an unverified proof"}
    move = fingerprint(proof)
    signature = featurize_goal(statement, preamble)
    gen = generalize(statement, proof, preamble, imports, lake_dir)
    return {
        "schema": "witsoc.proof_autopsy.v1",
        "status": "ARCHIVED",
        "statement": statement,
        "proof": proof,
        "move": move,
        "goal_signature": signature,
        "generalization": gen,
        "note": ("generalization kernel-verified: the parametric statement is the reusable form"
                 if gen else "no kernel-verified generalization found (literals may be essential)"),
    }


def record_to_atlas(report: dict, atlas_path: Path) -> dict:
    """Merge an ARCHIVED autopsy into the technique atlas; duplicate (move,
    signature) keys update stats instead of duplicating."""
    if report.get("status") != "ARCHIVED":
        return {"recorded": False, "reason": report.get("reason", "not archived")}
    atlas = witcore.load_json(atlas_path, [])
    if not isinstance(atlas, list):
        atlas = []
    key = _entry_key(report["move"], report["goal_signature"])
    for e in atlas:
        if e.get("key") == key:
            e["stats"]["uses"] = e["stats"].get("uses", 0) + 1
            e["examples"] = (e.get("examples", []) + [report["statement"]])[-4:]
            if report.get("generalization") and not e.get("generalization"):
                e["generalization"] = report["generalization"]
            witcore.save_json(atlas_path, atlas)
            return {"recorded": True, "key": key, "merged": True, "uses": e["stats"]["uses"]}
    atlas.append({
        "key": key,
        "move": report["move"],
        "goal_signature": report["goal_signature"],
        "proof_skeleton": report["proof"],
        "examples": [report["statement"]],
        "generalization": report.get("generalization"),
        "stats": {"uses": 1},
        "provenance": "proof_autopsy (kernel-verified closure)",
    })
    witcore.save_json(atlas_path, atlas)
    return {"recorded": True, "key": key, "merged": False, "uses": 1}


def suggest_from_atlas(statement: str, *, preamble: str = "", atlas_path: Path | None = None,
                       k: int = 3) -> list[dict]:
    """Retrieval for analogical_transfer: rank atlas techniques by goal-signature
    overlap (Jaccard) weighted by use count. Suggestions are SPECULATIVE hints in
    the same shape as the curated KB's — never trust."""
    atlas = witcore.load_json(atlas_path or default_atlas(), [])
    if not isinstance(atlas, list) or not atlas:
        return []
    sig = set(featurize_goal(statement, preamble))
    scored = []
    for e in atlas:
        esig = set(e.get("goal_signature", []))
        if not esig:
            continue
        jac = len(sig & esig) / len(sig | esig) if sig | esig else 0.0
        if jac <= 0:
            continue
        import math
        scored.append((jac * (1 + 0.2 * math.log1p(e.get("stats", {}).get("uses", 1))), jac, e))
    scored.sort(key=lambda x: -x[0])
    out = []
    for score, jac, e in scored[:k]:
        gen = e.get("generalization") or {}
        out.append({
            "technique": e["move"],
            "construction": f"reuse the '{e['move']}' move that closed a structurally similar goal; "
                            f"proof skeleton: {e['proof_skeleton']}",
            "matched_concepts": sorted(set(featurize_goal(statement, preamble)) &
                                       set(e.get("goal_signature", []))),
            "analogy_example": e.get("examples", [""])[0],
            "unlocks": (f"parametric form available: {gen.get('statement')}" if gen
                        else "goals sharing this structure signature"),
            "relevance": round(score, 4),
            "status": "OPEN_UNFALSIFIED",
            "arena": "SPECULATIVE",
            "source": "technique_atlas",
            "next_action": "instantiate the skeleton on the current goal and kernel-dispatch it",
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--statement", default=None)
    ap.add_argument("--proof", default=None)
    ap.add_argument("--closures", type=Path, default=None, help="batch: a closure ledger JSON list")
    ap.add_argument("--max-records", type=int, default=20)
    ap.add_argument("--preamble", default="")
    ap.add_argument("--imports", default="")
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--atlas", type=Path, default=None)
    ap.add_argument("--suggest", default=None, help="query mode: suggest techniques for this goal")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    atlas_path = args.atlas or default_atlas()

    if args.suggest:
        result = {"schema": "witsoc.technique_suggestions.v1", "goal": args.suggest,
                  "suggestions": suggest_from_atlas(args.suggest, preamble=args.preamble,
                                                    atlas_path=atlas_path)}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.out:
            witcore.save_json(args.out, result)
        return 0

    jobs: list[tuple[str, str, str]] = []
    if args.closures:
        for r in witcore.records(args.closures)[: args.max_records]:
            if r.get("statement") and r.get("proof"):
                jobs.append((r["statement"], r["proof"], r.get("preamble", "")))
    elif args.statement and args.proof:
        jobs.append((args.statement, args.proof, args.preamble))
    else:
        print(json.dumps({"error": "need --statement/--proof, --closures, or --suggest"}))
        return 2

    reports = []
    for stmt, proof, pre in jobs:
        rep = autopsy_one(stmt, proof, preamble=pre, imports=args.imports,
                          lake_dir=args.lake_dir)
        rep["atlas"] = record_to_atlas(rep, atlas_path)
        reports.append(rep)

    result = {"schema": "witsoc.proof_autopsy.v1", "atlas_path": str(atlas_path),
              "archived": sum(1 for r in reports if r["status"] == "ARCHIVED"),
              "rejected": sum(1 for r in reports if r["status"] == "REJECTED_INPUT"),
              "generalized": sum(1 for r in reports if r.get("generalization")),
              "reports": reports}
    if args.out:
        witcore.save_json(args.out, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
