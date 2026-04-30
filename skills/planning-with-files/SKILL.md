---
name: planning-with-files
description: Manus-style file-based persistent memory for long-running deep agents. Maintains task_plan.md (phases + decisions + errors), findings.md (discoveries), progress.md (session log), report.md (final deliverable), claims.md (numbered claims with confidence) inside `.openscientist/sessions/<session-id>/`. Use whenever a task spans many tool calls and you need to survive context compaction or worker handoffs. **Stacks cleanly on top of any other meta-skill** (autoresearch, lit-review, …) — it never owns the work, only the bookkeeping. The frontend deep-run window reads these files directly; updating them is how the user sees progress. Activated by both orchestrator and workers.
metadata:
  skill-author: OpenScientist
category: memory
---

# Planning With Files

The context window is RAM. The filesystem is disk. **Anything important goes to disk before it can fall off the back of the context.** This skill is the convention for *where* and *how*.

## 0. Where the files live, and who writes them

For a deep run with session id `$SESSION` (set by the orchestrator at start: `SESSION="session-$(openssl rand -hex 4)"`), the canonical files are:

```
.openscientist/sessions/$SESSION/
  task_plan.md     # the plan: task, phases, decisions, errors, paths
  findings.md      # what scouts/workers discovered (raw evidence + provenance)
  progress.md      # session log: one line per significant event, time-ordered
  report.md        # the final deliverable for the user
  claims.md        # numbered claims with confidence + provenance
  preview.html     # optional — live HTML the deep-run window renders
  agents/
    <session-id>/  # one directory per worker / hypothesizer / scout — their private scratch
```

The frontend deep-run window reads the canonical paths directly — they are the source of every panel the user looks at. Update them; the user sees the update on the next 5-second poll.

### Single-writer rule for the canonical files

The **orchestrator** is the only writer of `task_plan.md`, `progress.md`, `findings.md`, `claims.md`, `report.md`, `preview.html`. Children (workers, hypothesizers, scouts) **never** edit those files. They:

- commit their work to their own branches (per-experiment commits, structured trailers);
- write any longer-form notes / drafts into their own scratch directory under `agents/<their-session-id>/`;
- mail the orchestrator a short pointer when something is ready.

The orchestrator wakes on the mail, reads the pointer's target (commit trailers or scratch file), transcribes the relevant facts into the canonical file, and commits. This single-writer discipline keeps the canonical files coherent (no concurrent edits, no merge conflicts on prose, one editorial voice) and makes the audit trail straightforward.

Whether you are the orchestrator or a child, this is the rule:

| Role         | Writes to                                                  | Reads               |
|---           |---                                                         |---                  |
| Orchestrator | the canonical files; no scratch dir of its own              | everything          |
| Worker       | candidate branch (commits) + `agents/<own-id>/` scratch     | canonical files (read-only) + own branch |
| Hypothesizer | `agents/<own-id>/` scratch                                  | canonical files + git tree |
| Scout        | `agents/<own-id>/` scratch                                  | canonical files + external sources |

If `$SESSION` is unset, set it now (orchestrator only) and `mkdir -p .openscientist/sessions/$SESSION`.

## 1. The five rules

### 1.1 Plan before act

Before any non-trivial work, `task_plan.md` exists with at minimum:

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

Phases are 3–7 chunks, each completable in a known number of orchestrator loops. If you cannot name them yet, write `Phase 1: Recon — figure out the phases` and start there.

### 1.2 Read before decide

Before any *strategic* decision (what to do next, whether to spawn a worker, whether to terminate), read `task_plan.md`. Yes, every time. The cost is small; the cost of having drifted from your stated goal is large.

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

Every meaningful update to `task_plan.md` / `findings.md` / `progress.md` / `report.md` / `claims.md` is followed by a git commit on the worktree's session branch. The Evolution panel of the deep-run window shows your commits — uncommitted updates are invisible.

```bash
git add .openscientist/sessions/$SESSION/
git commit -m "<file>: <one-line of what changed>"
```

## 2. File-by-file conventions

### `task_plan.md`

The plan, the phases, the open questions, the decisions, the errors. Always current. Sections, in order:

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

`## Active workers` is the orchestrator's local view of `get-relatives`; refresh every loop.

### `progress.md`

The chronological log. One line per significant event. Read top-down to recover state.

```markdown
## <ISO timestamp>
- <one line — what happened, by whom, with which commit/file ref>
```

What counts as significant: a phase transition, a worker spawn, a worker mail you acted on, a decision, a commit you made. Not: every tool call. The git log is the per-tool-call log.

### `findings.md`

Raw evidence, **transcribed by the orchestrator** from worker / scout scratch entries and worker commit trailers. Append-only.

```markdown
## <ISO timestamp> — <one-line claim>
Source: <file:line | URL | DOI | commit hash>
Reported by: <worker-session-id>
Notes: <1–3 sentences>
```

Workers and scouts write findings to their own scratch directory at `agents/<their-id>/findings.md`, then mail the orchestrator a pointer ("3 new findings at <path>"). The orchestrator opens the scratch, picks the entries worth surfacing to the user, transcribes them here (compressed, deduplicated, attributed), commits.

### `claims.md`

Distilled claims with confidence. The integrator worker drafts entries in its scratch dir during synthesis; the **orchestrator** transcribes them into this canonical file and commits.

```markdown
## C1 — <claim, one sentence>
Confidence: strong | moderate | weak
Provenance: <commit hash | findings.md anchor | external citation>
Status: open | confirmed | refuted
```

Numbered, monotonic — `C1`, `C2`, ... — so other files can cite by id.

### `report.md`

The user-facing deliverable. Shape depends on the task: a paper, a technical report, a benchmark write-up, a summary. Driven by the active research/writing meta-skill. The integrator worker writes a draft (`agents/<id>/report.draft.md`) during synthesis; the **orchestrator** transcribes it here.

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

### `preview.html` (optional)

If the deliverable benefits from a rendered view (a chart, a styled report, an interactive demo), the integrator worker drops a draft at `agents/<id>/preview.draft.html`; the **orchestrator** promotes it to the canonical `preview.html`. The deep-run window's Preview panel renders it live. Skip if not relevant.

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
