#!/usr/bin/env python3
"""A1 problem theory engine — `witsoc theory`.

The missing brain: Lovasz accumulated FACTS (ledgers, failures, certificates)
but never a CAUSAL MODEL of why the problem is hard. The problem theory is
that model — a living, versioned object that compounds understanding across
loops and months, and that every fleet prompt carries (the AlphaEvolve
lesson: rich context with prior attempts beats blind search; the Wiles/
Polymath lesson: accumulated understanding is the primary artifact).

`problem_theory.json` per run:
  formulations      equivalent statements of the target (each a distinct
                    attack surface)
  example_zoo       positive/negative examples and generator commands — the
                    Gowers discipline: know your objects
  enemy_profile     the structure theory of the hypothetical counterexample:
                    constraints it MUST satisfy (each from a proof fragment
                    or refutation), candidates refuted, and the live verdict
                    (Tao: study the enemy until it is constructed or
                    impossible)
  method_failures   per method family: the MECHANISM of failure, not a label
                    ("density increment loses a log factor at step 3", not
                    "genuine_barrier")
  main_attack       the committed strategy, its exact stall point, and since
                    when (the depth spine reads this)
  techniques_tried  atlas/literature imports attempted, with outcomes
  theory_log        one entry per revision: what changed and WHY — a loop
                    that ends with no diff learned nothing, and the driver
                    says so

Statuses/trust: the theory asserts nothing — it is attention machinery; every
mathematical claim inside it carries its evidence pointer or is marked
belief. `prompt_context()` is the compact serialization every fleet request
embeds.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

THEORY_NAME = "problem_theory.json"


def theory_path(run: Path) -> Path:
    return run / THEORY_NAME


def init_theory(run: Path, target: str = "", target_hash: str = "") -> dict:
    if theory_path(run).exists():
        return load_theory(run)
    if not target:
        manifest = witcore.load_json(run / "lovasz_run.json", {})
        if isinstance(manifest, dict):
            target = str(manifest.get("source_target_text") or "")
            target_hash = target_hash or str(manifest.get("target_hash") or "")
    theory = {
        "schema": "witsoc.problem_theory.v1",
        "target": target,
        "target_hash": target_hash,
        "version": 1,
        "formulations": [{"statement": target, "source": "frozen target", "attack_surface": "direct"}] if target else [],
        "example_zoo": {"positive": [], "negative": [], "generators": []},
        "enemy_profile": {
            "constraints": [],  # {property, evidence, since_version}
            "refuted_candidates": [],
            "verdict": "UNCONSTRAINED",
            "note": "study the enemy until it is constructed or impossible",
        },
        "method_failures": {},  # method -> {mechanism, evidence, loops_spent}
        "main_attack": {"strategy": "", "rationale": "", "stall_point": "", "since_version": 1, "breaks": 0},
        "techniques_tried": [],  # {technique, source, outcome}
        "theory_log": [{"version": 1, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "change": "theory initialized", "why": "campaign start"}],
    }
    run.mkdir(parents=True, exist_ok=True)
    witcore.save_json(theory_path(run), theory)
    return theory


def load_theory(run: Path) -> dict:
    data = witcore.load_json(theory_path(run), None)
    if not (isinstance(data, dict) and data.get("schema") == "witsoc.problem_theory.v1"):
        raise SystemExit(f"no problem_theory.json in {run}; run `witsoc theory init` first")
    return data


def update_theory(run: Path, patch: dict, why: str) -> dict:
    """Apply a patch and log the diff. Patch keys (all optional):
    add_formulation, add_positive_example, add_negative_example, add_generator,
    add_enemy_constraint, add_refuted_candidate, set_enemy_verdict,
    set_method_failure {method, mechanism, evidence}, set_main_attack
    {strategy, rationale, stall_point}, add_technique {technique, source,
    outcome}. Every update increments the version and records WHY."""
    theory = load_theory(run)
    changes: list[str] = []

    if patch.get("add_formulation"):
        theory["formulations"].append(patch["add_formulation"])
        changes.append("formulation added")
    for key, bucket in (("add_positive_example", "positive"), ("add_negative_example", "negative"),
                        ("add_generator", "generators")):
        if patch.get(key):
            theory["example_zoo"][bucket].append(patch[key])
            changes.append(f"{bucket} example added")
    if patch.get("add_enemy_constraint"):
        entry = dict(patch["add_enemy_constraint"])
        entry["since_version"] = theory["version"] + 1
        theory["enemy_profile"]["constraints"].append(entry)
        changes.append(f"enemy constraint: {entry.get('property', '?')}")
    if patch.get("add_refuted_candidate"):
        theory["enemy_profile"]["refuted_candidates"].append(patch["add_refuted_candidate"])
        changes.append("enemy candidate refuted")
    if patch.get("set_enemy_verdict"):
        theory["enemy_profile"]["verdict"] = str(patch["set_enemy_verdict"])
        changes.append(f"enemy verdict: {patch['set_enemy_verdict']}")
    if patch.get("set_method_failure"):
        mf = patch["set_method_failure"]
        method = str(mf.get("method") or "unknown")
        prior = theory["method_failures"].get(method, {"loops_spent": 0})
        theory["method_failures"][method] = {
            "mechanism": str(mf.get("mechanism") or prior.get("mechanism") or ""),
            "evidence": str(mf.get("evidence") or prior.get("evidence") or ""),
            "loops_spent": int(prior.get("loops_spent", 0)) + 1,
        }
        changes.append(f"method failure mechanism: {method}")
    if patch.get("set_main_attack"):
        ma = patch["set_main_attack"]
        prior = theory["main_attack"]
        new_strategy = str(ma.get("strategy") or prior.get("strategy") or "")
        strategy_changed = new_strategy != prior.get("strategy")
        # A5 depth spine: `breaks` counts consecutive recorded breaks on the
        # SAME attack (a pivot resets it); the driver recommends a pivot at 3.
        if strategy_changed:
            breaks = 0
            changes.append(f"main attack -> {new_strategy or '?'} (breaks reset)")
        else:
            breaks = int(prior.get("breaks", 0)) + (1 if ma.get("_break") else 0)
            changes.append("main attack break recorded" if ma.get("_break")
                           else "main attack stall point updated")
        merged = {**prior, **{k: v for k, v in ma.items() if not k.startswith("_")}}
        theory["main_attack"] = {
            "strategy": new_strategy,
            "rationale": str(merged.get("rationale") or ""),
            "stall_point": str(merged.get("stall_point") or ""),
            "since_version": (theory["version"] + 1) if strategy_changed else prior.get("since_version", 1),
            "breaks": breaks,
        }
    if patch.get("add_technique"):
        theory["techniques_tried"].append(patch["add_technique"])
        changes.append(f"technique tried: {patch['add_technique'].get('technique', '?')}")

    if not changes:
        return {"updated": False, "version": theory["version"],
                "note": "empty patch — a loop that ends with no theory diff learned nothing"}
    theory["version"] += 1
    theory["theory_log"].append({"version": theory["version"],
                                 "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                 "change": "; ".join(changes), "why": why})
    witcore.save_json(theory_path(run), theory)
    return {"updated": True, "version": theory["version"], "changes": changes}


def prompt_context(run: Path, max_words: int = 700) -> dict:
    """The compact serialization every fleet request embeds (rich prompts beat
    blind search). Bounded so it never dominates a prompt."""
    theory = load_theory(run)
    ctx = {
        "target": theory["target"],
        "formulations": [f.get("statement") for f in theory["formulations"][:4]],
        "enemy_profile": {
            "verdict": theory["enemy_profile"]["verdict"],
            "constraints": [c.get("property") for c in theory["enemy_profile"]["constraints"][:8]],
            "refuted_candidates": len(theory["enemy_profile"]["refuted_candidates"]),
        },
        "method_failures": {m: f.get("mechanism") for m, f in
                            sorted(theory["method_failures"].items(),
                                   key=lambda kv: -kv[1].get("loops_spent", 0))[:6]},
        "main_attack": theory["main_attack"],
        "examples": {"positive": theory["example_zoo"]["positive"][:3],
                     "negative": theory["example_zoo"]["negative"][:3]},
        "techniques_already_tried": [t.get("technique") for t in theory["techniques_tried"][:8]],
        "instruction": ("Build on this theory: respect refuted candidates and recorded failure "
                        "mechanisms; attack the main attack's stall point or justify a pivot."),
    }
    # crude word budget: drop the bulkiest fields until under budget
    for victim in ("examples", "techniques_already_tried", "formulations"):
        if len(json.dumps(ctx)) // 5 <= max_words:
            break
        ctx.pop(victim, None)
    return ctx


def absorb_gap_feedback(run: Path, feedback: dict, loop_label: str) -> dict:
    """Driver hook: turn a loop's gap feedback into theory updates — failure
    MECHANISMS per gap class and a stall-point note. The driver flags loops
    whose absorb produced no diff AND no other update happened."""
    nodes = feedback.get("nodes", {}) if isinstance(feedback, dict) else {}
    if not nodes:
        return {"updated": False, "version": load_theory(run)["version"]}
    patch: dict[str, Any] = {}
    by_class: dict[str, list[str]] = {}
    for nid, g in nodes.items():
        if isinstance(g, dict):
            by_class.setdefault(str(g.get("gap_class") or "unknown"), []).append(str(nid))
    worst = max(by_class.items(), key=lambda kv: len(kv[1]))
    patch["set_method_failure"] = {
        "method": worst[0],
        "mechanism": (f"{len(worst[1])} node(s) blocked as {worst[0]} this loop "
                      f"({', '.join(worst[1][:4])}); proposed mutations recorded in gap_feedback.json"),
        "evidence": "gap_feedback.json",
    }
    patch["set_main_attack"] = {"stall_point": f"{loop_label}: {len(nodes)} open gaps, "
                                               f"dominant class {worst[0]}",
                                "_break": True}
    return update_theory(run, patch, why=f"absorbed gap feedback ({loop_label})")


def insight_score(run: Path) -> dict:
    """Ω10: Tao's 'odorless proof' warning as a metric — grade a campaign by
    what it UNDERSTOOD, not just what it closed. Verified closures matter, but
    so do enemy constraints won, failure mechanisms named, refutations,
    reusable lemmas, and theory revisions. Attention/reporting machinery: the
    score never touches a status."""
    theory = load_theory(run)
    signals = {
        "theory_revisions": theory["version"] - 1,
        "enemy_constraints": len(theory["enemy_profile"]["constraints"]),
        "refuted_candidates": len(theory["enemy_profile"]["refuted_candidates"]),
        "failure_mechanisms_named": len(theory["method_failures"]),
        "examples_in_zoo": (len(theory["example_zoo"]["positive"])
                            + len(theory["example_zoo"]["negative"])),
        "techniques_tried": len(theory["techniques_tried"]),
    }
    try:
        import lemma_pool as lp
        pool = lp.load_pool(run)
        signals["pool_lemmas_proved"] = sum(1 for e in pool["lemmas"].values()
                                            if e["status"] == "PROVED")
        signals["pool_dead_ends_recorded"] = sum(1 for e in pool["lemmas"].values()
                                                 if e["status"] == "INTRACTABLE")
    except Exception:
        pass
    weights = {"theory_revisions": 1.0, "enemy_constraints": 2.0, "refuted_candidates": 2.0,
               "failure_mechanisms_named": 1.5, "examples_in_zoo": 0.5, "techniques_tried": 0.5,
               "pool_lemmas_proved": 2.0, "pool_dead_ends_recorded": 1.0}
    score = round(sum(weights.get(k, 0) * v for k, v in signals.items()), 2)
    return {"schema": "witsoc.insight.v1", "run_dir": str(run), "signals": signals,
            "insight_score": score,
            "note": ("understanding metric, not a trust label: a campaign that closes nothing but "
                     "constrains the enemy and names failure mechanisms still moved the problem")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("run_dir", type=Path)
    p_init.add_argument("--target", default="")
    for name in ("show", "log", "prompt-context", "insight"):
        p = sub.add_parser(name)
        p.add_argument("run_dir", type=Path)
    p_up = sub.add_parser("update")
    p_up.add_argument("run_dir", type=Path)
    p_up.add_argument("--patch-json", required=True, help="patch dict (see update_theory)")
    p_up.add_argument("--why", required=True)
    args = ap.parse_args()

    if args.cmd == "init":
        result: Any = init_theory(args.run_dir, args.target)
        result = {"initialized": True, "version": result["version"], "path": str(theory_path(args.run_dir))}
    elif args.cmd == "show":
        result = load_theory(args.run_dir)
    elif args.cmd == "log":
        result = {"theory_log": load_theory(args.run_dir)["theory_log"]}
    elif args.cmd == "prompt-context":
        result = prompt_context(args.run_dir)
    elif args.cmd == "insight":
        result = insight_score(args.run_dir)
    else:
        result = update_theory(args.run_dir, json.loads(args.patch_json), args.why)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
