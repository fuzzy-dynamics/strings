# Strategy Doctrine (advisory)

These are strategy-layer practices, not contracts. Load this when planning a
nontrivial exploration. Nothing here overrides the contract layer (freeze,
authorization, gates, status discipline); it shapes *how the agent chooses*
within those bounds. See `SKILL.md` for the contract/strategy split.

## Capability Discovery Loop (retrieval before invention)

Witsoc is deliberately lazy: expertise lives in retrievable stores, not in
prompt text. For any hard step, run the loop:

1. **Identify the missing knowledge** — a status, a technique, a lemma, a
   counterexample family, an encoder, a domain playbook.
2. **Search the memory stores and atlases** — lemma library, proof bank,
   technique atlas, Mathlib atlas, the two-part knowledge store
   (`references/knowledge-stores.md`), literature engine, ontology mappings.
3. **Retrieve candidate techniques and skills** — including from analogous
   domains and similar solved problems; treat retrieved skills as composable
   building blocks, and expand them recursively when they point further.
4. **Surface ≥2 candidate approaches** whenever the step is nontrivial, each
   with applicability conditions, tradeoffs, historical precedent, and a
   confidence note stating what would lower it. Selection stays with the
   reasoning agent. `witsoc decide options --statement "<goal>"` assembles
   this table from the LIVE stores (technique atlas, L5 priors, L4 failure
   warnings, past decisions at this point) with a recommended default — use
   it instead of reciting doctrine from memory. Record nontrivial choices
   (`witsoc decide record`) and their outcomes (`witsoc decide resolve`):
   resolved decisions feed the priors, so defaults are LEARNED from what
   actually worked. Contracts are never decision points.
5. **Expand promising branches; recurse** when a branch reveals new missing
   knowledge.

Prefer discovering and adapting an existing technique before assuming novel
mathematics is required: many hard steps fall to a transferred method. The
standing question is *"what successful technique from another context could
work here?"* The full playbook — resource map, transfer checklist,
candidate-approach template, branch ledger — is
`references/core/technique_discovery.md`.

## Tree Search Over Linear Plans

Avoid premature commitment to a single strategy. The machinery for this
exists — use it as a portfolio manager, not a formality:

- keep several hypotheses/sketches alive (`scripts/sketch_population.py`,
  `scripts/sketch_tournament.py`; EV-ranked sketches in handoffs),
- compare competing techniques on the same node (distinct method families
  across workers),
- track dead ends with *revival conditions*, not just failure labels (retry
  ledger, failure memory, `do_not_repeat` entries should record what new
  evidence would justify revisiting),
- revisit previously discarded approaches when new evidence appears — a new
  lemma, a refuted obstruction, or a fresh counterexample family changes the
  EV landscape.

A linear plan is a special case the agent may choose for cheap targets — not
the default shape of serious work.

## Primitives Over Wrappers

Prefer composing general primitives (search, enumerate, mine, prove, check,
certify, remember) over reaching for a narrow wrapper that hides the
decision. The deterministic scripts form a capability catalog, organized by
what each primitive does, when it applies, what evidence grade its output
carries, and what it composes with: `references/core/capability_catalog.md`.
Novel compositions are encouraged; the only non-composable layer is the
contract layer (an LLM never substitutes for a structural check, receipt
parse, or kernel verdict).
