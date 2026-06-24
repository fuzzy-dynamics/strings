# Primitive Capability Catalog

Advisory (strategy layer), except where a row is marked **contract**. This
catalog presents Witsoc's deterministic machinery as general, composable
primitives — organized by *what each one does*, not by which phase
traditionally calls it. Any composition that respects the contract layer is
legitimate, including ones no protocol file anticipates; record the
composition chosen and why. Exact invocations live in `tooling.md` and the
per-script `--help`.

Reading a row: **Primitive** (entry point) — what it does; *applies when*;
*output grade* (the ceiling of what its result can claim); *composes with*.

## Search & Retrieval

- **Lemma library** (`lemma_library.py`) — semantic search over persistent
  lemmas, trust-tiered WIT_STRUCTURE → WIT_RECEIPT → LEAN_VERIFIED. *Applies*:
  before re-deriving anything. *Grade*: as tiered. *Composes*: seeds provers,
  handoffs, the lemma pool; `verify-lean` upgrades tiers.
- **Proof bank** (`proof_bank.py`) — archive of successful proofs by goal
  shape. *Applies*: prompt/example seeding for provers and narrative agents.
  *Grade*: examples only. *Composes*: nexus, tiered-prove.
- **Mathlib atlas** (`mathlib_atlas.py`) — formal availability + module path
  lookup. *Applies*: before any Mathlib dependency enters a plan (contract:
  no match → availability `UNKNOWN`, search target only). *Grade*:
  availability fact. *Composes*: handoffs, external-fact records.
- **Literature engine** (`literature_engine.py`) — dated source ledgers for
  status claims; 90-day staleness gate. *Applies*: solved/open status, best
  known results. *Grade*: sourced status. *Composes*: barrier packets,
  novelty triage.
- **Knowledge stores** (`witsoc atlas` / `witsoc library` / `witsoc memory`)
  — curated reference atlas (read-only) + live global library + cross-run
  memory. *Applies*: start and end of every serious run. *Composes*:
  everything; promote = the only live→reference path.
- **Technique atlas** (`analogical-transfer`, fed by `proof-autopsy`,
  `mathlib-autopsy`) — techniques indexed by applicability fingerprint.
  *Applies*: stuck steps, transfer checklist. *Grade*: candidate technique.
- **Goal cache** (`goal_cache.md` machinery) — prior attempts on a goal hash.
  *Applies*: before any prover dispatch. *Composes*: retry discipline.

## Enumeration, Mining & Falsification

- **Research search** (`research_search.py`) — bounded falsification and
  witness search across number theory / graphs / finite models; `--inflate`
  grows a counterexample into an obstruction-family candidate. *Grade*:
  CHECKED at most, bounded scope. *Composes*: falsification passes, enemy
  profile, obstruction ledgers.
- **Empirical miner** (`empirical_miner.py`) — pattern mining over
  enumerated families. *Grade*: CONJECTURE/CHECKED bounded evidence.
  *Composes*: conjecture pipeline.
- **Finite graph backend** (`finite_graph_backend.py`) — exact bounded graph
  checks (nauty when present). *Grade*: CHECKED on the enumerated scope.
- **Number theory backend** (`number_theory_backend.py`) — verified
  arithmetic certificates (factorization with product check, Miller–Rabin,
  sigma classes, witness checks). *Grade*: CHECKED certificate.
- **Asymptotic analyzer** (`asymptotic_analyzer.py`) — deterministic
  asymptotic claim screening. *Applies*: every asymptotic claim before it
  becomes a proof path. *Grade*: rejection is REJECTED; unavailability is a
  precondition gap, never evidence.
- **Counterexample search** (`counterexample_search.py`) — front-end over
  the engine + evaluators for targeted refutation. *Composes*: dialectic,
  disproof-first.

## Construction & Synthesis

- **Discovery engine** (`discovery_engine.py` + `discovery_evaluators.py`) —
  island-model evolutionary search; generation cheap and untrusted, the exact
  evaluator is the moat; optional LLM-as-mutation-operator sampler. *Applies*:
  extremal/existence targets with a finite witness. *Grade*: CHECKED witness.
  *Composes*: program-evolve, lemma promotion to WIT/Lean.
- **Program evolution** (`witsoc evolve`) — FunSearch/AlphaEvolve-style
  evolution of `construct(n)` programs against exploit-hardened evaluators
  with independent re-verification. *Grade*: CHECKED records.
- **Formula synthesis** (`formula-synthesis`) — parametric witness-formula
  families (e.g. residue-class witness triples), whole-class statements via
  exact substitution, then kernel gating. *Grade*: CONJECTURE until the
  whole-class proof passes the kernel.
- **Definition synthesis** (`definition-synthesis`) — grammar search for
  separating invariants; the Invention Mode primitive (never invent a concept
  by prose). *Grade*: candidate definition, OPEN_UNFALSIFIED.
