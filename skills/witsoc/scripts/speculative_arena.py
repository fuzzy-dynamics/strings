#!/usr/bin/env python3
"""Phase 3 (idea generator): the speculative-arena consequence loop.

A mathematician explores a hard target by ASSUMING a plausible bridge lemma H and
asking "what would H give me?". This automates that, kernel-gated:

  1. take SPECULATIVE bridges H1..Hn (from concept_generator / domain_barrier_lemmas /
     conjecture_to_lemma_pipeline — each unproved, `OPEN_UNFALSIFIED`/`SPECULATIVE`);
  2. CONSEQUENCE step: for each Hi, kernel-prove the CONDITIONAL `Hi -> T`. The
     implication is a real theorem even though Hi is not asserted. A discharged
     `Hi -> T` means "Hi is a SUFFICIENT bridge for the target";
  3. CONSEQUENCE GRAPH: kernel-prove `Hi -> Hj` to see which bridges imply others;
  4. rank bridges by LEVERAGE (sufficient-for-target + how many others it implies) —
     this tells Lovász which bridge is worth the effort to actually prove;
  5. PROMOTION (the only way out of the arena): try to prove the best bridge H
     UNCONDITIONALLY. If it discharges, COMPOSE `proof(H)` with `proof(H -> T)` to get
     a kernel proof of T (modus ponens of two verified proofs is sound), optionally
     re-verified. Only then does the target become a real claim.

CALIBRATION SPINE: the arena NEVER asserts a bridge or the target. Every bridge stays
`OPEN_UNFALSIFIED`/`SPECULATIVE`; a verified `H -> T` is a CONDITIONAL fact, not a solve.
The target is promoted to `CHECKED` only when H itself passes the kernel. So feeding it
the odd-perfect bridge yields, at most, "IF this bridge holds THEN odd-perfect-even" —
never a proof of the open problem.

Usage:
  speculative_arena.py --target "<Lean T>" --bridge "<Lean H1>" --bridge "<Lean H2>" ...
      [--imports P] [--lake-dir D] [--no-promote] [--out arena.json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

OPEN = "OPEN_UNFALSIFIED"
ARENA = "SPECULATIVE"
FORBIDDEN = ("sorry", "admit", "axiom", "native_decide")


def conditional(hyp: str, concl: str) -> str:
    return f"({hyp}) → ({concl})"


def explore(target: str, bridges: list[dict], prove, imports: str = "",
            consequence_graph: bool = True, promote: bool = True, verify=None) -> dict:
    """Pure core: `prove(statement, imports) -> {discharged, proof}` is the oracle
    (real prover or a mock). `verify(statement, proof, imports) -> bool` optionally
    re-checks the composed target proof. Returns the arena report."""
    arena: list[dict] = []
    for b in bridges:
        H = b["lean_statement"]
        cond = conditional(H, target)
        v = prove(cond, imports)
        arena.append({
            "bridge_id": b.get("id", H[:24]),
            "hypothesis": H,
            "conditional": cond,
            "conditional_verified": bool(v.get("discharged")),
            "conditional_proof": v.get("proof"),
            "implies_count": 0,
            "leverage": 0,
            "status": OPEN, "arena": ARENA,
            "interpretation": "kernel-verified that ASSUMING this bridge proves the target; "
                              "the bridge itself is NOT asserted.",
        })

    implications: list[dict] = []
    if consequence_graph:
        for a in bridges:
            for c in bridges:
                if a.get("id") == c.get("id"):
                    continue
                v = prove(conditional(a["lean_statement"], c["lean_statement"]), imports)
                if v.get("discharged"):
                    implications.append({"from": a.get("id"), "to": c.get("id")})
    implied = {}
    for im in implications:
        implied[im["from"]] = implied.get(im["from"], 0) + 1
    for node in arena:
        node["implies_count"] = implied.get(node["bridge_id"], 0)
        node["leverage"] = (2 if node["conditional_verified"] else 0) + node["implies_count"]
    arena.sort(key=lambda n: -n["leverage"])

    promoted = None
    if promote:
        for node in arena:
            if not node["conditional_verified"]:
                continue
            pv = prove(node["hypothesis"], imports)            # try to prove H itself
            if not pv.get("discharged"):
                continue
            # COMPOSE: (proof of H -> T) applied to (proof of H) is a proof of T.
            composed = f"({node['conditional_proof']}) ({pv.get('proof')})"
            ok = True
            if verify is not None:
                ok = bool(verify(target, composed, imports))
            if ok and not any(t in composed for t in FORBIDDEN):
                promoted = {
                    "bridge_id": node["bridge_id"],
                    "hypothesis": node["hypothesis"],
                    "bridge_proof": pv.get("proof"),
                    "conditional_proof": node["conditional_proof"],
                    "composed_target_proof": composed,
                    "target_status": "CHECKED",     # T now follows unconditionally (kernel-composed)
                    "composition": "modus ponens: proof(H) + proof(H -> T) => proof(T)",
                }
                node["promotion"] = "PROMOTED: bridge proven; target follows unconditionally"
                break

    # CALIBRATION (structural): the arena never asserts a bridge/target. Every bridge
    # stays OPEN_UNFALSIFIED/SPECULATIVE; only an explicit `promoted` (kernel-proven H)
    # turns the target into a claim.
    for node in arena:
        assert node["status"] == OPEN and node["arena"] == ARENA, "arena must not assert a bridge"

    return {
        "schema": "witsoc.speculative_arena.v1",
        "target": target,
        "bridges_explored": len(arena),
        "sufficient_bridges": [n["bridge_id"] for n in arena if n["conditional_verified"]],
        "arena": arena,
        "consequence_graph": implications,
        "promoted": promoted,
        "target_status": (promoted or {}).get("target_status", OPEN),
        "calibration": "verified `H -> T` are CONDITIONAL facts, not solves; the target is promoted to "
                       "CHECKED only when the bridge H itself passes the kernel. Bridges are never asserted.",
    }


def real_prover(lake_dir: Path | None = None, search: bool = True, timeout: int = 600):
    def prove(statement: str, imports: str = "") -> dict:
        cmd = [sys.executable, str(SCRIPT_DIR / "close_obligation.py"),
               "--lean-statement", statement, "--out-ledger", "/dev/null"]
        if search:
            cmd.append("--search")
        if imports:
            cmd += ["--imports", imports]
        if lake_dir:
            cmd += ["--lake-dir", str(lake_dir)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
            d = json.loads(r.stdout) if r.stdout.strip() else {}
        except Exception:
            d = {}
        return {"discharged": bool(d.get("discharged")), "proof": d.get("proof")}
    return prove


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True, help="frozen Lean target T")
    ap.add_argument("--bridge", action="append", dest="bridges", default=[], help="a speculative bridge H (repeatable)")
    ap.add_argument("--imports", default="")
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--no-promote", action="store_true", help="explore consequences only; do not try to prove bridges")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    bridges = [{"id": f"H{i+1}", "lean_statement": h, "status": OPEN, "arena": ARENA}
               for i, h in enumerate(args.bridges)]
    prove = real_prover(args.lake_dir)
    report = explore(args.target, bridges, prove, args.imports, promote=not args.no_promote)
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
