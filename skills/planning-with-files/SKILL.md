---
name: planning-with-files
description: Manus-style file-based persistent memory for long-running deep agents. Maintains the deep-run UI files in `$PLANE_SESSION_DIR` (`plan.json`, evolution.json, findings.md, progress.md, report.md, claims.md, preview.html) and mirrors markdown state into `.openscientist/sessions/<run-session-id>/` for git history. Use whenever a task spans many tool calls and you need to survive context compaction or worker handoffs. **Stacks cleanly on top of any other meta-skill** (autoresearch, lit-review, …) — it never owns the work, only the bookkeeping. The frontend deep-run window reads `$PLANE_SESSION_DIR` through the plane files API; updating those files is how the user sees progress. Activated by both orchestrator and workers.
metadata:
  skill-author: OpenScientist
category: memory
---

# Planning With Files

The context window is RAM. The filesystem is disk. **Anything important goes to disk before it can fall off the back of the context.** This skill is the convention for *where* and *how*.

## 0. Where the files live, and who writes them

For an orchestrator deep run, the UI-visible canonical files live directly in the orchestrator's `$PLANE_SESSION_DIR`:

```
$PLANE_SESSION_DIR/
  plan.json       # the Plan panel: phases + tasks, valid JSON
  evolution.json  # the Evolution panel: causal mission/path graph, valid JSON
  findings.md     # evidence the orchestrator has surfaced
  progress.md     # session log: one line per significant event, time-ordered
  report.md       # the final deliverable for the user
  claims.md       # numbered claims with confidence + provenance
  preview.html    # live HTML summary the deep-run window renders
```

The orchestrator also keeps a git-backed mirror in the worktree:

```
.openscientist/sessions/$SESSION/
  plan.json       # mirror of the UI plan
  evolution.json  # mirror of the UI evolution graph
  task_plan.md     # the plan: task, phases, decisions, errors, paths
  findings.md      # mirror of the UI findings
  progress.md      # mirror of the UI progress log
  report.md        # mirror of the UI report
  claims.md        # mirror of the UI claims
  preview.html     # mirror of the UI preview
  agents/
    <session-id>/  # one directory per worker / hypothesizer / scout — their private scratch
```

The frontend deep-run window reads `$PLANE_SESSION_DIR` through the plane files API. The worktree mirror exists for commits, pull-back, and worker scratch. Update both; the user sees `$PLANE_SESSION_DIR` on the next poll, including the Evolution graph from `evolution.json`.

### Single-writer rule for the canonical files

The **orchestrator** is the only writer of `$PLANE_SESSION_DIR/plan.json`, `evolution.json`, `progress.md`, `findings.md`, `claims.md`, `report.md`, `preview.html`, and the worktree mirror's `task_plan.md`. Children (workers, hypothesizers, scouts) **never** edit those files. They:

- commit their work to their own branches (per-experiment commits, structured trailers);
- write any longer-form notes / drafts into their own scratch directory under `.openscientist/sessions/$SESSION/agents/<their-session-id>/`;
- mail the orchestrator a short pointer when something is ready.

When spawning a child, pass the scratch path as a literal path in the prompt. Do not use `$PLANE_SESSION_DIR` in child prompts to mean the orchestrator's directory; each child gets its own `$PLANE_SESSION_DIR`.

The orchestrator wakes on the mail, reads the pointer's target (commit trailers or scratch file), transcribes the relevant facts into the canonical file, and commits. This single-writer discipline keeps the canonical files coherent (no concurrent edits, no merge conflicts on prose, one editorial voice) and makes the audit trail straightforward.

Whether you are the orchestrator or a child, this is the rule:

| Role         | Writes to                                                  | Reads               |
|---           |---                                                         |---                  |
| Orchestrator | `$PLANE_SESSION_DIR` UI files + worktree mirror; no scratch dir of its own | everything          |
| Worker       | candidate branch (commits) + `agents/<own-id>/` scratch     | worktree mirror (read-only) + own branch |
| Hypothesizer | `agents/<own-id>/` scratch                                  | worktree mirror + git tree |
| Scout        | `agents/<own-id>/` scratch                                  | worktree mirror + external sources |

If `$SESSION` is unset, set it now from `$PLANE_SESSION_ID` (orchestrator only). Children use the `SESSION` value the orchestrator passed in their spawn prompt. If the orchestrator's `$PLANE_SESSION_ID` or `$PLANE_SESSION_DIR` is missing, block visibly instead of choosing a random id.

## 1. The five rules

### 1.1 Plan before act

Before any non-trivial work, `$PLANE_SESSION_DIR/plan.json` exists with at minimum:

