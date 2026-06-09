#!/usr/bin/env python3
"""Phase 5: faithfulness-gated acceptance — so a kernel proof is a proof of the RIGHT thing.

A kernel proof certifies a Lean statement; it says nothing about whether that statement
faithfully captures the informal problem. A *wrong-but-true* formalization (e.g. the
one-directional `even → ∃k` instead of the intended `even ↔ ∃k`) is a perfectly valid
theorem the kernel happily verifies — yet it is NOT a solve of the stated problem. This
combines the kernel verdict with the K≥2 back-translator faithfulness gate so that:

  kernel-verified  AND  faithful (≥2 independent back-translations agree)  -> VERIFIED_LEAN_FAITHFUL
  kernel-verified  AND  faithfulness GAP                                   -> FAITHFULNESS_GAP (proved the wrong thing — NOT a solve)
  kernel-verified  AND  faithfulness UNCHECKED (<2 translators)            -> CHECKED_NEEDS_HUMAN (at most CHECKED + human gate)
  not kernel-verified                                                      -> OPEN

The faithfulness judgement stays human/LLM-grounded by construction — faithfulness is
not kernel-decidable (a wrong-but-true statement passes the kernel). This module makes
that boundary explicit and ensures NOTHING is emitted VERIFIED while a faithfulness gap
is unresolved.

Usage:
  faithfulness_pipeline.py --informal "..." --lean "<Lean Prop>" --kernel-verified
      [--translator cmd:CMD ...] [--threshold 0.4] [--out J]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import faithfulness_gate as fg  # noqa: E402


def accept(informal: str, lean: str, translators: list[str], kernel_verified: bool,
           threshold: float = 0.4) -> dict:
    verdict = fg.gate(lean, informal, translators, threshold)
    fstatus = verdict["status"]   # FAITHFUL | FAITHFULNESS_GAP | UNCHECKED_FAITHFULNESS

    if not kernel_verified:
        final = "OPEN"
    elif fstatus == "FAITHFUL":
        final = "VERIFIED_LEAN_FAITHFUL"
    elif fstatus == "FAITHFULNESS_GAP":
        final = "FAITHFULNESS_GAP"
    else:
        final = "CHECKED_NEEDS_HUMAN"

    return {
        "schema": "witsoc.faithfulness_pipeline.v1",
        "informal": informal,
        "lean": lean,
        "kernel_verified": kernel_verified,
        "faithfulness": fstatus,
        "faithfulness_detail": verdict,
        "final_status": final,
        # the one invariant: VERIFIED is emitted only when BOTH gates pass.
        "emits_verified": final == "VERIFIED_LEAN_FAITHFUL",
        "note": ("a kernel proof of a non-faithful formalization is NOT a solve; faithfulness is "
                 "human/LLM-grounded (a wrong-but-true statement passes the kernel), so VERIFIED "
                 "requires the back-translation gate AND, end to end, a human gate."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--informal", required=True)
    ap.add_argument("--lean", required=True)
    ap.add_argument("--kernel-verified", action="store_true",
                    help="set when the Lean statement has a kernel proof")
    ap.add_argument("--translator", action="append", default=[], help="cmd:CMD back-translator (>=2 for FAITHFUL)")
    ap.add_argument("--threshold", type=float, default=0.4)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    result = accept(args.informal, args.lean, args.translator, args.kernel_verified, args.threshold)
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # exit non-zero on a faithfulness gap (a kernel proof of the wrong statement).
    return 1 if result["final_status"] == "FAITHFULNESS_GAP" else 0


if __name__ == "__main__":
    raise SystemExit(main())
