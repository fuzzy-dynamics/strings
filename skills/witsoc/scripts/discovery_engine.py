#!/usr/bin/env python3
"""Witsoc discovery engine: island-model evolutionary program/object search.

This is a FunSearch / AlphaEvolve style loop. The shape is:

    propose candidate object  ->  HARD deterministic evaluator scores it
           ^                                       |
           |                                       v
    sampler (LLM or built-in operators)  <--  island-model selection

The only judge of a candidate is `discovery_evaluators` (exact, deterministic,
no LLM). Generation is cheap and untrusted; the evaluator is the moat. The
engine keeps a population spread across islands, periodically resets the weakest
islands from the global best to preserve diversity, and checkpoints every
generation so a long campaign can be resumed (Temporal-friendly).

Two samplers:

  builtin        : domain operators from the evaluator (mutate/crossover/seed).
                   Fully offline and deterministic given --seed. Use for
                   autonomous runs, CI, and as a strong baseline.

  cmd:<command>  : an external sampler (the LLM-as-mutation-operator plug point).
                   The engine writes a JSON request to the command's stdin:
                     {"problem", "params", "objective", "parents":[{object,score,size}],
                      "n_requested", "instructions"}
                   and reads JSON from stdout:
                     {"candidates": [<object>, ...]}        (objects directly), or
                     {"program": "<python defining build(params)->object>"}
                   Any malformed / invalid candidate is silently dropped by the
                   evaluator gate, so a bad LLM turn can never corrupt the run.

CLI:
  discovery_engine.py init  <run_dir> --evaluator no_three_ap --params '{"n":80}' [--islands 6 --capacity 12 --seed 0]
  discovery_engine.py run   <run_dir> --generations 200 [--sampler builtin | --sampler 'cmd:python3 my_llm_sampler.py'] [--time-budget 60]
  discovery_engine.py status <run_dir>
  discovery_engine.py best  <run_dir> [--write best.json]
  discovery_engine.py list-evaluators
"""

from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discovery_evaluators import EVALUATORS, get_evaluator  # noqa: E402

CHECKPOINT = "discovery_run.json"
SCHEMA = "witsoc.discovery_run.v1"


# ---------------------------------------------------------------------------
# Checkpoint I/O
# ---------------------------------------------------------------------------
def run_path(run_dir: Path) -> Path:
    return run_dir / CHECKPOINT


def load_run(run_dir: Path) -> dict[str, Any]:
    path = run_path(run_dir)
    if not path.exists():
        raise SystemExit(f"no discovery run at {path}; run `init` first")
    return json.loads(path.read_text(encoding="utf-8"))


