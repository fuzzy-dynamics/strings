# SafeVerify

SafeVerify prevents proof artifacts from succeeding by changing the target.

## Target Freezing

Before proof generation or repair, freeze:

- original user problem text,
- canonical theorem statement,
- variables and domains,
- definitions,
- `GIVEN` block,
- `CLAIM` block,
- allowed external facts,
- artifact scope for open-problem partial results.

Record hashes in `handoff.json` or beside the artifact:

```json
{
  "target_freeze": {
    "source_text_sha256": "...",
    "canonical_target_sha256": "...",
    "given_block_sha256": "...",
    "claim_block_sha256": "...",
    "definitions_sha256": "..."
  }
}
```

Before semantic review, diff the final artifact against the frozen target. A mismatch is `REJECTED: target_drift` unless the user explicitly approved a new target.

## Anti-Cheating Rules

Reject artifacts that:

- use `sorry`, `admit`, `axiom`, `constant`, `opaque`, `unsafe`, or equivalent escape hatches,
- weaken the theorem to `True`, `Nonempty`, a toy proposition, or an easier domain,
- change definitions to make the theorem trivial,
- add hidden assumptions to theorem binders or helper lemmas,
- introduce fake bridge lemmas or postulated paper results,
- use comments as proof,
- claim full resolution of an open problem from a partial artifact.

Lean compiler success is necessary but not sufficient. WIT structural success is necessary but not sufficient.

