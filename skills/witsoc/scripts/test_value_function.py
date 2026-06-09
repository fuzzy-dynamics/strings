#!/usr/bin/env python3
"""Phase 1: the learned value function for candidate ordering (deterministic, no Lean).

Checks the lever, not proof outcomes:
  1. Featurization is sensible (strategy/tactic/length, goal structure).
  2. A model TRAINED on closures that close with `simp; omega` scores such a
     candidate above an unrelated one on a similar goal.
  3. With NO model, score is 0 — so candidate ordering falls back EXACTLY to the
     hand-cost order (zero behavior change / soundness: ordering never trusts).
  4. Integration: a trained model actually moves a matching compound candidate
     EARLIER in proof_search's candidate list (so it lands within the node budget).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import value_function as vf
import proof_search as ps


def main() -> int:
    failures: list[str] = []

    # 1. Featurization.
    gf = vf.featurize_goal("∀ n : Nat, fa n 0 = n",
                           "def fa : Nat → Nat → Nat\n  | 0, acc => acc\n  | (n+1), acc => fa n (acc+1)")
    for want in ("g:forall", "g:eq", "g:nat", "g:recdef", "g:accumulator"):
        if want not in gf:
            failures.append(f"goal features missing {want}: {gf}")
    cf = vf.featurize_candidate("by intro n; induction n with | zero => simp [fa] | succ k ih => simp [fa, ih]; omega")
    for want in ("c:induction", "c:simp", "c:omega", "c:intro"):
        if want not in cf:
            failures.append(f"candidate features missing {want}: {cf}")
    if "c:listinduction" not in vf.featurize_candidate("by intro l; induction l with | nil => simp | cons hd tl ih => simp [ih]"):
        failures.append("List induction proof must get c:listinduction")

    # 2. Trained model ranks the matching candidate higher.
    closures = [{"statement": "∀ n : Nat, foo n = n", "preamble": "def foo (n : Nat) : Nat := n",
                 "discharged": True, "proof": "by intro n; simp [foo]; omega"} for _ in range(6)]
    model = vf.train(closures)
    if model["trained_on"] != 6:
        failures.append(f"train should count 6 closures, got {model['trained_on']}")
    g = vf.featurize_goal("∀ n : Nat, bar n = n", "def bar (n : Nat) : Nat := n")
    s_match = vf.score(g, "by intro n; simp [bar]; omega", model)
    s_other = vf.score(g, "by exact rfl", model)
    if not (s_match > s_other):
        failures.append(f"trained model must score the simp;omega candidate above an unrelated one ({s_match} !> {s_other})")

    # 3. No model => score 0 (graceful fallback, never trusts).
    if vf.score(g, "by intro n; simp [bar]; omega", {}) != 0.0:
        failures.append("score with no model must be 0.0 (ordering falls back to hand-cost)")

    # 4. Integration: a trained model moves a matching compound candidate earlier.
    G, PRE = "∀ n : Nat, bar n = n", "def bar (n : Nat) : Nat := n"
    with tempfile.TemporaryDirectory() as td:
        mp = Path(td) / "value_model.json"
        mp.write_text(json.dumps(model), encoding="utf-8")

        no_model = ps.candidates(G, PRE, None, None)
        os.environ["WITSOC_VALUE_MODEL"] = str(mp)
        try:
            with_model = ps.candidates(G, PRE, None, None)
        finally:
            os.environ.pop("WITSOC_VALUE_MODEL", None)

        # a seqs-only compound (not a front cheap tactic): contains `simp only` + omega
        def first_idx(cands):
            for i, c in enumerate(cands):
                if "simp only" in c and "omega" in c:
                    return i
            return None
        i_no, i_yes = first_idx(no_model), first_idx(with_model)
        if i_no is None or i_yes is None:
            failures.append("expected a `simp only ...; omega` compound candidate in both lists")
        elif not (i_yes <= i_no):
            failures.append(f"trained model should rank the matching compound EARLIER, got with={i_yes} no={i_no}")
        if no_model == with_model:
            failures.append("a trained value model must change the candidate ordering")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("VALUE_FUNCTION_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
