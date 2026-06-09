#!/usr/bin/env python3
"""Phase 1: structural induction over inductive types beyond Nat.

`proof_search.structural_induction_candidates` adds the List `nil`/`cons` induction
skeleton (the Nat case is handled by `induction_candidates`). A goal over a custom
recursive List def cannot be closed by `simp` alone (verified) but closes by
structural induction — kernel-gated."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_search as ps

LLEN = "def llen : List Nat → Nat\n  | [] => 0\n  | (_ :: xs) => llen xs + 1"


def main() -> int:
    failures: list[str] = []

    # 1. Generation: a List goal yields nil/cons induction candidates. (Deterministic.)
    cands = ps.structural_induction_candidates("∀ (l : List Nat), llen l = l.length", LLEN)
    if not cands:
        failures.append("structural_induction_candidates must fire on a List goal")
    if not all("| nil =>" in c and "| cons hd tl ih =>" in c for c in cands):
        failures.append("every structural candidate must use the List nil/cons skeleton")

    # 1b. The registry also covers Option (none/some), extensibly.
    ocands = ps.structural_induction_candidates("∀ (o : Option Nat), oval o = o.getD 0",
                                                "def oval : Option Nat → Nat\n  | none => 0\n  | some x => x")
    if not ocands or not all("| none =>" in c and "| some x =>" in c for c in ocands):
        failures.append("structural induction must support Option (none/some)")

    # 2. It does NOT fire on a Nat goal (that is induction_candidates' job) or a
    #    non-inductive goal — no spurious structural induction.
    if ps.structural_induction_candidates("∀ n : Nat, n + 0 = n", ""):
        failures.append("structural induction must not fire on a Nat goal")
    if ps.structural_induction_candidates("2 + 2 = 4", ""):
        failures.append("structural induction must not fire on a ground goal")

    # 3. End to end (needs Lean): the custom-List-def goal closes via structural
    #    induction — `simp` alone makes no progress on it.
    r = ps.search("∀ (l : List Nat), llen l = l.length", LLEN, None, None, None, max_nodes=300, workers=12)
    if r.get("label") == "UNCHECKED_NO_TOOLCHAIN":
        print("STRUCTURAL_INDUCTION_TESTS_SKIP (no Lean toolchain)")
        return 0 if not failures else 1
    if not r.get("discharged"):
        failures.append(f"List goal should close via structural induction, got {r.get('label')}")
    else:
        proof = r.get("proof", "")
        if "induction" not in proof or "nil" not in proof:
            failures.append(f"closing proof must use List induction, got {proof!r}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("STRUCTURAL_INDUCTION_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
