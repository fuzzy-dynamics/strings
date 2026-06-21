# Agent Roles

`agents/` contains canonical OpenScientist role definitions. Treat these as
source material for harness-specific agents, not as product UI files.

Current roles:

| Role | Purpose |
|---|---|
| `osci-orchestrator` | Coordinates deep runs, delegates work, tracks shared files, and synthesizes results. |
| `osci-worker` | Executes implementation, experiments, documents, and verification in a bounded worktree. |
| `osci-scout` | Performs read-only exploration across code, papers, docs, and web sources. |
| `osci-hypothesizer` | Proposes ranked research paths, variants, pivots, and resource-aware hypotheses. |
| `osci-general` | General-purpose local assistant role with broad tools. |

## Canonical Files

Each agent directory may contain:

| File | Meaning |
|---|---|
| `agent.yaml` | OpenScientist/Kimi-style agent manifest: model, tools, exclusions, and prompt path. |
| `system.md` | Canonical role instructions. Prefer editing this before editing generated adapters. |
| `osci-<name>.md` | Markdown agent prompt for harnesses that consume single Markdown agent files. |

Keep role behavior in `system.md` where possible. Keep provider-specific tool
lists and launch details in adapter files.

## Adapting To Claude Code

Claude Code custom subagents are Markdown files with YAML frontmatter. Project
subagents live under `.claude/agents/`; personal subagents live under
`~/.claude/agents/`.

Minimal shape:

```md
---
name: osci-scout
description: Read-only research and exploration across codebases, papers, and web sources.
tools: Read, Glob, Grep, WebSearch, WebFetch
---

<contents adapted from agents/osci-scout/system.md>
```

Guidance:

- Use Claude Code subagents for isolated context and tool restrictions.
- Keep read-only roles read-only.
- Put subagent-specific hooks in the subagent frontmatter only when they are
  part of the role's contract.
- Keep shared project rules in `CLAUDE.md`; keep reusable procedures in skills.

## Adapting To Codex

Codex custom agents are TOML files. Project agents live under `.codex/agents/`;
personal agents live under `~/.codex/agents/`.

Minimal shape:

```toml
name = "osci-worker"
description = "Execution-focused worker for implementation, experiments, documents, and verification."
developer_instructions = """
<contents adapted from agents/osci-worker/system.md>
"""
```

Guidance:

- Use Codex custom agents when a spawned worker needs a different role,
  instructions, model, sandbox, or MCP setup.
- Codex subagents are explicitly spawned by the user or parent workflow, so
  prompts should name the desired agent role.
- Keep skill installation separate from custom agent files. A custom agent can
  use installed skills, but the agent file should not vendor whole skills.

## Adapter Generation

A future adapter script should be able to generate harness files from the
canonical roles:

```bash
scripts/install-harness.sh claude-code --scope repo --agents osci-worker,osci-scout
scripts/install-harness.sh codex --scope user --agents osci-worker,osci-hypothesizer
```

The generator should:

1. Read `agents/<name>/system.md`.
2. Read a small harness template.
3. Write the generated file into the target harness dotdir.
4. Avoid modifying the canonical source role.
5. Print the files it wrote.

Generated adapter files should be easy to delete and recreate.

## Porting Rules

- Do not put secrets in agent prompts.
- Do not hardcode closed-source app paths in portable role instructions.
- Keep provider tool names in adapter metadata, not in the canonical role body,
  unless the role is explicitly provider-specific.
- Preserve role boundaries. A scout should not become a worker just because one
  harness makes editing easy.
- Prefer links to skills over copying workflow instructions into every agent.

## Role And Skill Relationship

Agents define who is doing the work. Skills define how a repeatable task should
be done.

Examples:

- `osci-worker` can activate `planning-with-files` to maintain durable progress.
- `osci-scout` can use literature or search skills when researching a domain.
- `osci-hypothesizer` can use `autoresearch-hypothesizer` to produce ranked
  research paths.
- `osci-orchestrator` can coordinate `autoresearch` without executing the
  experiments itself.

When behavior starts appearing in multiple agents, extract it into a skill.
