#!/usr/bin/env python3
"""Tests for Layer 2 concept_generator.py — generation/judgement separation and
the structural non-upgrade (calibration) guarantee."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import concept_generator as cg

HAVE_LEAN = shutil.which("lean") is not None


def main() -> int:
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="witsoc_l2_"))
    try:
        # --- structural calibration guard ---
        # force_open coerces; assert_no_upgrade raises on any non-OPEN candidate.
        c = cg.force_open({"form": "x", "kind": "lemma"})
        if c["status"] != cg.OPEN or c["arena"] != cg.ARENA:
            failures.append(f"force_open must coerce to OPEN/SPECULATIVE, got {c}")
        raised = False
        try:
            cg.assert_no_upgrade([{"form": "tampered", "status": "VERIFIED", "arena": cg.ARENA}])
        except AssertionError:
            raised = True
        if not raised:
            failures.append("assert_no_upgrade must raise on an upgraded candidate")
        # a SPECULATIVE/OPEN candidate passes
        cg.assert_no_upgrade([cg.force_open({"form": "ok"})])

        # --- trivial kill ---
        if cg.is_trivial({"form": "P -> P", "lean_statement": "∀ n : Nat, (P n) → (P n)"}) is None:
            failures.append("P->P must be detected trivial")
        if cg.is_trivial({"form": "x", "lean_statement": "True"}) is None:
            failures.append("-> True must be detected trivial")

        # --- CLI: deterministic generation for a Nat goal ---
        out = tmp / "cands.json"
        queue = tmp / "queue.json"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "concept_generator.py"),
             "--goal", "∀ n : Nat, n + 0 = n", "--domain", "number_theory",
             "--out", str(out), "--queue-out", str(queue)],
            capture_output=True, text=True, timeout=60, check=False)
        if proc.returncode != 0:
            failures.append(f"generator exited {proc.returncode}: {proc.stderr[:300]}")
        doc = json.loads(out.read_text())
        cands = doc["candidates"]
        if not cands:
            failures.append("expected non-empty candidate set")
        if not all(c["status"] == cg.OPEN and c["arena"] == cg.ARENA for c in cands):
            failures.append("every candidate must be OPEN_UNFALSIFIED/SPECULATIVE")
        kinds = {c["kind"] for c in cands}
        for need in ("base_case", "inductive_step", "even_case", "odd_case"):
            if need not in kinds:
                failures.append(f"missing stepping-stone kind {need}")

        # queue projection is dispatch-compatible (statement + lean_statement + OPEN)
        q = json.loads(queue.read_text())
        if not all(e["status"] == cg.OPEN and "lean_statement" in e for e in q):
            failures.append("queue projection must carry OPEN status + lean_statement")

        # --- end-to-end: a candidate exits the arena ONLY via the kernel ---
        if HAVE_LEAN:
            base = next((c for c in cands if c["kind"] == "base_case"), None)
            if not base or not base.get("lean_statement"):
                failures.append("base_case should carry a lean_statement")
            else:
                pr = subprocess.run(
                    [sys.executable, str(SCRIPT_DIR / "close_obligation.py"),
                     "--lean-statement", base["lean_statement"], "--out-ledger", "/dev/null"],
                    capture_output=True, text=True, timeout=120, check=False)
                rec = json.loads(pr.stdout)
                # The generator never marked it proved; the KERNEL discharges 0+0=0.
                if rec["label"] != "PROOF_DISCHARGED":
                    failures.append(f"base case 0+0=0 should discharge via kernel, got {rec['label']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print(f"CONCEPT_GENERATOR_TESTS_PASS (lean={'yes' if HAVE_LEAN else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
