# Generator Harness (optional)

Moved here from `witsoc-generator/SKILL.md` during the R6.5 doctrine
compression — operational detail, load on demand.

Use the harness only when configured and appropriate:

```bash
export GEMINI_API_KEY=...
export WITSOC_HARNESS_INTERACTIVE_LEAN=1
cd witsoc
harness/env/bin/uvicorn harness.main:app --reload
```

Then POST to `/prove` with `problem_statement`, `max_wit_iterations`, and
`max_lean_iterations`.

The harness can run informal proof planning, WIT generation, deterministic
WIT checking, WIT semantic LLM review, Lean formalization, Lake build,
contract checks, and Lean semantic review. Harness WIT semantic acceptance
may be advisory depending on configuration; do not conflate it with a
`.wit.receipt.json`.
