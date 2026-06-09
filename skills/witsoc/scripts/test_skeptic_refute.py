#!/usr/bin/env python3
"""Tests for Layer 3.6 skeptic_refute.py (mock skeptics; no real LLM)."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skeptic_refute as sr


def mk(tmp: Path, name: str, refuted: bool) -> str:
    p = tmp / name
    p.write_text(f"import sys, json\nsys.stdin.read()\nprint(json.dumps({{'refuted': {refuted}, 'reason': 'mock'}}))\n", encoding="utf-8")
    return f"cmd:{sys.executable} {p}"


def mk_broken(tmp: Path, name: str) -> str:
    p = tmp / name
    p.write_text("import sys\nsys.stdin.read()\nprint('not json')\n", encoding="utf-8")
    return f"cmd:{sys.executable} {p}"


def main() -> int:
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="witsoc_skep_"))
    try:
        ref = lambda n: mk(tmp, f"r{n}.py", True)
        ok = lambda n: mk(tmp, f"o{n}.py", False)

        # majority refute (2/3) -> REJECTED
        r = sr.panel("step", "", [ref(1), ref(2), ok(3)])
        if r["status"] != "REJECTED":
            failures.append(f"majority refute should be REJECTED, got {r['status']} ({r['refutes']}/{r['skeptics']})")

        # survives (1/3 refute) -> CHECKED_LLM, never VERIFIED
        r2 = sr.panel("step", "", [ref(4), ok(5), ok(6)])
        if r2["status"] != "CHECKED_LLM":
            failures.append(f"minority refute should be CHECKED_LLM, got {r2['status']}")
        if r2["emits_verified"] or r2["is_solve"]:
            failures.append("skeptic panel must never emit VERIFIED/solve")

        # tie counts as refute (1/2 -> ceil(2/2)=1) -> REJECTED (conservative)
        r3 = sr.panel("step", "", [ref(7), ok(8)])
        if r3["status"] != "REJECTED":
            failures.append(f"tie should be REJECTED (conservative), got {r3['status']}")

        # no skeptics -> UNCHECKED_LLM (not acceptance)
        r4 = sr.panel("step", "", [])
        if r4["status"] != "UNCHECKED_LLM":
            failures.append(f"no skeptics should be UNCHECKED_LLM, got {r4['status']}")

        # broken skeptic reply -> treated as refute (uncertainty kills)
        r5 = sr.panel("step", "", [mk_broken(tmp, "b1.py"), ok(9)])
        if r5["refutes"] < 1:
            failures.append("a malformed skeptic reply must count as a refute (conservative)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("SKEPTIC_REFUTE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
