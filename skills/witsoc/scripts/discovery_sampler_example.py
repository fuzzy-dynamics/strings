#!/usr/bin/env python3
"""Reference implementation of the discovery-engine external sampler protocol.

This is the LLM-as-mutation-operator plug point. The discovery engine runs it as

    python3 discovery_engine.py run <run> --sampler 'cmd:python3 discovery_sampler_example.py'

and for each island writes a JSON request to this process's stdin:

    {"problem": "<natural language>", "params": {...}, "objective": "maximize",
     "parents": [{"object": ..., "score": ..., "size": ...}], "n_requested": K,
     "instructions": "..."}

The sampler must write a JSON reply to stdout, either:

    {"candidates": [<object>, ...]}                 # objects in the parents' format
or  {"program": "<python defining build(params)->object>"}

The engine then scores every returned candidate with the HARD evaluator and keeps
only validity-preserving improvements, so a bad reply can never corrupt the run.

To wire a real model: send `problem`, `instructions`, and `parents` to your LLM
(e.g. the OpenScientist LLM proxy), ask it to return improved objects in the same
format, and print {"candidates": [...]}. The stand-in below uses the evaluator's
own local-search operators instead of a model, purely so the protocol is runnable
and testable offline.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discovery_evaluators import EVALUATORS  # noqa: E402


def evaluator_for(problem: str, params: dict):
    # Match the problem text to a known evaluator (a real LLM would not need this;
    # it would reason from `problem` directly).
    for name, ev in EVALUATORS.items():
        if name.replace("_", " ") in problem.lower() or name in problem.lower():
            return ev
    # crude keyword fallback
    if "cap set" in problem.lower():
        return EVALUATORS["cap_set"]
    if "arithmetic progression" in problem.lower():
        return EVALUATORS["no_three_ap"]
    if "sidon" in problem.lower():
        return EVALUATORS["sidon_set"]
    if "triangle-free" in problem.lower():
        return EVALUATORS["triangle_free_chromatic"]
    return None


def main() -> int:
    request = json.loads(sys.stdin.read())
    params = request.get("params", {})
    parents = request.get("parents", [])
    n = max(1, int(request.get("n_requested", 4)))
    ev = evaluator_for(request.get("problem", ""), params)
    if ev is None or not parents:
        print(json.dumps({"candidates": []}))
        return 0

    rng = random.Random(hash(json.dumps(parents, sort_keys=True)) & 0xFFFFFFFF)
    candidates = []
    for _ in range(n):
        parent = max(parents, key=lambda p: p["score"])["object"]
        # STAND-IN for an LLM: a local-search neighbour. Replace with a model call.
        candidates.append(ev.mutate(parent, params, rng))
    print(json.dumps({"candidates": candidates}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
