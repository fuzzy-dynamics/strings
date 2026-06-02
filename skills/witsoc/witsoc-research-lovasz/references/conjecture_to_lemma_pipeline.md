# Conjecture-To-Lemma Pipeline

Use this to convert patterns into proof obligations that Explorer and Generator can attack.

## Pipeline

```text
pattern -> conjecture -> falsification -> scoped conjecture -> special case -> lemma -> proof object -> artifact
```

## Record

```markdown
### Lemma Candidate L<N>
- Origin pattern:
- Conjecture:
- Falsification performed:
- Scoped lemma statement:
- Actual barrier/unlocked proof gap:
- Why this is not merely a weaker detour:
- Hypotheses:
- Dependencies:
- Proof strategy:
- Counterexample pressure:
- Formalization risk:
- Status: candidate | falsified | special_case | proof_sketch | artifact_ready
```

## Rules

- Do not send broad conjectures directly to Generator.
- First produce a scoped lemma with explicit hypotheses.
- If falsification finds exceptions, add them as hypotheses or demote.
- Prefer lemmas that unlock multiple proof gaps.
- Prefer lemmas that directly attack the actual barrier over convenient weaker variants.
- If no lemma survives, return a failed lemma schema record, not just "no lemma found."
- Store reusable lemma candidates in `lovasz.soc`.
