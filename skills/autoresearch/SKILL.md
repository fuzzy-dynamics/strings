---
name: autoresearch
description: Karpathy-style autoresearch loop for the orchestrator. Hypothesizers draft a small number of paths; one biased worker takes ownership of each path and hill-climbs (every experiment a commit, mail-as-pointer-to-git); the orchestrator watches, prunes diminishing-returns paths, and ends with a single merged branch and a written report. Activate when the task is open-ended research with measurable progress (a metric, a benchmark, a "find the best X"). Pairs with sub-skills `autoresearch-worker` and `autoresearch-hypothesizer`, which the orchestrator activates by naming them in the worker spawn prompts. Stacks cleanly with `planning-with-files`.
metadata:
  skill-author: OpenScientist
category: research
---

# Autoresearch — the orchestrator side

This skill defines how the orchestrator runs an autoresearch loop. It assumes you have already read the orchestrator system prompt (`osci-orchestrator/system.md`) — this file describes the *flavour* on top of that policy.

The pattern is Karpathy-style: a small number of independent paths, each owned end-to-end by one biased worker that hill-climbs on a measurable metric, with the orchestrator watching the trajectory, intervening only when paths plateau, regress, or hit a strategic decision. **Reasoning is the git tree. Mail is a pointer.** Workers commit every experiment; you read the git log to see what they tried.

If `${SESSION}` is unset for you, set it now: `SESSION="session-$(openssl rand -hex 4)"`. Reuse the same `$SESSION` for the entire run.

## 0. Stack on top of `planning-with-files`

`UseSkill(name="planning-with-files")` immediately after activating this one. Your run will live in `.openscientist/sessions/$SESSION/{task_plan,findings,claims,progress,report}.md` from there on. **You — the orchestrator — are the only writer of those files** (orchestrator §5). Workers commit to candidate branches and write into their own scratch directories at `.openscientist/sessions/$SESSION/agents/<worker-id>/`; they mail you pointers; you transcribe.

## 1. The five phases

```
PHASE 0  Bootstrap        — write task_plan.md with the task, the metric, the budget
PHASE 1  Recon            — scouts gather background; hypothesizer drafts paths
PHASE 2  Path commitment  — one biased worker per path; bias is the point
PHASE 3  Hill-climbing    — workers iterate; you watch, prune, redirect
PHASE 4  Synthesis        — one worker writes the report; unbiased critic gates termination
```

You are at PHASE 0 when this skill activates.

### PHASE 0 — Bootstrap

Write into `task_plan.md`:

```markdown
## Task
<verbatim user task>

## Metric
<the measurable thing — e.g. "val accuracy on dataset X", "wall-clock for proof Y", "citation count of cited works in section 3">
<if the task has no clean metric, name a proxy and say so>

## Budget
- Wall-clock: <e.g. 4 hours>
- Max iterations of the orchestrator loop: <e.g. 50>
- Max concurrent workers: <≤5>
- GPU constraint: <none | 1 GPU | N GPUs>

## Paths (filled in PHASE 1)

## Open questions (filled in PHASE 1)
```

Commit. Then move to PHASE 1.

### PHASE 1 — Recon

The orchestrator does not research. Spawn at most 2 `osci-scout` workers in parallel (no shared worktree needed; they are read-only). Hand each scout a focused query, e.g.:

- "Read the codebase under `<dir>` and write findings to `.openscientist/sessions/$SESSION/agents/<your-id>/findings.md` about how X is currently done. Cite file:line refs. Mail the orchestrator a one-line pointer when done."
- "Search the web + arxiv for prior art on <task>. ≤ 8 sources, each with a 1-sentence claim and a URL or DOI. Write to your own scratch findings file. Mail orchestrator when done."

Each scout exits after its rehydration packet — the plane mails you `worker_complete` and wakes you. **You** then read each scout's scratch findings file and **transcribe** the relevant entries into the canonical `.openscientist/sessions/$SESSION/findings.md`. Compress, deduplicate, attribute. Commit.

Then spawn ONE `osci-hypothesizer` (with `autoresearch-hypothesizer` skill named in its prompt) and ask it to draft paths. Hand it: the task, the metric, the budget, the path of `findings.md`. Tell it: **3–5 paths, ranked by information value under the budget**, written into its own scratch file (`agents/<id>/paths.md`). The hypothesizer mails you `hypothesis-complete` and exits.

