# OpenScientist World Model Filesystem

## Meta
trigger: browse the /global/ knowledge base, read world model files (skills, tools, prompts, agents)
not_for: reading LOCAL project files (use Read/Glob/Grep), searching indexed documents (use search tool), reading notes (use notes tool)
cost: low
tools: filesystem__ls, filesystem__cat, filesystem__grep, filesystem__search

## Important: Local Files vs World Model Files

There are TWO separate file systems:

1. **Local filesystem** — your project files on disk. Use native tools: `Read`, `Write`, `Edit`, `Glob`, `Grep`, `Bash`.
2. **OpenScientist world model** — cloud-hosted knowledge base with skills, tool docs, prompts, and domain knowledge. Use these `files_*` / `filesystem__*` tools.

The world model is organized as:
- `/global/tools/` — tool documentation (arxiv, openalex, notes, etc.)
- `/global/skills/` — research workflow skills (paper-discovery, literature-review, etc.)
- `/global/prompts/` — discipline prompts (research-discipline, verification-standards, etc.)
- `/global/agents/` — agent definitions
- `/global/packages/` — domain-specific packages (qiskit, cirq, etc.)
- `/skills/` — space-specific skills (read/write)
- `/agents/` — space-specific agents (read/write)

You CANNOT read local project files with these tools. You CANNOT read world model files with local Read/Glob.

## Functions

### filesystem__ls
List files in a world model directory.
params:
  - directory (str, optional, default="/"): directory path to list
  - recursive (bool, optional, default=false): include all descendants
  - limit (int, optional, default=100): max entries to return

### filesystem__cat
Read a world model file's contents.
params:
  - path (str, required): file path to read

### filesystem__grep
Search for a text pattern in world model files.
params:
  - pattern (str, required): text pattern to search for
  - directory (str, optional, default="/"): directory to search in
  - case_insensitive (bool, optional, default=true): case-insensitive matching
  - limit (int, optional, default=50): max matching files to return

### filesystem__search
Full-text semantic search over world model file contents.
params:
  - query (str, required): search query
  - path_pattern (str, optional): path filter
  - limit (int, optional, default=10): max results

## Examples

files_cat(path="/global/tools/INDEX.md")
files_ls(path="/global/skills/", recursive=true)
files_grep(pattern="transformer", path="/global/")
run(tool="filesystem__search", params={"query": "how to search papers"})
