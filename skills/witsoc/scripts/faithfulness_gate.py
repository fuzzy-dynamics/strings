#!/usr/bin/env python3
"""Layer 3.5: faithfulness gate — does the Lean statement actually mean the
informal/WIT target?

The kernel proves the FORMAL statement; whether that statement faithfully captures
the informal claim is the field's human-grounded ceiling (REPORT.md). This gate
produces MACHINE EVIDENCE for that judgement and can only ever DOWNGRADE trust:

  * Back-translate the Lean signature to NL with K>=2 INDEPENDENT formalizers
    (`--translator cmd:CMD`, repeatable), diff each against the informal target.
  * >=2 independent back-translations agree with the informal target  -> FAITHFUL
    (machine evidence; still needs a human gate for end-to-end VERIFIED).
  * back-translations disagree with the informal target                -> FAITHFULNESS_GAP
  * fewer than 2 independent translators available                     -> UNCHECKED_FAITHFULNESS
    (cannot certify; never silently "faithful").

It NEVER emits VERIFIED and never upgrades. Ambiguity resolves toward GAP/UNCHECKED.

Usage:
  faithfulness_gate.py --lean "<Lean Prop>" --informal "<NL/WIT claim>"
      [--translator cmd:CMD ...] [--threshold 0.5] [--out J]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

# Lean surface -> NL tokens, so even the structural fallback is comparable to prose.
_OP_WORDS = [("*", "multiplication product"), ("+", "addition sum"), ("^", "power exponent"),
             ("-", "subtraction difference"), ("=", "equal equality"), ("≤", "less or equal"),
             ("<", "less than"), ("≥", "greater or equal"), (">", "greater than"),
             ("∀", "for all every"), ("∃", "there exists"), ("∧", "and"), ("∨", "or"),
             ("→", "implies"), ("¬", "not"), ("∣", "divides")]
_WORD_WORDS = [("Nat", "natural number"), ("ℕ", "natural number"), ("Int", "integer"),
               ("Prime", "prime"), ("List", "list"), ("reverse", "reverse"),
               ("Even", "even"), ("Odd", "odd")]


def tok(s: str) -> Counter:
    return Counter(w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) > 1)


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0) for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def structural_back_translation(lean: str) -> str:
    """A deterministic, model-free NL rendering of the Lean surface. Weak but
    honest — used only to compute overlap, never to certify."""
    words: list[str] = []
    for sym, w in _OP_WORDS:
        if sym in lean:
            words.append(w)
    for sym, w in _WORD_WORDS:
        if re.search(rf"\b{re.escape(sym)}\b", lean):
            words.append(w)
    # also keep identifiers (e.g. mul_comm) split into words
    for ident in re.findall(r"[A-Za-z_][A-Za-z0-9_.]+", lean):
        words.append(ident.replace("_", " ").replace(".", " "))
    return " ".join(words)


def run_translators(lean: str, translators: list[str]) -> list[dict]:
    out = []
    for cmd in translators:
        reply = witcore.run_sampler(cmd, {"task": "back_translate_lean_to_nl", "lean": lean})
        nl = None
        if isinstance(reply, dict):
            nl = reply.get("nl") or reply.get("translation") or reply.get("text")
        if isinstance(nl, str) and nl.strip():
            out.append({"translator": cmd, "nl": nl.strip(), "independent": True})
    return out


def gate(lean: str, informal: str, translators: list[str], threshold: float) -> dict:
    informal_vec = tok(informal)
    translations = run_translators(lean, translators)
    independent = len(translations)

    agreements = [{"translator": t["translator"], "agreement": round(cosine(tok(t["nl"]), informal_vec), 3),
                   "nl": t["nl"]} for t in translations]
    n_agree = sum(1 for a in agreements if a["agreement"] >= threshold)

    # structural fallback (not independent; advisory only)
    struct = structural_back_translation(lean)
    struct_overlap = round(cosine(tok(struct), informal_vec), 3)

    result = {
        "schema": "witsoc.faithfulness.v1",
        "lean": lean, "informal": informal, "threshold": threshold,
        "independent_translators": independent,
        "agreements": agreements,
        "structural_overlap": struct_overlap,
        "is_solve": False, "emits_verified": False,
    }

    if independent >= 2:
        if n_agree >= 2:
            result["status"] = "FAITHFUL"
            result["reason"] = f"{n_agree}/{independent} independent back-translations agree with the informal target; machine evidence only (human gate still required for end-to-end VERIFIED)"
        else:
            result["status"] = "FAITHFULNESS_GAP"
            result["reason"] = f"only {n_agree}/{independent} independent back-translations agree with the informal target -> informal<->formal mismatch"
    else:
        result["status"] = "UNCHECKED_FAITHFULNESS"
        result["reason"] = f"need >=2 independent formalizers, have {independent}; cannot certify faithfulness (structural overlap {struct_overlap} is advisory only)"
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lean", required=True)
    ap.add_argument("--informal", required=True)
    ap.add_argument("--translator", action="append", default=[], help="cmd:CMD back-translator (repeatable)")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    result = gate(args.lean, args.informal, args.translator, args.threshold)
    if args.out:
        witcore.save_json(args.out, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # exit 1 on an explicit GAP so callers can hard-gate; 0 otherwise (advisory).
    return 1 if result["status"] == "FAITHFULNESS_GAP" else 0


if __name__ == "__main__":
    raise SystemExit(main())
