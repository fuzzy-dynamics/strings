# Structured Handoffs

Explorer-to-Generator handoffs must be structured data, not prose templates.

## State File

For nontrivial tasks, write two persistent files when Generator is needed:

```text
runs/<task>/handoff.json
runs/<task>/handoff_v1.json
```

`handoff.json` is the rich research state. `handoff_v1.json` is the strict Generator blueprint and is the only file Generator should execute into WIT. If only prose exists, Generator should request a structured blueprint before writing WIT.

The top-level Witsoc router treats the run as a state machine:

```text
INTAKE -> EXPLORE -> RESEARCH_HANDOFF_READY -> BLUEPRINT_READY -> VALIDATE_BLUEPRINT -> GENERATE_WIT -> CHECK_WIT -> BUILD_CONTEXT -> SEMANTIC_REVIEW -> RECEIPT -> OPTIONAL_LEAN -> REPORT
```

Allowed transitions:

- `CHECK_WIT` failure goes to `REPAIR_WIT` or `EXPLORE`.
- verifier rejection goes to `REPAIR_WIT` or `EXPLORE`.
- Lean/LSP/REPL failure goes to `REPAIR_LEAN` or `EXPLORE`.
- target drift or SafeVerify failure goes to `REPAIR_*` after restoring the frozen target.
- open-problem work may stop at `PARTIAL`, `CONDITIONAL`, `CONJECTURE`, `FAILED_ATTEMPT`, or `OPEN` with artifacts.
- `VALIDATE_BLUEPRINT` failure returns exact schema/DAG/precondition errors to Explorer before Generator is woken up.

## Schema

Use `references/schemas/handoff.schema.json` for research state and `references/schemas/witsoc-handoff-schema.json` for the strict Generator blueprint.

Blueprint required fields:

- `metadata`
- `target_formalization`
- `epistemic_context`
- `external_dependencies`
- `lemma_plan`
- `generator_directive`

The blueprint is intentionally smaller than the research state. It quarantines external theorems, freezes target boundaries, and gives Generator a DAG of exact steps.

Research-state required top-level fields include:

- `schema_version`
- `run_id`
- `state`
- `target`
- `artifact_target`
- `source_citations`
- `theorem_candidates`
- `rejected_theorem_candidates`
- `search_budget`
- `proof_compression`
- `sketches`
- `selected_sketch_id`
- `obligation_graph`
- `external_facts`
- `target_freeze`
- `status`

Each proof sketch includes EV ranking fields:

```json
{
  "theorem_fidelity": 0.9,
  "probability_of_completion": 0.5,
  "verifier_friendliness": 0.7,
  "expected_value": 0.315
}
```

Compute `expected_value = theorem_fidelity * probability_of_completion * verifier_friendliness`. Prioritize the highest-EV sketch unless a lower-EV sketch has a strategic reason that is recorded explicitly.

Validation sequence:

```bash
VALIDATOR="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_handoff.py)"
python3 "$VALIDATOR" runs/<task>/handoff.json
python3 "$VALIDATOR" runs/<task>/handoff_v1.json
```

Generator prompt contract:

```text
Execute runs/<task>/handoff_v1.json into a .wit artifact.
Do not invent new helper lemmas unless a structural check explicitly fails.
Do not change target_formalization.
Do not cite any theorem outside external_dependencies.
```
