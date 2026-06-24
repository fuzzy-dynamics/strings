# Production Gates

Use this protocol before final response on serious Witsoc runs.

## Before Final Answer

Check:

- route state is complete or the remaining phase is explicitly blocked,
- frozen target and target hash are stated,
- target-hash consistency has been checked,
- accepted statuses satisfy `claim_acceptance.md`,
- all cited artifacts are registered or their paths are shown,
- citations are calibrated per the top-level `Citation Calibration` rules: every status claim and load-bearing external theorem in the final answer cites a findable source, standard facts are not cited, and short answers carry no reference list,
- WIT/Lean status is stated exactly,
- final artifact block includes WIT, Lean, receipt, exact status flags, and plugin-open status,
- Lovasz return packet was reviewed when Lovasz ran,
- no delegated worker, verifier, or critic is still running (`harness_discipline.md`): collect every spawned result before reporting,
- Generator was authorized before artifact generation,
- report grade or production gaps are stated when Lovasz ran,
- final answer includes the achieved quality level.

## Production Complete

A run is production-complete only if:

- route complete,
- target frozen,
- no unexplained target mismatch,
- no illegal status upgrade,
- no accepted claim without evidence,
- no unregistered cited artifact,
- no required Lovasz phase skipped,
- no Generator handoff before Explorer authorization,
- final answer states exact verification level.

## Quality Levels

- `L0_DIRECT`: direct answer with reasoning.
- `L1_SKETCH`: informal proof sketch or disproof sketch.
- `L2_CHECKED_DERIVATION`: deterministic calculation, bounded check, or structural check.
- `L3_WIT_ARTIFACT`: WIT artifact produced.
- `L4_WIT_LEAN_ATTEMPTED`: WIT plus Lean attempted, not necessarily verified.
- `L5_WIT_LEAN_VERIFIED`: WIT plus Lean/SafeVerify verified.
- `L6_RESEARCH_PRODUCT`: Lovasz research product with verified/checked artifacts and Explorer review.

Do not imply a higher level than achieved.

## Report Shape

The final answer should state:

- result/status,
- exact target interpretation,
- achieved quality level,
- sources for status claims and load-bearing external theorems, cited once at point of use,
- artifact paths if generated,
- verification/check status,
- blockers or remaining gaps,
- next exact action when not complete.

For serious Witsoc, Generator, Lovasz, WIT, or Lean runs, include:

```text
Artifacts:
- WIT: <path|none>
- Lean: <path|none>
- Receipt: <path|none>
- Status: STRUCTURE_OK=<yes/no/not run>; CONTEXT_BUILT=<yes/no/not run>; RECEIPT_ACCEPTED=<yes/no/not run>; LEAN_VERIFIED=<yes/no/not run>
- Plugin: <opened/open failed/not attempted>
```
