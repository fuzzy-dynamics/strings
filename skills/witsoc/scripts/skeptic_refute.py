#!/usr/bin/env python3
"""Layer 3.6: adversarial skeptic panel for residual LLM-only steps.

A WIT/proof step that the kernel cannot back (no Lean discharge, no computation
PASS) is, at best, LLM-judged. This runs N INDEPENDENT skeptics each prompted to
REFUTE the step (default to refuted=true when uncertain). The result can only ever
DOWNGRADE:

  * majority refute  -> REJECTED (the step is killed)
  * survives refute  -> CHECKED_LLM  (LLM-only acceptance; never VERIFIED — only the
                        kernel gate can reach VERIFIED)
  * no skeptics       -> UNCHECKED_LLM (cannot even run the panel; not acceptance)

It NEVER emits VERIFIED and NEVER upgrades. The refute rate is logged for
calibration.

Usage:
  skeptic_refute.py --claim "<step claim>" [--context "<premises>"]
      --skeptic cmd:CMD [--skeptic cmd:CMD ...] [--out J]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402


def ask_skeptic(cmd: str, claim: str, context: str) -> dict:
    """A skeptic returns {refuted: bool, reason}. Any malformed/missing reply is
    treated as refuted=True (conservative: uncertainty kills the step)."""
    reply = witcore.run_sampler(cmd, {"task": "refute_step", "claim": claim, "context": context,
                                      "instruction": "Try to REFUTE this step. If you are not certain it is correct, set refuted=true."})
    if not isinstance(reply, dict) or "refuted" not in reply:
        return {"skeptic": cmd, "refuted": True, "reason": "missing/malformed reply -> conservative refute"}
    return {"skeptic": cmd, "refuted": bool(reply.get("refuted")), "reason": str(reply.get("reason", ""))}


def panel(claim: str, context: str, skeptics: list[str]) -> dict:
    verdicts = [ask_skeptic(s, claim, context) for s in skeptics]
    n = len(verdicts)
    refutes = sum(1 for v in verdicts if v["refuted"])
    result = {
        "schema": "witsoc.skeptic_panel.v1",
        "claim": claim, "skeptics": n, "refutes": refutes,
        "refute_rate": round(refutes / n, 3) if n else None,
        "verdicts": verdicts,
        "is_solve": False, "emits_verified": False,
    }
    if n == 0:
        result["status"] = "UNCHECKED_LLM"
        result["reason"] = "no skeptics available; cannot run the panel (not acceptance)"
    elif refutes >= math.ceil(n / 2):
        result["status"] = "REJECTED"
        result["reason"] = f"majority refute ({refutes}/{n}) -> step killed"
    else:
        result["status"] = "CHECKED_LLM"
        result["reason"] = f"survived refute ({refutes}/{n}); LLM-only acceptance -> at most CHECKED, never VERIFIED (kernel gate required for VERIFIED)"
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claim", required=True)
    ap.add_argument("--context", default="")
    ap.add_argument("--skeptic", action="append", default=[], help="cmd:CMD skeptic (repeatable)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    result = panel(args.claim, args.context, args.skeptic)
    if args.out:
        witcore.save_json(args.out, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result["status"] == "REJECTED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
