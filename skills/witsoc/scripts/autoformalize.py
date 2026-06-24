#!/usr/bin/env python3
"""Autoformalization harness with a verification protocol (Tier B).

Translating an informal claim into a *faithful* Lean proposition is unsolved, and
"looks right" is not a guarantee. This tool does not certify faithfulness. It
provides the strongest machine checks available around the human judgement:

  1. TYPE-CHECK gate — every candidate must be a well-formed Lean `Prop`
     (ill-formed candidates, the common failure, are dropped).
  2. BACK-TRANSLATION — `--back-translate cmd:CMD` asks a model to render each
     compiling candidate back into English, surfaced next to the original claim
     so a human (or another model) can spot a mistranslation.
  3. MUTUAL EQUIVALENCE — `--check-equivalence` emits a Lean `(A) ↔ (B)`
     obligation for each pair of compiling candidates and tries to *prove* it with
     the prover. Candidates proven equivalent are grouped; this is a real,
     machine-checked guarantee that they say the same thing (to each other, not to
     the informal claim).

Semantic faithfulness to the informal claim stays `UNVERIFIED_NEEDS_HUMAN`.

Candidate sources: --candidate (repeatable), --candidates-file, --sampler cmd:CMD.

Usage:
  autoformalize.py --claim "..." --candidate "2 + 2 = 4" --candidate "4 = 2 + 2"
      [--imports "import Mathlib"] [--lake-dir DIR] [--back-translate cmd:CMD]
      [--check-equivalence] [--out formalization_candidates.json]
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


def typechecks(statement: str, imports: str, lake_dir: Path | None) -> dict[str, Any]:
    src = (f"{imports}\n" if imports else "") + (
        f"namespace WitsocAF\ntheorem candidate : {statement} := sorry\nend WitsocAF\n")
    v = witcore.lean_verify_cached(src, lake_dir)
    if not v.get("checked"):
        return {"compiles": "UNCHECKED", "reason": v.get("reason")}
    # Statement type-checks iff the build is green (the `sorry` is expected).
    return {"compiles": "PASS" if v.get("build_ok") else "FAIL", "reason": v.get("reason")}


def prove_iff(a: str, b: str, imports: str, lake_dir: Path | None) -> bool:
    """Ask the prover to prove (A) ↔ (B). True => machine-checked equivalent."""
    stmt = f"({a}) ↔ ({b})"
    cmd = [sys.executable, str(SCRIPT_DIR / "close_obligation.py"),
           "--lean-statement", stmt, "--name", "equiv", "--imports", imports,
           "--out-ledger", "/dev/null"]
    if lake_dir:
        cmd += ["--lake-dir", str(lake_dir)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
        return json.loads(r.stdout).get("discharged", False) if r.stdout.strip() else False
    except Exception:
        return False


def equivalence_classes(stmts: list[str], imports: str, lake_dir: Path | None) -> list[list[int]]:
    """Union-find over pairwise proven equivalences (indices into stmts)."""
    parent = list(range(len(stmts)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(stmts)):
        for j in range(i + 1, len(stmts)):
            if find(i) != find(j) and prove_iff(stmts[i], stmts[j], imports, lake_dir):
                parent[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for i in range(len(stmts)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claim", required=True)
    ap.add_argument("--candidate", action="append", default=[])
    ap.add_argument("--candidates-file", type=Path, default=None)
    ap.add_argument("--sampler", default=None, help="cmd:<command> proposer")
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--imports", default="")
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--back-translate", default=None, help="cmd:<command> Lean->informal")
    ap.add_argument("--check-equivalence", action="store_true")
    ap.add_argument("--out", type=Path, default=Path("formalization_candidates.json"))
    args = ap.parse_args()

    candidates: list[str] = list(args.candidate)
    if args.candidates_file and args.candidates_file.exists():
        candidates += [ln.strip() for ln in args.candidates_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if args.sampler and args.sampler.startswith("cmd:"):
        reply = witcore.run_sampler(args.sampler, {"claim": args.claim, "n_requested": args.n,
                                                   "instructions": "Return {\"candidates\":[\"<Lean Prop>\"...]}."})
        if isinstance(reply, dict):
            candidates += [str(c) for c in reply.get("candidates", []) if isinstance(c, str)]
    seen: set[str] = set()
    candidates = [c for c in candidates if not (c in seen or seen.add(c))]

    results = []
    for stmt in candidates:
        tc = typechecks(stmt, args.imports, args.lake_dir)
        entry = {"statement": stmt, "compiles": tc["compiles"], "compile_error": tc.get("reason"),
                 "semantic_equivalence": "UNVERIFIED_NEEDS_HUMAN"}
        if args.back_translate and args.back_translate.startswith("cmd:") and tc["compiles"] == "PASS":
            bt = witcore.run_sampler(args.back_translate, {"lean_statement": stmt})
            entry["back_translation"] = (bt or {}).get("informal")
        results.append(entry)

    well_formed = [r["statement"] for r in results if r["compiles"] == "PASS"]
    classes = None
    if args.check_equivalence and len(well_formed) >= 2:
        idx_groups = equivalence_classes(well_formed, args.imports, args.lake_dir)
        classes = [[well_formed[i] for i in g] for g in idx_groups]

    payload = {
        "schema": "witsoc.formalization_candidates.v1",
        "claim": args.claim,
        "candidates_total": len(results),
        "candidates_well_formed": len(well_formed),
        "proven_equivalence_classes": classes,
        "note": "compiles==PASS means well-formed Lean only; proven_equivalence_classes are "
                "machine-checked equivalences AMONG candidates; faithfulness to the informal "
                "claim is NOT verified (UNVERIFIED_NEEDS_HUMAN).",
        "candidates": results,
    }
    witcore.save_json(args.out, payload)
    print(json.dumps({k: v for k, v in payload.items() if k != "candidates"}, indent=2, ensure_ascii=False))
    return 0 if well_formed else 1


if __name__ == "__main__":
    raise SystemExit(main())
