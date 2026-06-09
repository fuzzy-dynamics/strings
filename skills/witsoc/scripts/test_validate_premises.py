#!/usr/bin/env python3
"""Tests for Layer 3.3 validate_premises.py."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_premises as vp

HAVE_LEAN = shutil.which("lean") is not None


def main() -> int:
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="witsoc_prem_"))
    try:
        atlas = tmp / "a.json"
        atlas.write_text(json.dumps({"nodes": [
            {"module": "m1", "symbols": ["Nat.mul_comm", "Nat.add_comm"]},
            {"module": "m2", "symbols": ["Nat.add_comm", "Nat.totally_made_up_lemma_xyz"]},
        ]}), encoding="utf-8")
        names = vp.names_from_atlas(atlas)
        if names != ["Nat.mul_comm", "Nat.add_comm", "Nat.totally_made_up_lemma_xyz"]:
            failures.append(f"names_from_atlas dedup/order wrong: {names}")

        if HAVE_LEAN:
            known = vp.resolve("Nat.mul_comm", "", None)
            if known["state"] != "KNOWN":
                failures.append(f"Nat.mul_comm should be KNOWN, got {known}")
            made_up = vp.resolve("Nat.totally_made_up_lemma_xyz", "", None)
            if made_up["state"] != "SEARCH_TARGET":
                failures.append(f"a non-existent lemma must be SEARCH_TARGET, got {made_up}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print(f"VALIDATE_PREMISES_TESTS_PASS (lean={'yes' if HAVE_LEAN else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