- **SAT / reduction hunt** (`sat`, `reduction-hunt`, `smt_synthesizer.py`) —
  encode finite instance families; CDCL with DRAT-checked UNSAT
  (RECEIPT_ACCEPTED certificates); `sat` = candidate gadget, `unsat`+core =
  obstruction evidence. *Applies*: rediscovery brackets, covering systems,
  Ramsey-type bounds, finite gadgets. *Composes*: computational_certificate
  DAG nodes.
- **Construction search** (`construction_search.py`) — direct search drivers
  for known construction shapes.

## Conjecture Machinery

- **Ideation** (`ideate.py`) — move-class divergence, sampler-fleet widened;
  generation unfiltered, the kernel stack filters. (Gate floor for open
  targets: ≥15 ideas, ≥4 move classes.)
- **Conjecture pipeline** (`conjecture_miner.py`, `conjecture-pipeline`) —
  mine → rank (`interestingness`, ordering only) → formalize via predicate
  registry → dispatch. *Grade*: CONJECTURE.
- **Speculative arena** (`speculative-arena`) — kernel-proved
  hypothesis→target bridges, leverage-ranked. *Grade*: bridge is VERIFIED
  conditional; hypothesis stays open.
- **Lemma repair** (`lemma-repair`) — counterexample-guided one-axis repair
  of refuted conjectures; survivors are CONJECTURE.
- **Variant posing** (`pose-variants`, `discovery-lift`) — self-play
  curriculum around a target; `cluster` attacks target + variants under one
  shared theory so rungs and refutations transfer.

## Proving & Formalization

- **Tiered prover** (`witsoc tiered-prove --tier light|medium|heavy`) —
  deterministic saturation → external prover fleet (kernel-replayed) → Nexus.
  *Grade*: kernel-passing closures only.
- **Nexus loop** (`witsoc nexus prove|formalize`) — fleet proposals iterating
  against real Lean compiler diagnostics with proof-bank examples embedded.
- **Dual narrative agent** (`witsoc narrative compose|ground`) — informal
  proof first, then step-by-step formal grounding; gaps feed the lemma pool.
  *Applies*: whole informal arguments.
- **Lemma pool** (`pool`, `witsoc retrieve build-corpus`) — bridging lemmas
  mined from real residual diagnostics; proved ones reused everywhere.
- **Decomposition** (`decompose_problem.py`, `sketch_tournament.py`,
  `sketch_population.py`, `result_ladder.py`) — competing decompositions and
  EV-ranked sketch populations; effort allocation only, never status.
- **Proof search** (`proof_search.py`), **structural induction** drivers,
  **wit→lean obligation** (`wit_to_lean_obligation.py`) — the kernel-facing
  floor.
- **Ontology pivot** (`ontology-pivot`) — functorial transfer to an
  orthogonal domain; new subgoals still point at the original target. (Gate
  floor: mandatory after two failed native-domain attacks on a barrier
  lemma.)

## Verification & Audit — **contract layer**

Not optional once a claim is made, and never LLM-substitutable: `wit check`
and structural checks, receipt parsing, `lake build` + SafeVerify
(`lean_verification.md`, `safeverify.md`), target-freeze checks, the
`validate_*` family (route state, handoffs, Lovasz phases/runs, proof-DAG
integrity, open-problem runs, mathematical solve), `solve_claim_protocol.py`,
report grading (`grade_witsoc_report.py`), status legality
(`status_lattice`), and the rediscovery benchmark (`witsoc rediscovery`) as
the only honest meaning of "top tier".

## Orchestration & Memory

- **Campaign driver** (`campaign_driver.py`) — one crank of the loop:
  preflight, dispatch, skeptic, gap feedback, theory update,
  dialectic, re-ideation, ledgers; `--finalize` for the production-gate
  sequence. *Applies*: sustained campaigns where turn discipline, not math,
  is the historical failure mode.
- **Problem theory** (`problem_theory.py`) — the living causal model:
  equivalent formulations, example zoo, enemy profile, failure mechanisms,
  main attack + stall point; embedded in every fleet prompt.
- **Gap feedback** (`proof_gap_to_barrier_feedback.py`) — **contract** floor
  for mutation-before-retry.
- **Barrier machinery** (`barrier_attack.py`, `rung_saturation`,
  `lovasz_top_tier.py`) — depth spine + breadth ladder + readiness audit.
- **Run ledger** (`run_ledger.py`, `run.sqlite3`), **trace harvester**
  (`trace_harvester.py`) — unified state and the machine-checkable reward
  record `(problem → solution, reward)` for expert iteration.
- **Self-play** (`witsoc self-play frontier-round`) — keeps the curriculum at
  the prover's frontier between campaigns.

## Composition Notes

- A primitive's output grade caps every downstream claim: a CHECKED witness
  piped into a prover does not make the general theorem CHECKED; a
  CONJECTURE-grade family kernel-verified for its whole class becomes
  VERIFIED for exactly that class.
- Prefer a pipeline of two general primitives over one narrow wrapper when
  both exist; prefer the wrapper when it carries a gate you would otherwise
  have to re-implement.
- When a needed primitive is missing, say so explicitly (`backend_pending`
  is honest) rather than simulating it in prose — and check sibling skills
  and plugins before concluding it doesn't exist.