```json
{
  "phases": [
    { "name": "Bootstrap", "description": "Initialize the run", "subphases": [] },
    { "name": "Work", "description": "Execute the task", "subphases": [] },
    { "name": "Synthesis", "description": "Write the final report", "subphases": [] }
  ],
  "tasks": [
    { "task_name": "Create run files", "phase": "Bootstrap", "status": "completed" },
    { "task_name": "Choose workflow", "phase": "Bootstrap", "status": "running" }
  ]
}
```

Valid task statuses are `pending`, `running`, `completed`, `failed`, and `skipped`.

Before dispatching workers, `$PLANE_SESSION_DIR/evolution.json` also exists. If paths are not known yet, start with:

```json
{ "missions": [] }
```

If the installed plugin catalog includes `evolution-tab` with a UI surface, open it after creating `evolution.json`:

```bash
"$PLANE_TOOL_BIN" plugins use evolution-tab
"$PLANE_TOOL_BIN" plugins iframe use evolution-tab
```

Verify `$PLANE_SESSION_DIR/plugins.json` marks `plugins["evolution-tab"].iframe_used === true`; otherwise the user may have valid graph data with no visible Evolution tab.

As soon as missions or workers are chosen, replace it with a graph like:

```json
{
  "missions": [
    {
      "mission_name": "state-of-vla-models",
      "mission_base_branch": "openscientist/session-cebf82-root",
      "selected_branch": "",
      "candidates": [
        {
          "candidate_name": "key-architectures",
          "candidate_branch": "openscientist/session-cebf82/missions/key-architectures/candidates/research",
          "branched_from": "openscientist/session-cebf82-root",
          "hypothesis": "Transformer and decision-transformer style policies explain the dominant VLA architecture families.",
          "verdict": "weak",
          "active": true,
          "metrics": [
            {
              "metric_name": "evidence status",
              "metric_type": "card",
              "configuration": {},
              "data": { "label": "architectures.md", "value": "running" }
            }
          ]
        }
      ]
    }
  ]
}
```

The top-level shape is always `{ "missions": [...] }`. Do not write `mission_branches`, `worker_sessions`, or a plain agent map as the Evolution file.

The worktree mirror's `task_plan.md` also exists with at minimum:

```markdown
## Task
<verbatim user task>

## Goal
<one sentence — what done looks like>

## Phases
- [ ] Phase 1: <name>  — pending
- [ ] Phase 2: <name>  — pending
- ...
```

Phases are 3–7 chunks, each completable in a known number of orchestrator loops. If you cannot name them yet, write `Phase 1: Recon — figure out the phases` and start there. Keep `plan.json` and `task_plan.md` in sync whenever phase or task status changes.

### 1.2 Read before decide

Before any *strategic* decision (what to do next, whether to spawn a worker, whether to terminate), read the worktree mirror's `task_plan.md`. Yes, every time. The cost is small; the cost of having drifted from your stated goal is large.

### 1.3 Write after find

The 2-action rule: **after every 2 search/read/browser/scout operations, append to `findings.md`** before doing anything else. Multimodal inputs (PDFs, images, web pages) are *especially* lossy — extract the claim plus the citation immediately.

`findings.md` entries:

```markdown
## <YYYY-MM-DDThh:mm> — <one-line claim>
Source: <file:line | URL | DOI | commit hash>
Notes: <1–3 sentences of context>
```

### 1.4 Log after fail

Every error goes in `task_plan.md` under `## Errors Encountered`:

| Error                | Attempt | Resolution                                                     |
|---                   |---      |---                                                              |
| `ModuleNotFoundError: torch` | 1       | Installed via `uv pip install torch`; succeeded                |
| OOM at batch=32      | 2       | Reduced to batch=16 + `gradient_accumulation_steps=2`           |

Three-strike rule: **never** repeat the exact same failing action. Each retry mutates one variable. If the third attempt fails, mail an `escalation:resource` or `escalation:decision` and ask for input rather than thrashing.

### 1.5 Commit after update

Every meaningful update to `$PLANE_SESSION_DIR/plan.json` / `evolution.json` / `findings.md` / `progress.md` / `report.md` / `claims.md` is mirrored into `.openscientist/sessions/$SESSION/` and followed by a git commit on the worktree's session branch. The Evolution panel reads `$PLANE_SESSION_DIR/evolution.json`; the mirror commit is for recovery and pull-back.

```bash
git add .openscientist/sessions/$SESSION/
git -c user.email=openscientist@fydy.ai -c user.name=OpenScientist commit -m "<file>: <one-line of what changed>"
```

Do not run `git config --global`; provider home directories can be read-only.

## 2. File-by-file conventions

