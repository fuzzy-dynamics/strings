# Lovasz SOC Memory Protocol

Use `.soc` memory for every substantial Lovasz run. It prevents repeated dead approaches and preserves reusable barriers, reductions, conjectures, and verified partials.

Read `../../references/soc.md` for the base `.soc` format.

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

## Efficient Use

- Keep detailed derivations in `research.md`, `barriers.md`, or experiment files; put concise pointers in `.soc`.
- Use `SEE runs/<task>/...` links for bulky evidence.
- Do not store vague optimism. Store reusable facts and warnings.
- Before repeating an approach, check `FAILED_APPROACHES` for matching `do_not_repeat`.
- If three entries share the same blocker, convert the blocker into a named barrier in `barriers.md`.

## Memory Template

```text
-- Status: RUNNING

GOAL: <exact research target>

CURRENT:
  Selected product: <product>
  Active barrier: <barrier>
  Active move: <move>

INSIGHTS:
  - <short reusable insight>. SEE <path>

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

QUEUE:
  - source_triage: pending
  - barrier_map: pending
  - first_experiment: pending
```
