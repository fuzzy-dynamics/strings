# Ideation Protocol (Mandatory Divergent Phase)

Run this phase for every open, unsolved, unconfirmed, or frontier-level target,
after the barrier landscape is profiled and before the sketch tournament or any
proof-DAG freeze. Its purpose is genuine idea generation: produce many candidate
directions the way a working mathematician does, before any convergent
filtering. Skipping ideation and going straight from barriers to decomposition
produces only template-shaped attacks.

Calibration spine (unchanged): ideation produces candidates, never claims. Every
idea is born `OPEN_UNFALSIFIED` / `SPECULATIVE`. Ideation allocates attention and
effort only; the kernel gate (`witsoc prove` / `lovasz-prover-dispatch` ->
`validate_prover_result`) remains the only way anything becomes `CHECKED` or
`VERIFIED`.

## The Divergent Quota

Before convergence, generate at least 15 distinct ideas spanning at least 4 of
the move classes below. Quantity before quality: do not filter, rank, or
criticize during generation. If the deterministic generators plus sampler cannot
reach the quota, record the honest shortfall in the ideation ledger rather than
padding with duplicates.

Run:

```bash
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/ideate.py)" \
  --target "<frozen informal statement>" \
  [--lean-target "<frozen Lean statement>"] --domain <domain> \
  [--barrier "<barrier 1>" --barrier "<barrier 2>"] \
  [--quota 15] [--sampler cmd:<command>] \
  --out runs/<task>/ideation.json [--run-dir runs/<task> --write]
```

Set `WITSOC_IDEATION_SAMPLER=cmd:<command>` to give the ideation phase an LLM
sampler by default. The sampler is untrusted: its ideas enter the same arena as
template ideas, forced `OPEN_UNFALSIFIED`, with forbidden tokens stripped.

## Move Classes

These are the cognitive moves of working mathematicians. Each idea must name its
move class; the selector enforces diversity across classes.

1. **examples_first** — compute before theorizing. Tabulate the relevant
   invariant on the smallest instances, the extremal instances, and the boundary
   instances. Route to `empirical_miner.py`, `research_search.py`, or a bounded
   script. Patterns found here feed `conjecture_to_lemma_pipeline.py`.
2. **wishful_lemma** — "what lemma do I wish were true?" State the dream bridge
   H even if it looks too strong; `speculative_arena.py` kernel-proves `H → T`
   to find which wish is sufficient, and `lemma_repair.py` debugs a refuted wish
   into a survivable one. The wish is never asserted.
3. **strengthen_to_prove** — inductive loading. A stronger, more uniform
   statement is often easier to prove (the induction hypothesis gets stronger
   too). Generalize literals to parameters, add the accumulator, strengthen the
   invariant.
4. **find_the_enemy** — characterize the object that would refute the claim.
   Assume a minimal counterexample and derive forced local structure; search for
   near-violating extremal witnesses. Route to `counterexample_search.py`,
   `construction_search.py`, `discovery_evaluators.py`.
5. **dualize_reformulate** — translate to an orthogonal language where the
   blocked operation becomes native (cuts/flows, additive/Fourier,
   combinatorial/spectral). Route to `ontology_pivot.py`, `smt_synthesizer.py`.
6. **invent_concept** — name the missing invariant that would make the proof
   trivial, then search for it: emit a grammar-search record and route to
   `definition_synthesis.py` (Invention Mode). New definitions are the deepest
   creative lever; they start as `CONJECTURE` until falsified and checked.
7. **vary_problem** — pose the nearby questions: stronger version (try to
   break it), weaker version (try to prove it), boundary case, finite/bounded
   version, split conjuncts. Route to `pose_variants.py` and
   `curriculum_portfolio.py` so easy variants harvest lemmas that compound
   toward the target.

## Convergence

After the quota is met, rank ideas by novelty (distance from the lemma library
and from each other) and specificity (a concrete `lean_statement` or
falsification test beats prose), keeping round-robin diversity across move
classes. The top ideas feed the sketch tournament (`sketch_tournament.py`) and
the actual lemma queue; the rest stay in `ideation.json` as a reservoir for
later loops. Re-rank the reservoir before generating fresh ideas in a new loop.

## Serendipity Lane

Reserve up to 20% of dispatch budget (`--serendipity-fraction`, default 0.2)
for high-novelty ideas with no recorded dependency path to the frozen target.
This is deliberate: stepping stones whose value cannot be predicted in advance
are how unexpected connections are found, and a rule that every worker must
trace to the actual barrier lemma structurally suppresses them.

Rules for the serendipity lane:

- entries carry `lane: "serendipity"` and
  `dependency_path_to_target: ["serendipity_lane", <target>]` so validators and
  reviewers can see exactly what they are;
- results harvest into the verified lemma library as stepping stones when the
  kernel checks them;
- a serendipity result is NEVER reported as progress on the frozen target and
  never appears in `explorer_return_packet.json` accepted products unless a
  later loop records a real dependency path;
- the lane is capped: serendipity dispatch must not exceed the configured
  fraction of the loop's dispatched workers.

## Anti-patterns

- Generating 15 cosmetic variants of one idea — the move-class diversity rule
  exists to prevent this.
- Filtering during generation ("that's probably false") — falsity is decided by
  the disproof-first pass and the kernel, not by taste during ideation.
- Treating a ranked idea as evidence — ranking is attention allocation only.
- Skipping ideation because a campaign template exists — templates seed the
  tournament, but the quota still applies to fresh targets.
