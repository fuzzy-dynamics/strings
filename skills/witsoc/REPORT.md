# Witsoc capability report

Reproducible via `scripts/eval_harness.py` against `benchmarks/manifest.json`.
Every number below is produced by the harness; nothing is claimed that the
harness did not certify. Trust root: `lean_check.lean_verify` (real lake/lean
build + soundness scan) for Lean, independently re-decided z3 for SMT, the
evaluator's own verifier for discovery witnesses.

## Headline (seed 0, lean 4 toolchain, z3 4.16 via kernel venv)

| Bucket | Oracle | Baseline (portfolio) | Phase 1 (search) |
|---|---|---|---|
| solved | a verified Lean proof exists | 5/7 | **7/7** |
| bounds | certified witness / UNSAT | 3/3 | 3/3 |
| false | certified counterexample (SMT-SAT) | 2/2 | 2/2 |
| **capability_score** | mean(solved,bounds,false) | **0.905** | **1.00** |
| calibration | genuinely-open: honest non-solve | 2/2 clean | **2/2 clean** |
| fake-solve violations | must be 0 | 0 | **0** |

The two items Phase 1 added (`solved-intro-rfl`, `solved-have-bridge`) need a
*compound* proof (`by intro n; rfl`, `by unfold gtwice; omega`) that the
single-tactic portfolio cannot express. Verifier-guided search closes them.

## The honesty result (the point of the calibration bucket)

The same deep search that closed the two provable multistep goals did **not**
fake-solve the genuinely-open targets:

- `cal-erdos-straus` (Erdős–Straus, general n): stays `OBLIGATION_OPEN` under
  full search — not discharged.
- `cal-odd-perfect` (odd perfect number): surfaced by the miner as an
  `OPEN_UNFALSIFIED` conjecture, never as a theorem.

A discharged proof on either would be a calibration VIOLATION and would fail the
whole report (guardrail 3). Both stayed clean before and after. This is the
property that matters: capability went up without the system learning to lie.

## What moved, what didn't

- **Moved:** the `solved` bucket (5/7 → 7/7) — proof *reachability* improved by
  searching compound tactic scripts and recombining library lemmas (have-inlining),
  all pruned by the kernel.
- **Did not move (correctly):** `bounds`, `false`, `calibration` were already at
  ceiling; search neither helped nor hurt them, as expected.
- **Saturation note:** this corpus now reads 1.00 capability. That means it can no
  longer discriminate stronger provers — the next honest step is *harder* corpus
  items (genuine induction, mathlib-premise goals), not more tuning. Phases 2–4
  should be accepted only against a corpus with headroom.

## Status lattice

`INDEPENDENT` / `RELATIVE_CONSISTENCY` are now legitimate terminal outcomes, but
reachable **only** behind `human_gate=true` + a written `independence_argument` +
evidence, and they never upgrade to anything (terminal → DEMOTED only). They are
not an automatic escape hatch.

## The remaining insight ceiling (unchanged by this work)

This work lowers the cost of *reachable* proofs and raises the honesty floor. It
does not touch the in-principle limits:

- **Undecidability / incompleteness:** no procedure decides arbitrary
  mathematical truth; some true statements are unprovable in the fixed foundation.
- **Independence:** some targets are independent of ZFC — handled as a terminal
  outcome, not a solve.
- **Proof length:** minimal proofs can be astronomically long; search cannot clear
  those regardless of policy.
- **Faithfulness:** informal→formal faithfulness is human-grounded. In the harness,
  the corpus author owns the formal statement, so `solved`-bucket PASSes are honest
  for *that statement*; end-to-end-from-informal is the `calibration` regime and is
  at most CHECKED + human gate, never auto-VERIFIED.

Net: a measured, reproducible capability lift (0.905 → 1.00 on this corpus) with
zero loss of calibration, plus the search/lattice infrastructure for the research
phases — and an explicit, unmoved statement of what no amount of engineering will
settle.

---

# Phases 2–4 (the research bets)

