#!/usr/bin/env python3
"""F2 technique atlas at Mathlib scale — `witsoc mathlib-autopsy`.

proof_autopsy grows the technique atlas from witsoc's OWN kernel-verified
closures — a trickle. This tool mines an entire Lean source tree (a built
mathlib4 checkout, or any Lean library) for theorem/proof pairs and merges
their techniques into the same global atlas, so analogical_transfer's grown
analogy base starts from ~100k proofs instead of a handful.

Extraction is syntactic (regex + a depth-aware binder/statement split), and
the entries say so: provenance `mathlib_source` with the trust note
"kernel-verified upstream (Lean library CI), extracted syntactically — not
re-verified locally". They are retrieval HINTS in exactly the existing atlas
shape (suggest_from_atlas ranks them by goal-signature overlap unchanged);
nothing here carries or upgrades trust.

Usage:
  mathlib_autopsy.py --src ~/mathlib4/Mathlib [--limit N] [--atlas PATH]
                     [--dry-run] [--min-tactic-len 1]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
from proof_autopsy import default_atlas, fingerprint  # noqa: E402
from value_function import featurize_goal  # noqa: E402

# theorem/lemma header up to `:= by`, then the same-line tail plus any
# more-indented continuation lines (the tactic block).
_DECL = re.compile(
    r"(?:^|\n)[ \t]*(?:@\[[^\]]*\]\s*)?(?:protected\s+|private\s+|nonrec\s+)*"
    r"(?:theorem|lemma)\s+([A-Za-z0-9_.'₀-ₜ]+)"
    r"((?:[^:=]|:(?!=)|=(?!\s*by\b))*?):=\s*by\b([^\n]*(?:\n[ \t]+[^\n]+)*)",
    re.MULTILINE)


def split_binders_statement(header: str) -> str:
    """The statement is what follows the first depth-0 `:` of the header
    (binders like `(n : Nat)` keep their colons inside brackets)."""
    depth = 0
    opens, closes = "([{⟨", ")]}⟩"
    for i, ch in enumerate(header):
        if ch in opens:
            depth += 1
        elif ch in closes:
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            return header[i + 1:].strip()
    return header.strip()


def extract_theorems(text: str) -> list[dict]:
    out = []
    for m in _DECL.finditer(text):
        name, header, tactics = m.group(1), m.group(2), m.group(3)
        statement = re.sub(r"\s+", " ", split_binders_statement(header)).strip()
        proof = "by " + re.sub(r"\s+", " ", tactics).strip()
        if not statement or len(statement) > 600:
            continue
        out.append({"name": name, "statement": statement, "proof": proof})
    return out


def _entry_key(move: str, signature: list[str]) -> str:
    return hashlib.sha256((move + "|" + ",".join(sorted(signature))).encode()).hexdigest()[:16]


def mine(src: Path, limit: int, min_tactic_len: int) -> list[dict]:
    reports = []
    for path in sorted(src.rglob("*.lean")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for decl in extract_theorems(text):
            if len(decl["proof"]) < 3 + min_tactic_len:
                continue
            reports.append({**decl, "file": str(path.relative_to(src))})
            if len(reports) >= limit:
                return reports
    return reports


def merge_into_atlas(reports: list[dict], atlas_path: Path, src_label: str) -> dict:
    """Same merge semantics as proof_autopsy.record_to_atlas, same entry shape —
    suggest_from_atlas retrieval works on mined entries unchanged."""
    atlas = witcore.load_json(atlas_path, [])
    if not isinstance(atlas, list):
        atlas = []
    by_key = {e.get("key"): e for e in atlas if isinstance(e, dict)}
    added = merged = 0
    for decl in reports:
        move = fingerprint(decl["proof"])
        signature = featurize_goal(decl["statement"])
        key = _entry_key(move, signature)
        entry = by_key.get(key)
        if entry is not None:
            entry["stats"]["uses"] = entry["stats"].get("uses", 0) + 1
            entry["examples"] = (entry.get("examples", []) + [decl["statement"]])[-4:]
            merged += 1
            continue
        entry = {
            "key": key,
            "move": move,
            "goal_signature": signature,
            "proof_skeleton": decl["proof"][:200],
            "examples": [decl["statement"]],
            "generalization": None,
            "stats": {"uses": 1},
            "provenance": f"mathlib_source:{src_label}/{decl['file']}#{decl['name']}",
            "trust_note": ("kernel-verified upstream (Lean library CI), extracted "
                           "syntactically — not re-verified locally; retrieval hint only"),
        }
        atlas.append(entry)
        by_key[key] = entry
        added += 1
    witcore.save_json(atlas_path, atlas)
    return {"added": added, "merged": merged, "atlas_size": len(atlas)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, required=True, help="Lean source tree (e.g. ~/mathlib4/Mathlib)")
    ap.add_argument("--limit", type=int, default=200_000)
    ap.add_argument("--min-tactic-len", type=int, default=1)
    ap.add_argument("--atlas", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true", help="extraction statistics only; write nothing")
    args = ap.parse_args()

    if not args.src.exists():
        print(json.dumps({"error": f"source tree {args.src} does not exist "
                                   "(a built mathlib4 checkout is the intended input)"}))
        return 1
    reports = mine(args.src, args.limit, args.min_tactic_len)
    moves: dict[str, int] = {}
    for decl in reports:
        move = fingerprint(decl["proof"])
        moves[move] = moves.get(move, 0) + 1
    summary = {
        "schema": "witsoc.mathlib_autopsy.v1",
        "src": str(args.src),
        "theorems_extracted": len(reports),
        "moves": dict(sorted(moves.items(), key=lambda kv: -kv[1])),
        "dry_run": args.dry_run,
    }
    if not args.dry_run:
        atlas_path = args.atlas or default_atlas()
        summary["atlas"] = str(atlas_path)
        summary.update(merge_into_atlas(reports, atlas_path, args.src.name))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
