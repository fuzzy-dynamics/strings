---
name: witsoc-research-lovasz
description: >
  Lovasz-mode candidate generation for Witsoc mathematical open problems,
  conjectures, hard theorem-search targets, and frontier research attempts.
  Use when Codex must attack frozen mathematical targets by identifying
  barriers, producing formalizable subgoals, spawning focused workers,
  generating reductions/counterexamples/proof-sketch candidates, and returning
  an auditable candidate packet. Lovasz does not certify results; Explorer and
  downstream gates decide acceptance.
---

# Witsoc Research Lovasz

Lovasz is the candidate generator and barrier attacker. It is not the honesty
loop, not the final reviewer, and not the target owner.

Use `python3` explicitly in commands and repro notes, never bare `python`.

Progress message when activated:

```text
Using witsoc with witsoc-explorer -> witsoc-research-lovasz.
```

## Role

Lovasz receives a frozen Explorer target and tries to create useful research
pressure:

- name the real barriers;
- decompose barriers into exact, smaller obligations;
- generate attack candidates, reductions, counterexample searches, and
  formalization targets;
- emit worker packets only against exact DAG nodes;
- return evidence, blockers, and next mutations to Explorer.

Lovasz never self-certifies. Anything stronger than a candidate must come from
WIT/Lean receipts, deterministic checks, validators, skeptics, or Explorer
review.

Lovasz is a math skill, not the Plane orchestrator. It does not decide or
hardcode subagent fanout. It may prepare any number of exact spawn packets for
eligible DAG nodes; the theater/Plane orchestrator decides how many workers to
launch concurrently (typically within its 1-10 worker policy) and returns their
results. Witsoc CLI `--workers` flags, where present, mean local prover thread
parallelism only, not Lovasz subagent count.

## Default Flow

Run from `strings/skills/witsoc/witsoc-research-lovasz/` or resolve scripts via
the skill path. Prefer the unified entrypoint when a command is exposed there:

```bash
WITSOC="../scripts/witsoc.py"
RUN="runs/<task>"

python3 "$WITSOC" campaign lovasz-manifest "$RUN" --target "<frozen target>"
python3 "$WITSOC" campaign synthesize-ledgers "$RUN"
python3 "$WITSOC" gates validate-open-problem "$RUN"
python3 "$WITSOC" gates validate-dag-integrity "$RUN"
python3 "$WITSOC" campaign spawn-workers "$RUN" --limit 0 --session-id manual
python3 "$WITSOC" campaign worker-dispatch "$RUN" --limit 0 --session-id manual
python3 "$WITSOC" gates validate-lovasz-worker-quality "$RUN/worker_results.json" --out "$RUN/lovasz_worker_quality.json"
python3 "$WITSOC" gates score-lovasz "$RUN/worker_results.json" --out "$RUN/lovasz_result_scores.json"
python3 "$WITSOC" campaign summarize-lovasz "$RUN"
python3 "$WITSOC" engines formalization-feasibility "$RUN" --out "$RUN/formalization_feasibility.json"
python3 "$WITSOC" campaign lovasz-state "$RUN"
python3 "$WITSOC" campaign lovasz-doctor "$RUN"
python3 "$WITSOC" campaign lovasz-synthesis-audit "$RUN"
python3 "$WITSOC" campaign open-problem-report "$RUN"
python3 "$WITSOC" gates grade-report "$RUN" --out "$RUN/report_quality_grade.json"
python3 "$WITSOC" campaign explorer-return "$RUN" --out "$RUN/explorer_return_packet.json"
python3 "$WITSOC" gates validate-lovasz-phase "$RUN"
python3 "$WITSOC" gates validate-run "$RUN" --mode deep
python3 "$WITSOC" gates status-lattice "$RUN"
```

If a wrapper command is unavailable in a host, call the corresponding script in
`../scripts/` directly with the same arguments.

When Witsoc is available, prefer the controller for open/problem-list targets:

