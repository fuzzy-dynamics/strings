# Soc Language Reference

The `.soc` file is the persistent working memory for the solve loop. It tracks what's been tried, what's been learned, and what to do next. One `.soc` file per run.

## File Structure

A `.soc` file contains:

1. Status header: `-- Status: RUNNING | DONE | STUCK`
2. Goal description
3. Current work and notes
4. Insights accumulated across approaches
5. Progress tracking
6. Optionally: a queue of sub-problems or sub-tasks

## Status Header

```
-- Status: RUNNING
```

Valid statuses:
- `RUNNING` -- the loop should continue
- `DONE` -- work is complete
- `STUCK` -- no progress being made, needs intervention

The stop hook reads this to decide whether to keep the agent running.

## Goal

Example:
```
GOAL: Prove that the chromatic number of the plane is at least 5
```

The research task. Can be a single hard problem, a research question, a project with sub-tasks, or a set of related problems.

## Current Work

Example:
```
CURRENT:
  Trying algebraic construction via unit-distance graphs.
  Approach 1 (probabilistic) failed -- see runs/chromatic/soc_approach_1.md
  Approach 2 (de Grey style) looks promising but needs more structure.
```

Free-form notes about what's being worked on right now.

## Insights

Example:
```
INSIGHTS:
  - Chevalley-Warning: quadratic forms in 3+ vars over F_q always have nontrivial zeros.
    This killed the polarity graph triangle-freeness claim. SEE runs/erdos_573/result.md
  - Pell + inert primes forces divisibility in consecutive integers. SEE runs/erdos_935/
  - The (r-1)! barrier: norm graphs give K_{r+1,(r-1)!+1}-free, not K_{r,r}-free for r>=4
```

Accumulated learnings. Write what's useful -- sometimes a sentence, sometimes a paragraph, sometimes a reference to a file with `SEE`. As the file grows, naturally use more SEE references for detailed content.

## Progress

Example:
```
PROGRESS:
  - problems_since_last_progress: 2
  - total_verified: 5
  - total_gap: 7
```

The stop hook reads `problems_since_last_progress`. If this exceeds a threshold (configured in `witsoc.toml`, default 5) with no new insights, the hook suggests stopping.

## Queue (optional)

Example:
```
QUEUE:
  - lemma_3: verified
  - construction_section_4: pending
  - theorem_5_gap: pending
```

When the task has multiple discrete sub-tasks, use a QUEUE. Each item: `- <id>: <status>`. The stop hook counts items containing `pending`.

For deep work on a single problem, a QUEUE is unnecessary -- GOAL and CURRENT are enough.

## Per-Task Workspace

Work products go in `runs/<task>/`:
- `soc_approach_N.md` -- informal exploration sketches
- `approach_N.wit` -- formalized proof
- `approach_N.wit.receipt.json` -- verification audit trail
- `result.md` -- summary of outcomes
- Scratch files, computation scripts, notes -- anything that helps

## Examples

### Deep research on one problem

```
-- soc working memory
-- Status: RUNNING

GOAL: Prove that every triangle-free planar graph is 3-choosable

CURRENT:
  Thomassen's proof of 5-choosability uses a clever induction on the outer face.
  Trying to adapt this to 3-choosability with additional structural constraints.
  SEE runs/3choosable/soc_approach_2.md for current attempt.

INSIGHTS:
  - Voigt (1993) showed not all planar graphs are 4-choosable -- so 3-choosable
    for triangle-free is not implied by any general planarity result
  - The key obstacle: degree-4 vertices with 3 colors available after neighbor
    constraints can create forced colorings that propagate

PROGRESS:
  - problems_since_last_progress: 1
```

### Multiple related sub-problems

```
-- soc working memory
-- Status: RUNNING

GOAL: Complete the proofs for sections 3-5 of the paper

QUEUE:
  - lemma_3.2: verified
  - prop_4.1: pending
  - theorem_5: pending
  - corollary_5.3: pending

CURRENT: prop_4.1
  The construction needs to handle the case when n is not a prime power.
  SEE runs/paper/prop_4_1/ for approaches.

INSIGHTS:
  - Lemma 3.2's proof technique (Pell + CRT) may also apply to Prop 4.1

PROGRESS:
  - problems_since_last_progress: 0
  - total_verified: 1
```

## Design Principles

- **Write what helps, skip what doesn't.** The format above is a guide, not a rigid schema.
- **The .soc file grows naturally.** As work accumulates, use more SEE references for detailed content.
- **The stop hook has a minimal contract.** It only needs: Status header, pending count (if QUEUE exists), and `problems_since_last_progress`. Everything else is for the agent's benefit.
- **Freedom over structure.** The agent manages its own context.
