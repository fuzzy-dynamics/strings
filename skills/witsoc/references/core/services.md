# Witsoc Service Boundary

Witsoc is the support platform; Lovasz is the candidate generator and barrier
attacker. One rule resolves every boundary question:

> **Witsoc never decides strategy; Lovasz never verifies itself.**

Witsoc exposes deterministic, certificate-emitting, strategy-free SERVICES.
Lovasz — the research director — decides what to call, when, and with what stop condition,
and what to try after a failure. Gates decide what to trust. Print the
machine-readable registry with:

```bash
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/witsoc.py)" services
```

## Roles

- `service`: a callable engine. Input in, certificate/result out. No service
  ever assigns trust, upgrades a status, or chooses the next move.
- `validator`: an honesty or audit gate. Demote-only; never upgrades.
- `candidate_generator`: Lovasz-owned campaign machinery. Candidate-generator
  entry points refuse bare invocation: they require a Lovasz run context
  (`--lovasz-run <dir>` with a `lovasz_run.json`) or an explicit `--standalone`
  opt-out, which is recorded in their output. Tests and module-level callers
  are unaffected.
- `scheduler`: portfolio-level launcher (`research-campaign`). It prepares
  per-problem Lovasz run contexts and launches campaigns; it does not drive
  engines directly.

## The service table