You read its scratch `paths.md`, transcribe the path list under `## Paths` in `task_plan.md`. Commit. Move to PHASE 2.

### PHASE 2 — Path commitment

For each top-K path (K ≤ 5; in practice 2–3 unless the budget is generous), spawn ONE `osci-worker` with the `autoresearch-worker` skill named in its prompt. The worker takes **complete ownership** of that path until it terminates the path itself. You will not split a path across multiple workers.

Worker spawn prompt template:

```
PATH: <path-id> — <one-line title>
GOAL: <metric to maximize/minimize>
BUDGET: <iterations | wall-clock | gpu-time> — when this is exhausted, exit normally with a final rehydration packet.
SESSION: $SESSION
HYPOTHESIS: <verbatim from paths.md>
SKILL: UseSkill(name="autoresearch-worker") on your first turn — that skill defines your loop.
WORKTREE: <inherited unless paths conflict on the same files; if so, give a fresh worktree>
ESCALATION SESSION: <your orchestrator session id, from get-status>
EXIT EARLY ON: subject "stop" mail.
```

Workers commit per-experiment to a candidate branch (`openscientist/$SESSION/paths/<path-id>`); they mail `escalation:*` / `progress:update` / `alive` notifications pointing at commits, then exit when their budget is done (or sooner on `stop`). **You read the commits, not the mail bodies.**

`git log openscientist/$SESSION/paths/<path-id> --format='%h %s'` is your view into what they have tried.

When a worker exits and the path is not yet done, **mail the same session id with the next sub-task**. The plane respawns it with a fresh process pointed at its existing candidate branch and scratch dir; it reads the commit log on its first turn and continues. Do not `launch-worker` for a path that already has an owner — that creates a sibling competing for the same branch.

### PHASE 3 — Hill-climbing — your loop

You are event-driven (orchestrator §1.5). Every wake-up runs this body once, then ends the turn:

```
on each wake-up:
  1. mailbox = "$PLANE_TOOL_BIN" get-status      # drain mail
  2. tree    = "$PLANE_TOOL_BIN" get-relatives   # snapshot child state
  3. for each mail in mailbox:
       read what it points at (commit trailers, scratch files)
       transcribe relevant facts into findings.md / progress.md / claims.md / report.md
       handle_escalation(mail) if it is one
  4. for each child in tree:
       check liveness (cleanup §10 of orchestrator policy)
  5. commit
  6. if any path has hit "diminishing returns" (see below): consult hypothesizer
  7. if termination conditions met (PHASE 4): stop spawning, move to synthesis
  8. end turn — the plane will wake you on the next mail
```

