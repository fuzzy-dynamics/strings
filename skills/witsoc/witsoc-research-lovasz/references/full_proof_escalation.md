# Full-Proof Escalation Protocol

Use this before Lovasz attempts to turn partial progress on an open problem into a full proof. The default is not to escalate.

## Escalation Criteria

All must hold:

- exact target and variant are frozen,
- source triage does not show the target already solved or false,
- all named barriers are addressed, bypassed, or converted into lemmas,
- no small counterexample or boundary failure remains unexplained,
- proof sketch has explicit dependencies and low gap count,
- external facts have exact statements and audited preconditions,
- Explorer can produce a coherent proof object or lemma DAG,
- Generator target can be stated narrowly without changing the theorem,
- SafeVerify target-freeze checks can be run or approximated.

## Escalation Record

```markdown
### Full-Proof Escalation
- Frozen theorem:
- Why partial mode is insufficient:
- Barriers discharged:
- Remaining gaps:
- Counterexample search summary:
- Dependency audit:
- Explorer proof object:
- Generator artifact plan:
- Escalation verdict: allowed | rejected | defer
```

## Rejection Rules

Reject escalation if:

- the proof depends on a conjecture,
- a barrier is only waved away,
- the theorem statement drifted during exploration,
- the target is a famous open problem and only local evidence exists,
- the proposed artifact would prove a weaker theorem than the frozen target.

When rejected, choose a narrower product: special case, conditional theorem, obstruction, computation, reduction, or failed attempt.
