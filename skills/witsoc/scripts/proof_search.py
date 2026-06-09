#!/usr/bin/env python3
"""Verifier-guided best-first proof search (Phase 1).

The fixed portfolio only tries atomic one-tactic proofs. This searches *compound*
proofs — setup (intro/constructor/induction) + rewriting (unfold/simp-only on the
defs named in the goal) + a finisher — and RECOMBINES verified lemmas from the
lemma library by inlining them as `have`s. Every candidate is the WHOLE proof,
accepted only by lean_check (the kernel is the sole trust root); the policy only
*orders* candidates, it never certifies one.

Two oracles, same trust root:
  - REPL mode (WITSOC_LEAN_REPL_CMD / --repl-cmd): mcts_lean.py gives per-tactic
    goal-count feedback to guide expansion (true tactic-state search).
  - REPL-free (default): each compound candidate is built and checked by
    lean_check; candidates are ordered by the policy and the simplest verified one
    wins. Works with a bare `lean`, no project/REPL needed.

This module is the engine; close_obligation.py --search is the entry point.

CLI (for testing):
  proof_search.py --lean-statement "∀ n:Nat, f n = n+n" --imports "def f (n:Nat):Nat:=n+n"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
import proof_policy  # noqa: E402
import value_function  # noqa: E402  -- learned candidate-ordering value function

# Proof setup moves (introduce binders / split goals / start induction).
PREFIXES = ["", "intro n", "intro m n", "intro a b c", "intro h", "intro n h",
            "rintro ⟨h1, h2⟩", "constructor", "intro n; induction n with | zero => skip | succ k ih => skip"]
# Finisher tactic BODIES (no leading `by`); ordered further by the policy.
FINISHERS = ["rfl", "decide", "omega", "simp", "simp_all", "norm_num", "linarith",
             "ring", "trivial", "tauto", "exact ⟨_, rfl⟩", "exact h.2", "exact h.1",
             "exact ⟨h.2, h.1⟩", "assumption"]

_IDENT = re.compile(r"\b([a-z][A-Za-z0-9_]*)\b")
_LEAN_KEYWORDS = {"fun", "let", "by", "match", "with", "then", "else", "if", "do"}


def goal_idents(statement: str, preamble: str) -> list[str]:
    """Lowercase identifiers in the goal that are also defined in the preamble —
    candidate targets for `unfold`/`simp only [..]`."""
    defined = set(re.findall(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)", preamble))
    found = [m.group(1) for m in _IDENT.finditer(statement) if m.group(1) in defined]
    # preserve order, dedup
    seen: set[str] = set()
    return [x for x in found if not (x in seen or seen.add(x))]


def library_haves(statement: str, library: Path | None, limit: int = 3) -> list[tuple[str, str]]:
    """Retrieve verified lemmas whose Lean proof is recoverable; return
    (lean_have_block, finisher_hint) candidates that inline them as a `have`."""
    if not library:
        return []
    try:
        r = subprocess.run([sys.executable, str(SCRIPT_DIR / "lemma_library.py"),
                            "--library", str(library), "search", "--query", statement, "--limit", str(limit)],
                           capture_output=True, text=True, timeout=30, check=False)
        matches = json.loads(r.stdout).get("matches", []) if r.returncode == 0 else []
    except Exception:
        return []
    haves: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        stmt = m.get("statement")
        # provenance ("close_obligation:<proof>") now comes back in the search result,
        # so no second `get` subprocess per match.
        prov = m.get("provenance") or ""
        if stmt and prov.startswith("close_obligation:"):
            proof = prov.split("close_obligation:", 1)[1].strip()
            # Parenthesize the proof term: a `by ...` block greedily eats every
            # following tactic, so an un-grouped `have h := by t1; t2` would absorb
            # the candidate's finisher (`; simp [hlib]`) into the have's own proof
            # and leave the MAIN goal unsolved. `:= (by ...)` closes the block so the
            # finisher applies to the goal — this is what makes lemma-as-premise
            # recombination actually compose.
            haves.append((f"have hlib{i} : {stmt} := ({proof})", f"hlib{i}"))
    return haves


def premise_pool(statement: str, library: Path | None) -> tuple[list[str], list[str]]:
    """Layer 3.2: mirror `close_obligation`'s reachability wiring inside the deep
    search. Returns (atlas_premises, library_proofs):

      - atlas_premises: library lemma names selected from the premise atlas by the
        goal's signature (e.g. `Nat.mul_comm` for a commutativity goal). Turned into
        `exact/apply/simp [prem]` candidates — this is what `prove` had and the deep
        search did not, the measured 8/12-vs-10/12 reach gap.
      - library_proofs: whole proofs that closed similar goals in past runs (cross-run
        compounding). Every candidate is still kernel-gated, so a premise that does
        not apply simply fails; this only changes ordering and REACH.
    """
    try:
        import close_obligation as co
    except Exception:
        return [], []
    try:
        atlas = co.default_atlas()
        prems = co.atlas_premises(statement, None, atlas) if atlas else []
    except Exception:
        prems = []
    try:
        lib_proofs = co.library_premises(statement, library) if library else []
    except Exception:
        lib_proofs = []
    return prems, lib_proofs


_FORALL_NAT_RE = re.compile(r"^\s*∀\s*\(?\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(Nat|ℕ)\s*\)?\s*,\s*(.+)$")


# Core (no-Mathlib) distribution/refactor lemmas that let omega finish a
# polynomial Nat identity after the product is factored out and a `congr` peels
# the common factor. (`ring`/`ring_nf`/`nlinarith` are Mathlib and absent here.)
_DISTRIB = ["Nat.mul_add", "Nat.add_mul"]
_REFACTOR = ["← Nat.add_mul", "← Nat.mul_add"]


def induction_candidates(statement: str, preamble: str) -> list[str]:
    """Real structural-induction proofs for `∀ v : Nat, body` goals (the old
    induction prefix used `skip` and could never close). The successor case
    unfolds the recursive defs, rewrites with the induction hypothesis `ih`, and
    closes the residual arithmetic — including NONLINEAR (Gauss-style) residuals,
    which need a core-only `distribute -> apply ih -> refactor -> congr -> omega`
    chain because `ring` is unavailable."""
    m = _FORALL_NAT_RE.match(statement.strip())
    if not m:
        return []
    v = m.group(1)
    defs = goal_idents(statement, preamble)
    defset = ", ".join(defs)
    ih_simp = f"{defset}, ih" if defs else "ih"

    base_fins = ["rfl", "simp", "decide", "omega", "simp_all"]
    if defs:
        base_fins = [f"simp [{defset}]", f"simp only [{defset}]"] + base_fins

    # Linear-residual finishers (close goals like dbl-rec).
    succ_fins: list[str] = [
        f"simp [{ih_simp}]", f"simp [{ih_simp}]; omega", f"simp [{ih_simp}] <;> omega",
        f"simp_all [{ih_simp}]", "omega",
    ]
    # Nonlinear-residual finishers: factor the product back out, peel it with
    # `congr`, and let omega close the linear factor equality (Gauss-style).
    if defs:
        succ_fins.append(f"simp [{defset}]; omega")
        succ_fins.append(f"simp only [{defset}, Nat.mul_add, Nat.add_mul, ih]; congr 1 <;> omega")
        for d in _DISTRIB:
            succ_fins.append(f"rw [{defset}, {d}, ih]; omega")
            succ_fins.append(f"rw [{defset}, {d}, ih]; congr 1 <;> omega")
            for ref in _REFACTOR:
                succ_fins.append(f"rw [{defset}, {d}, ih, {ref}, Nat.mul_comm]; congr 1 <;> omega")
                succ_fins.append(f"rw [{defset}, {d}, ih, {ref}, Nat.mul_comm]; congr 1; omega")
                succ_fins.append(f"rw [{defset}, {d}, ih, {ref}, Nat.mul_comm]; omega")
                succ_fins.append(f"rw [{defset}, {d}, ih, {ref}]; congr 1 <;> omega")
    # dedup succ finishers preserving order
    seen_s: set[str] = set()
    succ_fins = [s for s in succ_fins if not (s in seen_s or seen_s.add(s))]

    out: list[str] = []
    for z in base_fins:
        for s in succ_fins:
            out.append(f"by intro {v}; induction {v} with | zero => {z} | succ k ih => {s}")
    seen: set[str] = set()
    return [c for c in out if not (c in seen or seen.add(c))]


_REC_DEF_RE = re.compile(
    r"def\s+(\w+)\s*:\s*Nat\s*(?:→|->)\s*\w+\s*\n\s*\|\s*0\s*=>\s*([^\n]+)\n\s*\|\s*\(?\s*(\w+)\s*\+\s*1\s*\)?\s*=>\s*([^\n]+)")


def recursive_defs(preamble: str) -> list[dict]:
    """Detect `def f : Nat → _ | 0 => .. | (n+1) => ..` recursive definitions."""
    out = []
    for m in _REC_DEF_RE.finditer(preamble or ""):
        out.append({"name": m.group(1), "base_rhs": m.group(2).strip(),
                    "succ_var": m.group(3), "succ_rhs": m.group(4).strip()})
    return out


_REC_DEF2_RE = re.compile(
    r"def\s+(\w+)\s*:\s*Nat\s*(?:→|->)\s*Nat\s*(?:→|->)\s*\w+\s*\n"
    r"\s*\|\s*0\s*,\s*(\w+)\s*=>\s*([^\n]+)\n"
    r"\s*\|\s*\(?\s*(\w+)\s*\+\s*1\s*\)?\s*,\s*(\w+)\s*=>\s*([^\n]+)")


def recursive_defs2(preamble: str) -> list[dict]:
    """Detect a 2-argument accumulator recursion
    `def f : Nat → Nat → _ | 0, acc => base | (n+1), acc => step`."""
    out = []
    for m in _REC_DEF2_RE.finditer(preamble or ""):
        out.append({"name": m.group(1), "succ_var": m.group(4)})
    return out


def generalization_candidates(statement: str, preamble: str) -> list[str]:
    """Phase 1 — deep search across the INDUCTION-GENERALIZATION barrier.

    A goal like `∀ n, f n 0 = n` where `f` accumulates cannot be closed by induction
    on the goal as stated: the IH (`f k 0 = k`) is too weak for the successor case
    (`f k 1 = k+1`). The proof needs a STRONGER, generalized auxiliary lemma
    (`∀ n a, f n a = a + n`) proved by induction, then specialized. We don't know the
    generalized right-hand side, so we SEARCH a small template family for it; each
    candidate is a full two-level proof, kernel-gated, so a wrong template just fails.
    This reaches proofs the one-level induction route provably cannot."""
    m = _FORALL_NAT_RE.match(statement.strip())
    defs2 = recursive_defs2(preamble)
    if not m or not defs2 or "=" not in m.group(3):
        return []
    v, body = m.group(1), m.group(3)
    lhs, _, rhs = body.partition("=")
    lhs, rhs = lhs.strip(), rhs.strip()
    a = "a" if v != "a" else "a0"
    out: list[str] = []
    for d in defs2:
        f = d["name"]
        # locate `f v <literal-const>` on either side; generalize that constant.
        for side, goal_rhs in ((lhs, rhs), (rhs, lhs)):
            cm = re.search(rf"\b{re.escape(f)}\s+{re.escape(v)}\s+(\d+)\b", side)
            if not cm:
                continue
            # candidate generalized RHS g(v,a). `a + goal_rhs` is the principled one
            # for an additive accumulator; the rest are cheap structural variants.
            # `a + goal_rhs` is the principled invariant for an additive accumulator;
            # the others are cheap structural variants. Kept small — each candidate is
            # an expensive two-level Lean build.
            templates = [f"{a} + {goal_rhs}", f"{goal_rhs} + {a}", f"{a} + {v}", f"{v} + {a}"]
            # the generalized-lemma proof shape that closes additive accumulators
            # (verified end to end); parenthesized so the main finisher is not
            # absorbed into the `have`'s `by` block.
            gproof = (f"by intro {v}; induction {v} with "
                      f"| zero => simp [{f}] | succ k ih => simp [{f}, ih]; omega")
            for t in templates:
                have = f"have hgen : ∀ {v} {a} : Nat, {f} {v} {a} = {t} := ({gproof})"
                for fin in (f"simp [hgen]", f"simp [hgen]; omega", f"rw [hgen]"):
                    out.append(f"by intro {v}; {have}; {fin}")
            break  # first matching occurrence per def is enough
    seen: set[str] = set()
    return [c for c in out if not (c in seen or seen.add(c))]


def helper_lemmas(preamble: str) -> list[dict]:
    """Generate the base + recurrence helper lemmas for each recursive def. These
    are `rfl`-true facts (kernel-checkable); returned for reporting/harvest."""
    out = []
    for d in recursive_defs(preamble):
        out.append({"name": f"{d['name']}_zero",
                    "statement": f"{d['name']} 0 = {d['base_rhs']}", "proof": "rfl"})
        out.append({"name": f"{d['name']}_succ",
                    "statement": f"{d['name']} ({d['succ_var']}+1) = {d['succ_rhs']}", "proof": "rfl"})
    return out


def helper_induction_candidates(statement: str, preamble: str) -> list[str]:
    """Induction proofs that inline the recurrence as a local `have` (self-
    contained, no preamble change), then run the same close chains. Used as a
    fallback route when the def-equation route does not fire."""
    m = _FORALL_NAT_RE.match(statement.strip())
    defs = recursive_defs(preamble)
    if not m or not defs:
        return []
    v = m.group(1)
    out: list[str] = []
    for d in defs:
        name = d["name"]
        # recurrence at the induction variable k (substitute the def's succ var)
        succ_k = re.sub(rf"\b{re.escape(d['succ_var'])}\b", "k", d["succ_rhs"])
        have = f"have hs : {name} (k+1) = {succ_k} := rfl"
        for fin in [f"rw [hs, Nat.mul_add, ih, ← Nat.add_mul, Nat.mul_comm]; congr 1 <;> omega",
                    f"rw [hs, Nat.mul_add, ih]; omega",
                    f"simp [hs, ih]; omega", f"simp [hs, ih]"]:
            out.append(f"by intro {v}; induction {v} with | zero => simp [{name}] | succ k ih => {have}; {fin}")
    seen: set[str] = set()
    return [c for c in out if not (c in seen or seen.add(c))]


_FORALL_TYPED_RE = re.compile(r"^\s*∀\s*\(?\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^,]+?)\s*\)?\s*,\s*(.+)$")

# Registry of inductive types we can do structural induction over. Each entry maps a
# type-head pattern to its constructor cases `(case_name, binders, has_induction_hyp)`.
# Nat stays in induction_candidates (it has a tuned arithmetic finisher set); this is
# the extension point — add an entry to support a new inductive type.
_INDUCT_TYPES = [
    (re.compile(r"List\b"),   [("nil", "", False), ("cons", "hd tl ih", True)]),
    (re.compile(r"Option\b"), [("none", "", False), ("some", "x", False)]),
]


def structural_induction_candidates(statement: str, preamble: str) -> list[str]:
    """Phase 1: structural induction over inductive types BEYOND Nat (List, Option, …).

    A goal like `∀ (l : List _), llen l = l.length` or `∀ (o : Option _), oval o = …`
    needs `induction x with | <ctor> … => …`, which `simp` alone cannot do (verified:
    it makes no progress / leaves unsolved goals). For each registered type this emits
    one induction skeleton per finisher PROFILE — a `(non-recursive-case, recursive-
    case)` finisher pair applied uniformly across the constructors — kept bounded.
    Kernel-gated, so a wrong finisher just fails."""
    m = _FORALL_TYPED_RE.match(statement.strip())
    if not m:
        return []
    v, typ = m.group(1), m.group(2).strip()
    cases = next((c for pat, c in _INDUCT_TYPES if pat.match(typ)), None)
    if not cases:
        return []
    defs = goal_idents(statement, preamble)
    defset = ", ".join(defs)
    base = f"simp [{defset}]" if defs else "simp"
    ih = f"simp [{defset}, ih]" if defs else "simp [ih]"
    # (non-recursive-case finisher, recursive-case finisher) profiles.
    profiles = [
        (base, ih), (base, f"{ih}; omega"), (base, f"{ih} <;> omega"),
        (base, "simp_all"), ("simp", "simp_all"), ("rfl", ih),
        (f"simp only [{defset}]" if defs else "simp", ih),
    ]
    out: list[str] = []
    for nonrec_fin, rec_fin in profiles:
        parts = []
        for name, binders, has_ih in cases:
            b = f" {binders}" if binders else ""
            parts.append(f"| {name}{b} => {rec_fin if has_ih else nonrec_fin}")
        out.append(f"by intro {v}; induction {v} with " + " ".join(parts))
    seen: set[str] = set()
    return [c for c in out if not (c in seen or seen.add(c))]


def candidates(statement: str, preamble: str, policy: dict | None, library: Path | None,
               premises: list[str] | None = None, lib_proofs: list[str] | None = None) -> list[str]:
    """Ordered list of compound proof bodies to try (simplest first).

    `premises`/`lib_proofs` come from `premise_pool`; pass them in to avoid a
    second atlas/library lookup. If omitted they are derived here so every caller
    (close_obligation --search, flywheel, curriculum) gets atlas-strength search."""
    if premises is None or lib_proofs is None:
        p2, l2 = premise_pool(statement, library)
        premises = premises if premises is not None else p2
        lib_proofs = lib_proofs if lib_proofs is not None else l2
    finishers = [t[3:] if t.startswith("by ") else t
                 for t in proof_policy.rank_tactics(statement, policy, [])]
    finishers += [f for f in FINISHERS if f not in finishers]
    # Layer 3.2: premise-guided finishers (so a premise also closes goals that need a
    # setup prefix or an unfold first, via the compound cross-product below).
    for prem in premises:
        for body in (f"exact {prem}", f"apply {prem}", f"simp [{prem}]"):
            if body not in finishers:
                finishers.append(body)
    idents = goal_idents(statement, preamble)
    mids = [""] + [f"unfold {i}" for i in idents] + [f"simp only [{i}]" for i in idents]
    haves = library_haves(statement, library)

    seqs: list[tuple[int, str]] = []  # (cost, proof_body)
    for pi, prefix in enumerate(PREFIXES):
        for mi, mid in enumerate(mids):
            for fi, fin in enumerate(finishers):
                parts = [p for p in (prefix, mid, fin) if p]
                if not parts:
                    continue
                cost = (pi > 0) * 2 + (mi > 0) * 1 + fi  # prefer short, policy-ranked
                seqs.append((cost, "by " + "; ".join(parts)))
    # Learned value re-ranking of the compound cross-product (the largest, most
    # truncation-prone part): order by PREDICTED SUCCESS on this goal so good
    # compound proofs land within the node budget. With no trained model the score
    # is 0 everywhere, so the secondary key (hand-cost) gives EXACTLY the previous
    # order — zero behavior change until the flywheel trains a model.
    vmodel = value_function.load_model(library)
    gfeats = value_function.featurize_goal(statement, preamble)
    seqs.sort(key=lambda x: (-value_function.score(gfeats, x[1], vmodel), x[0]))

    # Layer 3.4: library-have RECOMBINATION (inline a harvested lemma as a `have`,
    # then discharge the goal with it). These were previously appended to `seqs` at
    # the very end, so the closing candidate landed past the node budget and a
    # harvested lemma never actually got used — the library compounded efficiency
    # but not REACH. They are high-value (a harvested lemma is often the missing
    # premise), so they go near the FRONT, under simple prefixes, with a finisher
    # set that also unfolds the goal's defs so a wrapper-def goal can use the lemma.
    have_fins = lambda hint: ([f"exact {hint}", f"simp [{hint}]", "simp_all",
                               f"simp [{hint}]; omega", "omega"]
                              + ([f"simp [{', '.join(idents)}, {hint}]"] if idents else []))
    have_bodies: list[str] = []
    for prefix in ("", "intro n", "intro m n", "intro a b c", "intro n h"):
        for hv, hint in haves:
            for fin in have_fins(hint):
                parts = [p for p in (prefix, hv, fin) if p]
                have_bodies.append("by " + "; ".join(parts))
    # Try cheap atomic finishers, then real induction proofs, then the compound
    # cross-product. Induction is early so a ∀-Nat goal that needs it is reached
    # within the node budget instead of being crowded out.
    cheap = ["by rfl", "by simp", "by omega", "by decide", "by simp_all", "by norm_num"]
    # High-value, cheap-to-check, kernel-gated: cross-run library proofs (whole
    # proofs reused verbatim) and direct atlas-premise applications. Placed before
    # the heavy induction/compound cross-product so a reachable goal closes early
    # within the node budget (this is the Layer-3.2 reach fix for the deep search).
    lib_bodies = [p if p.startswith(("by ", "fun ")) else f"by exact {p}" for p in (lib_proofs or [])]
    prem_direct = [f"by exact {p}" for p in premises] + [f"by simp [{p}]" for p in premises]
    # Order: verbatim library reuse + cheap atomics + direct atlas premises, then the
    # cheap-and-high-value induction route, then library-have RECOMBINATION, then the
    # large compound cross-product. have_bodies sit AFTER induction (so a recursive
    # goal still closes by induction within budget) but FAR BEFORE the old position
    # (index ~1400, past the budget) so a harvested lemma is actually reachable.
    # Phase 1: generalization (two-level) proofs after the cheap one-level induction
    # route — they cross the generalization barrier the one-level route cannot, and
    # are bounded so they fit the node budget.
    gen_cands = generalization_candidates(statement, preamble)
    ordered = (lib_bodies + cheap + prem_direct
               + induction_candidates(statement, preamble)
               + structural_induction_candidates(statement, preamble)
               + gen_cands + have_bodies + [s for _, s in seqs])
    seen: set[str] = set()
    return [s for s in ordered if not (s in seen or seen.add(s))]


def _error_class(reason: str | None) -> str | None:
    r = (reason or "").lower()
    if not r:
        return None
    if any(s in r for s in ("unknown tactic", "unknown identifier", "unknown constant")):
        return "unknown_symbol"
    if "unsolved goals" in r:
        return "unsolved_goals"
    if "type mismatch" in r:
        return "type_mismatch"
    if "timeout" in r or "deterministic" in r:
        return "timeout"
    return "other"


def search(statement: str, preamble: str, lake_dir: Path | None, policy: dict | None,
           library: Path | None, max_nodes: int, workers: int, name: str = "obligation") -> dict[str, Any]:
    premises, lib_proofs = premise_pool(statement, library)
    base_cands = candidates(statement, preamble, policy, library, premises, lib_proofs)
    # Self-contained helper-lemma induction route (fallback), appended within budget.
    hcands = helper_induction_candidates(statement, preamble)
    cands = (base_cands + [h for h in hcands if h not in base_cands])[:max_nodes]
    recdefs = recursive_defs(preamble)
    helpers = helper_lemmas(preamble)
    trace: dict[str, Any] = {
        "recursive_defs_detected": [d["name"] for d in recdefs],
        "induction_candidates_generated": sum(1 for c in cands if "induction" in c),
        "generalization_candidates_generated": sum(1 for c in cands if "hgen" in c),
        "structural_induction_candidates_generated": sum(1 for c in cands if "| nil =>" in c or "| none =>" in c),
        "value_model_trained_on": value_function.load_model(library).get("trained_on", 0),
        "helper_lemmas_generated": [h["statement"] for h in helpers],
        "atlas_premises": premises,
        "library_proofs_reused": len(lib_proofs),
        "candidates_tried": len(cands),
        "last_error_class": None,
        "strategy": None,
    }

    def make(proof: str):
        def run():
            src = (f"{preamble}\n" if preamble else "") + (
                f"namespace WitsocObligation\ntheorem {name} : {statement} := {proof}\nend WitsocObligation\n")
            v = witcore.lean_verify_cached(src, lake_dir)
            return {"proof": proof, **v}
        return run

    def discharged_result(proof: str, nodes: int) -> dict[str, Any]:
        if "hgen" in proof:
            trace["strategy"] = "generalization"  # two-level: generalized aux lemma + specialize
        elif "hlib" in proof:
            trace["strategy"] = "library_reuse"  # a harvested lemma used as a premise
        elif "induction" in proof:
            trace["strategy"] = "induction"
        elif any(p in proof for p in premises):
            trace["strategy"] = "atlas_premise"
        else:
            trace["strategy"] = "compound"
        return {"discharged": True, "proof": proof, "label": "PROOF_DISCHARGED", "nodes": nodes, "trace": trace}

    # probe toolchain on the first candidate
    if cands:
        probe = make(cands[0])()
        if not probe.get("checked"):
            return {"discharged": False, "label": "UNCHECKED_NO_TOOLCHAIN",
                    "reason": probe.get("reason"), "nodes": 1, "trace": trace}
        if probe.get("verified"):
            return discharged_result(cands[0], 1)
        trace["last_error_class"] = _error_class(probe.get("reason"))

    # Race ALL candidates through one pipelined pool with early-exit (see witcore).
    first = witcore.parallel_first([make(p) for p in cands[1:]],
                                   accept=lambda r: bool(r.get("verified")), max_workers=workers)
    if first and first.get("verified"):
        # Report the ORDINAL DEPTH of the winning candidate in the priority order,
        # not the pool size: a meaningful efficiency signal (how far down the ranked
        # candidates the working proof was) that rewards good ordering, instead of
        # always reporting the (capped) candidate count.
        try:
            depth = cands.index(first["proof"]) + 1
        except ValueError:
            depth = len(cands)
        return discharged_result(first["proof"], depth)
    return {"discharged": False, "label": "OBLIGATION_OPEN", "nodes": len(cands), "trace": trace}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lean-statement", required=True)
    ap.add_argument("--imports", default="", help="preamble (defs) prepended before the theorem")
    ap.add_argument("--name", default="obligation")
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--policy", default=None)
    ap.add_argument("--library", type=Path, default=None)
    ap.add_argument("--max-nodes", type=int, default=300)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    policy = witcore.load_json(Path(args.policy), None) if args.policy and not args.policy.startswith("cmd:") else None
    lib = args.library or (witcore.global_library() if witcore.global_library().exists() else None)
    result = search(args.lean_statement, args.imports, args.lake_dir, policy, lib,
                    args.max_nodes, args.workers, args.name)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("discharged") else 1


if __name__ == "__main__":
    raise SystemExit(main())