def save_run(run_dir: Path, state: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    run_path(run_dir).write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Selection helpers
# ---------------------------------------------------------------------------
def signature(member: dict[str, Any]) -> str:
    """A coarse score bucket; members with equal score compete on length."""
    return f"{member['score']:.4f}"


def boltzmann_pick(members: list[dict[str, Any]], rng: random.Random, temperature: float) -> dict[str, Any]:
    """Pick a member with probability rising in score (FunSearch-style)."""
    if not members:
        raise ValueError("empty island")
    best = max(m["score"] for m in members)
    weights = [math.exp((m["score"] - best) / max(temperature, 1e-9)) for m in members]
    total = sum(weights)
    r = rng.random() * total
    upto = 0.0
    for m, w in zip(members, weights):
        upto += w
        if upto >= r:
            return m
    return members[-1]


def insert_member(island: list[dict[str, Any]], member: dict[str, Any], capacity: int) -> bool:
    """Insert a candidate into an island, dedup by object, cap by score then short length.

    Returns True if the island changed.
    """
    key = json.dumps(member["object"], sort_keys=True)
    for existing in island:
        if json.dumps(existing["object"], sort_keys=True) == key:
            return False
    island.append(member)
    # Keep the strongest `capacity`: higher score first, then smaller object.
    island.sort(key=lambda m: (-m["score"], m["size"]))
    if len(island) > capacity:
        del island[capacity:]
    return member in island


# ---------------------------------------------------------------------------
# External (LLM) sampler bridge
# ---------------------------------------------------------------------------
def run_program_to_object(program: str, params: dict, timeout: float) -> Any:
    """Execute an LLM-proposed program defining build(params)->object in a subprocess."""
    harness = (
        "import json,sys\n"
        "ns={}\n"
        "exec(compile(sys.stdin.read(), '<candidate>', 'exec'), ns)\n"
        "params=json.loads(sys.argv[1])\n"
        "print(json.dumps(ns['build'](params)))\n"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", harness, json.dumps(params)],
            input=program, text=True, capture_output=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    if completed.returncode != 0:
        return None
    try:
        return json.loads(completed.stdout.strip().splitlines()[-1])
    except Exception:
        return None


def external_sampler(command: str, request: dict, timeout: float) -> list[Any]:
    try:
        completed = subprocess.run(
            command, shell=True, input=json.dumps(request), text=True,
            capture_output=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return []
    if completed.returncode != 0:
        return []
    try:
        reply = json.loads(completed.stdout)
    except Exception:
        return []
    if isinstance(reply.get("candidates"), list):
        return reply["candidates"]
    if isinstance(reply.get("program"), str):
        obj = run_program_to_object(reply["program"], request["params"], timeout)
        return [obj] if obj is not None else []
    return []


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------
def cmd_init(args: argparse.Namespace) -> int:
    ev = get_evaluator(args.evaluator)
    params = json.loads(args.params)
    rng = random.Random(args.seed)
    islands: list[list[dict[str, Any]]] = [[] for _ in range(args.islands)]
    best: dict[str, Any] | None = None
    for i in range(args.islands):
        # Seed each island with a few independent greedy starts.
        for _ in range(max(1, args.seeds_per_island)):
            obj = ev.seed(params, rng)
            ev_res = ev.evaluate(obj, params)
            if not ev_res["valid"]:
                continue
            member = {"object": obj, "score": ev_res["score"], "size": ev_res["size"]}
            insert_member(islands[i], member, args.capacity)
            if best is None or member["score"] > best["score"]:
                best = {**member, "certificate": ev_res["certificate"], "generation": 0}
    state = {
        "schema": SCHEMA,
        "evaluator": args.evaluator,
        "params": params,
        "objective": ev.objective,
        "problem": ev.describe(params),
        "config": {
            "islands": args.islands,
            "capacity": args.capacity,
            "offspring_per_island": args.offspring,
            "temperature": args.temperature,
            "reset_period": args.reset_period,
            "reset_fraction": args.reset_fraction,
            "crossover_rate": args.crossover_rate,
            "migrate_period": args.migrate_period,
            "patience": args.patience,
        },
        "seed": args.seed,
        "generation": 0,
        "islands": islands,
        "best": best,
        "history": [] if best is None else [{"generation": 0, "best_score": best["score"], "best_size": best["size"]}],
        "stagnation": 0,
        "telemetry": {"candidates_evaluated": 0, "candidates_valid": 0, "candidates_invalid": 0,
                      "improvements": 0, "migrations": 0, "stagnation_restarts": 0},
        "rng_state": _dump_rng(rng),
    }
    save_run(args.run_dir, state)
    print(json.dumps({
        "status": "initialized",
        "evaluator": args.evaluator,
        "best_score": None if best is None else best["score"],
        "run": str(run_path(args.run_dir)),
    }, indent=2))
    return 0


def _dump_rng(rng: random.Random) -> Any:
    state = rng.getstate()
    return [state[0], list(state[1]), state[2]]


def _load_rng(blob: Any) -> random.Random:
    rng = random.Random()
    rng.setstate((blob[0], tuple(blob[1]), blob[2]))
    return rng


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
def cmd_run(args: argparse.Namespace) -> int:
    state = load_run(args.run_dir)
    ev = get_evaluator(state["evaluator"])
    params = state["params"]
    cfg = state["config"]
    rng = _load_rng(state["rng_state"])
    islands: list[list[dict[str, Any]]] = state["islands"]
    best = state["best"]
    # Backward-compatible defaults for checkpoints written before these fields existed.
    cfg.setdefault("migrate_period", 8)
    cfg.setdefault("patience", 40)
    stagnation = state.get("stagnation", 0)
    telemetry = state.setdefault("telemetry", {
        "candidates_evaluated": 0, "candidates_valid": 0, "candidates_invalid": 0,
        "improvements": 0, "migrations": 0, "stagnation_restarts": 0})

    sampler = args.sampler or "builtin"
    use_external = sampler.startswith("cmd:")
    command = sampler[4:] if use_external else ""

    deadline = time.monotonic() + args.time_budget if args.time_budget > 0 else None
    start_gen = state["generation"]
    target_gen = start_gen + args.generations
    improved = 0

    for gen in range(start_gen + 1, target_gen + 1):
        if deadline is not None and time.monotonic() > deadline:
            break
        # Adaptive temperature: as stagnation grows, widen Boltzmann selection so
        # the search escapes the basin it is stuck in. Clamped to 4x the base.
        patience = max(1, int(cfg["patience"]))
        eff_temp = cfg["temperature"] * min(4.0, 1.0 + stagnation / patience)
        gen_improved_before = improved
        for idx, island in enumerate(islands):
            if not island:
                # reseed an empty island from a fresh greedy start
                obj = ev.seed(params, rng)
                res = ev.evaluate(obj, params)
                if res["valid"]:
                    insert_member(island, {"object": obj, "score": res["score"], "size": res["size"]}, cfg["capacity"])
                continue

            candidates: list[Any] = []
            if use_external:
                parents = sorted(island, key=lambda m: -m["score"])[: max(1, args.parents)]
                request = {
                    "problem": state["problem"],
                    "params": params,
                    "objective": state["objective"],
                    "parents": [{"object": p["object"], "score": p["score"], "size": p["size"]} for p in parents],
                    "n_requested": cfg["offspring_per_island"],
                    "instructions": (
                        "Return improved candidate objects in the SAME canonical "
                        "format as the parents. Only validity-preserving, higher-"
                        "scoring objects help; invalid ones are discarded."
                    ),
                }
                candidates = external_sampler(command, request, args.sampler_timeout)
            else:
                for _ in range(cfg["offspring_per_island"]):
                    parent = boltzmann_pick(island, rng, eff_temp)
                    if len(island) >= 2 and rng.random() < cfg["crossover_rate"]:
                        mate = boltzmann_pick(island, rng, eff_temp)
                        candidates.append(ev.crossover(parent["object"], mate["object"], params, rng))
                    else:
                        candidates.append(ev.mutate(parent["object"], params, rng))

            for obj in candidates:
                telemetry["candidates_evaluated"] += 1
                res = ev.evaluate(obj, params)
                if not res["valid"]:
                    telemetry["candidates_invalid"] += 1
                    continue
                telemetry["candidates_valid"] += 1
                member = {"object": obj, "score": res["score"], "size": res["size"]}
                insert_member(island, member, cfg["capacity"])
                if best is None or member["score"] > best["score"]:
                    best = {**member, "certificate": res["certificate"], "generation": gen}
                    improved += 1
                    telemetry["improvements"] += 1

        # Migration ring: seed island i+1 with island i's champion so a strong
        # gene discovered on one island can propagate, while reset/restart keep
        # diversity. Dedup in insert_member prevents collapse to one genotype.
        if cfg["migrate_period"] and gen % cfg["migrate_period"] == 0 and len(islands) > 1:
            champions = [max(isl, key=lambda m: m["score"]) if isl else None for isl in islands]
            for i, champ in enumerate(champions):
                if champ is None:
                    continue
                dst = (i + 1) % len(islands)
                if insert_member(islands[dst], {"object": champ["object"], "score": champ["score"],
                                                "size": champ["size"]}, cfg["capacity"]):
                    telemetry["migrations"] += 1

        # Stagnation restart: if the global best has not improved for `patience`
        # generations, inject FRESH random greedy starts (not mutations of best)
        # into the weakest islands — exploration to escape a stuck basin. This is
        # distinct from the periodic reset below, which exploits the best.
        if best is not None and stagnation >= patience:
            strengths = sorted(range(len(islands)),
                               key=lambda i: max((m["score"] for m in islands[i]), default=float("-inf")))
            n_fresh = max(1, int(len(islands) * cfg["reset_fraction"]))
            for i in strengths[:n_fresh]:
                islands[i] = []
                for _ in range(max(1, args.seeds_per_island)):
                    obj = ev.seed(params, rng)
                    res = ev.evaluate(obj, params)
                    if res["valid"]:
                        insert_member(islands[i], {"object": obj, "score": res["score"], "size": res["size"]}, cfg["capacity"])
            telemetry["stagnation_restarts"] += 1
            stagnation = 0

        # Periodic island reset: kill the weakest half, reseed from global best.
        if cfg["reset_period"] and gen % cfg["reset_period"] == 0 and best is not None:
            strengths = [(max((m["score"] for m in isl), default=float("-inf")), i) for i, isl in enumerate(islands)]
            strengths.sort()
            n_reset = max(1, int(len(islands) * cfg["reset_fraction"]))
            for _, i in strengths[:n_reset]:
                islands[i] = []
                base = best["object"]
                for _ in range(max(1, args.seeds_per_island)):
                    obj = ev.mutate(base, params, rng)
                    res = ev.evaluate(obj, params)
                    if res["valid"]:
                        insert_member(islands[i], {"object": obj, "score": res["score"], "size": res["size"]}, cfg["capacity"])

        # Track stagnation: a generation with no new global best increments it.
        stagnation = 0 if improved > gen_improved_before else stagnation + 1

        state["history"].append({"generation": gen, "best_score": None if best is None else best["score"],
                                  "best_size": None if best is None else best["size"],
                                  "stagnation": stagnation})
        state["generation"] = gen
        state["islands"] = islands
        state["best"] = best
        state["stagnation"] = stagnation
        state["telemetry"] = telemetry
        state["rng_state"] = _dump_rng(rng)
        if gen % max(1, args.checkpoint_every) == 0 or gen == target_gen:
            save_run(args.run_dir, state)

    save_run(args.run_dir, state)
    valid = telemetry["candidates_valid"]
    evaluated = telemetry["candidates_evaluated"]
    print(json.dumps({
        "status": "ran",
        "generation": state["generation"],
        "improvements_this_call": improved,
        "best_score": None if best is None else best["score"],
        "best_size": None if best is None else best["size"],
        "stagnation": stagnation,
        "acceptance_rate": round(valid / evaluated, 4) if evaluated else None,
        "telemetry": telemetry,
        "sampler": "external" if use_external else "builtin",
    }, indent=2))
    return 0


# ---------------------------------------------------------------------------
# status / best
# ---------------------------------------------------------------------------
def cmd_status(args: argparse.Namespace) -> int:
    state = load_run(args.run_dir)
    best = state.get("best")
    telemetry = state.get("telemetry", {})
    evaluated = telemetry.get("candidates_evaluated", 0)
    print(json.dumps({
        "evaluator": state["evaluator"],
        "params": state["params"],
        "generation": state["generation"],
        "best_score": None if not best else best["score"],
        "best_size": None if not best else best["size"],
        "stagnation": state.get("stagnation", 0),
        "acceptance_rate": round(telemetry.get("candidates_valid", 0) / evaluated, 4) if evaluated else None,
        "telemetry": telemetry,
        "island_sizes": [len(isl) for isl in state["islands"]],
        "island_best": [max((m["score"] for m in isl), default=None) for isl in state["islands"]],
    }, indent=2))
    return 0


def cmd_best(args: argparse.Namespace) -> int:
    state = load_run(args.run_dir)
    ev = get_evaluator(state["evaluator"])
    best = state.get("best")
    if not best:
        print(json.dumps({"status": "no_result"}, indent=2))
        return 1
    # Re-run the INDEPENDENT verifier so the emitted certificate is self-checking.
    verify = ev.verify(best["object"], state["params"])
    payload = {
        "schema": "witsoc.discovery_best.v1",
        "evaluator": state["evaluator"],
        "params": state["params"],
        "problem": state["problem"],
        "best_score": best["score"],
        "best_size": best["size"],
        "found_at_generation": best.get("generation"),
        "object": best["object"],
        "certificate": best.get("certificate"),
        "independent_verification": verify,
        "claim_status": "CHECKED" if verify.get("ok") else "REJECTED",
        "scope": (
            "Bounded constructive existence witness, exactly verified. This is a "
            "lower bound / counterexample object, NOT an asymptotic or general "
            "proof. Promote to a WIT/Lean artifact for a theorem-level claim."
        ),
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text, encoding="utf-8")

    # Optionally emit a proof-DAG node that plugs straight into the certificate
    # re-check spine: the node carries a `discovery` certificate that
    # recheck_certificates.py re-runs through the evaluator's independent verify.
    if args.emit_dag:
        import hashlib
        obj_hash = hashlib.sha256(json.dumps(best["object"], sort_keys=True).encode()).hexdigest()[:16]
        node = {
            "node_id": f"discovery-{state['evaluator']}-{obj_hash}",
            "status": "CHECKED" if verify.get("ok") else "REJECTED",
            "statement": state["problem"],
            "evidence": f"constructive witness, score {best['score']}, independently verified",
            "target_hash": obj_hash,
            "dependency_path_to_target": "constructive lower-bound / existence witness",
            "dependencies": [],
            "certificate": {"kind": "discovery", "evaluator": state["evaluator"],
                            "params": state["params"], "object": best["object"]},
        }
        if args.review_id:
            node["skeptic_review_id"] = args.review_id
        existing = []
        if args.emit_dag.exists():
            try:
                data = json.loads(args.emit_dag.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    existing = data
            except Exception:
                existing = []
        existing = [n for n in existing if not (isinstance(n, dict) and n.get("node_id") == node["node_id"])]
        existing.append(node)
        args.emit_dag.parent.mkdir(parents=True, exist_ok=True)
        args.emit_dag.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(text, end="")
    return 0 if verify.get("ok") else 2


def cmd_list_evaluators(_: argparse.Namespace) -> int:
    print(json.dumps({name: {"objective": ev.objective, "domain": ev.domain} for name, ev in EVALUATORS.items()}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("run_dir", type=Path)
    p_init.add_argument("--evaluator", required=True)
    p_init.add_argument("--params", default="{}")
    p_init.add_argument("--islands", type=int, default=6)
    p_init.add_argument("--capacity", type=int, default=12)
    p_init.add_argument("--offspring", type=int, default=8)
    p_init.add_argument("--temperature", type=float, default=1.0)
    p_init.add_argument("--reset-period", type=int, default=25)
    p_init.add_argument("--reset-fraction", type=float, default=0.5)
    p_init.add_argument("--crossover-rate", type=float, default=0.3)
    p_init.add_argument("--migrate-period", type=int, default=8,
                        help="every k generations, ring-migrate each island's champion to the next island")
    p_init.add_argument("--patience", type=int, default=40,
                        help="generations with no global-best improvement before a fresh-seed restart")
    p_init.add_argument("--seeds-per-island", type=int, default=2)
    p_init.add_argument("--seed", type=int, default=0)

    p_run = sub.add_parser("run")
    p_run.add_argument("run_dir", type=Path)
    p_run.add_argument("--generations", type=int, default=100)
    p_run.add_argument("--sampler", default="builtin",
                       help="'builtin' or 'cmd:<command>' for an external LLM sampler.")
    p_run.add_argument("--parents", type=int, default=3, help="Parents shown to an external sampler.")
    p_run.add_argument("--sampler-timeout", type=float, default=60.0)
    p_run.add_argument("--time-budget", type=float, default=0.0, help="Wall-clock seconds; 0 disables.")
    p_run.add_argument("--checkpoint-every", type=int, default=10)
    p_run.add_argument("--seeds-per-island", type=int, default=2)

    p_status = sub.add_parser("status")
    p_status.add_argument("run_dir", type=Path)

    p_best = sub.add_parser("best")
    p_best.add_argument("run_dir", type=Path)
    p_best.add_argument("--write", type=Path, default=None)
    p_best.add_argument("--emit-dag", type=Path, default=None,
                        help="append a proof-DAG node with a re-checkable discovery certificate to this JSON file")
    p_best.add_argument("--review-id", default=None,
                        help="skeptic_review_id to attach to the emitted DAG node (for DAG-integrity validation)")

    sub.add_parser("list-evaluators")

    args = parser.parse_args()
    if args.cmd == "init":
        return cmd_init(args)
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "best":
        return cmd_best(args)
    if args.cmd == "list-evaluators":
        return cmd_list_evaluators(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
