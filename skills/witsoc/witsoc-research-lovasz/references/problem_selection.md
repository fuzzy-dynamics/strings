# Problem Selection Protocol

Use this before choosing a Lovasz research product or subproblem. The goal is not to choose the grandest target; it is to choose the target most likely to produce verified mathematical progress.

## Candidate Products

List 3-7 candidate products:

```markdown
## P<N>: <product title>
- Product type: special_case | bound | conditional_theorem | reduction | obstruction | counterexample | computation | conjecture | failed_attempt
- Statement:
- Relation to original problem:
- Actual barrier lemma targeted:
- How this product helps prove/disprove that lemma:
- Required background:
- Likely verification route:
- Likely WIT/Lean artifact:
- First decisive test:
```

## Scoring

Score each product from 0 to 5:

```markdown
| Product | Target fidelity | Actual-lemma leverage | Novelty | Tractability | Verification ease | Barrier leverage | Experimentability | Artifactability | Source confidence | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
```

Weights:

- Target fidelity: `3`
- Actual-lemma leverage: `3`
- Novelty: `1`
- Tractability: `2`
- Verification ease: `2`
- Barrier leverage: `2`
- Experimentability: `1`
- Artifactability: `1`
- Source confidence: `1`

Compute:

```text
total = 3*target_fidelity + 3*actual_lemma_leverage + novelty + 2*tractability + 2*verification_ease + 2*barrier_leverage + experimentability + artifactability + source_confidence
```

Select the highest total unless a lower-scoring product has a recorded strategic reason, such as exposing a suspected false variant or creating a reusable formal lemma. A high-tractability weak result cannot beat an actual-barrier lemma route unless the weak result has explicit actual-lemma leverage.

## Selection Rules

- Prefer narrow products with clear stop conditions.
- Prefer products that attack a named barrier.
- Prefer products that attack the actual missing lemma needed by the frozen target.
- Prefer products that can be checked by computation, WIT, Lean, or short independent proof.
- Penalize weaker variants unless their relation to the actual barrier lemma is explicit.
- Penalize products that depend on vague external theorems or broad literature claims.
- Penalize products whose failure would teach little.
- If all products score low, select `failed_attempt` or `obstruction` instead of forcing a proof target, but the record must still state the actual barrier lemma schema that failed.

## Output

Write the selected product to `research.md` and the rejected products to `lovasz.soc` under `INSIGHTS` or `FAILED_APPROACHES` if they contain reusable information.