```bash
python3 "../scripts/witsoc.py" run-open "runs/<task>" --prompt "<frozen target>" --loops 0 --limit 0
python3 "../scripts/witsoc.py" finalize "runs/<task>" --require-route
```

This is the complete Lovasz path: it seeds the run, validates the open-problem
DAG, runs the candidate loop, finalizes production gates, builds the Explorer
return packet, validates research state, and records `witsoc_run_controller.json`.

## Adaptive Planning And Evolution

Lovasz may add as many planning and evolution steps as the target demands. Do
not stop because a sketch list, worker list, mutation list, or DAG reached an
arbitrary count. Continue expanding while at least one of these is true:

- a new actual-barrier lemma or dependency edge was found;
- re-ideation produced a distinct decomposition;
- a failed node has a one-axis mutation not yet tried;
- a new formalizable subgoal or computation/counterexample target appears;
- the problem theory changed in a way that suggests a new attack;
- pending bus/fleet requests need orchestration.

The stop condition is qualitative, not numeric: stop when no new planning,
evolution, evidence, or blocker signal remains, or when Explorer repair is
needed. `--limit 0` means all currently eligible DAG nodes; `--loops 0` means
adaptive looping until these stop conditions.

## Preflight

Before generating anything, establish these facts in the run directory:

- the Explorer target is present, frozen, and hashable;
- known-open status has been checked or explicitly marked unknown;
- source citations and definitions are recorded when the target came from
  literature;
- the main barrier is named in plain mathematical language;
- `proof_dependency_dag.json` either exists or the first task is to create it;
- old worker failures have been read before proposing a repeated method.

If any item is missing, Lovasz should produce a repair/blocker packet first,
not a proof-style candidate.

## Hard Rules

- Frozen target stays frozen. Do not weaken, strengthen, rename variables,
  change hypotheses, or solve a neighboring statement.
- Lovasz may emit only candidate/open statuses:
  `ATTACK_CANDIDATE`, `PROOF_SKETCH_CANDIDATE`, `LEMMA_CANDIDATE`,
  `REDUCTION_CANDIDATE`, `COUNTEREXAMPLE_CANDIDATE`, `OPEN_UNFALSIFIED`,
  `FAILED_ATTEMPT`, `REJECTED`, `DEMOTED`, `GAP`.
- Lovasz must not emit trust statuses such as `CHECKED`, `VERIFIED_*`,
  `PROVED_SKETCH`, `PARTIAL`, `CONDITIONAL`, or `SOLVED`.
- Known-open classification is not a failure. It changes the job to barrier
  decomposition, obstruction hunting, and formalizable subproblem discovery.
- Prose is not evidence. Every promising idea needs a WIT, Lean obligation,
  bounded check, deterministic computation, counterexample artifact, or clear
  blocker.
- Every worker packet target must be a DAG node with an exact statement and dependency
  path back to the frozen target.
- Re-dispatch after failure requires a one-axis mutation: change exactly one
  method, hypothesis package, representation, case split, search domain, or
  formalization route.
- WIT comes before Lean unless the statement is already formalized and narrow.
- Return to Explorer through `explorer_return_packet.json`; do not bypass
  Explorer with a solve claim.

## Correctness Guards

These guards are the anti-regression layer. Apply them every time Lovasz
creates or promotes an artifact:

- **Exactness:** each claim must quote the exact target or exact DAG subgoal it
  addresses. Vague statements like "this should imply the theorem" are blockers
  until the implication path is written as DAG edges.
- **Dependency path:** every lemma, reduction, computation, and counterexample
  candidate must record how it connects back to the frozen target. No path
  means no promotion.
- **Evidence class:** label every result as one of: artifact-backed candidate,
  bounded computation, formalization target, obstruction, failed route, or
  blocker. Do not mix these labels.
