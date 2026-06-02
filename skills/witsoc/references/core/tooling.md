# Tooling Discipline

Prefer explicit, deterministic tools over model-written shell incantations.

## WIT Tooling

Preferred future interface:

- `run_wit_init`
- `run_wit_check`
- `run_wit_audit`
- `run_wit_context`
- `run_wit_verify`
- `run_wit_receipt`
- `run_wit_status`
- `run_wit_cycle`
- `run_target_freeze_check`
- `run_handoff_validate`

When typed API tools are unavailable, use the existing deterministic scripts or native `wit` CLI. Do not use an LLM for structural checking, context building, status parsing, receipt parsing, or target-freeze checks.

## CLI Consolidation Target

The shell scripts are a compatibility layer. Long term, consolidate WIT cycle behavior into a single typed CLI, preferably Rust or Go, so multiline mathematical content, structured handoffs, target hashes, receipts, and verifier contexts are handled deterministically.

Suggested shape:

```text
witsoc init --handoff runs/task/handoff.json --out runs/task/artifact.wit
witsoc check runs/task/artifact.wit
witsoc cycle runs/task/artifact.wit --handoff runs/task/handoff.json --out runs/task/
witsoc freeze-check runs/task/artifact.wit --handoff runs/task/handoff.json
witsoc handoff validate runs/task/handoff.json
witsoc receipt runs/task/artifact.wit --from verifier.txt
```

Until such a binary exists, report the exact script or CLI command used and its status.
