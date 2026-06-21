# Authoring Portable Workflows

The goal is to make workflows useful outside one product. A good workflow in
this repo can be loaded by OpenScientist, Codex, Claude Code, or a generic
Agent Skills client with minimal adapter code.

## Choose The Right Artifact

| Artifact | Use it for | Avoid using it for |
|---|---|---|
| `SKILL.md` | Reusable procedures, domain knowledge, checklists, and task-specific instructions | Whole-repo policy that should load every session |
| `references/` | Longer background, schemas, examples, playbooks, and domain notes | Steps that must always be read before using the skill |
| `scripts/` | Deterministic commands that reduce ambiguity or handle tedious mechanics | Logic that only works in one local checkout without saying so |
| `assets/` | Templates, fixtures, images, sample data, static resources | Generated run output |
| Agent role | A reusable persona or worker type with a bounded job | A one-off task prompt |
| Harness adapter | Installation paths, generated agent manifests, MCP or hook glue | Core workflow logic |

## Skill Structure

Every portable skill should keep this shape:

```text
skill-name/
  SKILL.md
  references/
  scripts/
  assets/
```

Only `SKILL.md` is required. Use the optional directories when they preserve
progressive disclosure.

Recommended frontmatter:

```md
---
name: skill-name
description: Action-oriented trigger text. Say what the skill does and when to use it.
compatibility: Works in Codex, Claude Code, OpenScientist, and generic Agent Skills clients. Requires git and jq.
metadata:
  maintainer: openscientist
  portability: portable
---
```

Rules:

- The `name` should match the directory name.
- Put the strongest trigger words in the first sentence of `description`.
- Say when not to use the skill if accidental invocation would be expensive.
- Keep `SKILL.md` concise. Move long details to `references/`.
- Reference files by relative path from the skill root.
- Do not rely on a second skill being loaded unless the instructions explicitly
  tell the agent to activate or read it.

## Writing Workflow Instructions

Write instructions as operational steps, not background narration.

Prefer:

```md
1. Inspect the target repository's test commands before editing.
2. Create or update `plan.json` in the session directory.
3. Run the smallest verification command that covers the changed behavior.
```

Avoid:

```md
This skill helps the agent think carefully and be a good engineer.
```

A workflow should name:

- Inputs the agent needs.
- Files or directories it may read.
- Files or directories it may write.
- Commands it may run.
- Expected output or stopping condition.
- Escalation rules for ambiguity, missing dependencies, or failed checks.

## Script Contract

Scripts inside skills should be boring and predictable.

Each script should:

- Support `--help` or print usage on invalid arguments.
- Resolve sibling files relative to the script path, not the caller's CWD.
- Accept explicit paths and flags instead of assuming OpenScientist paths.
- Print machine-readable output when another tool will consume it.
- Send progress and diagnostics to stderr.
- Exit nonzero on failure.
- Avoid printing secrets.
- Check dependencies before doing stateful work.
- Be idempotent when possible.
- Offer `--dry-run` when it mutates external state.

For shell scripts, start from:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
```

Avoid hidden dependencies on:

- `$PLANE_TOOL_BIN`
- `~/.openscientist`
- frontend app paths
- a specific provider's tool names
- local secrets or untracked env files

If the script requires one of those, declare it in `compatibility` and near the
top of `SKILL.md`.

## Harness-Specific Notes

Keep harness-specific behavior in adapters.

Good:

- `docs/harnesses.md` explains where to install a skill for Codex or Claude
  Code.
- A future `scripts/install-harness.sh` links selected skills into the right
  dotdir.
- `docs/agents.md` shows how to render canonical agent roles into each harness.

Bad:

- A portable skill says "always call Plane" when a local script would work.
- A scientific package skill assumes OpenScientist's note tool exists.
- A Codex-only config file is copied into the source skill directory.

When a workflow really is product-specific, say so clearly:

```md
compatibility: OpenScientist Plane only. Requires PLANE_TOOL_BIN and a running plane server.
```

## Turning A Repeated Task Into A Skill

Use this path:

1. Write the task as a concrete prompt and run it manually once.
2. Save the commands, files touched, and verification steps.
3. Create `skills/<name>/SKILL.md`.
4. Move long examples to `references/`.
5. Move repeatable shell or Python mechanics to `scripts/`.
6. Test explicit invocation in at least one harness.
7. Test whether the description triggers correctly from a natural request.
8. Add compatibility notes for missing tools or harness limits.

## Turning A Command Into A Workflow

Do not add a bare script without teaching agents when and how to use it.

Pair scripts with skill instructions:

```text
skills/my-workflow/
  SKILL.md
  scripts/run-check.sh
  references/output-schema.md
```

The `SKILL.md` should explain:

- When to run `scripts/run-check.sh`.
- What arguments it needs.
- What output means success or failure.
- What the agent should do after failure.
- Whether the script changes files or external state.

## Review Checklist

Before merging a workflow:

- `SKILL.md` has `name` and `description`.
- The description says when to use the skill.
- Harness-specific requirements are declared.
- Long references are outside the main skill body.
- Scripts have usage text and dependency checks.
- Scripts do not print secrets.
- The skill can be installed as a selected folder into Codex or Claude Code.
- Generated output is not committed.
- The workflow has a clear success condition.
