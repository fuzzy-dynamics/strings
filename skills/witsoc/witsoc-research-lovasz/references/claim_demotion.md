# Claim Demotion Protocol

Use this whenever verification, counterexample search, Explorer, Generator, or Lean weakens a claim. Demotion preserves useful research instead of hiding failure.

## Demotion Ladder

```text
VERIFIED -> CHECKED -> PROVED_SKETCH -> PARTIAL -> CONJECTURE -> pattern -> FAILED_ATTEMPT -> REJECTED
```

Move only as far down as the evidence requires.

## Common Demotions

- theorem -> `PROVED_SKETCH`: proof is coherent but lacks formal artifact.
- theorem -> `PARTIAL`: only a special case, bounded case, or conditional statement survives.
- theorem -> `CONJECTURE`: examples support it but a proof gap remains.
- conjecture -> `pattern`: statement is too vague or scope is unclear.
- proof -> `FAILED_ATTEMPT`: method fails but teaches a reusable blocker.
- claim -> `REJECTED`: false, circular, contradicted, or source-mismatched.
- broad problem -> `obstruction`: the best product is a barrier theorem or counterexample.

## Demotion Record

```markdown
### Demotion D<N>
- Original claim:
- Previous status:
- New status:
- Trigger:
- Evidence:
- Surviving weaker statement:
- Actual barrier lemma affected:
- Why the weaker statement still helps or why it does not:
- Barrier learned:
- Memory update:
- Next product:
```

## Rules

- Never delete the original failed claim; mark it demoted.
- Preserve the strongest true weaker statement.
- Do not let the weaker statement become the main target unless it is explicitly marked `PARTIAL` or `CONDITIONAL` and the original frozen target remains open.
- Demotion must name the actual barrier lemma or obstruction that blocked the original claim.
- If a counterexample exists, minimize and record it.
- If the failure is a hidden hypothesis, create a conditional theorem candidate.
- If Generator fails because the target drifted, restore the frozen target and demote the artifact, not the original theorem silently.
- Write reusable demotions to `lovasz.soc` under `INSIGHTS` or `FAILED_APPROACHES`.
