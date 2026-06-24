#!/usr/bin/env python3
"""A3 Nexus loop — `witsoc nexus`.

The architecture that just solved open Erdős problems (AlphaProof Nexus,
2026) is an LLM-generates / Lean-verifies loop where COMPILER FEEDBACK is the
grounding signal: the model's proposal goes to the kernel, the kernel's exact
error goes back to the model, repeat. Lovasz had every piece of this except
the loop itself — fleet proposals were judged once and never saw a Lean
error. This module closes that gap:

  iterate_goal(sampler, request, rounds)
      one sampler iterates a (lean_statement, proof) proposal against real
      compiler diagnostics for up to `rounds` rounds; every accepted result
      is REPLAYED through the kernel (the sampler is never trusted);

  fleet_prove(goal, theory, rounds, per_sampler)
      the whole fleet races compiler-feedback loops on one goal, after the
      deterministic prover (close_goal) gets first shot — the AlphaGeometry
      split: saturate deterministically, spend the model only on what
      survives;

  fleet_formalize(statement, theory, rounds)
      the same loop for STATEMENT formalization: propose Lean for an informal
      node, fix until it elaborates (proof `sorry` allowed for elaboration
      probing ONLY — the result is a formalized OPEN node, never evidence).

Every request embeds the problem theory (problem_theory.prompt_context) plus
prior rounds — rich prompts beat blind search. Trust contract: the only
upgrade path is the kernel replay; sampler output is OPEN_UNFALSIFIED until
the kernel says otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import sampler_fleet as sf  # noqa: E402
import witcore  # noqa: E402

DEFAULT_ROUNDS = 4
FORBIDDEN = ("sorry", "admit", "axiom ", "native_decide")


def _lean_source(name: str, statement: str, imports: str, proof: str) -> str:
    import close_obligation as co
    return co.lean_source(name, statement, imports, proof)


def _verify(name: str, statement: str, imports: str, proof: str, lake_dir: Path | None) -> dict:
    return witcore.lean_verify_cached(_lean_source(name, statement, imports, proof), lake_dir)


def _diagnostics(name: str, statement: str, imports: str, proof: str, lake_dir: Path | None) -> str:
    """Uncached probe build to capture full compiler output for feedback."""
    src = _lean_source(name, statement, imports, proof)
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as fh:
        fh.write(src)
        tmp = Path(fh.name)
    try:
        verdict = witcore.lean_verify(tmp, lake_dir)
    finally:
        tmp.unlink(missing_ok=True)
    build = verdict.get("build", {}) or {}
    return (str(build.get("stdout", "")) + "\n" + str(build.get("stderr", ""))).strip()[:1500]


def iterate_goal(sampler: dict, goal: str, imports: str, theory: dict | None,
                 rounds: int, lake_dir: Path | None, name: str = "nexus") -> dict:
    """One sampler, one goal, up to `rounds` compiler-feedback rounds.
    Returns {discharged, proof?, rounds_used, trace} — proof only if the
    kernel replay verifies it."""
    trace: list[dict] = []
    diagnostics = ""
    last_proof = ""
    # Ω6: few-shot examples from the proof bank (signature-similar verified
    # pairs) join every prove prompt — the expert-iteration surface.
    try:
        import proof_bank
        examples = proof_bank.examples_for(goal, k=3)
    except Exception:
        examples = []
    for rnd in range(1, rounds + 1):
        request: dict[str, Any] = {
            "task": "prove_goal",
            "lean_statement": goal,
            "imports": imports,
            "round": rnd,
            "problem_theory": theory or {},
            "verified_examples": examples,
            "previous_attempt": last_proof,
            "compiler_diagnostics": diagnostics,
            "rules": "Return {proof: \"by ...\"} — a complete Lean 4 tactic proof of exactly this "
                     "statement. Use the compiler diagnostics to fix the previous attempt. "
                     "Never sorry/admit/axiom.",
        }
        reply = witcore.run_sampler(sampler["command"], request)
        proof = str((reply or {}).get("proof") or "").strip()
        if not proof or any(t in proof for t in FORBIDDEN):
            trace.append({"round": rnd, "outcome": "no_clean_proposal"})
            break
        if not proof.startswith("by"):
            proof = "by " + proof
        last_proof = proof
        verdict = _verify(name, goal, imports, proof, lake_dir)
        if verdict.get("verified"):
            trace.append({"round": rnd, "outcome": "kernel_verified"})
            try:
                import proof_bank
                proof_bank.bank(goal, proof, imports, lake_dir)  # Ω6: simplify + bank
            except Exception:
                pass
            return {"discharged": True, "proof": proof, "sampler_id": sampler["id"],
                    "rounds_used": rnd, "trace": trace}
        if not verdict.get("checked"):
            trace.append({"round": rnd, "outcome": "no_toolchain"})
            break
        diagnostics = verdict.get("diagnostics") or _diagnostics(name, goal, imports, proof, lake_dir)
        trace.append({"round": rnd, "outcome": "rejected", "diagnostic_excerpt": diagnostics[:200]})
    return {"discharged": False, "proof": None, "sampler_id": sampler["id"],
            "rounds_used": len(trace), "trace": trace}


def fleet_prove(goal: str, *, imports: str = "", theory: dict | None = None,
                rounds: int = DEFAULT_ROUNDS, lake_dir: Path | None = None,
                deterministic_first: bool = True, search: bool = False,
                name: str = "nexus") -> dict:
    """The Nexus engine for one goal: deterministic saturation first (the
    model is spent only on what survives), then every fleet sampler runs its
    own compiler-feedback loop. First kernel-verified proof wins."""
    if deterministic_first:
        try:
            import close_obligation as co
            det = co.close_goal(goal, name=name, imports=imports, search=search,
                                lake_dir=lake_dir)
            if det.get("discharged"):
                return {"discharged": True, "proof": det["proof"], "via": "deterministic",
                        "label": det.get("label"), "fleet_rounds": 0}
        except Exception:
            pass
    fleet = sf.samplers()
    if not fleet:
        return {"discharged": False, "proof": None, "via": "none",
                "reason": "deterministic prover missed and no sampler fleet is configured"}
    attempts = []
    for sampler in fleet:
        result = iterate_goal(sampler, goal, imports, theory, rounds, lake_dir, name)
        attempts.append({k: result[k] for k in ("sampler_id", "discharged", "rounds_used")})
        if result["discharged"]:
            return {"discharged": True, "proof": result["proof"], "via": f"fleet:{result['sampler_id']}",
                    "fleet_rounds": result["rounds_used"], "attempts": attempts}
    return {"discharged": False, "proof": None, "via": "fleet_exhausted", "attempts": attempts}


def fleet_formalize(statement: str, *, theory: dict | None = None,
                    rounds: int = DEFAULT_ROUNDS, imports: str = "",
                    lake_dir: Path | None = None) -> dict:
    """Compiler-feedback formalization of an INFORMAL statement: the fleet
    proposes a Lean statement, the elaboration probe (`example : <stmt> :=
    sorry` — sorry used ONLY to test elaboration, stripped afterwards) feeds
    errors back until the statement elaborates. Output is a formalized OPEN
    node; faithfulness remains the caller's gate."""
    fleet = sf.samplers()
    if not fleet:
        return {"formalized": False, "reason": "no sampler fleet configured"}
    for sampler in fleet:
        diagnostics = ""
        last = ""
        for rnd in range(1, rounds + 1):
            reply = witcore.run_sampler(sampler["command"], {
                "task": "formalize_statement", "statement": statement, "round": rnd,
                "problem_theory": theory or {}, "previous_attempt": last,
                "compiler_diagnostics": diagnostics,
                "rules": "Return {lean_statement: \"...\"} — a faithful Lean 4 Prop for the statement. "
                         "Fix elaboration errors from the diagnostics. Change nothing mathematical.",
            })
            lean = str((reply or {}).get("lean_statement") or "").strip()
            if not lean or any(t in lean for t in FORBIDDEN):
                break
            last = lean
            probe_src = (f"{imports}\n" if imports else "") + f"example : {lean} := sorry\n"
            verdict = witcore.lean_verify_cached(probe_src, lake_dir)
            if not verdict.get("checked"):
                return {"formalized": False, "reason": "no toolchain"}
            # elaboration succeeds iff the only complaint is the sorry itself
            diag = str(verdict.get("diagnostics") or "")
            build_failed = not verdict.get("verified") and ("error" in diag.lower())
            if not build_failed:
                return {"formalized": True, "lean_statement": lean, "sampler_id": sampler["id"],
                        "rounds_used": rnd,
                        "note": "elaborates; node stays OPEN — faithfulness is the caller's gate"}
            diagnostics = diag[:1500]
    return {"formalized": False, "reason": "fleet exhausted without an elaborating statement"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_prove = sub.add_parser("prove")
    p_prove.add_argument("--lean-statement", required=True)
    p_prove.add_argument("--imports", default="")
    p_prove.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    p_prove.add_argument("--search", action="store_true")
    p_prove.add_argument("--run-dir", type=Path, default=None, help="embed this run's problem theory")
    p_form = sub.add_parser("formalize")
    p_form.add_argument("--statement", required=True)
    p_form.add_argument("--imports", default="")
    p_form.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    p_form.add_argument("--run-dir", type=Path, default=None)
    args = ap.parse_args()

    theory = None
    if args.run_dir is not None:
        try:
            import problem_theory as pt
            if pt.theory_path(args.run_dir).exists():
                theory = pt.prompt_context(args.run_dir)
        except Exception:
            theory = None

    if args.cmd == "prove":
        result = fleet_prove(args.lean_statement, imports=args.imports, theory=theory,
                             rounds=args.rounds, search=args.search)
    else:
        result = fleet_formalize(args.statement, theory=theory, rounds=args.rounds,
                                 imports=args.imports)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("discharged") or result.get("formalized") else 1


if __name__ == "__main__":
    raise SystemExit(main())
