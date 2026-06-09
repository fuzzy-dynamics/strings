#!/usr/bin/env python3
"""Test Phase D: generator_package.py packages WIT -> Lean(from WIT) -> SafeVerify
and completes the CHECKED -> VERIFIED_LEAN upgrade, while refusing to over-claim
on target drift or a missing proof.

Uses the real Lean toolchain when present; degrades to honest GAP otherwise.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
HAVE_LEAN = shutil.which("lean") is not None

WIT = """-- Status: UNVERIFIED
MODULE NatAddZero

THEOREM NatAddZero:
  GIVEN:
    - n: a natural number
  CLAIM:
    n + 0 = n.

PROOF OF NatAddZero:
  [1] SHOW n + 0 = n.
      BY @Nat.add_zero.
  QED BY [1].
"""

STMT = "∀ n : Nat, n + 0 = n"


def sha(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text.strip()).encode()).hexdigest()


def run_package(tmp: Path, *extra: str) -> dict:
    wit = tmp / "nataddzero.wit"
    wit.write_text(WIT, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "generator_package.py"), str(wit),
         "--lean-statement", STMT, "--emit", str(tmp / "out.lean"),
         "--out", str(tmp / "package.json"), *extra],
        capture_output=True, text=True, timeout=400, check=False)
    return json.loads(proc.stdout)


def main() -> int:
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="witsoc_phased_"))
    try:
        # 1. Discharged proof + no frozen target -> VERIFIED_LEAN (with Lean).
        pkg = run_package(tmp, "--proof", "by simp")
        if HAVE_LEAN:
            if pkg.get("witsoc_status") != "VERIFIED_LEAN" or not pkg.get("lean_verified"):
                failures.append(f"discharged proof should be VERIFIED_LEAN, got {pkg.get('witsoc_status')} ({pkg.get('reason')})")
            if pkg.get("statement_faithfulness") != "human_grounded":
                failures.append("must record statement_faithfulness=human_grounded")
        else:
            if pkg.get("witsoc_status") != "GAP":
                failures.append(f"no Lean -> expected GAP, got {pkg.get('witsoc_status')}")

        # 2. No proof -> must NOT be VERIFIED_LEAN (obligation open / sorry).
        pkg_noproof = run_package(tmp)
        if pkg_noproof.get("witsoc_status") == "VERIFIED_LEAN":
            failures.append("missing proof must never package as VERIFIED_LEAN")

        # 3. Target-freeze drift -> REJECTED (even with a discharged proof).
        if HAVE_LEAN:
            wrong = sha("∀ n : Nat, n + 1 = n")  # not the WIT's statement
            pkg_drift = run_package(tmp, "--proof", "by simp", "--frozen-lean-sha256", wrong)
            if pkg_drift.get("witsoc_status") != "REJECTED":
                failures.append(f"target drift must be REJECTED, got {pkg_drift.get('witsoc_status')}")
            if pkg_drift.get("lean_verified"):
                failures.append("target drift must not be lean_verified")
            # matching frozen hash -> VERIFIED_LEAN
            right = sha(STMT)
            pkg_ok = run_package(tmp, "--proof", "by simp", "--frozen-lean-sha256", right)
            if pkg_ok.get("witsoc_status") != "VERIFIED_LEAN":
                failures.append(f"matching frozen hash should be VERIFIED_LEAN, got {pkg_ok.get('witsoc_status')}")

        # 4. Reuse a Prover result (close_obligation record) for the proof.
        if HAVE_LEAN:
            pr = tmp / "prover.json"
            pr.write_text(json.dumps({"label": "PROOF_DISCHARGED", "discharged": True,
                                      "proof": "by simp", "statement": STMT}), encoding="utf-8")
            pkg_reuse = run_package(tmp, "--prover-result", str(pr))
            if not pkg_reuse.get("proof_reused_from_prover"):
                failures.append("should report proof_reused_from_prover=true")
            if pkg_reuse.get("witsoc_status") != "VERIFIED_LEAN":
                failures.append(f"reused prover proof should be VERIFIED_LEAN, got {pkg_reuse.get('witsoc_status')}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print(f"PHASE_D_TESTS_PASS (lean={'yes' if HAVE_LEAN else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
