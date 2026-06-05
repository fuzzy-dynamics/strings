# Target Freeze And Mutation Protocol

Use this protocol whenever Witsoc, Explorer, Lovasz, Generator, WIT, or Lean refers to a theorem target.

## Canonical Target Record

Every serious run should maintain a canonical target record, preferably `target.json`:

```json
{
  "schema": "witsoc.target.v1",
  "target_id": "target:T",
  "statement": "",
  "normalized_statement": "",
  "target_hash": "",
  "source": "user | explorer | lovasz | generator",
  "status": "OPEN | ROUTINE | SOLVED | FALSE | UNDER_SPECIFIED | UNCONFIRMED",
  "normalization_version": "witsoc.target.v1",
  "created_at": ""
}
```

If `target.json` is unavailable, the frozen target and hash must be recovered from `handoff_v1.json`, `lovasz_run.json`, `proof_dependency_dag.json`, or the route state. Do not invent a new hash silently.

## Freeze Rule

After Explorer freezes the target:

- all proof-DAG nodes must carry the same `target_hash` unless they explicitly target a narrower accepted subclaim,
- all WIT/Lean artifacts must record the target hash used to generate them,
- all worker results and receipts must reference the target hash,
- Generator may not alter hypotheses, quantifiers, object classes, or conclusion strength.

## Target Mutation Rule

A target may change only through `target_mutation.json` or `target_mutations.jsonl`:

```json
{
  "schema": "witsoc.target_mutation.v1",
  "mutation_id": "M1",
  "old_target": "",
  "old_target_hash": "",
  "new_target": "",
  "new_target_hash": "",
  "mutation_kind": "rephrase | strengthen | weaken | specialize | generalize | repair_ambiguity",
  "reason": "",
  "authorized_by": "explorer | user",
  "weakens_original": false,
  "dependency_path_to_original": []
}
```

Weakening is allowed only as an explicitly classified partial product. It must not be reported as a solution to the original target.

## Consistency Checks

Before final reporting, scan all available target hashes in:

- `target.json`,
- `handoff_v1.json`,
- `lovasz_run.json`,
- `proof_dependency_dag.json`,
- `actual_lemma_queue.json`,
- `worker_results.json`,
- `generator_artifacts.json`,
- `witsoc_artifacts.json`,
- `explorer_return_packet.json`,
- `formalization_feasibility.json`.

If multiple hashes appear without a mutation record, stop and route to Explorer target-freeze repair.