### `plan.json`

The Plan panel's data source. It lives in `$PLANE_SESSION_DIR/plan.json` and is mirrored to `.openscientist/sessions/$SESSION/plan.json`.

Keep it valid JSON. Phases are stable containers. Tasks are the live status rows the user scans while the run is active.

```json
{
  "phases": [
    { "name": "Bootstrap", "description": "Initialize the run", "subphases": [] }
  ],
  "tasks": [
    { "task_name": "Create run files", "phase": "Bootstrap", "status": "completed" }
  ]
}
```

Every task's `phase` must exactly match a phase `name`. `subphase` is optional, but if present it must match a listed subphase. Do not put markdown in this file.

### `evolution.json`

The Evolution panel's data source. It lives in `$PLANE_SESSION_DIR/evolution.json` and is mirrored to `.openscientist/sessions/$SESSION/evolution.json`.

Keep it valid JSON. It is a causal graph over alternatives, not a chronological log. One candidate is one path; `hypothesis` explains why the path exists; `metrics` holds the current evidence; `selected_branch` marks the path taken while siblings remain visible as alternatives.

```json
{
  "missions": [
    {
      "mission_name": "state-of-vla-models",
      "mission_base_branch": "openscientist/session-cebf82-root",
      "selected_branch": "openscientist/session-cebf82/missions/synthesis/candidates/final-report",
      "candidates": [
        {
          "candidate_name": "training-datasets",
          "candidate_branch": "openscientist/session-cebf82/missions/training-datasets/candidates/research",
          "branched_from": "openscientist/session-cebf82-root",
          "hypothesis": "Training methodology and dataset coverage explain the largest VLA capability gaps.",
          "verdict": "positive",
          "active": false,
          "metrics": [
            {
              "metric_name": "evidence status",
              "metric_type": "card",
              "configuration": {},
              "data": { "label": "datasets.md", "value": "complete" }
            }
          ]
        }
      ]
    }
  ]
}
```

Valid verdicts are `weak`, `positive`, and `negative`. Update this file in the same turn as each worker dispatch, completion, escalation, prune, merge, or synthesis decision. Do not wait until the report is complete.

### `task_plan.md`

The detailed plan mirror in `.openscientist/sessions/$SESSION/task_plan.md`. The UI does not poll this file directly, but the orchestrator and workers use it for recovery and decisions. Always current. Sections, in order:

```markdown
## Task            (verbatim user task — never edit)
## Goal            (one sentence)
## Current phase   (which phase number you're in)
## Phases          (numbered, each with status: pending | in_progress | complete | blocked)
## Paths           (only if a research-style meta-skill is active — list of paths and their owner sessions)
## Open questions  (numbered, each with status: open | answered)
## Decisions       (table: Decision | Rationale | Date)
## Errors          (table: Error | Attempt | Resolution)
## Active workers  (table: session-id | role | path-id | status | last-mail-at)
```

`## Active workers` is the orchestrator's local view of `get-relatives`; refresh every loop. When this file changes phase or task status, update `plan.json` in the same turn.

### `progress.md`

The chronological log. It lives in `$PLANE_SESSION_DIR/progress.md` and is mirrored to the worktree. One line per significant event. Read top-down to recover state.

```markdown
## <ISO timestamp>
- <one line — what happened, by whom, with which commit/file ref>
```

What counts as significant: a phase transition, a worker spawn, a worker mail you acted on, a decision, a commit you made. Not: every tool call. The git log is the per-tool-call log.

### `findings.md`

Raw evidence, **transcribed by the orchestrator** from worker / scout scratch entries and worker commit trailers. It lives in `$PLANE_SESSION_DIR/findings.md` and is mirrored to the worktree. Append-only.

```markdown
## <ISO timestamp> — <one-line claim>
Source: <file:line | URL | DOI | commit hash>
Reported by: <worker-session-id>
Notes: <1–3 sentences>
```

Workers and scouts write findings to the literal scratch path the orchestrator assigned, usually `.openscientist/sessions/$SESSION/agents/<their-id>/findings.md`, then mail the orchestrator a pointer ("3 new findings at <path>"). The orchestrator opens the scratch, picks the entries worth surfacing to the user, transcribes them here (compressed, deduplicated, attributed), mirrors, and commits.

### `claims.md`

Distilled claims with confidence. The integrator worker drafts entries in its scratch dir during synthesis; the **orchestrator** transcribes them into `$PLANE_SESSION_DIR/claims.md`, mirrors, and commits.

```markdown
## C1 — <claim, one sentence>
Confidence: strong | moderate | weak
Provenance: <commit hash | findings.md anchor | external citation>
Status: open | confirmed | refuted
```

