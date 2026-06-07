# Proof Gap Ledger

Use this for every candidate proof or disproof that has unresolved bridges. A proof attempt is not mature until the gap ledger is empty or every remaining gap is explicitly demoted.

## File

Write:

```text
runs/<task>/proof_gaps.md
```

## Gap Record

```markdown
### G<N>: <gap title>
- Claim needed:
- Where used:
- Dependencies:
- Known theorem candidates:
- Failed attempts:
- Counterexample search:
- Formalization risk:
- Owner: Lovasz | Explorer | Generator
- Status: open | reduced | blocked | discharged | demoted
- Discharge evidence:
```

## Rules

- Every phrase like "it remains to show", "standard", "clear", "by known theorem", or "should follow" becomes a gap unless an exact dependency is cited.
- If a gap is as hard as the original problem, stop full-proof escalation and select a narrower product.
- If a gap repeats across routes, promote it to `barriers.md`.
- Generator cannot receive a full-proof target while any essential gap is `open`, `blocked`, or `demoted`.
- Explorer may receive individual gaps as lemma-discovery targets.

## Empty Ledger Requirement

Before full proof/disproof acceptance:

- all essential gaps are `discharged`,
- discharged gaps cite proof, computation, source, WIT, Lean, or verifier evidence,
- nonessential gaps are explicitly marked as not needed after proof compression.
