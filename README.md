# strings

The **global world-model** for [OpenScientist](https://github.com/fuzzy-dynamics/OpenScientist/releases/) — the source-of-truth bundle of agents, skills, tool docs, and sandbox specs that the OpenScientist agents load at runtime.

## What's inside

| Dir | What it is |
|---|---|
| `agents/` | 5 canonical agent specs — `osci-orchestrator`, `osci-worker`, `osci-scout`, `osci-hypothesizer`, `osci-general`. |
| `skills/` | 7 first-party skills — `machine-setup`, `machine-use`, `sandbox-use`, `autoresearch`, `autoresearch-worker`, `autoresearch-hypothesizer`, `planning-with-files`. |
| `tools/` | Reference docs for the OpenScientist cloud tools (arxiv, openalex, openreview, huggingface, search, notes, annotation, filesystem). |
| `sandboxes/` | Sandbox image specs — `alpine` and `math`. |
| `packages/skills/` | 109 packaged domain skills — scientific Python libraries, workflow skills, integrations. |