Numbered, monotonic — `C1`, `C2`, ... — so other files can cite by id.

### `report.md`

The user-facing deliverable. Shape depends on the task: a paper, a technical report, a benchmark write-up, a summary. Driven by the active research/writing meta-skill. The integrator worker writes a draft (`agents/<id>/report.draft.md`) during synthesis; the **orchestrator** transcribes it into `$PLANE_SESSION_DIR/report.md`, mirrors, and commits.

Minimum every report has:

```markdown
# <Title>

## Summary
<3–5 sentences>

## What we did
<one paragraph per phase>

## Results
<table | numbers | plot reference>

## References
<file paths, commit hashes, external citations>
```

Cite specific commits and `findings.md` entries — never claim a result without a citation reachable from this worktree.

### `preview.html`

The Preview panel's live HTML surface. It lives in `$PLANE_SESSION_DIR/preview.html` and is mirrored to the worktree. Create it during bootstrap for orchestrator deep runs unless the task is strictly non-visual and has no user-facing state beyond a one-line answer; even then, prefer a compact status board over a blank Preview tab.

Minimum content:

- title and one-sentence goal;
- current phase/status, active workers, and last meaningful update;
- best current answer/path and the evidence that supports it;
- blockers, weak claims, or missing evidence;
- next action.

The integrator worker may draft richer HTML at `agents/<id>/preview.draft.html`, but the **orchestrator** still owns promotion into `$PLANE_SESSION_DIR/preview.html`, mirroring, and commit. Keep the file standalone: complete HTML, inline CSS, no remote assets, responsive layout. Update it when `report.md`, `claims.md`, `findings.md`, or the selected candidate changes.

## 3. Stacks on top of other meta-skills

This skill is a **memory protocol**, not a workflow. It does not decide what to do next; it decides where to write what you have already done. Activate it on top of any other meta-skill — `autoresearch`, a future `lit-review`, anything — and it composes cleanly:

- The other meta-skill drives the loop: phases, sub-skills, when to spawn, when to merge.
- This skill ensures that each tick of that loop is recorded.

In particular: when the autoresearch hypothesizer skill writes `paths.md`, when the autoresearch worker commits with `[METRIC: ...]` trailers, when the autoresearch orchestrator updates `## Active workers` — those are all this skill's conventions, applied to that workflow.

## 4. Five-question reboot test

If your context was just compacted, answer these five questions before you do anything. The answers must come from files, not memory:

| Question                | Source                          |
|---                      |---                              |
| Where am I?             | `task_plan.md` § Current phase  |
| Where am I going?       | `task_plan.md` § Phases (remaining) |
| What's the goal?        | `task_plan.md` § Goal           |
| What have I learned?    | `findings.md` (last 5 entries)  |
| What have I done?       | `progress.md` (last 10 lines) + `git log -10` |

If any answer doesn't survive the trip from disk, your files are too thin — fix them before continuing.

## 5. When NOT to use this skill

- Single-question tasks (you'd burn 5x more time on bookkeeping than work).
- One-off scouts whose entire job is "produce one findings.md entry" — they don't need a `task_plan.md`.
- Tasks where the deliverable is a single file edit (the diff is the record).

The orchestrator never falls into these — deep runs always need the file structure. Workers may skip this skill for short, single-shot tasks (the orchestrator's spawn prompt will say so).

## 6. Read–write decision matrix

| Situation                       | Action                          | Reason                                  |
|---                              |---                              |---                                      |
| Just wrote a file               | Don't re-read                   | Content still in context                |
| Read a PDF / image              | Append `findings.md` *now*      | Multimodal → text before lost           |
| Web search returned data        | `findings.md` with the URL      | Screenshots don't persist               |
| Starting a new phase            | Read `task_plan.md` + last 10 of `progress.md` | Re-orient                |
| Error happened                  | Read the relevant file, then log to `task_plan.md` | Need current state to fix |
| Resuming after a context compact | Run the §4 reboot test          | Recover state from disk                 |
| About to spawn a worker         | Read `task_plan.md` § Active workers | Reuse before spawn (orchestrator §7)  |

## 7. Anti-patterns

- Using TodoWrite (or any in-context-only todo) for persistence — those die on compaction. Use `task_plan.md`.
- Stating goals once and forgetting them — re-read before decisions.
- Hiding errors and silently retrying — log every error to `task_plan.md`.
- Stuffing tool output into the next prompt — extract the claim, write it to `findings.md`, drop the rest.
- Starting work before `task_plan.md` exists — non-negotiable.
- Repeating the same failed action — three-strike rule.
- Updating files without committing — invisible to the user.