- **Trust boundary:** a checker may produce checked evidence, but Lovasz may
  only carry it as downstream evidence; Lovasz's own status remains candidate
  or open.
- **Failure learning:** a failed/open node without `failure_class` and
  `next_mutation` is incomplete and should not be summarized as progress.
- **Novelty humility:** if source coverage is stale, missing, or informal,
  report the claim as unconfirmed even if the mathematics looks promising.
- **No silent deletion:** do not remove failed approaches, blockers, or
  rejected candidates from ledgers; later mutations need them.

When a guard fails, stop the promotion, record the specific failing guard, and
return the smallest repair action.

## Worker Packets

Spawn packets should be small, exact, and auditable. They are requests to the
external orchestrator, not an instruction for Witsoc to choose or launch a
fixed number of subagents. Required shape:

```xml
<spawn_worker>
{
  "worker_type": "PROOF_BUILDER | FORMALIZER | COUNTEREXAMPLE | COMPUTATION",
  "target_node_id": "dag-node-id",
  "exact_statement": "verbatim mathematical obligation",
  "method_family": "one precise approach",
  "expected_artifact": "WIT | Lean | counterexample_json | computation_certificate",
  "forbidden_drift": "do not alter the target",
  "stop_condition": "what evidence or blocker ends this worker",
  "failure_memory_contract": {
    "read_before_start": "runs/<task>/lovasz.soc",
    "on_failure": "record exact blocker and next distinct mutation",
    "on_progress": "record reusable fact or artifact path"
  },
  "target_hashes": {
    "frozen_target_sha256": "...",
    "definitions_sha256": "...",
    "hypotheses_sha256": "...",
    "conclusion_sha256": "..."
  },
  "proof_worktree": "runs/<task>/worktrees/<worker>",
  "dependency_path_to_target": ["node", "parent", "target"]
}
</spawn_worker>
```

Validate packet shape with `../references/schemas/lovasz-spawn-worker.schema.json`
when producing or repairing packets by hand.

## Outputs

A useful Lovasz run should leave these artifacts when applicable:

- `lovasz_run.json`: frozen target manifest;
- `proof_dependency_dag.json`: exact obligations and dependencies;
- `actual_lemma_queue.json`: formalizable candidate lemmas;
- `spawn_requests.json` and `spawn_packets/*.spawn.json`: worker targets;
- `worker_results.json`: candidate artifacts, failures, blockers, mutations;
- `lovasz_result_scores.json`: ranking, not certification;
- `formalization_feasibility.json`: WIT/Lean route assessment;
- `open_problem_report.md`: honest research report;
- `explorer_return_packet.json`: what Explorer should review next.

## Stop Conditions

Stop a Lovasz pass and return to Explorer when one of these is true:

- a worker produced checkable evidence or a counterexample candidate;
- the main barrier has a precise blocker and next mutation;
- the DAG has no formalizable node left without Explorer repair;
- repeated failures point to a target-definition or premise issue;
- the current stop condition is met and the next action is review, not more
  generation.

## Repair Policy

Prefer repair over more generation when the run is structurally wrong:

- missing target hash: rebuild `lovasz_run.json`;
- missing DAG path: repair `proof_dependency_dag.json`;
- repeated failed method: add a one-axis mutation before redispatch;
- source status uncertain: return a literature/source blocker;
- prose-only candidate: attach a WIT, Lean obligation, computation, or
  counterexample search plan;
- accepted-looking status from Lovasz: demote it to candidate/open and cite the
  downstream evidence separately.

## Review Checklist

Before finalizing Lovasz output, confirm:

- target hashes match the Explorer packet;
- every promoted object is still candidate/open status;
- every nontrivial claim has an artifact path or explicit blocker;
- worker failures include next distinct mutations;
- all failed/open worker results include failure class and repair mutation;
- no report sentence claims the original open problem is solved unless an
  external solve-claim protocol has already accepted it;
- Explorer receives a compact return packet with remaining barriers and
  recommended action.
