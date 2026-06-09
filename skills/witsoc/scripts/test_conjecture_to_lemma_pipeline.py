#!/usr/bin/env python3
"""Tests for conjecture_to_lemma_pipeline.py — the discovery->formalize->dispatch loop.

Deterministic and offline: no Lean toolchain needed. We check the WIRING and the
CALIBRATION SPINE, not proof outcomes (proof outcomes are the kernel's job, tested
by test_lovasz_prover_dispatch.py)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conjecture_to_lemma_pipeline as pl


def main() -> int:
    failures: list[str] = []

    # 1. Faithful predicate expansion: P(n)->Q(n) becomes a real, dispatchable ∀ goal.
    lean, blocker, needs_mathlib = pl.formalize_form("perfect(n) -> even(n)")
    if lean is None:
        failures.append(f"perfect->even must formalize, got blocker={blocker}")
    else:
        if "Nat.divisors" not in lean or "% 2 = 0" not in lean:
            failures.append(f"perfect->even expansion not faithful: {lean}")
        if not needs_mathlib:
            failures.append("perfect/even expansion should be flagged needs_mathlib")
        if not lean.startswith("∀ n : Nat, 2 ≤ n →"):
            failures.append(f"expansion must be a guarded ∀ over Nat: {lean}")

    # 2. Unknown predicate -> honest blocker, never a fabricated goal.
    lean2, blocker2, _ = pl.formalize_form("totient(n) -> mystery(n)")
    if lean2 is not None or not blocker2:
        failures.append("unknown predicates must yield lean_statement=None + a blocker")

    # 3. No forbidden tokens ever appear in any expansion.
    for p in pl.PREDICATE_LEAN:
        for q in pl.PREDICATE_LEAN:
            if p == q:
                continue
            l, _, _ = pl.formalize_form(f"{p}(n) -> {q}(n)")
            if l and any(t in l for t in pl.FORBIDDEN_LEAN):
                failures.append(f"forbidden token leaked into expansion of {p}->{q}")

    # 4. Pipeline on synthetic conjectures: emits OPEN_UNFALSIFIED dispatchable nodes,
    #    a conditional (H->T) node, and a disproof certificate — all calibrated.
    conjectures = [
        {"form": "perfect(n) -> even(n)", "support": 4, "support_examples": [6, 28, 496, 8128],
         "status": "OPEN_UNFALSIFIED"},
        {"form": "abundant(n) -> deficient(n)", "support": 9, "status": "FALSIFIED", "falsified_at": 12},
        {"form": "square(n) -> odd(n)", "support": 5, "status": "OPEN_UNFALSIFIED"},
    ]
    target_lean = "∀ n : Nat, 2 ≤ n → (∑ d ∈ Nat.divisors n, d = 2 * n) → (n % 2 = 0)"
    res = pl.pipeline(conjectures, domain="number_theory", target_hash="h" * 64, top=8,
                      target_lean=target_lean, library=None, range_size=10000,
                      formalizer=None, translators=None, threshold=0.4)

    if res["dispatchable_count"] < 2:
        failures.append(f"expected >=2 dispatchable mined nodes, got {res['dispatchable_count']}")

    # every lemma + node is born OPEN_UNFALSIFIED / SPECULATIVE
    for l in res["actual_lemmas"]:
        if l.get("status") != pl.OPEN or l.get("arena") != pl.ARENA:
            failures.append(f"mined lemma not OPEN/SPECULATIVE: {l.get('lemma_id')}")
    for n in res["nodes"] + res["conditional_nodes"]:
        if n.get("research_status") != pl.OPEN or n.get("arena") != pl.ARENA:
            failures.append(f"node not OPEN_UNFALSIFIED/SPECULATIVE: {n.get('node_id')}")
        if n.get("lean_statement") and any(t in n["lean_statement"] for t in pl.FORBIDDEN_LEAN):
            failures.append(f"node lean_statement carries a forbidden token: {n.get('node_id')}")
        ft = n.get("falsification_test") or {}
        if not ft.get("kind"):
            failures.append(f"node missing falsification_test: {n.get('node_id')}")

    # speculative arena: a conditional (H -> T) node was built and is literally an implication
    if not res["conditional_nodes"]:
        failures.append("expected at least one conditional (H->T) node when target-lean is given")
    else:
        cn = res["conditional_nodes"][0]
        if cn.get("type") != "conditional_theorem" or "→" not in (cn.get("lean_statement") or ""):
            failures.append("conditional node must be an implication H -> T")
        if not cn.get("conditional_on"):
            failures.append("conditional node must name the hypothesis it is conditional on")

    # disprove: the FALSIFIED conjecture surfaces as a bounded disproof certificate
    if not res["disproofs"]:
        failures.append("a FALSIFIED conjecture must surface as a disproof certificate")
    else:
        d = res["disproofs"][0]
        if d.get("status") != "REFUTED" or d.get("witness") != 12:
            failures.append(f"disproof certificate must record REFUTED + the witness: {d}")

    # 5. CALIBRATION: the pipeline structurally cannot emit trust. Forge an upgrade
    #    and confirm the guard fires.
    try:
        bad = dict(res["actual_lemmas"][0]); bad["status"] = "VERIFIED"
        import concept_generator as cg
        cg.assert_no_upgrade([bad])
        failures.append("assert_no_upgrade FAILED to catch a forged VERIFIED status")
    except AssertionError:
        pass  # expected

    # 6. Odd-perfect stays a conjecture: the pipeline formalizes & dispatches it but
    #    NEVER marks it solved (only the kernel could, and it can't).
    op = [l for l in res["actual_lemmas"] if "perfect(n) -> even(n)" in l.get("statement", "")]
    if not op or op[0]["status"] != pl.OPEN:
        failures.append("odd-perfect conjecture must remain OPEN_UNFALSIFIED in the pipeline output")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("CONJECTURE_TO_LEMMA_PIPELINE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
