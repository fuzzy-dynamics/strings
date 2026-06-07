# Full Proof Campaign Protocol

Use this only after disproof-first search, product-ladder work, and full-proof escalation indicate the original open target may be attackable.

## Campaign Preconditions

All must be recorded:

- frozen target,
- source/variant status,
- disproof-first search summary,
- at least one successful partial product or structural mechanism,
- barrier map with bypass plan,
- proof gap ledger initialized,
- theorem retrieval spine,
- formalization feasibility notes.

## Independent Proof Routes

Run at least three materially distinct routes when possible:

```markdown
### Route R<N>: <title>
- Method family: extremal | minimal_counterexample | probabilistic | algebraic | spectral | analytic | reduction | computational_certificate | induction | compactness
- Central mechanism:
- Key lemmas:
- External facts:
- First hard gap:
- Counterexample pressure:
- Formalization risk:
- Status:
```

Default route set:

- one structural/minimal-counterexample route,
- one analytic/algebraic/probabilistic route appropriate to the domain,
- one reduction or computational-certificate route.

## Campaign Control

- Do not split into many cosmetic variants of the same method.
- Use `proof_gap_ledger.md` for every unresolved bridge.
- If two routes share the same gap, promote that gap to a named barrier.
- If a route closes a key lemma, send that lemma to Explorer/Generator before claiming the full theorem.
- If all routes fail, preserve the strongest partial product and update `.soc`.

## Exit

Exit campaign mode with one of:

- full proof candidate ready for skeptic pass,
- disproof witness ready for certificate,
- partial product ready for artifact,
- barrier/obstruction result,
- failed-attempt synthesis.
