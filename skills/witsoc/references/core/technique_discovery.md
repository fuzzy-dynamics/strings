# Technique Discovery and Transfer Playbook

Advisory (strategy layer). This is the playbook for the capability-discovery
loop named in the top-level `SKILL.md`: identify missing knowledge → search →
retrieve candidates → surface options → expand promising branches → recurse.
Nothing here overrides a contract; everything here is about lowering the cost
of finding a working approach.

Core principle: **retrieval before invention.** Many hard steps fall to an
adapted existing method. Before assuming a step needs new mathematics, spend
a bounded slice of budget asking *"what successful technique from another
context could work here?"* — and only then escalate to novel-theory mode.

## Resource Map (where techniques live)

Search these before re-deriving anything. Each row: what it stores, how to
query it, what grade its results carry.

| Store | Contents | Query | Result grade |
|---|---|---|---|
| Lemma library (`scripts/lemma_library.py`) | persistent verified/sketched lemmas, tiered WIT_STRUCTURE → LEAN_VERIFIED | semantic search; `--require-lean` for verified-only | as tiered |
| Proof bank (`scripts/proof_bank.py`) | successful proof artifacts and patterns | by goal shape | examples, not proofs of the new goal |
| Technique atlas (`analogical-transfer`, grown by `proof-autopsy` / `mathlib-autopsy`) | named techniques with applicability fingerprints from past kernel-verified closures | by structural analogy | candidate technique |
| Mathlib atlas (`scripts/mathlib_atlas.py`) | formal availability + module paths | query/signature | availability fact |
| Two-part knowledge store (`../knowledge-stores.md`) | reference atlas (read-only, curated) + live global library | `witsoc atlas` / `witsoc library` | as recorded |
| Literature engine (`scripts/literature_engine.py`) | dated source ledgers for status and known results | `witsoc literature triage` | sourced status (staleness-gated) |
| Ontology starter mappings (`exploration_strategy.md`) | structure → theorem-family hints | by detected structure | retrieval hint only |
| Domain playbooks (Lovasz `references/domain_playbooks.md`) | per-domain move repertoires | by domain | candidate moves |
| Campaign templates (`scripts/lovasz_campaign_template.py`) | seeds for recurring open-problem shapes | by target shape | seed, never proof |
| Goal cache (`goal_cache.md`) | previously attempted goals and outcomes | by goal hash | failure/success memory |
| Sibling skills and plugins | capabilities outside witsoc | skill discovery | read their instructions; treat as composable |

Recursive expansion: a retrieved resource that names a further skill,
reference, or technique you don't have loaded is a lead, not a dead end —
read it, and expand again if it points further. Bound the recursion with the
recorded search budget, not with reluctance.

## Transfer Checklist (run for hard or stuck steps)

For a difficult step, explicitly search for each of these before concluding
novel theory is required. Each found item becomes a candidate approach:

- **Structural analogies** — same shape in another domain (the ontology map
  and technique atlas are the indexes; `ontology-pivot` is the forced version
  after two failed native-domain attacks).
- **Technique transfers** — a method whose applicability fingerprint matches
  (e.g. discharging, polynomial method, entropy compression, container
  method, LTE) even if its home domain differs.
- **Known reductions** — is the step reducible to a solved or better-studied
  problem? (`reduction-hunt`, `smt_synthesizer` for finite gadgets.)
- **Equivalent formulations** — dual, complement, generating-function,
  Fourier, probabilistic reformulations (the problem theory's equivalent-
  formulations list; the mutation tracker's duality axis).
- **Invariants** — preserved/monotone quantities that trivialize the step
  (`definition-synthesis` for grammar-searched separating invariants).
- **Generalizations** — a stronger statement with a smoother induction
  (strengthen-induction-hypothesis axis; auto-generalization).
- **Special cases** — a settled subcase whose proof skeleton lifts.
- **Counterexample patterns** — known families that killed similar claims
  (counterexample search library; the enemy profile).
- **Proof skeletons** — past proofs of same-shaped goals (proof bank,
  proof-autopsy archive).
- **Literature connections** — is this step a named lemma in some survey?
  (literature engine; cite per the calibration rules.)

## Candidate-Approach Template

Whenever a nontrivial step admits more than one attack — and it almost always
does — surface the options instead of silently committing. Bad: "use
inclusion-exclusion." Better:

```json
{
  "step": "bound the number of bad configurations",
  "candidates": [
    {
      "approach": "inclusion-exclusion",
      "applicability": "few, structured overlap terms",
      "tradeoff": "exact but blows up with many terms",
      "precedent": "worked on the n=4 subcase (proof bank id ...)",
      "confidence": 0.6,
      "confidence_would_drop_if": "overlap terms are not nested"
    },
    {
      "approach": "first-moment / union bound",
      "applicability": "only an upper bound needed",
      "tradeoff": "lossy; may not reach the target constant",
      "precedent": "standard for existence variants",
      "confidence": 0.7,
      "confidence_would_drop_if": "the target needs the exact threshold"
    },
    {
      "approach": "generating functions",
      "applicability": "configurations decompose multiplicatively",
      "tradeoff": "needs a clean factorization; formalization risk higher",
      "precedent": "none in library",
      "confidence": 0.3,
      "confidence_would_drop_if": "no product structure found in 1 attempt"
    }
  ],
  "selected": "first-moment",
  "selection_reason": "cheapest probe; failure is informative for the others"
}
```

Rules of thumb: ≥2 candidates for any nontrivial step; every confidence
carries a falsifiable would-drop-if; the selection reason is recorded so a
later revisit knows what the choice was conditioned on. Selection always
stays with the reasoning agent.

## Branch Ledger (tree search discipline)

Serious work is a tree, not a line. Keep it honest and cheap to navigate:

- **Alive branches**: the sketch population with EV scores; cap by budget,
  not by an urge for a single story. Distinct method families on the same
  node beat redundant variants.
- **Dead ends**: record *why* dead and *what would revive them* —
  `{branch, killed_by, revival_condition}`. A `do_not_repeat` without a
  revival condition loses information; most "dead" approaches are dead
  conditional on current knowledge.
- **Revisit triggers**: a new verified lemma, a refuted obstruction, a new
  counterexample family, or a collapsed rival branch re-prices every EV —
  scan the dead-end ledger when one lands.
- **Comparison points**: when two branches disagree about a node's
  difficulty, that disagreement is itself evidence; route it to a skeptic or
  a cheap kernel probe rather than averaging it away.

The existing machinery implements this (sketch population/tournament, retry
ledger, gap feedback, enemy profile); the discipline this file adds is using
them as a live search tree rather than write-only compliance artifacts.

## Escalating to Novel-Theory Mode

Transfer-first has a bounded budget. Escalate to inventing new objects,
definitions, or lemma schemas when (record which trigger fired):

- the transfer checklist completed with no viable candidate,
- two transferred candidates failed with mechanisms (not just labels)
  recorded in the problem theory,
- or the barrier ledger names an obstruction that defeats the whole imported
  family.

Even then, invention is grounded: `definition-synthesis` (grammar search, not
prose) for new invariants, `ideate` with move-class divergence for new
attacks, `speculative-arena` for kernel-proved bridge hypotheses. New theory
enters as `OPEN_UNFALSIFIED`/`CONJECTURE` and earns status through the same
gates as everything else.
