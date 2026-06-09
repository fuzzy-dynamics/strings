#!/usr/bin/env python3
"""Tests for Layer 1 foundation_triage.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import foundation_triage as ft
import witcore

ARG = "Cohen forcing gives a model of ZFC + not-CH and Gödel's L gives ZFC + CH, so the statement is independent of ZFC."


def main() -> int:
    failures: list[str] = []

    def expect(label, cond, detail=""):
        if not cond:
            failures.append(f"{label}: {detail}")

    # --- explicit foundation walls flag with the right outcome ---
    ch = ft.triage("Prove the continuum hypothesis: 2^aleph0 = aleph1")
    expect("CH-flag", ch["flagged"] and ch["candidate_outcome"] == "INDEPENDENT", str(ch))
    expect("CH-no-gate", ch["terminal_status"] is None and ch["recommended_action"] == "human_gate_required", str(ch))

    ch_gated = ft.triage("Prove the continuum hypothesis", human_gate=True, independence_argument=ARG)
    expect("CH-gated-terminal", ch_gated["terminal_status"] == "INDEPENDENT", str(ch_gated))
    expect("CH-gated-action", ch_gated["recommended_action"] == "terminal_foundation_outcome", str(ch_gated))

    halt = ft.triage("Decide the halting problem for all Turing machines", human_gate=True, independence_argument=ARG)
    expect("halting-INFEASIBLE", halt["terminal_status"] == "INFEASIBLE", str(halt))

    con = ft.triage("Prove Con(ZFC) within ZFC", human_gate=True, independence_argument=ARG)
    expect("con-RELCON", con["terminal_status"] == "RELATIVE_CONSISTENCY", str(con))

    # short argument must NOT satisfy the gate
    weak = ft.triage("continuum hypothesis", human_gate=True, independence_argument="yes")
    expect("weak-arg-blocked", weak["terminal_status"] is None and weak["recommended_action"] == "human_gate_required", str(weak))

    # --- CALIBRATION: genuinely-open problems must NOT flag ---
    open_problems = [
        "Erdős–Straus: for all n>=2 there exist x,y,z with 4/n = 1/x + 1/y + 1/z",
        "Does there exist an odd perfect number?",
        "Collatz conjecture: every n eventually reaches 1",
        "Prove the Riemann hypothesis",
        "Goldbach: every even integer > 2 is a sum of two primes",
        "Twin prime conjecture",
    ]
    for stmt in open_problems:
        r = ft.triage(stmt)
        expect(f"calib-{stmt[:20]}", not r["flagged"] and r["terminal_status"] is None
               and r["recommended_action"] == "proceed_to_campaign", str(r))

    # --- structural guarantees ---
    for r in (ch, ch_gated, halt, con, weak):
        expect("never-solve", r["is_solve"] is False, str(r))
        if r["terminal_status"]:
            expect("terminal-in-vocab", r["terminal_status"] in witcore.FOUNDATION_OUTCOMES, str(r))

    # --- soft signal (router difficulty) alone never terminates ---
    soft = ft.triage("Some opaque statement with no known foundation marker",
                     route_difficulty="likely_undecidable", human_gate=True, independence_argument=ARG)
    expect("soft-no-terminal", soft["terminal_status"] is None and soft["soft_signal_only"], str(soft))
    expect("soft-action", soft["recommended_action"] == "human_review_difficulty", str(soft))

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("FOUNDATION_TRIAGE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
