#!/usr/bin/env python3
"""Tests for validate_prover_result.py — the PROVER_ATTEMPT honesty gate.

Verifies that a Prover result is mapped to a legal Witsoc status and that no
caller can assert a status stronger than the kernel/SafeVerify evidence supports.
"""

from __future__ import annotations

import argparse
import sys

import validate_prover_result as vpr


def run(record, **kw) -> tuple[str, dict]:
    args = argparse.Namespace(
        safeverify_passed=kw.get("safeverify_passed", False),
        safeverify=kw.get("safeverify", None),
        frozen_target_sha256=kw.get("frozen_target_sha256", None),
        assert_status=None,
    )
    return vpr.legal_status(record, args)


def main() -> int:
    failures: list[str] = []

    def expect(label, record, want, **kw):
        status, _ = run(record, **kw)
        if status != want:
            failures.append(f"{label}: expected {want}, got {status}")

    discharged = {"label": "PROOF_DISCHARGED", "discharged": True, "proof": "by intro n; rfl", "statement": "∀ n : Nat, n + 0 = n"}

    # Kernel proof alone is CHECKED, not VERIFIED (SafeVerify still required).
    expect("kernel-only", discharged, "CHECKED")
    # Kernel proof + SafeVerify => VERIFIED.
    expect("kernel+safeverify", discharged, "VERIFIED", safeverify_passed=True)
    # PROOF_DISCHARGED label but NO proof/receipt => cannot exceed OPEN.
    expect("discharged-no-receipt", {"label": "PROOF_DISCHARGED", "discharged": True, "proof": None}, "OPEN", safeverify_passed=True)
    # Open after search => FAILED_ATTEMPT; open with no search => OPEN.
    expect("open-with-search", {"label": "OBLIGATION_OPEN", "discharged": False, "search_nodes": 120}, "FAILED_ATTEMPT")
    expect("open-no-search", {"label": "OBLIGATION_OPEN", "discharged": False, "search_nodes": 0}, "OPEN")
    # No toolchain => GAP (no claim).
    expect("no-toolchain", {"label": "UNCHECKED_NO_TOOLCHAIN", "discharged": False}, "GAP")
    # Budget exhausted => FAILED_ATTEMPT finding, never a solve (Layer 1).
    expect("budget-exhausted", {"label": "BUDGET_EXHAUSTED", "discharged": False,
                                 "search_nodes": 300, "search_max_nodes": 300}, "FAILED_ATTEMPT")

    # Target-freeze drift demotes even a kernel proof.
    import hashlib
    right = hashlib.sha256("∀ n : Nat, n + 0 = n".encode()).hexdigest()
    wrong = hashlib.sha256("something else".encode()).hexdigest()
    expect("target-match", discharged, "VERIFIED", safeverify_passed=True, frozen_target_sha256=right)
    expect("target-drift", discharged, "FAILED_ATTEMPT", safeverify_passed=True, frozen_target_sha256=wrong)

    # The assertion guard: asserting VERIFIED on a kernel-only proof must fail.
    args = argparse.Namespace(safeverify_passed=False, safeverify=None, frozen_target_sha256=None, assert_status="VERIFIED")
    status, _ = vpr.legal_status(discharged, args)
    if vpr.rank(status) >= vpr.rank("VERIFIED"):
        failures.append("assert-guard: kernel-only proof must NOT satisfy assert VERIFIED")
    if vpr.rank(status) < vpr.rank("CHECKED"):
        failures.append("assert-guard: kernel-only proof should still satisfy assert CHECKED")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("PROVER_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
