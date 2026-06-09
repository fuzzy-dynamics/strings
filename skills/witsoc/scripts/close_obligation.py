#!/usr/bin/env python3
"""Automated Lean obligation closer — the prover front-end (Tier A).

Given a formal Lean statement, this discharges it by trying proof candidates and
accepting the FIRST that yields a green, `sorry`/`axiom`-free proof (shared
soundness gate). It is the prover loop that turns an `OBLIGATION_OPEN` into
`PROOF_DISCHARGED` for the reachable fragment.

What makes it more than a fixed portfolio:
  - candidate order comes from a learned policy (proof_policy.py), so tactics that
    historically close this kind of goal are tried first;
  - premises from the mathlib atlas (mathlib_atlas.py) are turned into
    `exact`/`apply`/`simp [..]` candidates;
  - candidates are raced in parallel with a content-hash Lean cache (witcore), so
    re-runs and shared sub-attempts are instant;
  - a discharged lemma is recorded to the closure ledger AND (optionally) added to
    the global lemma library, so it compounds across runs;
  - if nothing closes it and WITSOC_LEAN_REPL_CMD / --repl-cmd is set, it escalates
    to mcts_lean.py tactic-state search.

Soundness: success is gated by lean_verify, so a `sorry`/axiom proof is rejected.
`native_decide` is excluded by default.

Usage:
  close_obligation.py --lean-statement "∀ n : Nat, n + 0 = n" [--name foo]
      [--imports "import Mathlib"] [--lake-dir DIR] [--policy policy.json|cmd:CMD]
      [--atlas .witsoc/mathlib_atlas.json] [--premise-query "..."] [--portfolio "a,b"]
      [--emit out.lean] [--record-library] [--out-ledger formalization_obligations.json]
Exit 0 iff discharged.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
import proof_policy  # noqa: E402


def lean_source(name: str, statement: str, imports: str, proof: str) -> str:
    return (f"{imports}\n" if imports else "") + (
        f"namespace WitsocObligation\n\n"
        f"theorem {name} : {statement} := {proof}\n\n"
        f"end WitsocObligation\n")


# Map symbolic goal structure to keyword tokens so a symbolic statement (e.g.
# `a * b = b * a`) matches the right lemma node in the atlas (whose doc is words).
_OP_KEYWORDS = [
    ("*", "mul multiplication"),
    ("+", "add addition"),
    ("^", "pow power"),
    ("-", "sub subtraction"),
    ("=", "eq equal"),
    ("≤", "le order"), ("<", "lt order"), ("≥", "ge order"), (">", "gt order"),
    ("∀", "forall"), ("∃", "exists"),
    ("∧", "and"), ("∨", "or"), ("→", "imp"),
]
_WORD_KEYWORDS = [
    ("Nat", "nat natural"), ("ℕ", "nat natural"),
    ("List", "list"), ("reverse", "reverse"), ("append", "append"),
    ("length", "length"), ("map", "map"), ("succ", "successor"),
]
_COMM_RE = re.compile(r"(\w+)\s*([*+])\s*(\w+)\s*=\s*(\w+)\s*\2\s*(\w+)")


def signature_keywords(statement: str) -> str:
    kws: list[str] = []
    for sym, words in _OP_KEYWORDS:
        if sym in statement:
            kws.append(words)
    for sym, words in _WORD_KEYWORDS:
        if sym in statement:
            kws.append(words)
    m = _COMM_RE.search(statement)
    if m and m.group(1) == m.group(5) and m.group(3) == m.group(4):
        kws.append("comm commutative swap")
    return " ".join(kws)


def atlas_premises(statement: str, query: str | None, atlas: Path | None) -> list[str]:
    if not atlas or not atlas.exists():
        return []
    # Prefer an explicit query; otherwise derive keywords from the goal structure
    # (falling back to the raw statement so we never query with nothing).
    derived = signature_keywords(statement)
    effective_query = query or (f"{derived} {statement}".strip() if derived else statement)
    try:
        r = subprocess.run([sys.executable, str(SCRIPT_DIR / "mathlib_atlas.py"),
                            "--query", effective_query, "--atlas", str(atlas), "--limit", "6"],
                           capture_output=True, text=True, timeout=30, check=False)
        data = json.loads(r.stdout)
        prems: list[str] = []
        for m in data.get("matches", []):
            for sym in (m.get("symbols") or [])[:3]:
                if sym not in prems:
                    prems.append(str(sym))
        return prems[:10]
    except Exception:
        return []


def library_premises(statement: str, library: Path | None, limit: int = 6) -> list[str]:
    """Cross-run reuse: pull proofs that closed similar goals in past runs from the
    global lemma library (the proof is recorded in each lemma's provenance), and
    offer them as candidates. Every candidate is still kernel-gated, so a proof
    that does not transfer simply fails — this only changes ordering/reach."""
    if not library or not (Path(library) / "lemmas.db").exists():
        return []
    query = (f"{signature_keywords(statement)} {statement}").strip()
    try:
        r = subprocess.run([sys.executable, str(SCRIPT_DIR / "lemma_library.py"),
                            "--library", str(library), "search", "--query", query, "--limit", str(limit)],
                           capture_output=True, text=True, timeout=30, check=False)
        data = json.loads(r.stdout)
    except Exception:
        return []
    cands: list[str] = []
    for m in data.get("matches", []):
        prov = str(m.get("provenance") or "")
        if ":" not in prov:
            continue
        proof = prov.split(":", 1)[1].strip()
        # Only reuse things that look like a Lean proof term/tactic.
        if proof and (proof.startswith("by ") or proof.startswith("fun ") or proof[:1].isalpha()):
            if proof not in cands:
                cands.append(proof)
    return cands[:limit]


def default_atlas() -> Path | None:
    """Discover a premise atlas without requiring callers to pass --atlas:
    WITSOC_ATLAS, then the bundled core lemma atlas next to this script, then the
    cwd-relative atlas paths."""
    env = os.environ.get("WITSOC_ATLAS")
    if env and Path(env).exists():
        return Path(env)
    bundled = SCRIPT_DIR / "core_lemma_atlas.json"
    if bundled.exists():
        return bundled
    for candidate in (Path("runs/mathlib_atlas.json"), Path(".witsoc/mathlib_atlas.json")):
        if candidate.exists():
            return candidate
    return None


def mathlib_atlas_path() -> Path | None:
    """A Mathlib IMPORT atlas, distinct from the core PREMISE atlas: WITSOC_MATHLIB_ATLAS,
    then `.witsoc/mathlib_atlas.json`. Absent on a bare host (no Mathlib), so the import
    bridge below is a clean no-op until `build_mathlib_atlas.py` indexes a checkout."""
    env = os.environ.get("WITSOC_MATHLIB_ATLAS")
    if env and Path(env).exists():
        return Path(env)
    p = Path(".witsoc/mathlib_atlas.json")
    return p if p.exists() else None


def mathlib_context(statement: str, atlas: Path | None, limit: int = 3) -> tuple[list[str], list[str]]:
    """Type-aware retrieval -> (import_lines, premise_symbols) the goal needs.

    The premise selector pulled symbol NAMES from the atlas but dropped the modules,
    so a Mathlib symbol (e.g. `Nat.divisors`) was offered as a premise WITHOUT the
    `import Mathlib.NumberTheory.Divisors` it requires, and could never compile. This
    returns both the import lines (top atlas matches + their import closure) and the
    matched symbols, so a Mathlib goal is both importable and has its premises."""
    if not atlas or not atlas.exists():
        return [], []
    query = (f"{signature_keywords(statement)} {statement}").strip()
    try:
        r = subprocess.run([sys.executable, str(SCRIPT_DIR / "mathlib_atlas.py"),
                            "--query", query, "--atlas", str(atlas), "--limit", str(limit)],
                           capture_output=True, text=True, timeout=30, check=False)
        data = json.loads(r.stdout)
    except Exception:
        return [], []
    mods: list[str] = []
    syms: list[str] = []
    for m in data.get("matches", []):
        mod = m.get("module")
        if mod and mod not in mods:
            mods.append(str(mod))
        for s in (m.get("symbols") or [])[:3]:
            if s not in syms:
                syms.append(str(s))
    for imp in data.get("imports", []) or []:
        if imp not in mods:
            mods.append(str(imp))
    return [f"import {m}" for m in mods[:limit]], syms[:10]


def try_repl(statement: str, repl_cmd: str, lake_dir: Path | None) -> str | None:
    mcts = SCRIPT_DIR / "mcts_lean.py"
    if not mcts.exists():
        return None
    cmd = [sys.executable, str(mcts), "--goal", statement, "--repl-cmd", repl_cmd]
    if lake_dir:
        cmd += ["--lake-dir", str(lake_dir)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
        reply = json.loads(r.stdout) if r.stdout.strip() else {}
        return reply.get("proof")
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lean-statement", required=True)
    ap.add_argument("--name", default="obligation")
    ap.add_argument("--wit", type=Path, default=None)
    ap.add_argument("--imports", default="")
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--policy", default=None, help="policy.json or cmd:<command>")
    ap.add_argument("--atlas", type=Path, default=None)
    ap.add_argument("--no-mathlib-atlas", action="store_true",
                    help="disable Mathlib import/premise injection even if a Mathlib atlas is present")
    ap.add_argument("--premise-query", default=None)
    ap.add_argument("--portfolio", default=None, help="comma-separated proofs (overrides policy)")
    ap.add_argument("--max-candidates", type=int, default=24)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--search", action="store_true",
                    help="if the flat portfolio fails, escalate to verifier-guided compound proof search")
    ap.add_argument("--search-max-nodes", type=int, default=300,
                    help="hard node budget for compound search; exhausting it without a proof yields BUDGET_EXHAUSTED (a finding), not an infinite hang")
    ap.add_argument("--emit", type=Path, default=None)
    ap.add_argument("--record-library", action="store_true",
                    help="add the discharged lemma to the global lemma library")
    ap.add_argument("--use-library", action="store_true",
                    help="consult the lemma library for reusable proofs (cross-run compounding)")
    ap.add_argument("--library", type=Path, default=None,
                    help="lemma library dir (default: global WITSOC_LEMMA_LIBRARY)")
    ap.add_argument("--out-ledger", type=Path, default=Path("formalization_obligations.json"))
    ap.add_argument("--repl-cmd", default=None)
    args = ap.parse_args()

    stmt = args.lean_statement
    atlas = args.atlas if args.atlas is not None else default_atlas()
    premises = atlas_premises(stmt, args.premise_query, atlas)

    # Layer 3.3: type-aware Mathlib retrieval. When a Mathlib atlas is configured,
    # inject the imports the goal's premises need (the missing link: symbols were
    # offered without their import) and add the matched Mathlib symbols as premises.
    # No-op without a Mathlib atlas, so a bare host is unaffected.
    mlib_imports: list[str] = []
    if not args.no_mathlib_atlas:
        mlib = mathlib_atlas_path()
        if mlib:
            mlib_imports, mlib_syms = mathlib_context(stmt, mlib)
            for s in mlib_syms:
                if s not in premises:
                    premises.append(s)
            if mlib_imports and not args.imports:
                args.imports = "\n".join(mlib_imports)
    if args.portfolio:
        candidates = [p.strip() for p in args.portfolio.split(",") if p.strip()]
    else:
        policy = None
        if args.policy and not args.policy.startswith("cmd:"):
            policy = witcore.load_json(Path(args.policy), None)
        if args.policy and args.policy.startswith("cmd:"):
            reply = witcore.run_sampler(args.policy, {"goal": stmt, "premises": premises})
            candidates = (reply or {}).get("tactics") or proof_policy.rank_tactics(stmt, None, premises)
        else:
            candidates = proof_policy.rank_tactics(stmt, policy, premises)
    # Cross-run reuse: try proofs that closed similar goals before (library), first.
    library = args.library if args.library is not None else witcore.global_library()
    lib_cands = library_premises(stmt, library) if args.use_library else []
    if lib_cands:
        candidates = lib_cands + candidates
        seen: set[str] = set()
        candidates = [c for c in candidates if not (c in seen or seen.add(c))]
    # Keep room for premise-derived candidates (exact/apply/simp per premise) so a
    # high-value library lemma is not truncated away by the fixed-tactic prefix.
    effective_cap = max(args.max_candidates, 12 + 3 * len(premises) + len(lib_cands))
    candidates = candidates[:effective_cap]

    # Race candidates in parallel; first sound proof wins. Cache makes repeats free.
    def make_thunk(proof: str):
        def run():
            src = lean_source(args.name, stmt, args.imports, proof)
            verdict = witcore.lean_verify_cached(src, args.lake_dir)
            return {"proof": proof, **verdict}
        return run

    no_toolchain = False
    first = witcore.parallel_first(
        [make_thunk(p) for p in candidates],
        accept=lambda r: bool(r.get("verified")),
        max_workers=args.workers,
    )
    discharged = first["proof"] if first and first.get("verified") else None

    # Detect "no Lean toolchain" so we report UNCHECKED rather than OPEN.
    if discharged is None and candidates:
        probe = witcore.lean_verify_cached(lean_source(args.name, stmt, args.imports, candidates[0]), args.lake_dir)
        no_toolchain = not probe.get("checked")

    # Escalate to compound proof search (Phase 1) when the flat portfolio fails.
    search_nodes = 0
    budget_exhausted = False
    search_trace = None
    if discharged is None and not no_toolchain and args.search:
        import proof_search
        policy = witcore.load_json(Path(args.policy), None) if (args.policy and not args.policy.startswith("cmd:")) else None
        # Honor an explicit --library for the search escalation too (previously it
        # always used the global library, so an isolated library passed for a run or
        # a test was ignored). Backward-compatible: no --library => global as before.
        lib = args.library if args.library is not None else (witcore.global_library() if witcore.global_library().exists() else None)
        sr = proof_search.search(stmt, args.imports, args.lake_dir, policy, lib,
                                 max_nodes=args.search_max_nodes, workers=args.workers, name=args.name)
        search_nodes = sr.get("nodes", 0)
        search_trace = sr.get("trace")
        if sr.get("discharged"):
            discharged = sr["proof"]
        elif search_nodes >= args.search_max_nodes:
            # Layer 1: the search consumed its full node budget without a proof.
            # Report it as a finding (length/resource-blocked), not a hang.
            budget_exhausted = True

    if discharged is None and not no_toolchain and (args.repl_cmd or os.environ.get("WITSOC_LEAN_REPL_CMD")):
        repl = args.repl_cmd or os.environ["WITSOC_LEAN_REPL_CMD"]
        proof = try_repl(stmt, repl, args.lake_dir)
        if proof:
            src = lean_source(args.name, stmt, args.imports, proof)
            if witcore.lean_verify_cached(src, args.lake_dir).get("verified"):
                discharged = proof

    if no_toolchain:
        label = "UNCHECKED_NO_TOOLCHAIN"
    elif discharged:
        label = "PROOF_DISCHARGED"
    elif budget_exhausted:
        label = "BUDGET_EXHAUSTED"
    else:
        label = "OBLIGATION_OPEN"
    record = {
        "schema": "witsoc.obligation_closure.v1",
        "name": args.name, "statement": stmt, "wit": str(args.wit) if args.wit else None,
        "discharged": discharged is not None, "proof": discharged, "label": label,
        "candidates_tried": len(candidates), "search_nodes": search_nodes,
        "budget_exhausted": budget_exhausted, "search_max_nodes": args.search_max_nodes,
        "premises_used": premises,
    }
    if mlib_imports:
        record["mathlib_imports_injected"] = mlib_imports
    if search_trace is not None:
        record["search_trace"] = search_trace

    if discharged and args.emit:
        args.emit.parent.mkdir(parents=True, exist_ok=True)
        args.emit.write_text(lean_source(args.name, stmt, args.imports, discharged), encoding="utf-8")
        record["lean_path"] = str(args.emit)

    if discharged and args.record_library:
        try:
            subprocess.run([sys.executable, str(SCRIPT_DIR / "lemma_library.py"),
                            "--library", str(library), "add",
                            "--statement", stmt, "--tier", "WIT_STRUCTURE",
                            "--provenance", f"close_obligation:{discharged}"],
                           capture_output=True, text=True, timeout=30, check=False)
            record["recorded_to_global_library"] = True
        except Exception:
            pass

    witcore.append_record(args.out_ledger, record)
    print(json.dumps({k: v for k, v in record.items() if k != "premises_used"}, indent=2, ensure_ascii=False))
    return 0 if discharged else 1


if __name__ == "__main__":
    raise SystemExit(main())
