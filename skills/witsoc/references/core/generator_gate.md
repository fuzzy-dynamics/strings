# Generator Gate

Use this protocol before invoking `witsoc-generator`.

## Generator Responsibility

Generator produces and repairs WIT/Lean artifacts. It does not change mathematical targets, upgrade claim status, decide open-problem truth, or invent missing proof dependencies.

## Required Before Generator

Generator may run only when:

- Explorer has frozen and accepted the target,
- `handoff_v1.json` exists for nontrivial targets,
- route state authorizes Generator,
- target hash is consistent,
- accepted claims have evidence under `claim_acceptance.md`,
- Lovasz return packet exists if Lovasz was required,
- formalization feasibility is not `POOR_FORMALIZATION_TARGET`,
- proof DAG integrity passes when a proof DAG exists.

## Do Not Use Generator

Do not invoke Generator when:

- the target is open/blocked and no Lovasz return packet exists,
- the accepted product is only a conjecture,
- the proof DAG has an open dependency required for the target,
- target hashes disagree without mutation records,
- Explorer has not authorized artifact generation,
- formalization score says `POOR_FORMALIZATION_TARGET`,
- the user asked for exploration only and no artifact is requested.

## Failure Routing

- WIT lint failure: Generator repair.
- Lean syntax/import/context failure: Generator repair.
- Lean theorem mismatch or missing mathematical lemma: Explorer repair.
- DAG integrity failure: Lovasz repair.
- Target hash mismatch: Explorer target-freeze repair.
- Repeated same failure: apply `failure_recovery.md`.
