# Counterexample Certificate Protocol

Use this whenever Lovasz, Explorer, computation, or a solver finds a candidate disproof witness.

## Certificate Requirements

Every counterexample must include:

- exact target statement it refutes,
- witness in machine-readable form,
- human-readable description,
- verification script or hand-checkable calculation,
- minimization status,
- variant alignment check,
- source/status impact,
- artifact plan for WIT/Lean when feasible.

## Certificate Record

```markdown
### Counterexample CE<N>
- Refuted claim:
- Witness:
- Witness path:
- Verification command:
- Verification result:
- Minimality: minimal | locally_minimal | not_minimized | unknown
- Variant alignment:
- Why hypotheses are satisfied:
- Why conclusion fails:
- Independent check:
- Status: candidate | checked | verified | rejected
```

## Verification Rules

- Check hypotheses before checking conclusion failure.
- Minimize the witness when possible.
- Run an independent verifier script or second calculation.
- If the witness refutes only a stronger variant, demote that variant and keep the original target open.
- Do not call a disproof `VERIFIED` without a checked witness/certificate or formal artifact.

## Handoff

Send to Generator only after the witness is exact and the statement is narrow:

```text
Product type: counterexample
Artifact target: witness certificate
Status: CHECKED or PARTIAL unless formal receipt exists
```
