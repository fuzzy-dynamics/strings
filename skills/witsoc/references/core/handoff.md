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
INTAKE -> EXPLORER_TRIAGE
EXPLORER_TRIAGE -> DIRECT_ANSWER | EXPLORER_PROOF_PLAN | LOVASZ_BARRIER_PACKET
LOVASZ_BARRIER_PACKET -> LOVASZ_ATTACK -> EXPLORER_REVIEW
EXPLORER_REVIEW -> LOVASZ_BARRIER_PACKET | RESEARCH_HANDOFF_READY | HONEST_STOP
RESEARCH_HANDOFF_READY -> BLUEPRINT_READY -> VALIDATE_BLUEPRINT -> GENERATE_WIT -> CHECK_WIT -> BUILD_CONTEXT -> SEMANTIC_REVIEW -> RECEIPT -> OPTIONAL_LEAN -> REPORT
```

Allowed transitions:

- `CHECK_WIT` failure goes to `REPAIR_WIT` or `EXPLORER_REVIEW`.
- verifier rejection goes to `REPAIR_WIT` or `EXPLORER_REVIEW`.
- Lean/LSP/REPL failure goes to `REPAIR_LEAN` or `EXPLORER_REVIEW`.
- mathematical blockers in WIT/Lean repair go to `EXPLORER_REVIEW`; Explorer decides whether to send a new `LOVASZ_BARRIER_PACKET`.
- target drift or SafeVerify failure goes to `REPAIR_*` after restoring the frozen target.
- open-problem work may stop at `PARTIAL`, `CONDITIONAL`, `CONJECTURE`, `FAILED_ATTEMPT`, or `OPEN` with artifacts.
- `VALIDATE_BLUEPRINT` failure returns exact schema/DAG/precondition errors to Explorer before Generator is woken up.

Lovasz is not an intake state. Explorer must first freeze the target, triage status, and create a barrier packet. Generator is not a truth-arbitration state. It executes the accepted blueprint and reports checks, receipts, Lean status, and failures back to Explorer/top-level Witsoc.

## Completion Guard

For tasks asking to prove, disprove, solve, or deep-run an open-style target, a run is not complete when it only classifies the target as open, unsupported, or not proved by known results.

Completion requires one of:

- Explorer solved or disproved the frozen target as routine/known,
- Lovasz ran a barrier attack and Explorer reviewed the result,
- Generator produced and checked an accepted formal artifact,
- a concrete operational blocker prevented Lovasz dispatch and is recorded,
- Lovasz exhausted meaningful angles and returned a documented `FAILED_ATTEMPT`, `CONJECTURE`, `PARTIAL`, `CONDITIONAL`, or `OPEN` ledger.

For a known-open or conjecture-equivalent classification, a prose barrier artifact is not enough. Critic/review agents must reject proof/disproof deep runs unless the final state includes campaign evidence:

- `actual_lemma_queue` with exact missing lemmas,
- `proof_dependency_dag` containing an `actual_barrier_lemma` node,
- `barrier_attack_records` with at least two direct attacks or a concrete operational blocker,
- worker results for at least one counterexample/computation/miner/skeptic/formalizer path when worker spawning is available,
- skeptic review for accepted nodes,
- retry ledger for repeated methods,
- Explorer review of Lovasz output.

Critic/review agents must reject status-only reports for proof/disproof deep runs when no Lovasz proof-DAG, worker result, or barrier attack is present, and must also reject "known open, complete" reports that contain only a Lovasz barrier note without a campaign ledger or explicit dispatch blocker.

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
- `proof_dependency_dag`
- `worker_results`
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

For Lovasz-directed open-problem work, `proof_dependency_dag` records the decomposed subproblem nodes and dependency edges. Each node is one of: lemma, reduction, special case, obstruction, counterexample search, computational certificate, conditional theorem, or failed method to rule out. `worker_results` records each worker's subproblem statement, dependencies, WIT target, Lean target, session id, dedicated proof worktree, artifact paths, verification logs, cleanup status, and final status.

Each WIT/Lean proof artifact must be generated in a separate session-scoped proof worktree. Record `session_id`, `proof_id` or `node_id`, `proof_worktree`, `proof_worktree_dedicated`, and `worktree_status` for every worker result and final Generator artifact. Missing proof-worktree metadata is a validation failure for worker-generated WIT/Lean evidence and for final Generator artifacts.

Accepted Lovasz nodes and artifacts must also include target fidelity, skeptic review, retry/provenance, and hash evidence. Specifically: `target_fidelity`, `skeptic_review_id`, `wit_target_sha256`, `lean_target_sha256`, and `frozen_target_sha256` where WIT/Lean exists. Final Generator requires `final_synthesis_audit`; repeated Lovasz methods require `retry_ledger`; and open/unsolved/unconfirmed runs require `actual_lemma_queue`.

Accepted `VERIFIED` worker nodes require WIT artifact existence, Lean verification success from that WIT target, and SafeVerify target-preservation success. WIT structural checks alone are not enough.

Validation sequence:

```bash
VALIDATOR="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_handoff.py)"
python3 "$VALIDATOR" runs/<task>/handoff.json
python3 "$VALIDATOR" runs/<task>/handoff_v1.json
DAG_VALIDATOR="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_proof_dag.py)"
python3 "$DAG_VALIDATOR" runs/<task>/handoff.json
```

Generator prompt contract:

```text
Execute runs/<task>/handoff_v1.json into a .wit artifact.
Do not invent new helper lemmas unless a structural check explicitly fails.
Do not change target_formalization.
Do not cite any theorem outside external_dependencies.
```