| Service | Script | Contract |
|---|---|---|
| `prove` | `close_obligation.py` | Kernel-gated prover. Emits a proof or an honest `OBLIGATION_OPEN`; statuses only via `validate-prover`. |
| `ledger` | `run_ledger.py` | R1 unified run ledger: one `run.sqlite3` per run with the DAG node as the single entity. `ingest` (idempotent, reads every legacy JSON ledger), `status` (single-pane), `nodes` (joined view), `consistency` (cross-ledger validators as queries), `export` (regenerate legacy files). Writers auto-ingest (R1.5). See `references/core/architecture.md`. |
| `memory` | `knowledge_store.py` | R4 knowledge substrate (`~/.witsoc/knowledge.sqlite3`): global cross-run failure memory (L4 — `sync-run` on Explorer return, consulted by dispatch automatically) and bandit priors by goal signature (L5 — campaigns read/write automatically). Attention only, never trust. |
| `run` | `campaign_driver.py` | R5 campaign driver: one Lovasz candidate loop turn as one command — in-process prover dispatch → gap feedback → **theory update (A1: a loop with no theory diff is flagged)** → L2 re-ideation (>50% failed => tournament seeded with gap classes + theory, kernel-probed) → L6 serendipity cap → ledger. `--finalize` runs the whole production-gate sequence; Lovasz emits candidates, gates accept. |
| `theory` | `problem_theory.py` | A1 problem theory: the living causal model per run — formulations, example zoo, enemy profile (counterexample structure theory), per-method failure MECHANISMS, main attack + stall point, versioned theory log. `prompt-context` is embedded in every fleet request. Attention machinery; asserts nothing. |
| `nexus` | `nexus_loop.py` | A3 Nexus loop: fleet proposals iterate up to N rounds against REAL Lean compiler diagnostics (`prove` for goals, `formalize` for statements); deterministic saturation runs first so models are spent only on what survives; the kernel replay is the only acceptance. |
| `dialectic` | `dialectic.py` | A2 Lakatos engine: every gap-feedback node with a `∀ n : Nat` form gets kernel-gated instance refutation — witnesses mark the node REFUTED_INSTANCE (repair, never re-prove) and feed the enemy profile; exhausted searches record bounded negative evidence. The driver runs it every loop. |
| `evolve` | `program_evolve.py` | A4 program-space construction evolution (FunSearch/AlphaEvolve recipe): fleet-mutated `construct(n)` programs; exploit-hardened evaluators (exact ints, admissibility = errors never scores, time budgets); parametric scoring across an n-grid; independent re-verification of any record. CHECKED-grade at most. |
| `cluster` | `cluster_campaign.py` | A6 cluster campaigns: pose stronger/weaker/boundary variants, attack the family under ONE shared problem theory; proved rungs become positive examples + library harvest, stronger-variant outcomes feed the enemy profile. The frozen target's status is untouched. |
| `rediscovery` | `rediscovery_benchmark.py` | A7 rediscovery benchmark: hidden answers grade only (oracle discipline); SOLVED_MATCH/BRACKETED/OPEN scoring, WRONG_VALUE = soundness alarm, expected-open calibration rows fail the run if "solved". The measured meaning of "top tier". |
| `olympiad` | `olympiad.py` | Local-first olympiad fast lane: profile domain/style, run bounded kernel-gated proving, report search cost, and fall back to Lovasz solved-class mode on non-closure. |
| `open-rungs` | `open_rungs.py` | Rung-first open-problem target builder: emits special cases, bounded searches, reductions, and obstruction targets; never upgrades the original open problem. |
| `rung-saturation` | `rung_saturation.py` | Deterministic open-problem rung saturation: expands seed rungs, domain barrier families, formal probes, bounded searches, and theorem-precondition bridges into scored `OPEN_UNFALSIFIED` obligations. |
| `barrier-attack` | `barrier_attack.py` | Lovasz V2 barrier campaign prep: writes `barrier_attacks.json`, `rung_saturation.json`, DAG nodes, and lemma-queue entries for named barriers and partial rungs. It never upgrades trust; driver loops attack the generated obligations. |
| `lovasz-top-tier` | `lovasz_top_tier.py` | Top-tier Lovasz preparation/audit for items 2-12: barrier core, saturated rungs, hole-free Lean, strict roles, failure memory, novelty/literature discipline, solve protocol, engine portfolio, self-improving loops, rediscovery, and explicit success metrics. |
| `lovasz-agent-packets` | `lovasz_agent_packets.py` | Strict coordination packet templates/validation for Builder, Destroyer, Reducer, Formalizer, Historian, Strategist, and Skeptic roles. Packets may propose or critique; they cannot assert `CHECKED`/`VERIFIED`/solve statuses. |
| `lovasz-state` | `lovasz_campaign_state.py` | Derived Lovasz campaign health state across barrier, rung, DAG, worker, feedback, mutation, score, theory, and Explorer ledgers. |
| `lovasz-doctor` | `lovasz_doctor.py` | Campaign doctor that reports `GREEN`/`YELLOW`/`RED`, blockers, warnings, and exact next actions for barrier-depth campaigns. |
| `lovasz-loop-health` | `lovasz_loop_health.py` | Detects stuck Lovasz loops with no theory diff, mutation, score improvement, or learning signal. |
| `lovasz-mutation-ranker` | `lovasz_mutation_ranker.py` | Ranks one-axis mutations from gap class and prior mutation history; attention only. |
| `validate-lovasz-worker-quality` | `validate_lovasz_worker_quality.py` | Checks worker results for target hash, dependency path, candidate/process status discipline, evidence on accepted statuses, failure class, and next mutation. |
| `lovasz-synthesis-audit` | `lovasz_synthesis_audit.py` | Final synthesis gate before Explorer return; blocks solve language and Generator-ready claims beyond evidence. |
| `open-frontier` | `open_frontier.py` | Open-problem novelty and full-solve workbench: packages candidate products, records novelty bundles, registers checked evidence, and reports solve-claim gate status. |
| `retrieve` | `retrieval_v2.py` | Ω3 retrieval v2 (the LeanSearch-v2 recipe; Tao: "lemma search is the bottleneck"): hierarchy-informalized corpus (`build-corpus`, optional fleet enrichment), two-stage retrieve + fleet rerank (optional `WITSOC_EMBED_CMD` embedder with cached vectors), GLOBAL strategy-level premise sets, `reflect` (sketch-retrieve-reflect; unsupported needs are first-class signals). The prover consumes it automatically when a corpus exists; candidates only — the kernel rejects wrong ones. |
| `pool` | `lemma_pool.py` | Ω2 lemma pool (Seed-Prover's paradigm): per-campaign conjecture/lemma pool — `propose` (deduped), `mine` (residual `⊢` goals from REAL probe diagnostics become bridging-lemma proposals), `prove-pending` (kernel-gated; PROVED harvests into the library + proof bank for cross-attempt reuse; `INTRACTABLE` after 3 attempts with evidence). The driver mines + proves every loop. |
| `tiered-prove` | `prover_tiers.py` | Ω1 tiered proving (Seed-Prover's test-time scaling): light = deterministic portfolio; medium/heavy add compound search, external SOTA adapters (`WITSOC_PROVER_FLEET`, every adapter proof kernel-REPLAYED), and Nexus rounds. Computation matches difficulty. |
| `narrative` | `informal_proof.py` | Ω4 dual informal/formal proving (the Rethlas/Archon configuration that solved an open problem): `compose` the informal narrative (theory + retrieval reflection embedded), `ground` it step-by-step (Nexus formalization + tiered proving); gaps feed the lemma pool. PROVED_SKETCH-grade scaffolding; only kernel verdicts mark steps PROVED. |
| `self-play` | `self_play.py` | Ω5/Ω9: `frontier-round` (STP) generates conjectures at the prover's frontier, steered by solve-rate band stats; `game` runs PROVER vs ATTACKER (kernel-gated instance refutation) — survivors become verified corpus in the bank, refutations recorded negative knowledge. |
| `bank` | `proof_bank.py` | Ω6 proof bank (ProofOptimizer + expert iteration): kernel-gated simplification before archiving; signature-matched verified (goal, proof) examples embedded in every Nexus prove prompt. |
| `theory insight` | `problem_theory.py` | Ω10 insight metric (Tao's "odorless proof" warning): grade a campaign by understanding — enemy constraints, refutations, named failure mechanisms, proved pool lemmas, theory revisions — surfaced in `--finalize`. Never a trust label. |
| `tactics` | `tactic_ngrams.py` | W3 tactic n-grams: sequences (length 1–3) mined from every verified proof (proof bank + library provenance) by goal signature; the prover races them automatically as candidates. Mining only extends reach — the kernel rejects what doesn't fit. |
| `opt` | `opt_backend.py` | W4 ILP/SDP: exact pure-Python branch-and-bound ILP (`OPTIMAL`/`INFEASIBLE` are exhaustive claims, budget stops are honest `UNKNOWN`/`INCUMBENT`); `sdp-round` closes the SDP-discovery chain (numeric candidate → bounded-denominator rationals → EXACT PSD via flag-algebra elimination). `solvers` reports what's installed and how each slots in. |
| `premises` | `premise_retrieval.py` | Atlas retrieval + per-symbol Lean resolution. Returns known premises vs search targets; never assumes a premise exists. |
| `techniques` | `analogical_transfer.py` | Technique retrieval by goal-signature overlap. Sets search priors only — never trust. |
| `fleet` | `sampler_fleet.py` | F2 sampler fleet: `WITSOC_SAMPLER_FLEET` (`;;`-separated `id=cmd:...` entries) or `~/.witsoc/sampler_fleet.json`; concurrent untrusted generation for ideation, decomposition proposals, and LLM mutation operators. Everything born `OPEN_UNFALSIFIED`. |
| `mathlib-autopsy` | `mathlib_autopsy.py` | F2 technique mining over a Lean source tree (e.g. mathlib4) into the global technique atlas; entries carry provenance `mathlib_source` (kernel-verified upstream, syntactically extracted) and are retrieval hints only. |
| `counterexample` | `counterexample_search.py` | Bounded counterexample-search packets; search bounds always recorded. |
| `sat` | `sat_backend.py` | F1 verified SAT certificates (ramsey/vdw/schur/graph-coloring/covering/dimacs; cube-and-conquer via `--cubes`): SAT witnesses re-verified in-process, UNSAT refutations DRAT-checked (external solver) or honest `internal_exhaustive`. CHECKED-grade only; `--prove` hands the decidable Lean form to the kernel prover. |
| `reduction-hunt` | `reduction_hunt.py` | F1 reduction hunting: detect finite-reducible signatures in the frozen target, scan instance families upward to a witness/refutation bracket, emit `computational_certificate` DAG node drafts and the next escalation instance. Self-seeds the `finite_reduction` engine arm. |
| `construct` | `construction_search.py` | Evolutionary object search over registered deterministic evaluators. |
| `formalize` | `formalization_feasibility.py` | WIT/Lean readiness scoring; routes weak targets back for repair. Never proves. |
| `predicates` | `predicate_registry.py` | W1 formalization bridge: the predicate→Lean registry (built-ins + `witsoc predicates register`). Mined `P(n)→Q(n)` conjectures are dispatchable Lean statements by construction; an unregistered predicate is an honest blocker. |
| `blueprint` | `blueprint_campaign.py` | F3 blueprint formalization campaign: a proof DAG becomes a persistent obligation ledger (`blueprint.json`) — dependency-ordered `next`/`dispatch`/`record`, resumable across sessions; unknown-identifier failures auto-create prerequisite THEORY obligations (library-campaign mode). An all-VERIFIED blueprint is FORMAL_SOLVE evidence, reported only via `solve-claim`. |
| `novelty` | `novelty_triage.py` | Is-it-new verdicts (live library, reference atlas, external checker). Metadata only. Default external checker (no `WITSOC_NOVELTY_CMD`) is the literature engine's arXiv probe: a match is KNOWN with sources to read; no match stays honestly `LOCALLY_NEW_UNCHECKED`. |
| `literature` | `literature_engine.py` | F4 literature loop: arXiv Atom search (no dependencies), dated per-problem source ledgers under `~/.witsoc/literature/`, a ≤90-day staleness gate before re-campaigning, and the novelty probe. Offline → honest `network_unavailable`, never a guess. |
| `attackability` | `attackability.py` | F4 strategic problem selection: rank portfolio entries by finite-reduction signature, formalization readiness, technique-atlas density, literature freshness, computation-domain fit. Allocates attention only; every low score names how to raise it. |
| `atlas` / `library` | `theorem_atlas.py` / `lemma_library.py` | Two-part knowledge DB. `promote` is the only live→reference path. |
| `skeptic-check` | `refute_deterministic.py` | Deterministic adversarial refutation (drift, circularity, counterexample, citations). Demote-only. |
| `validate-prover` | `validate_prover_result.py` | Maps prover labels to legal statuses. |
| `discoveries` | `discovery_ledger.py` | Durable claim ledger; `publishable` requires kernel-grade AND novel AND human-gated. |
| `gap-feedback` | `proof_gap_to_barrier_feedback.py` | L1: classifies worker failures, proposes one one-axis mutation, enforces the re-dispatch contract. |
| `validate-math-solve` | `validate_mathematical_solve.py` | F0 stage-1 audit: every DAG node closed, skeptic fleet (≥3/node), no gaps, preconditions audited. Precondition for a solve claim — never itself a solve. |
| `solve-claim` | `solve_claim_protocol.py` | F0 frontier solve gate: audit + formal receipt for `FORMAL_SOLVE` + independent re-derivation + `NOVEL_CANDIDATE` novelty. Only `SOLVE_ACCEPTED` is reportable. |
| `validate-explorer-review` | `validate_explorer_review.py` | Explorer arbitration gate for Lovasz returns: candidates stay candidates; `GENERATOR_READY` requires one selected product, accepted downstream evidence, dependency path to target, formalization readiness, report quality, and no open-core reduction blocker. |
| `research-state` | `research_state.py` | Derived cross-phase run state assembled from existing route, handoff, Lovasz, Explorer, Generator, and artifact ledgers. View only; not a competing source of truth. |
| `validate-research-state` | `validate_research_state.py` | Explorer state gate for target hash consistency, open/research coverage, Lovasz review, and Generator authorization legality. |
| `generator-preflight` | `generator_preflight.py` | Generator entry gate: wraps handoff, Explorer review, DAG, and research-state checks; emits blocker owners. |
| `generator-receipt` | `generator_receipt_gate.py` | Generator exit gate for WIT/Lean artifacts, package status, target-freeze evidence, and status ceilings. |
| `generator-repair-packet` | `generator_repair_packet.py` | Normalizes Generator diagnostics into repair classes and owners. |
| `explorer-approach-tournament` | `explorer_approach_tournament.py` | Explorer search-priority scoring over handoff sketches. Attention only, never acceptance. |

  with a recorded reason
- `record-progress` — rung tracking; 3 stalled passes ⇒ escalation
  *recommended* (never auto-applied)

## The re-dispatch contract (gap feedback)

After every worker batch, run `witsoc gap-feedback <run_dir>`. Every
non-closed node is classified into exactly one gap class — `genuine_barrier`,
`formalization_block`, `precondition_gap` — with one proposed one-axis
mutation (axes rotate across rounds). A node listed in `gap_feedback.json`
may be re-dispatched only after its statement changes or its DAG entry
records `mutation_applied` describing the one-axis change;
`lovasz_worker_dispatch.py` blocks anything else as `BLOCKED_NO_MUTATION`.
New failures are also written into `lovasz.soc` FAILED_APPROACHES with a
`do_not_repeat` condition.
