# Orchestrator Fit

Witsoc is a mathematics skill for the orchestrator. The orchestrator owns
strategy: fanout, ordering, budget, agent assignment, reframing, when to ask the
user, and when to stop. Witsoc supplies mathematical affordances: route advice,
candidate lanes, barrier diagnostics, validators, evidence standards, progress
state, and report checks.

The intended shape is toolbox plus specialist bench. Witsoc should make many
good moves legible; it should not narrow the orchestrator's creative search
space. Explorer, Lovasz, and Generator are separate specialists that expose
their best local view of the task. The orchestrator is the only component that
composes those views into a global strategy.

## Boundary

Hard Witsoc contracts are limited to claim honesty:

- freeze the target before serious claims;
- do not upgrade a status without named evidence;
- do not treat a known/open-style solve request as complete with only a status
  lookup;
- keep Generator out of truth arbitration;
- make final reports name products, gates, blockers, and remaining gaps.

Everything else is advisory. Candidate lanes, mission menus, default ordering,
worker roles, and next actions are options for the orchestrator to accept,
modify, parallelize, ignore, or replace. If the orchestrator departs from a
Witsoc default, record the reason when it matters for later learning; do not
turn strategic disagreement into a failed gate.

Witsoc should avoid language that says a subskill "must decide the plan" or
"owns the run." Better language is "recommend", "rank", "expose", "score",
"packet", "gate", "candidate", "option", and "tradeoff." Strong language is
reserved for evidence honesty, target preservation, and verifier semantics.

## What Witsoc Should Emit

For nontrivial and deep routes, Witsoc should provide decision support:

- `route_state`: the conservative route and the non-negotiable gates;
- `deep_run_spec`: a menu of candidate lanes, not a fixed plan;
- `ui_state`: target, phase, gates, barriers, gaps, products, bus, next action;
- `report_contract`: sections and evidence expected in the final report;
- validators: commands that check honesty independent of strategy.

The orchestrator may use these artifacts to build prompts, spawn agents, update
progress, or explain the run to the user. Witsoc must not assume a specific
runtime implementation.

## Lazy Activation

Witsoc should be fast and opinionated at the boundary, then lazy behind that
boundary. The orchestrator should normally ask for cheap state first:

```bash
witsoc route "..."
witsoc orchestrator-plan route "..."
witsoc strategy rank-lanes --prompt "..."
witsoc lovasz packet runs/<task>
```

Only after the orchestrator chooses a plan should it activate heavier tools such
as worker dispatch, counterexample search, theorem retrieval, sketch
tournaments, proof search, report generation, or experimental discovery.

This lets the orchestrator decide whether Witsoc is being used as a router, a
strategy advisor, a Lovasz state packet provider, a validator/report gate, or a
full deep-research campaign engine. Use `witsoc commands --tier core`,
`witsoc commands --tier lovasz`, and `witsoc commands --tier heavy` to inspect
the available service tiers. Direct legacy aliases remain valid, but they are
explicit activation of a deeper service.

## Mission Menu, Not Mission Script

Deep-run route metadata should prefer `mission_menu` over an ordered `missions`
list. Each item describes value and risk:

```json
{
  "name": "counterexample-pressure",
  "lane": "disproof",
  "suggested_agent": "worker",
  "value": "Find witnesses, boundary cases, or refuted stronger variants before proof search.",
  "risk": "A negative bounded search is not proof.",
  "expected_outputs": ["counterexample-search.md", "disproof_first.json"],
  "validators": ["validate-open-problem"]
}
```

The orchestrator can run lanes in parallel, reorder them, add new lanes, or
replace them with a better idea. Witsoc's job is to make the tradeoffs and
evidence requirements explicit.

## Useful Lanes

- `statement-freeze`: exact target, variants, definitions, source status, hash.
- `literature-barriers`: best-known results, theorem preconditions, failed
  approaches, source trail.
- `counterexample-pressure`: definition stress, variants, bounded models,
  computational witnesses.
- `barrier-dag`: actual barrier lemmas, dependency paths, open core.
- `formalizable-rungs`: special cases, reductions, conditionals, computations,
  WIT/Lean feasibility.
- `idea-generation`: analogy, conjecture mining, construction search,
  speculative bridge lemmas.
- `prover-dispatch`: kernel-gated attempts on formalizable DAG nodes.
- `skeptic-synthesis`: adversarial review, gap feedback, mutation ledger,
  reportability decision.
- `artifact-package`: WIT/Lean packaging after Explorer authorization.

## Composition Hints

These are defaults, not orders:

- Run counterexample pressure early when definitions or variants are fragile.
- Run literature/barrier scouting in parallel with formalization feasibility on
  named problems.
- Use idea-generation when all current barriers have stale method families.
- Use skeptic review before promoting any product into a report.
- Use artifact packaging only after an accepted narrow product exists.

## UI And Report Fit

The best orchestrator UI can be driven entirely by Witsoc-side artifacts:

- target and route from `witsoc_route_state.json` / `lovasz_run.json`;
- gate progress from `witsoc_run_controller.json`;
- current barrier from `barrier_attacks.json`;
- gap class and next mutation from `gap_feedback.json`;
- selected product from `product_selection.json` / `explorer_return_packet.json`;
- trust status from `witsoc_final_status.json`;
- next action from `witsoc next-step`.

The final report should support the orchestrator's decision-making. It should
state what was learned, what is blocked, what is promising, what is verified,
what must not be claimed, and the best next few moves. It should not pretend the
route taken was the only possible route.
