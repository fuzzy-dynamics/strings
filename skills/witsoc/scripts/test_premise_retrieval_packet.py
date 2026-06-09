#!/usr/bin/env python3
"""Phase 2: Explorer-stage retrieval packet, GROUNDED by validation (needs Lean).

A retrieved premise is KNOWN only if it actually resolves in the available Lean; a
Mathlib symbol on a core-only host is a SEARCH_TARGET, never silently assumed to
exist. This is the honesty that lets Explorer hand Lovász a grounded packet."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import premise_retrieval as pr
import witcore

CORE_ATLAS = SCRIPT_DIR / "core_lemma_atlas.json"


def main() -> int:
    failures: list[str] = []

    # toolchain probe
    if not witcore.lean_verify_cached("#check @Nat.mul_comm\n", None).get("checked"):
        print("PREMISE_RETRIEVAL_PACKET_TESTS_SKIP (no Lean toolchain)")
        return 0

    # 1. Core goal: retrieves Nat.mul_comm and validates it KNOWN (resolvable now).
    pkt = pr.retrieve_packet("∀ a b : Nat, a * b = b * a", CORE_ATLAS, None, limit=3)
    if "Nat.mul_comm" not in pkt["retrieved_symbols"]:
        failures.append(f"core goal should retrieve Nat.mul_comm, got {pkt['retrieved_symbols']}")
    if "Nat.mul_comm" not in pkt["known_premises"]:
        failures.append(f"Nat.mul_comm should validate KNOWN, got known={pkt['known_premises']}")
    if pkt["search_targets"]:
        failures.append(f"core symbols should not be search targets, got {pkt['search_targets']}")

    # 2. HONESTY: a Mathlib-only symbol on a core host is a SEARCH_TARGET, never KNOWN.
    with tempfile.TemporaryDirectory() as td:
        atlas = Path(td) / "atlas.json"
        atlas.write_text(json.dumps({"nodes": [
            {"module": "Mathlib.NumberTheory.Divisors", "symbols": ["Nat.divisors", "Nat.sigma"],
             "doc": "divisors and the sum of divisors", "imports": []}]}), encoding="utf-8")
        pkt2 = pr.retrieve_packet("∀ n : Nat, Nat.divisors n = Nat.divisors n", atlas, None, limit=2)
        if "Nat.divisors" not in pkt2["retrieved_symbols"]:
            failures.append(f"divisors goal should retrieve Nat.divisors, got {pkt2['retrieved_symbols']}")
        if "Nat.divisors" in pkt2["known_premises"]:
            failures.append("a Mathlib symbol must NOT be KNOWN on a core host (no hallucinated existence)")
        if "Nat.divisors" not in pkt2["search_targets"]:
            failures.append(f"Nat.divisors should be a SEARCH_TARGET, got search_targets={pkt2['search_targets']}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("PREMISE_RETRIEVAL_PACKET_TESTS_PASS (lean=yes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
