# Discovery Engine and Learning Loop

This protocol covers the real construction/counterexample search engine and the
compounding memory loop. It is the part of Witsoc that actually *finds* objects
(constructions, counterexamples, bounds) for Erdos-style extremal and existence
problems, rather than only orchestrating prose.

Principle: **generation is cheap and untrusted; the evaluator is the moat.** No
LLM ever judges a candidate. A candidate is scored by an exact, deterministic
evaluator, and only validity-preserving improvements survive.

## When to use

- The frozen target is an extremal or existence question with an explicit finite
  witness: "is there an object of size k with property P?", "improve the best
  known lower bound", "find a counterexample to this (possibly false) variant".
- Domains: additive combinatorics (cap sets, sets with no 3-term AP, Sidon sets),
  extremal/Ramsey graph theory (triangle-free high-chromatic graphs), and any
  problem reducible to maximising a deterministic fitness over a finite universe.

A bounded construction is a `CHECKED` existence witness or counterexample. It is
never an asymptotic or general proof. Promote it to a WIT/Lean artifact for a
theorem-level claim.

## The loop (FunSearch / AlphaEvolve shape)

```
propose candidate object  ->  HARD deterministic evaluator scores it
       ^                                        |
       |                                        v
 sampler (LLM or operators)  <--  island-model selection + periodic reset
```

Entry points:

- `scripts/discovery_engine.py` — island-model evolutionary search with
  checkpointing (resume-friendly). `init` / `run` / `status` / `best`.
- `scripts/discovery_evaluators.py` — the exact evaluators (the moat) and their
  independent verifiers. `cap_set`, `no_three_ap`, `sidon_set`,
  `triangle_free_chromatic`. Each exposes `seed/mutate/crossover/evaluate/verify`.
- `scripts/discovery_sampler_example.py` — reference implementation of the
  external **LLM-as-mutation-operator** protocol (the `--sampler 'cmd:...'`
  plug point). Wire your model here; the engine still gates every reply through
  the evaluator.
- `scripts/counterexample_search.py` — front-end: emits search-template packets
  (legacy) and, with `--run-evaluator` / `--mode engine`, drives the real engine
  end to end.

Minimal run:

```bash
python3 discovery_engine.py init <run>/discovery/no_three_ap --evaluator no_three_ap --params '{"n":120}'
python3 discovery_engine.py run  <run>/discovery/no_three_ap --generations 300
python3 discovery_engine.py best <run>/discovery/no_three_ap --write <run>/discovery/no_three_ap/best.json
```

With an external LLM sampler:

```bash
python3 discovery_engine.py run <run>/discovery/cap_set --generations 300 \
  --sampler 'cmd:python3 my_llm_sampler.py'
```

The engine fans out naturally across islands; this is the workload the
Temporal/worker infrastructure is meant to parallelise.

## Upgraded evaluators (real tools, graceful fallback)

Each backend uses a real external tool when installed and degrades honestly when
not, always reporting which path ran:

- `scripts/finite_graph_backend.py --backend auto|nauty|brute` — nauty `geng`
  canonical (non-isomorphic) generation when available, else brute force.
- `scripts/smt_synthesizer.py --dimacs ...` — industrial CDCL (CaDiCaL/Kissat)
  with a **DRAT proof checked by drat-trim**, so UNSAT becomes a checkable
  certificate (`claim_status: RECEIPT_ACCEPTED`), not "the solver said so". Falls
  back to the z3 SMT path.
- `scripts/number_theory_backend.py` — verified arithmetic certificates
  (factorisation with product check, deterministic Miller-Rabin, sigma/perfect
  classes, Erdos-Straus witnesses), cross-checked against PARI/GP when present.
- `scripts/flag_algebra_backend.py` — exact rational PSD test and SOS/flag
  certificate verifier. Finding the SDP matrix Q needs an external solver
  (CSDP/SDPA/cvxpy); **verifying** a rational Q is exact and is implemented here.
  Round a numerical Q to rationals and `verify-bound` before claiming any
  flag-algebra density bound.

## Learning loop: compounding verified memory

Runs must not be stateless. Two components turn one-shot results into memory:

- `scripts/lemma_library.py` — persistent, semantically-searchable lemma store
  (SQLite). **WIT is the primary record of every lemma**; Lean is layered on as a
  stronger trust tier:

  ```
  WIT_STRUCTURE  (wit check)      rank 1   <- base, WIT remains the engine
  WIT_RECEIPT    (semantic review) rank 2
  LEAN_VERIFIED  (lake build/lean) rank 3   <- strongest, machine-checked
  ```

  Search ranks by token-cosine similarity times a Lean-significance boost, so
  verified lemmas surface first; `--require-lean` restricts to `LEAN_VERIFIED`.
  `verify-lean` runs the real Lean toolchain (`lean` / `lake build`) and upgrades
  the tier on success. Future runs query the library before re-deriving a lemma.

- `scripts/trace_harvester.py` — captures the reward signal for expert iteration.
  It walks a run/session tree and the lemma library and emits
  `training_traces.jsonl` of `(problem -> solution, reward)` records, where reward
  is derived ONLY from machine-checkable status (LEAN_VERIFIED/RECEIPT_ACCEPTED =
  1.0 down to FAILED_ATTEMPT = 0.0; negatives are kept because they train too).
  This is the dataset a fine-tuning / RL job consumes to make the proposer better
  over time. The Lean kernel and the evaluators are the reward; this harvests it.

## Reporting discipline

- Discovery results are `CHECKED` constructions/counterexamples with an attached
  independent verifier, never `VERIFIED`.
- A flag-algebra bound is `RECEIPT_ACCEPTED` only after `verify-bound` passes on a
  rational certificate; a numerical-only Q is not acceptable.
- Promote a construction to a theorem claim only through WIT and, for the strong
  gate, Lean — at which point it enters the lemma library as `LEAN_VERIFIED` and
  contributes a maximal-reward training trace.
