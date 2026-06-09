#!/usr/bin/env python3
"""Phase 3: the speculative-arena consequence loop (deterministic, mock prover).

The calibration-critical property: the arena can VERIFY that assuming a bridge proves
the target (`H -> T`), rank that bridge as high-leverage, and STILL leave the target
open — because the bridge itself is unproved. The target becomes a claim only when the
bridge is independently proven (promotion), via composing the two kernel proofs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import speculative_arena as sa

T = "∀ n : Nat, fb n 1 = 2 ^ n"          # target (open to the prover)
H1 = "∀ n a : Nat, fb n a = a * 2 ^ n"   # the SUFFICIENT generalized bridge (also open)
H2 = "∀ n : Nat, fb n 0 = 0"             # a true-but-useless bridge (does not give T)
BRIDGES = [{"id": "H1", "lean_statement": H1}, {"id": "H2", "lean_statement": H2}]


def mock_prover(can_prove_bridge: bool):
    """`H1 -> T` is provable; `H2 -> T` is not; H1/H2 themselves are provable only when
    `can_prove_bridge` is set (simulating a later/stronger run)."""
    def prove(statement: str, imports: str = "") -> dict:
        s = statement.replace(" ", "")
        cond_H1_T = sa.conditional(H1, T).replace(" ", "")
        if s == cond_H1_T:
            return {"discharged": True, "proof": "by intro h n; simp [h]"}
        if statement in (H1, H2):
            return {"discharged": can_prove_bridge, "proof": "by <bridge proof>"} if can_prove_bridge else {"discharged": False, "proof": None}
        return {"discharged": False, "proof": None}   # H2->T and everything else: open
    return prove


def main() -> int:
    failures: list[str] = []

    # 1. Consequence step WITHOUT promotion power: H1 is a verified sufficient bridge,
    #    ranked first — but the target STAYS OPEN (bridge unproved). This is the point.
    rep = sa.explore(T, BRIDGES, mock_prover(can_prove_bridge=False), promote=True)
    if "H1" not in rep["sufficient_bridges"]:
        failures.append(f"H1 should be a verified sufficient bridge (H1->T), got {rep['sufficient_bridges']}")
    if "H2" in rep["sufficient_bridges"]:
        failures.append("H2 must NOT be sufficient (H2->T not provable)")
    if rep["arena"][0]["bridge_id"] != "H1":
        failures.append(f"the sufficient bridge should rank first by leverage, got {rep['arena'][0]['bridge_id']}")
    if rep["promoted"] is not None:
        failures.append("with an unprovable bridge, nothing may be promoted")
    if rep["target_status"] != sa.OPEN:
        failures.append(f"target must stay OPEN_UNFALSIFIED when the bridge is unproved, got {rep['target_status']}")
    for n in rep["arena"]:
        if n["status"] != sa.OPEN or n["arena"] != sa.ARENA:
            failures.append("every bridge must remain OPEN_UNFALSIFIED/SPECULATIVE (never asserted)")

    # 2. PROMOTION: once the bridge is provable, compose proof(H1)+proof(H1->T) => T,
    #    and the target becomes CHECKED (the only way out of the arena).
    rep2 = sa.explore(T, BRIDGES, mock_prover(can_prove_bridge=True), promote=True)
    pr = rep2["promoted"]
    if not pr or pr["bridge_id"] != "H1":
        failures.append(f"a provable sufficient bridge must promote, got {pr}")
    elif rep2["target_status"] != "CHECKED":
        failures.append(f"promotion must mark the target CHECKED, got {rep2['target_status']}")
    elif "composed_target_proof" not in pr or "by <bridge proof>" not in pr["composed_target_proof"]:
        failures.append("promotion must compose the bridge proof into the target proof")
    # even after promotion, the BRIDGE nodes themselves stay speculative (calibration).
    for n in rep2["arena"]:
        if n["status"] != sa.OPEN:
            failures.append("bridge nodes stay OPEN_UNFALSIFIED even after target promotion")

    # 3. Calibration honesty: a verified conditional is NOT a solve of the target.
    rep3 = sa.explore(T, BRIDGES, mock_prover(can_prove_bridge=False), consequence_graph=False, promote=False)
    if rep3["target_status"] != sa.OPEN or rep3["promoted"] is not None:
        failures.append("explore without promotion must never produce a target claim")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("SPECULATIVE_ARENA_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
