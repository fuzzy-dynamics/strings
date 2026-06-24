#!/usr/bin/env python3
"""Interestingness scoring for mined conjectures (Phase 4 — the open-ended bet).

Most mined statements are trivial or already known. This scores each surviving
conjecture so the search can chase *interesting* stepping-stones, not just any
unfalsified pattern. It NEVER changes a conjecture's status — a conjecture stays
a conjecture; interestingness only orders and prunes. That is the calibration
guarantee: this module cannot manufacture a solve (asserted at the end).

Score components (each in [0,1]):
  novelty        distance from the nearest lemma already in the library
                 (known statements score ~0 and are killed).
  non_triviality antecedent is not vacuous and the implication is not a trivial
                 special case; a hand list of trivial pairs is killed outright.
  surprise       a RARE antecedent that nonetheless always forces the consequent
                 is more surprising than a common one.
  fruitfulness   how many other surviving conjectures share a predicate with this
                 one (a hub predicate is a fertile stepping-stone).

interestingness = mean of the four (killed items excluded from the ranking).

Usage:
  interestingness.py --conjectures conjectures.json [--library DIR]
      [--novelty-seek] [--out interestingness.json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

# Pairs considered trivial/known for the arithmetic predicate miner — killed.
TRIVIAL_FORMS = {
    "prime(n) -> prime_power(n)",     # a prime is a prime power by definition
    "square(n) -> square_or_2square(n)",  # square ⊂ square_or_2square by definition
    "odd(n) -> odd(n)", "even(n) -> even(n)",
}


def predicates_of(form: str) -> list[str]:
    return re.findall(r"([a-z_0-9]+)\(n\)", form)


def tok(s: str) -> Counter:
    return Counter(re.findall(r"[a-z0-9_]+", s.lower()))


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0) for k in a)
    import math
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def library_statements(library: Path | None) -> list[str]:
    if not library or not library.exists():
        return []
    try:
        r = subprocess.run([sys.executable, str(SCRIPT_DIR / "lemma_library.py"),
                            "--library", str(library), "search", "--query", "implication", "--limit", "50"],
                           capture_output=True, text=True, timeout=30, check=False)
        return [m.get("statement", "") for m in json.loads(r.stdout).get("matches", [])]
    except Exception:
        return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--conjectures", type=Path, required=True)
    ap.add_argument("--library", type=Path, default=None)
    ap.add_argument("--range-size", type=int, default=10000, help="size of the mined range (for surprise)")
    ap.add_argument("--novelty-seek", action="store_true", help="rank by novelty alone")
    ap.add_argument("--out", type=Path, default=Path("interestingness.json"))
    args = ap.parse_args()

    doc = witcore.load_json(args.conjectures, {})
    conjectures = [c for c in doc.get("conjectures", []) if c.get("status") == "OPEN_UNFALSIFIED"]
    lib = library_statements(args.library)
    lib_vecs = [tok(s) for s in lib]

    # predicate frequency across surviving conjectures (for fruitfulness)
    pred_freq: Counter = Counter()
    for c in conjectures:
        for p in predicates_of(c.get("form", "")):
            pred_freq[p] += 1

    scored, killed = [], []
    for c in conjectures:
        form = c.get("form", "")
        if form in TRIVIAL_FORMS:
            killed.append({"form": form, "reason": "trivial/known"})
            continue
        preds = predicates_of(form)
        # novelty: 1 - max cosine to any library statement
        novelty = 1.0 - (max((cosine(tok(form), v) for v in lib_vecs), default=0.0))
        support = c.get("support", 0)
        # surprise: rarer antecedent that still always implies Q is more surprising
        surprise = max(0.0, 1.0 - support / max(1, args.range_size) * 50.0)
        non_triviality = 1.0 if support >= 3 and len(set(preds)) == 2 else 0.4
        fruitfulness = min(1.0, (sum(pred_freq[p] for p in preds) - len(preds)) / 4.0)
        score = round((novelty + surprise + non_triviality + fruitfulness) / 4.0, 4)
        scored.append({"form": form, "interestingness": score,
                       "components": {"novelty": round(novelty, 3), "surprise": round(surprise, 3),
                                      "non_triviality": non_triviality, "fruitfulness": round(fruitfulness, 3)},
                       "support": support, "status": c.get("status")})

    key = (lambda x: -x["components"]["novelty"]) if args.novelty_seek else (lambda x: -x["interestingness"])
    scored.sort(key=key)

    # CALIBRATION GUARANTEE: no status was changed; nothing became a solve.
    assert all(s["status"] == "OPEN_UNFALSIFIED" for s in scored), "interestingness must not change status"

    out = {"schema": "witsoc.interestingness.v1", "mode": "novelty-seek" if args.novelty_seek else "balanced",
           "ranked": scored, "killed": killed,
           "calibration": "every item remains OPEN_UNFALSIFIED; ranking cannot create a solve",
           "note": "Interestingness orders stepping-stones; it is heuristic taste, not truth."}
    witcore.save_json(args.out, out)
    print(json.dumps({k: v for k, v in out.items() if k != "ranked"}
                     | {"top": [{"form": s["form"], "score": s["interestingness"]} for s in scored[:6]]},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