Handling escalations (the worker prompt's `escalation:*` subjects):

| Subject               | What it means                                                  | Your move                                                                                                              |
|---                    |---                                                             |---                                                                                                                     |
| `escalation:plateau`  | 5+ experiments < 1% improvement                                | Mail `steer:adjust` with a hypothesis variant, OR consult hypothesizer for adjacent ideas, OR mail `stop` if budget short. |
| `escalation:regression` | 3 consecutive worsened metrics                               | Mail `steer:adjust` with a roll-back-to-best instruction, OR consult hypothesizer.                                       |
| `escalation:anomaly`  | result contradicts expectations                                 | Read the commit. Update `findings.md`. Mail `steer:continue` if it's a real signal, `steer:adjust` to investigate it.    |
| `escalation:resource` | OOM, timeout, disk full                                         | Most often a ceiling on the path. Mail `steer:adjust` with a concrete shrink (smaller model, smaller batch, shorter run). If the path is GPU-bound and there is one GPU, see §3 below. |
| `escalation:decision` | multiple equally viable directions                              | Decide yourself if it's tactical (one-line); consult hypothesizer for strategic forks.                                  |
| `progress:update`     | routine progress, every 5 experiments                           | Update `progress.md` and `report.md`'s "Best so far" table. No reply required.                                          |

Diminishing-returns rule for path-pruning: if a path has emitted ≥2 `escalation:plateau` mails without recovering, AND the hypothesizer's adjacent suggestions have all been tried (track this in `task_plan.md`), the path is done. Mail the worker `stop`, mark the path closed in `task_plan.md`, free the slot.

### PHASE 4 — Synthesis

When **at least one path has produced a usable result** AND the orchestrator's iteration budget is ≥80% spent OR the wall-clock is ≥80% spent OR every path is closed, move to synthesis. Do not begin synthesis with paths still running unless the budget forces it; finish or close them first.

1. **Pick the integrator worker.** The worker that owns the best-scoring path is the integrator. They already know the code. Mail them:
   ```
   subject: prepare-merge
   body: Synthesis phase. Read paths.md and the candidate branches openscientist/$SESSION/paths/*.
   For each closed path, decide what (if anything) is worth merging into the main session branch.
   Produce a single coherent state on this worktree. Commit. Then UseSkill(name="autoresearch-worker") with sub-mode "writer" and produce report.md.
   ```
2. **Wait** for them. They mail `merge-ready` when done.
3. **Run the unbiased termination check** (orchestrator §8). Spawn a fresh `osci-general`, hand it the task, the worktree, and `report.md`. Ask `complete, ship` / `missing: ...`.
4. If `missing:`, mail the integrator with the specific gaps. Loop.
5. If `complete, ship`, ensure §4.1 commit discipline and end.

## 2. Reasoning is the git tree

The biggest mistake in this loop is treating mail as data. **Mail is signal — a pointer to a git commit. Data lives on the branch.** When a worker says `escalation:plateau, branch openscientist/.../paths/lr-sweep, latest a1b2c3d`, your action is `git log openscientist/.../paths/lr-sweep --format='%h %s%n%b' | head -40` — read the trailers, infer the trajectory, then act.

This is also how you survive worker context loss. If a worker terminates and you spawn a fresh one to continue the path, the new worker reads the candidate branch's git log and recovers the entire experiment history. Mail history would be gone.

## 3. Resource allocation under constraint

If the user task implies limited resources (one GPU, one expensive API budget) and multiple paths are GPU-bound, **serialize the GPU-bound paths** rather than time-slicing them — concurrent GPU contention destroys both runs.

The serialization decision belongs to the hypothesizer. Mail it:
```
subject: prioritize
body: Paths <A>, <B>, <C> are GPU-bound and we have 1 GPU. Rank them by expected information value if I run them sequentially. Reply with an ordered list and a 1-sentence justification per path.
```

Run them in that order. Use `get-relatives` to confirm only one path's worker is `running` at a time on GPU work. Other paths can be in `waiting_for_mail` between turns.

If the user task is CPU-bound or pure literature work, parallelism up to the §9 ceiling is fine.

## 4. Spawning sub-skill workers

When you spawn the workers, name the sub-skill explicitly in the prompt — the worker activates it on its first turn:

- `osci-hypothesizer` → `UseSkill(name="autoresearch-hypothesizer")`
- `osci-worker` → `UseSkill(name="autoresearch-worker")`
- `osci-scout` → no flavour skill — the agent's own prompt is enough
- `osci-general` → no flavour skill — keep the critic untrained

Both sub-skills exist in this world-model bundle (`autoresearch-worker/SKILL.md`, `autoresearch-hypothesizer/SKILL.md`) and will sync with the worker on session start.

## 5. Termination defaults for this skill

- Hard wall-clock: **4 hours** unless the user task names a different budget.
- Hard iteration cap: **80 orchestrator loop turns** before forcing PHASE 4.
- Per-path stuck cap: ≥2 plateau escalations + exhausted hypothesizer suggestions → close the path.

When you terminate, the run's deliverable is:

- `report.md` (written by the integrator) — the technical report or paper draft. Cited claims tie to specific commits or files.
- `findings.md` (accumulated by scouts and workers) — raw evidence, optional.
- `claims.md` (written by the integrator during synthesis) — numbered claims with confidence and provenance.
- `task_plan.md` — final state with all paths marked closed/merged.
- The merged session branch with all integrated work.

The unbiased agent (orchestrator §8) checks against the original task, not against this skill's internal phases. If the task is "write a paper", `report.md` had better look like a paper.
