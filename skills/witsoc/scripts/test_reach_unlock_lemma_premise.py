#!/usr/bin/env python3
"""Layer 3.4: the library unlocks STRICTLY HARDER reach via a harvested lemma used
as a PREMISE (composition) — not merely reusing a proof for the same goal.

The barrier is a MULTIPLICATIVE induction-generalization failure: proving
`fb n 1 = 2^n` directly by induction gives too weak an IH (`fb k 1 = 2^k`, but the
successor case needs `fb k 2 = 2^(k+1)`). The generalized lemma is
`∀ n a, fb n a = a * 2^n` — its right-hand side `a * 2^n` is NOT additive, so the
Phase-1 generalization search (which only tries additive `a + …` templates) cannot
synthesize it either. So this target is OPEN to the full current search, and the
ONLY route is reusing the generalized lemma from the library as a `have`.

(The earlier additive accumulator `fa n 0 = n` is now closed directly by the Phase-1
generalization search, so it is no longer a library-only barrier — hence the
multiplicative version here.)

So: target OPEN alone -> the generalized lemma is in the library -> target closes by
using it. Reach moved, and only kernel-checked proofs are ever trusted."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_search as ps
import witcore

PRE = "def fb : Nat → Nat → Nat\n  | 0, acc => acc\n  | (n+1), acc => fb n (acc * 2)"
GEN = "∀ n : Nat, ∀ a : Nat, fb n a = a * 2 ^ n"        # generalized lemma (non-additive)
# A verified core-Lean proof of GEN. The current search would not regenerate the
# exact mul_comm rewrite, so this stands in for a proof accumulated by a prior run
# (the library is cross-run memory). We re-verify it with the kernel below.
GEN_PROOF = ("by intro n; induction n with | zero => simp [fb] | succ k ih => "
             "intro a; rw [fb, ih, Nat.pow_succ, Nat.mul_assoc, Nat.mul_comm 2 (2 ^ k)]")
TARGET = "∀ n : Nat, fb n 1 = 2 ^ n"                    # corollary (barrier without GEN)


def search(stmt: str, library: Path | None):
    return ps.search(stmt, PRE, None, None, library, max_nodes=300, workers=12)


def harvest(library: Path, statement: str, proof: str) -> None:
    subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "lemma_library.py"),
                    "--library", str(library), "add", "--statement", statement,
                    "--tier", "WIT_STRUCTURE", "--provenance", f"close_obligation:{proof}"],
                   capture_output=True, text=True, timeout=30, check=False)


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        library = Path(td) / "lib"

        # 0. Toolchain probe + validate the seeded proof: the generalized lemma's
        #    proof must independently kernel-verify (skip cleanly if no Lean).
        src_gen = f"{PRE}\nnamespace T\ntheorem gen : {GEN} := {GEN_PROOF}\nend T\n"
        verdict = witcore.lean_verify_cached(src_gen, None)
        if not verdict.get("checked"):
            print("REACH_UNLOCK_TESTS_SKIP (no Lean toolchain)")
            return 0
        if not verdict.get("verified"):
            failures.append("the seeded generalized-lemma proof must kernel-verify")

        # 1. The target is a genuine barrier on its own: direct induction's IH is too
        #    weak AND the additive generalization search cannot synthesize a*2^n.
        before = search(TARGET, None)
        if before.get("discharged"):
            failures.append(f"target should be OPEN without the library (barrier), got proof {before.get('proof')!r}")

        # 2. Seed the generalized lemma (with its kernel-verified proof) into the library.
        harvest(library, GEN, GEN_PROOF)

        # 3. With the lemma in the library, the target closes BY USING it as a premise.
        after = search(TARGET, library)
        if not after.get("discharged"):
            failures.append(f"target should close once the generalized lemma is in the library, got {after.get('label')}")
        else:
            proof = after.get("proof", "")
            if "hlib" not in proof:
                failures.append(f"closing proof must actually USE the harvested lemma (a `have`), got {proof!r}")
            if (after.get("trace") or {}).get("strategy") != "library_reuse":
                failures.append(f"strategy should be library_reuse, got {(after.get('trace') or {}).get('strategy')!r}")

        # 4. Calibration: re-verify the closing proof independently (no fake solve).
        if after.get("discharged"):
            src = f"{PRE}\nnamespace T\ntheorem t : {TARGET} := {after['proof']}\nend T\n"
            if not witcore.lean_verify_cached(src, None).get("verified"):
                failures.append("the closing proof must independently kernel-verify (no fake solve)")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("REACH_UNLOCK_TESTS_PASS (reach unlocked by harvested lemma-as-premise)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
