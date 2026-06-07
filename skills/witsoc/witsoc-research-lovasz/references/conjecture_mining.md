# Conjecture Mining Protocol

Use this when computations, examples, failed proofs, or boundary cases reveal a pattern. Conjectures guide research, but they do not count as proof.

## Sources Of Conjectures

- repeated small-case behavior,
- extremal examples with stable structure,
- failed proof step that would become true under a new hypothesis,
- counterexample to a stronger variant,
- equality cases in a bound,
- theorem precondition that appears stronger than needed,
- formalization failure exposing a missing lemma.

## Conjecture Record

```markdown
### K<N>: <conjecture>
- Scope:
- Evidence:
- Small cases tested:
- Stronger variants likely false:
- Weaker variants likely provable:
- Barrier addressed:
- First falsification test:
- Proof route if true:
- Value if false:
- Rank: HIGH | MEDIUM | LOW
- Status: live | demoted | rejected | promoted_to_claim
```

## Ranking

Rank a conjecture high only when it has:

- precise scope and quantifiers,
- evidence beyond one example,
- a clear falsification test,
- a relation to a named barrier,
- a plausible route to `PARTIAL`, `PROVED_SKETCH`, or `CHECKED`.

Rank it low if it is only aesthetic, broad, or hard to test.

## Strength Control

For each conjecture, generate:

- one stronger version and try to break it,
- one weaker version and try to prove or compute it,
- one boundary case where the conjecture almost fails.

If the stronger version fails, preserve the counterexample as an obstruction. If the weaker version works, promote it as the next research product candidate.

## Promotion And Demotion

- Promote to `PARTIAL` only with exact scope and evidence.
- Promote to `PROVED_SKETCH` only after a coherent proof sketch survives counterexample tests.
- Demote to `FAILED_ATTEMPT` when the conjecture depends on a false hidden assumption.
- Demote to `pattern` in `.soc` memory when useful but too vague for the claim ledger.
