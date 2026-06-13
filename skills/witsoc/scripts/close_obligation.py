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


def minimization_pass(statement: str, name: str, imports: str, lake_dir: Path | None,
                      premises: list[str], workers: int, deep: bool = False) -> tuple[str | None, dict]:
    """OBLIGATION MINIMIZATION: try hypothesis-pruned (STRONGER) variants of the
    goal with a cheap portfolio; when one closes, wrap its proof back onto the
    full goal (`apply hmin <;> assumption`) and kernel-check the wrapper against
    the ORIGINAL statement. Sound by construction — pruning only strengthens, and
    the returned proof is a verified proof of the original goal.

    This is the lever for goals whose irrelevant hypotheses confuse the tactic
    portfolio (e.g. a nonlinear hypothesis makes `omega` reject a goal whose
    conclusion alone is linear). No hypotheses -> no variants -> zero cost."""
    import goal_structure as gs
    trace: dict = {"variants_tried": 0, "variant_closed": None, "dropped": None}
    variants = gs.pruned_variants(statement)
    if not variants:
        return None, trace
    cheap = ["by rfl", "by simp", "by omega", "by decide", "by simp_all", "by norm_num"]
    prem = [f"by exact {p}" for p in premises[:4]] + [f"by simp [{p}]" for p in premises[:4]]
    for v in variants:
        trace["variants_tried"] += 1
        vstmt = v["statement"]

        def vthunk(proof: str):
            def run():
                verdict = witcore.lean_verify_cached(lean_source(name, vstmt, imports, proof), lake_dir)
                return {"proof": proof, **verdict}
            return run

        win = witcore.parallel_first([vthunk(p) for p in (cheap + prem)[:10]],
                                     accept=lambda r: bool(r.get("verified")), max_workers=workers)
        # When the cheap portfolio misses and the caller is already in --search
        # mode, give the pruned variant a SMALL compound search (induction /
        # generalization routes) — this is where minimization buys real reach:
        # the conclusion needs a deep route the hypothesis-burdened goal blocks.
        if not (win and win.get("verified")) and deep:
            import proof_search
            sr = proof_search.search(vstmt, imports, lake_dir, None, None,
                                     max_nodes=60, workers=workers, name=name, repair=False)
            if sr.get("discharged"):
                win = {"proof": sr["proof"], "verified": True}
        if not (win and win.get("verified")):
            continue
        for wrapper in gs.wrapper_candidates(vstmt, win["proof"]):
            verdict = witcore.lean_verify_cached(lean_source(name, statement, imports, wrapper), lake_dir)
            if verdict.get("verified"):
                trace["variant_closed"] = vstmt
                trace["dropped"] = v["dropped"]
                return wrapper, trace
    return None, trace


_TRY_THIS_RE = re.compile(r"Try this:\s*(.+)")


def library_search_repair(statement: str, name: str, imports: str,
                          lake_dir: Path | None, max_suggestions: int = 6) -> tuple[str | None, dict]:
    """F3 ATP step: Lean's library search (`exact?` / `apply?`). One probe build
    each; the compiler's 'Try this: <term>' suggestions are harvested from the
    build output and each is REPLAYED and kernel-verified against the original
    goal. The probe itself is never the recorded proof — library search is
    version-dependent; the replayed suggestion is the stable artifact."""
    import tempfile
    trace: dict = {"probes": [], "suggestions_tried": 0}
    suggestions: list[str] = []
    for probe in ("exact?", "apply?"):
        src = lean_source(name, statement, imports, f"by {probe}")
        with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as fh:
            fh.write(src)
            tmp = Path(fh.name)
        try:
            # uncached on purpose: a successful probe's suggestion message is
            # not retained by the slim cache record.
            verdict = witcore.lean_verify(tmp, lake_dir)
        finally:
            tmp.unlink(missing_ok=True)
        build = verdict.get("build", {}) or {}
        if build.get("tool") == "absent":
            trace["probes"].append({"probe": probe, "status": "no_toolchain"})
            return None, trace
        blob = str(build.get("stdout", "")) + "\n" + str(build.get("stderr", ""))
        found = [s.strip() for s in _TRY_THIS_RE.findall(blob)]
        trace["probes"].append({"probe": probe, "suggestions": len(found)})
        for s in found:
            if s and s not in suggestions:
                suggestions.append(s)
    for s in suggestions[:max_suggestions]:
        proof = s if s.startswith("by ") else f"by {s}"
        trace["suggestions_tried"] += 1
        if witcore.lean_verify_cached(lean_source(name, statement, imports, proof), lake_dir).get("verified"):
            return proof, trace
    return None, trace


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
    ap.add_argument("--no-minimize", action="store_true",
                    help="disable the hypothesis-pruning minimization pass (on by default; "
                         "free for goals without hypotheses)")
    ap.add_argument("--time-budget", type=float, default=None,
                    help="wall-clock seconds for compound search (None = unlimited); a goal that "
                         "would close, closes fast — past this the search yields OPEN and the bus takes over")
    ap.add_argument("--search-max-nodes", type=int, default=300,
                    help="hard node budget for compound search; exhausting it without a proof yields BUDGET_EXHAUSTED (a finding), not an infinite hang")
    ap.add_argument("--library-search", action="store_true",
                    help="force the Lean library-search step (exact?/apply? suggestion replay)")
    ap.add_argument("--no-library-search", action="store_true",
                    help="disable the library-search step even in Mathlib mode")
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
    record = _close(args)
    print(json.dumps({k: v for k, v in record.items() if k != "premises_used"}, indent=2, ensure_ascii=False))
    return 0 if record["discharged"] else 1


