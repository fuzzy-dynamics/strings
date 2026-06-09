#!/usr/bin/env python3
"""Tests for Layer 3.5 faithfulness_gate.py (mock back-translators; no real LLM)."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import faithfulness_gate as fg

LEAN = "∀ a b : Nat, a * b = b * a"
INFORMAL = "multiplication on natural numbers is commutative"


def write_translator(tmp: Path, name: str, nl: str) -> str:
    p = tmp / name
    p.write_text(f"import sys, json\nsys.stdin.read()\nprint(json.dumps({{'nl': {nl!r}}}))\n", encoding="utf-8")
    return f"cmd:{sys.executable} {p}"


def main() -> int:
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="witsoc_faith_"))
    try:
        faithful_a = write_translator(tmp, "fa.py", "multiplication on naturals is commutative, product order does not matter")
        faithful_b = write_translator(tmp, "fb.py", "for all naturals the product is commutative under multiplication")
        wrong_a = write_translator(tmp, "wa.py", "the weather today is sunny and warm with light wind")
        wrong_b = write_translator(tmp, "wb.py", "a recipe for chocolate cake with flour and sugar")

        # >=2 faithful translators agreeing -> FAITHFUL, never VERIFIED
        r1 = fg.gate(LEAN, INFORMAL, [faithful_a, faithful_b], 0.3)
        if r1["status"] != "FAITHFUL":
            failures.append(f"two faithful translations should be FAITHFUL, got {r1['status']} ({r1.get('agreements')})")
        if r1["emits_verified"] or r1["is_solve"]:
            failures.append("faithfulness gate must never emit VERIFIED or solve")

        # translations disagree with the informal target -> FAITHFULNESS_GAP
        r2 = fg.gate(LEAN, INFORMAL, [wrong_a, wrong_b], 0.3)
        if r2["status"] != "FAITHFULNESS_GAP":
            failures.append(f"disagreeing translations should be FAITHFULNESS_GAP, got {r2['status']}")

        # fewer than 2 independent translators -> UNCHECKED (never silently faithful)
        r3 = fg.gate(LEAN, INFORMAL, [faithful_a], 0.3)
        if r3["status"] != "UNCHECKED_FAITHFULNESS":
            failures.append(f"one translator should be UNCHECKED_FAITHFULNESS, got {r3['status']}")
        r4 = fg.gate(LEAN, INFORMAL, [], 0.3)
        if r4["status"] != "UNCHECKED_FAITHFULNESS":
            failures.append(f"zero translators should be UNCHECKED_FAITHFULNESS, got {r4['status']}")

        # mismatched informal (says addition) with faithful-to-multiplication translators -> GAP
        r5 = fg.gate(LEAN, "addition on naturals is associative", [faithful_a, faithful_b], 0.3)
        if r5["status"] != "FAITHFULNESS_GAP":
            failures.append(f"informal/formal mismatch should be FAITHFULNESS_GAP, got {r5['status']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("FAITHFULNESS_GATE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
