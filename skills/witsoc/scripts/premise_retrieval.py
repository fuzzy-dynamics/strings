#!/usr/bin/env python3
"""Phase 2: Explorer-stage premise retrieval, GROUNDED by validation.

Explorer's job is to be a top-notch retrieval engine: given a frozen target, find the
declarations a proof will likely need — and say honestly which ones actually EXIST in
the available Lean/Mathlib vs which are only search targets. This assembles that into
a structured packet for the Lovász barrier packet:

  1. retrieve candidate premises with the type-aware atlas (`mathlib_atlas`, symbol
     overlap), getting modules + symbols + the import closure;
  2. VALIDATE each symbol with `validate_premises.resolve` — KNOWN (resolves now),
     SEARCH_TARGET (named but does not resolve, e.g. needs Mathlib not installed), or
     UNCHECKED (no toolchain);
  3. emit `premise_retrieval.json`: known premises the prover can cite immediately vs
     search targets Lovász must locate/replace. A premise is NEVER silently assumed to
     exist — a hallucinated citation can't slip through.

Usage:
  premise_retrieval.py --statement "<Lean goal>" [--atlas A] [--lake-dir D]
      [--limit 6] [--out premise_retrieval.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import mathlib_atlas as ma  # noqa: E402
import validate_premises as vp  # noqa: E402
import close_obligation as co  # noqa: E402  -- signature_keywords (operator -> doc words)


def _real_module(m: str) -> bool:
    """A genuinely importable Lean module path (`Mathlib.X`, `Std.X`, …) — NOT the
    core atlas's synthetic `core.Nat.mul_comm` ids (core symbols need no import)."""
    head = str(m).split(".", 1)[0]
    return bool(head) and head[0].isupper() and head != "core"


def _resolve_state(symbol: str, real_imports: str, lake_dir: Path | None) -> str:
    """Resolve against the prelude first (core symbols need no import); only if that
    fails AND there is a real Mathlib import to try, resolve again with it."""
    state = vp.resolve(symbol, "", lake_dir).get("state")
    if state == "KNOWN" or not real_imports:
        return state
    return vp.resolve(symbol, real_imports, lake_dir).get("state")


def retrieve_packet(statement: str, atlas_path: Path | None, lake_dir: Path | None,
                    limit: int = 6, validate: bool = True) -> dict:
    atlas = ma.load_atlas(atlas_path, None) if atlas_path else {"nodes": []}
    # Use the same query the prover uses (operator/notation -> doc words) so a goal
    # that names no qualified symbol (e.g. `a*b=b*a`) still retrieves the right node.
    query = f"{co.signature_keywords(statement)} {statement}".strip()
    res = ma.query_atlas(atlas, query, "", limit)
    symbols: list[str] = []
    for m in res.get("matches", []):
        for s in (m.get("symbols") or [])[:4]:
            if s not in symbols:
                symbols.append(str(s))
    real_imports = [m for m in res.get("imports", [])[:limit] if _real_module(m)]
    imports_str = "\n".join(f"import {m}" for m in real_imports) if real_imports else ""

    known: list[str] = []
    search_targets: list[str] = []
    unchecked: list[str] = []
    if validate:
        for s in symbols:
            state = _resolve_state(s, imports_str, lake_dir)
            (known if state == "KNOWN" else search_targets if state == "SEARCH_TARGET" else unchecked).append(s)
    else:
        unchecked = list(symbols)
    imports = real_imports

    toolchain = "absent" if (unchecked and not known and not search_targets) else "present"
    return {
        "schema": "witsoc.premise_retrieval.v1",
        "target": statement,
        "retrieved_symbols": symbols,
        "recommended_imports": [f"import {m}" for m in imports],
        "known_premises": known,            # exist now -> the prover may cite directly
        "search_targets": search_targets,   # named but unresolved -> Lovász must locate/replace
        "unchecked": unchecked,             # no toolchain to decide
        "toolchain": toolchain,
        "retrieval_status": res.get("status"),
        "note": "known_premises are kernel-resolvable; search_targets are NOT assumed to exist "
                "(a hallucinated citation cannot pass) and become Lovász retrieval obligations.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--statement", required=True)
    ap.add_argument("--atlas", type=Path, default=None)
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--no-validate", action="store_true", help="skip Lean resolution (retrieval only)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    atlas = args.atlas
    if atlas is None:
        # default to the bundled core atlas so this works with no Mathlib present.
        core = SCRIPT_DIR / "core_lemma_atlas.json"
        atlas = core if core.exists() else None
    packet = retrieve_packet(args.statement, atlas, args.lake_dir, args.limit, not args.no_validate)
    if args.out:
        args.out.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(packet, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
