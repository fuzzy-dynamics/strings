# Interactive Intake And Deep Runs

Use this protocol when a mathematical request is ambiguous, expensive, open-style,
or likely to benefit from a long Lovasz campaign. This file is a Witsoc-side
contract only: do not require changes in the surrounding runtime.

## Principle

Ask only questions that change the route, cost, or truth standard. Do not ask
for permission to follow non-negotiable contracts such as target freezing,
Lovasz dispatch on open-style solve attempts, status discipline, or Generator
authorization.

If an interactive question tool exists, use it. If a deep-run preview form
exists, use it for serious campaigns. If neither exists, ask the same question
in plain text and continue with conservative defaults when the user does not
answer.

## When To Ask

Ask a short structured question when one of these is unclear:

- the exact target statement or variant;
- whether the user wants a quick triage or a serious/deep campaign;
- whether partial progress is acceptable on a likely open problem;
- whether the desired artifact is prose, WIT, Lean, or both;
- which source/variant should be treated as authoritative.

Do not ask when the target is routine, when the next step is a mandatory gate,
or when a deterministic validator already names the repair.

## Default Choices

When the user is unavailable:

- exact statement unclear: freeze the narrowest statement explicitly present and
  record a variant blocker;
- output unclear: produce an honest prose report plus checked artifacts only
  when they already exist;
- likely open and user asked to prove/solve/attack: choose the serious/deep
  Witsoc route and stop only at a gate-backed result or honest blocker;
- partial progress unclear: allow partial/conditional/counterexample products,
  but never call them a solve of the original target.

## Suggested Questions

Target:

```text
Which target should Witsoc freeze?
- Exact statement in prompt (Recommended): Attack only the statement already written.
- Named problem variant: First identify and freeze the standard published variant.
- Artifact target: Focus on generating/checking WIT or Lean for a supplied statement.
```

Depth:

```text
How deep should this run go?
- Serious/deep campaign (Recommended): Run Explorer -> Lovasz -> Explorer with
  barrier ledgers, worker packets, gap feedback, and final gates.
- Quick triage: Freeze/status/source/barrier summary only; not complete for a
  solve request.
- Artifact only: Produce/repair WIT/Lean after Explorer authorization.
```

Endpoint:

```text
What endpoint is useful if the full target stays open?
- Verified partial progress (Recommended): special case, bound, reduction,
  conditional theorem, computation, obstruction, or counterexample.
- Barrier map: exact open core, failed approaches, and next mutation.
- Full solve only: stop honestly if no solve-claim gate can pass.
```

## Deep-Run Preview Contract

For serious or campaign-mode routes, Witsoc route output may include a
`deep_run_spec` object. It is advisory metadata for an existing steerer or
orchestrator UI. If the runtime supports a preview form, present it to the user;
otherwise paste the spec into the final/working note and proceed manually.
The orchestrator may reframe, reorder, parallelize, ignore, or replace any
candidate lane. Only claim-honesty gates are mandatory.

Required shape:

```json
{
  "title": "Witsoc: <short target>",
  "prompt": "<frozen target or intake target>",
  "suggested_duration_minutes": null,
  "orchestrator_authority": "The orchestrator owns strategy, fanout, ordering, budget, and reframing.",
  "mission_menu": [
    {
      "name": "statement-freeze",
      "lane": "intake",
      "value": "Freeze exact statement, variants, sources, and hashes.",
      "risk": "Over-freezing the wrong variant wastes the campaign.",
      "suggested_agent": "scout"
    },
    {
      "name": "counterexample-pressure",
      "lane": "disproof",
      "value": "Search variants, boundary cases, bounded witnesses, and obstruction families.",
      "risk": "Negative bounded search is not proof.",
      "suggested_agent": "worker"
    },
    {
      "name": "idea-generation",
      "lane": "creative",
      "value": "Try analogy, conjecture mining, construction search, and speculative bridge lemmas.",
      "risk": "Ideas enter only as candidates until checked.",
      "suggested_agent": "worker"
    },
    {
      "name": "skeptic-synthesis",
      "lane": "review",
      "value": "Run skeptic review, gap feedback, novelty accounting, and final gates.",
      "risk": "Review can demote attractive but unsupported products.",
      "suggested_agent": "reviewer"
    }
  ],
  "composition_hints": [
    "Run counterexample pressure early when definitions or variants are fragile.",
    "Run literature/barrier scouting in parallel with formalization feasibility on named problems.",
    "Use idea-generation when current barriers have stale method families.",
    "Run skeptic review before promoting products into a report."
  ],
  "required_artifacts": [
    "statement-ledger.md",
    "proof_dependency_dag.json",
    "actual_lemma_queue.json",
    "barrier_attacks.json",
    "gap_feedback.json",
    "mutation_ledger.json",
    "explorer_return_packet.json"
  ]
}
```

The spec never authorizes weaker truth language. It only helps the user approve
or inspect a long run. Strategy is owned by the orchestrator.

## User-Facing Deep-Run Status

At every pause or final report, surface:

- frozen target;
- current open core;
- named barrier under attack;
- exact missing lemma or precondition;
- failed method family and failure class;
- next one-axis mutation;
- verified/checked product, if any;
- the first failing gate, if the run is not finalizable.

Status-only reports are not complete for a solve/deep-run request.