These were built and tested. Each is honest about being a bet, and each is gated
so it cannot manufacture a false solve.

## Phase 2 — curriculum / reward densification (`curriculum.py`)

On the conjunction target `(2+2=4) ∧ (∀n, n+0=n) ∧ (∀n, fdouble n = n+n)`:

- ladder verified intermediate nodes: **3** (each rung kernel-checked)
- direct-attack verified nodes: **1**
- `ladder_beats_direct = true` (the Phase-2 acceptance signal)

So one sparse all-or-nothing reward becomes 3 dense, individually-verified
rewards — exactly the densification self-play needs. Caveat (stated, not hidden):
on this *easy* target direct search also closed the whole conjunction, so the win
here is reward *density* (3 vs 1), not *enabling an otherwise-unreachable proof*.
Showing curriculum unlock a proof direct search cannot needs a harder corpus
(genuine induction / mathlib premises). The mechanism is in place and verified;
the stronger claim is not yet demonstrated.

## Phase 3 — expert-iteration flywheel (`flywheel.py`)

Loop: search → harvest kernel-verified proofs into the **global** library
(`WITSOC_LEMMA_LIBRARY`) → retrain the policy → re-run; capability, closures,
mean nodes-to-close, and library size logged per iteration.

Result (3 iterations, isolated library), measured:

| iter | closed | capability | library size | **mean nodes to close** | calibration |
|---|---|---|---|---|---|
| 1 | 7/7 | 1.00 | 7 | **214.4** | clean |
| 2 | 7/7 | 1.00 | 14 | **84.4** | clean |
| 3 | 7/7 | 1.00 | 21 | 84.4 | clean |

verdict: **PLATEAU** (on accuracy).

Honest reading — and it is more nuanced than a flat plateau:

- **Accuracy plateaus** (1.00 → 1.00). The corpus is already at ceiling and the
  search closes everything without help, so harvesting cannot raise the score.
  The tool reports `PLATEAU`; that is the truthful result, not a bug.
- **Efficiency turns.** After one round of training on harvested closures, the
  policy closes the *same* goals with **~2.5× fewer search nodes** (214 → 84).
  That is the flywheel genuinely moving the distribution — just on cost, not
  reach, because reach has no headroom here.
- **The library compounds** (7 → 14 → 21) — durable cross-run memory accrues.
- **Calibration clean every iteration**: the flywheel never learned to fake a
  solve.

To demonstrate the flywheel raising *accuracy* (not just efficiency) needs a
corpus with headroom — harder lemmas where earlier-proved library results unlock
later goals. The infrastructure (harvest → train → compound library → re-measure)
is real, runs, and already shows a measurable efficiency gain.

## Phase 4 — interestingness / novelty (`interestingness.py`)

Scores surviving conjectures by novelty (vs library), non-triviality, surprise,
and fruitfulness; kills trivial/known forms. On the arithmetic miner:

- killed trivial: `prime → prime_power`, `square → square_or_2square`
- top-ranked (balanced): **`perfect(n) → even(n)` at 0.80** — the odd-perfect
  problem surfaced as the most interesting stepping-stone — and Euler's
  `σ odd ↔ square/2·square`.
- **Calibration guarantee (asserted in code):** every ranked item stays
  `OPEN_UNFALSIFIED`; ranking can never turn a conjecture into a solve. The unit
  test fails if that assertion ever fires.

## Honest overall verdict on 2–4

Phase 4 delivers real value now (it elevates a famous open problem above noise
without ever claiming to solve it). Phase 2's mechanism is verified but its
strongest claim awaits a harder corpus. Phase 3's accuracy plateaus on this
saturated corpus but its **efficiency turns** (2.5× fewer search nodes after
training) and the library compounds — the flywheel moves, just on cost not reach
here. The decisive property held throughout all phases: **no configuration
produced a fake solve** (calibration clean everywhere). The insight ceiling in
the Phase-0/1 section is unchanged; none of 2–4 touch it.
