# Claim Acceptance Contract

Use this protocol before Witsoc accepts, upgrades, reports, or sends any mathematical claim to Generator.

## Acceptance Conditions

A claim is accepted only if all required fields exist:

- stable `claim_id` or DAG `node_id`,
- exact statement,
- `target_hash`,
- dependency path to the frozen target,
- legal status under the status lattice,
- evidence receipt or checked artifact for the asserted status,
- skeptic review for strong claims,
- registered artifact path when an artifact is cited.

If any field is missing, the claim remains `OPEN`, `GAP`, `CONJECTURE`, `FAILED_ATTEMPT`, or `PARTIAL`.

## Status Classes

Research statuses:

- `OPEN`
- `CONJECTURE`
- `CHECKED_BOUNDED`
- `FAILED_ATTEMPT`
- `GAP`
- `REJECTED`

Acceptance statuses:

- `CHECKED_SYMBOLIC`
- `PROVED_SKETCH`
- `VERIFIED_WIT`
- `VERIFIED_LEAN`
- `VERIFIED_EXTERNAL`
- `PARTIAL`
- `CONDITIONAL`

Only the acceptance layer may assign acceptance statuses. Research workers may propose them, but they are not effective until the status lattice and evidence checks pass.

## Evidence Requirements

- `CHECKED_BOUNDED`: deterministic bounded computation with exact bounds and reproducible command.
- `CHECKED_SYMBOLIC`: deterministic symbolic or structural check.
- `PROVED_SKETCH`: coherent proof sketch with explicit dependencies and known gaps absent.
- `VERIFIED_WIT`: WIT artifact plus successful structural/verifier receipt as available.
- `VERIFIED_LEAN`: Lean build/check success plus SafeVerify/target-freeze success.
- `VERIFIED_EXTERNAL`: independent verifier or certificate with reproducible receipt.
- `PARTIAL`: explicit weaker/special/conditional target and dependency path to the original.
- `CONDITIONAL`: exact condition statement and proof of implication under those conditions.

## Forbidden Upgrades

Reject these upgrades unless a dedicated receipt and target-hash match exist:

- `CONJECTURE -> VERIFIED_*`
- `FAILED_ATTEMPT -> CHECKED_*`
- `OPEN -> GENERATOR_READY`
- `PARTIAL -> FULL_SOLUTION`
- `PROVED_SKETCH -> VERIFIED_LEAN`

Run `scripts/status_lattice.py` when available.
