# Harness Setup

This repository is a source library. Each harness needs a thin adapter layer
that places selected skills, instructions, and agent roles where that harness
expects to find them.

Do not make every harness consume the whole tree by default. Install profiles
should be small and intentional.

## OpenScientist And Plane

OpenScientist reads this repository as the central strings checkout, normally
under:

```bash
~/.openscientist/strings
```

In development, Plane can be pointed at a local checkout:

```bash
OSCI_STRINGS_REPO=/absolute/path/to/strings npm run desktop:dev
```

When using the default Git-backed sync, `OSCI_STRINGS_BRANCH` can select a
branch. The closed-source app is the consumer; this repo should not depend on
frontend internals except through documented runtime contracts.

OpenScientist-specific conventions:

- Skills are served centrally by Plane.
- Space-local overlays may appear under `space/`.
- Agent roles are materialized into target workspaces for providers that expect
  local agent files.
- OpenScientist tool docs under `tools/` describe platform tools, not local
  shell tools.

## Codex

Codex supports Agent Skills directly. Use either a user-level install for
personal reuse or a repo-level install when a project should carry its own
agent workflows.

User-level selected skills:

```bash
mkdir -p ~/.agents/skills
ln -s /absolute/path/to/strings/skills/witsoc ~/.agents/skills/witsoc
ln -s /absolute/path/to/strings/skills/planning-with-files ~/.agents/skills/planning-with-files
```

Repository-level selected skills:

```bash
mkdir -p .agents/skills
ln -s /absolute/path/to/strings/skills/autoresearch .agents/skills/autoresearch
ln -s /absolute/path/to/strings/skills/witsoc .agents/skills/witsoc
```

For shared repositories, prefer copying or vendoring a pinned subset over
committing symlinks to a developer's local path.

Codex project instructions use `AGENTS.md`. If a project uses this repo as a
workflow source, put only durable project rules in `AGENTS.md`; put reusable
procedures in skills. Codex custom agents live under `.codex/agents/` for a
project or `~/.codex/agents/` for a user.

Use patterns:

- Invoke a skill explicitly with `$skill-name` when the workflow must run.
- Let implicit invocation work only when the skill description is crisp enough.
- Use custom agents for role definitions such as reviewer, explorer, worker, or
  mathematical scout.
- Use plugins only when distributing stable bundles that include multiple
  skills, MCP configuration, hooks, or app integrations.

## Claude Code

Claude Code also supports Agent Skills. Project skills live under
`.claude/skills`; personal skills live under `~/.claude/skills`.

Project-level selected skills:

```bash
mkdir -p .claude/skills
ln -s /absolute/path/to/strings/skills/witsoc .claude/skills/witsoc
ln -s /absolute/path/to/strings/skills/autoresearch .claude/skills/autoresearch
```

Personal selected skills:

```bash
mkdir -p ~/.claude/skills
ln -s /absolute/path/to/strings/skills/notes-use ~/.claude/skills/notes-use
```

Claude Code reads `CLAUDE.md`, not `AGENTS.md`. When a repository already uses
`AGENTS.md`, create a small bridge file:

```md
@AGENTS.md

## Claude Code

Use Claude-specific notes here only when needed.
```

Claude Code subagents live under `.claude/agents/` for a project or
`~/.claude/agents/` for a user. Use the canonical files under `agents/osci-*`
as source material, then adapt them to Claude Code's Markdown-frontmatter
format.

Use patterns:

- Invoke a skill directly with `/skill-name` when you want a specific workflow.
- Keep `CLAUDE.md` for facts and rules that should load in every session.
- Move multi-step procedures from `CLAUDE.md` into skills.
- Use subagents when a role needs isolated context, tool restrictions, or a
  different model.

## Generic Agent Skills Clients

Generic clients should follow the Agent Skills pattern:

1. Discover skills by reading only `name` and `description` from `SKILL.md`.
2. Activate a skill when the user names it or the task matches its description.
3. Load the full `SKILL.md` only after activation.
4. Load `references/`, `scripts/`, and `assets/` only when the activated skill
   says they are needed.

Clients that do not support scripts should still benefit from instruction-only
skills. Script-heavy skills should declare dependencies in frontmatter or near
the top of the body.

## Recommended Install Profiles

| Profile | Skills |
|---|---|
| `research` | `autoresearch`, `autoresearch-worker`, `autoresearch-hypothesizer`, `planning-with-files`, `notes-use` |
| `math` | `witsoc`, `planning-with-files`, `sandbox-use` |
| `machine` | `machine-setup`, `machine-use` |
| `sandbox` | `sandbox-use` |
| `general` | `planning-with-files`, `notes-use`, selected `packages/skills/*` |

Future adapter scripts should expose profiles instead of asking users to link
everything manually. A reasonable command shape would be:

```bash
scripts/install-harness.sh codex --scope user --profile research
scripts/install-harness.sh claude-code --scope repo --skills witsoc,planning-with-files
scripts/install-harness.sh codex --scope repo --agents osci-worker,osci-scout
```

The script should be a thin installer: validate paths, link or copy selected
skills, generate harness-specific agent files, and print what it changed. It
should not rewrite the source skills.

## References

- Agent Skills specification: https://agentskills.io/specification
- Codex skills: https://developers.openai.com/codex/skills
- Codex `AGENTS.md`: https://developers.openai.com/codex/guides/agents-md
- Codex subagents: https://developers.openai.com/codex/subagents
- Claude Code skills: https://code.claude.com/docs/en/skills
- Claude Code subagents: https://code.claude.com/docs/en/sub-agents
- Claude Code memory and `CLAUDE.md`: https://code.claude.com/docs/en/memory
