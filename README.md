# strings

`strings/` is a versioned library of agent workflows for
[OpenScientist](http://fydy.ai/).

OpenScientist can be used alongside existing Claude Code and Codex
subscriptions. The skills in this repository are open source and can also be
used directly with other agent harnesses, including Claude Code, Codex, and
other Agent Skills-compatible clients.

## What Lives Here

| Path | Purpose |
|---|---|
| `agents/` | Canonical OpenScientist agent roles: orchestrator, worker, scout, hypothesizer, and general. |
| `skills/` | First-party operational and research skills. |
| `packages/skills/` | Packaged domain skills for scientific libraries, research workflows, writing, visualization, and integrations. |
| `tools/` | Reference docs for OpenScientist tools |
| `corpus/` | First-party Markdown documents that agents can read as stable platform context. |
| `sandboxes/` | Sandbox definitions and human-readable descriptions for isolated execution environments. |

## Using With Other Harnesses

Start with selected skills, not the entire repository. Large skill catalogs are
useful, but every harness has some discovery and context budget.

- Codex can read skills from `.agents/skills` in a repository or
  `$HOME/.agents/skills` for user-level skills.
- Claude Code can read project skills from `.claude/skills` and personal skills
  from `$HOME/.claude/skills`.
- Generic clients should read each skill's `name` and `description` first, then
  load `SKILL.md` and referenced files only when the task calls for that skill.

Detailed setup notes live in [docs/harnesses.md](docs/harnesses.md).

Authoring guidance for reusable skills, workflows, and scripts lives in
[docs/authoring-workflows.md](docs/authoring-workflows.md).

Agent role adaptation notes live in [docs/agents.md](docs/agents.md).

## Maintainer Rules

- Keep `SKILL.md` concise. Put long background material in `references/`.
- Put repeatable command logic in `scripts/` beside the skill that owns it.
- Avoid hardcoded OpenScientist-only paths unless the skill is explicitly
  OpenScientist-only and says so in `compatibility`.
- Do not commit secrets, local auth files, run logs, or generated scratch output.
- Prefer adding a small adapter doc or script over forking the same workflow for
  every harness.
- When a skill depends on external tools such as `git`, `jq`, `docker`, `uv`, or
  a networked API, state that requirement up front.

## Prized Skills

These are the skills that define the character of this repository:

| Skill | Why it matters |
|---|---|
| `witsoc` | A mathematics and proof-research subsystem for problem solving, proof critique, counterexample search, formalization planning, Lean-adjacent work, and long mathematical campaigns. |
| `autoresearch` | A meta-skill for open-ended research loops: propose paths, spawn focused workers, prune weak branches, and end with a durable report or committed artifact. |
| `autoresearch-worker` | The executor pattern for one research path, with experiments, commits, escalation, and bounded ownership. |
| `autoresearch-hypothesizer` | The path-generation half of research work: ranked hypotheses, adjacent variants, divergent pivots, and resource-aware suggestions. |
| `planning-with-files` | Persistent file-backed memory for long-running agents, handoffs, and deep runs. |
| `packages/skills/*` | The domain catalog: scientific Python, data science, chemistry, biology, medicine, writing, visualization, quantum, and research workflow skills. |

Use these as exemplars when adding new workflows: clear trigger conditions,
careful boundaries, scripts only where they remove real ambiguity, and enough
reference material for another harness to execute the workflow without the
OpenScientist app.