def _close(args: argparse.Namespace) -> dict:
    """The closure pipeline shared by the CLI and the in-process API (R3)."""
    stmt = args.lean_statement
    atlas = args.atlas if args.atlas is not None else default_atlas()
    premises = atlas_premises(stmt, args.premise_query, atlas)

    # Ω3 retrieval v2: when a hierarchy-informalized corpus exists, the GLOBAL
    # premise set (per-sub-query union — strategy-level, not keyword-level)
    # joins the keyword premises. The kernel rejects wrong candidates; this
    # only changes reach. No corpus, no cost.
    try:
        import retrieval_v2 as rv
        if rv.corpus_path().exists():
            for s in rv.global_premises(stmt).get("premise_symbols", []):
                if s not in premises:
                    premises.append(s)
    except Exception:
        pass

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
    # W3: mined tactic n-grams — sequences that closed structurally similar
    # goals join the candidate pool (empty table = no cost; kernel rejects
    # wrong candidates, so mining only extends reach).
    try:
        import tactic_ngrams
        for cand in tactic_ngrams.candidates_for(stmt, k=5):
            if cand not in lib_cands:
                lib_cands.append(cand)
    except Exception:
        pass
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

    # OBLIGATION MINIMIZATION: before the expensive compound search, try the
    # hypothesis-pruned variants (cheap, sound, and the wrapper proof is
    # kernel-checked against the original goal).
    minimize_trace = None
    if discharged is None and not no_toolchain and not args.no_minimize:
        proof_m, minimize_trace = minimization_pass(stmt, args.name, args.imports,
                                                    args.lake_dir, premises, args.workers,
                                                    deep=args.search)
        if proof_m:
            discharged = proof_m

    # F3 ATP step: Lean library search before the expensive compound search —
    # two cheap probe builds whose suggestions are replayed under the kernel.
    # Auto-on in Mathlib mode (that is where the searchable library lives).
    library_search_trace = None
    want_libsearch = args.library_search or (bool(os.environ.get("WITSOC_LAKE_ENV")) and not args.no_library_search)
    if discharged is None and not no_toolchain and want_libsearch:
        proof_ls, library_search_trace = library_search_repair(stmt, args.name, args.imports, args.lake_dir)
        if proof_ls:
            discharged = proof_ls

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
                                 max_nodes=args.search_max_nodes, workers=args.workers, name=args.name,
                                 time_budget=getattr(args, "time_budget", None))
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
    if minimize_trace is not None and minimize_trace.get("variants_tried"):
        record["minimization"] = minimize_trace
    if library_search_trace is not None:
        record["library_search"] = library_search_trace

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

    if args.out_ledger is not None and str(args.out_ledger) != "/dev/null":
        witcore.append_record(args.out_ledger, record)
    return record


def close_goal(statement: str, *, name: str = "obligation", imports: str = "",
               lake_dir: Path | None = None, search: bool = False, workers: int = 12,
               emit: Path | None = None, max_candidates: int = 24,
               use_library: bool = False, record_library: bool = False,
               library: Path | None = None, search_max_nodes: int = 300,
               library_search: bool = False, no_minimize: bool = False,
               out_ledger: Path | None = None) -> dict:
    """R3 in-process API: one prover call without a process spawn. Same record
    shape as the CLI. Batch callers (lovasz_prover_dispatch, blueprint
    dispatch, prove_many) share this process's module imports, atlas
    discovery, and the Lean verification cache."""
    ns = argparse.Namespace(
        lean_statement=statement, name=name, wit=None, imports=imports,
        lake_dir=lake_dir, policy=None, atlas=None, no_mathlib_atlas=False,
        premise_query=None, portfolio=None, max_candidates=max_candidates,
        workers=workers, search=search, no_minimize=no_minimize,
        search_max_nodes=search_max_nodes, library_search=library_search,
        no_library_search=not library_search and not os.environ.get("WITSOC_LAKE_ENV"),
        emit=emit, record_library=record_library, use_library=use_library,
        library=library, out_ledger=out_ledger, repl_cmd=None)
    return _close(ns)


def prove_many(goals: list[dict], **shared) -> list[dict]:
    """Batch closure: each goal is {statement, name?, imports?, emit?}; `shared`
    carries the common close_goal options. One process, one cache, zero spawns."""
    out = []
    for g in goals:
        opts = {**shared}
        for k in ("name", "imports", "emit"):
            if g.get(k) is not None:
                opts[k] = g[k]
        out.append(close_goal(str(g["statement"]), **opts))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
