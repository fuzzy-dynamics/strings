# Lovasz SOC Memory Protocol

Use `.soc` memory for every substantial Lovasz run. It prevents repeated dead approaches and preserves reusable barriers, reductions, conjectures, verified partials, active barriers, and orchestrator-facing decision notes.

Read `../../references/soc.md` for the base `.soc` format.

`.soc` is an active decision-support surface, not a passive log. Lovasz should
read it before selecting routes and update it immediately after outcomes. The
orchestrator remains free to choose a different route, but `.soc` should make
repeat risks and reusable insights impossible to miss.

## Required File

Create or update:

```text
runs/<task>/lovasz.soc
```

Use this status header:

```text
-- Status: RUNNING
```

## When To Read Memory

Read `lovasz.soc` before:

- choosing a research product,
- selecting a barrier-breaking move,
- proposing conjectures,
- asking Explorer for proof search,
- asking Generator for an artifact,
- declaring a path stuck.

Also search nearby run directories for `.soc` files when the problem is clearly related and the workspace has prior Witsoc runs.

## What To Write

Add to `INSIGHTS`:

- reusable reductions,
- true boundary examples,
- theorem preconditions that mattered,
- barrier moves that worked,
- conjectures worth retesting,
- verified or checked partial results with paths.

Add to `BARRIERS`:

- exact bottleneck lemma, obstruction, or theorem-precondition gap,
- status,
- next probe,
- evidence path.

Add to `REUSABLE_TOOLS`:

- useful search scripts,
- theorem families,
- domain encodings,
- successful proof patterns,
- reusable counterexample generators.

Add to `FAILED_APPROACHES`:

- exact method,
- blocker,
- evidence path,
- do-not-repeat condition,
- next distinct methods.

Add to `PROGRESS`:

```text
PROGRESS:
  - problems_since_last_progress: <n>
  - total_verified: <n>
  - total_partial: <n>
  - total_failed_attempts: <n>
```

Reset `problems_since_last_progress` to `0` only when a new reusable insight, counterexample, checked computation, verified artifact, or source-status clarification is recorded.

Add to `ORCHESTRATOR_NOTES`:

- repeat-risk warnings,
- recommended parallel splits,
- useful but optional creative routes,
- reasons a default Lovasz recommendation can be ignored or reframed.

## Efficient Use

- Keep detailed derivations in `research.md`, `barriers.md`, or experiment files; put concise pointers in `.soc`.
- Use `SEE runs/<task>/...` links for bulky evidence.
- Do not store vague optimism. Store reusable facts and warnings.
- Before repeating an approach, check `FAILED_APPROACHES` for matching `do_not_repeat`.
- If three entries share the same blocker, convert the blocker into a named barrier in `barriers.md`.

Use the deterministic helper whenever available:

```bash
python3 scripts/lovasz_soc_memory.py init runs/<task>
python3 scripts/lovasz_soc_memory.py context runs/<task>
python3 scripts/lovasz_soc_memory.py update-current runs/<task> --product "<product>" --barrier "<barrier>" --move "<move>" --decision "<orchestrator choice needed>"
python3 scripts/lovasz_soc_memory.py add-barrier runs/<task> --statement "<barrier>" --next-probe "<next exact test>"
python3 scripts/lovasz_soc_memory.py add-tool runs/<task> --tool "<tool/pattern>" --use "<when useful>"
python3 scripts/lovasz_soc_memory.py add-note runs/<task> --text "<orchestrator-facing warning or option>"
python3 scripts/lovasz_soc_memory.py query runs/<task> --statement "<exact node>" --method "<method family>"
python3 scripts/lovasz_soc_memory.py add-failure runs/<task> --method "<method>" --statement "<exact node>" --blocker "<blocker>" --evidence "<path>"
```

Worker dispatch must consume this memory through `scripts/lovasz_worker_dispatch.py`.
Packets with high repeat risk require a recorded one-axis mutation before retry.

## Memory Template

```text
-- Status: RUNNING

GOAL: <exact research target>

CURRENT:
  Selected product: <product>
  Active barrier: <barrier>
  Active move: <move>
  Last decision needed: <choice for orchestrator>

BARRIERS:
  - id: <barrier_id>
    statement: <exact bottleneck>
    status: open
    next_probe: <next exact test>

INSIGHTS:
  - <short reusable insight>. SEE <path>

REUSABLE_TOOLS:
  - <tool>: <when useful>. SEE <path>

PROGRESS:
  - problems_since_last_progress: 0
  - total_verified: 0
  - total_partial: 0
  - total_failed_attempts: 0

FAILED_APPROACHES:
  - id: approach_1
    method: <method>
    status: rejected
    blocker: <specific blocker>
    evidence: <path>
    do_not_repeat: <condition>
    next_methods:
      - <distinct method>

ORCHESTRATOR_NOTES:
  - <warning, option, or parallel split for orchestrator>

QUEUE:
  - source_triage: pending
  - barrier_map: pending
  - first_experiment: pending
```
