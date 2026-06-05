# Witsoc Research Lovasz Protocol

Use this reference when a mathematical task is open-ended, plausibly open, or framed as "solve an unsolved problem." It complements Witsoc Explorer; it does not replace Explorer's proof and handoff rules.

Lovasz mode is autonomous research control: it selects targets, designs experiments, attacks barriers, verifies claims, and only then routes precise claims into Witsoc Explorer or Generator. It must be bold in search and conservative in status.

For substantial runs, also load the focused reference that matches the current step:

- `problem_selection.md` before selecting a product.
- `literature_triage.md` before theorem search on serious open problems.
- `cross_run_memory.md` before selecting domain, theorem families, or proof routes.
- `domain_playbooks.md` and a specific domain playbook before barrier/product selection.
- `theorem_retrieval_engine.md` before proof route commitment.
- `erdos_level_playbook.md` when the problem is an Erdős-style frontier problem with asymptotic, extremal, probabilistic, additive, multiplicative, or sparse-structure behavior.
- `barrier_taxonomy.md` before barrier mapping.
- `conjecture_mining.md` when examples or failures reveal a pattern.
- `conjecture_to_lemma_pipeline.md` when a conjecture is useful enough to become a proof obligation.
- `experiment_design.md` before computation or model search.
- `computation_backends.md` before choosing a computation script or solver style.
- `counterexample_search_library.md` before ad hoc counterexample search.
- `lean_mathlib_integration.md` before Lean or formal dependency claims.
- `proof_strategy_agents.md` before full proof campaigns or repeated proof failures.
- `disproof_first_protocol.md` before proof campaigns for open/unsolved targets.
- `counterexample_certificate.md` when any disproof witness appears.
- `proof_gap_ledger.md` for proof/disproof candidates with unresolved bridges.
- `full_proof_campaign.md` when a full proof attempt is justified.
- `skeptic_pass.md` before accepting proof, disproof, or high-stakes handoff.
- `soc_memory.md` before and after each loop.
- `full_proof_escalation.md` before attempting full closure of an open problem.
- `claim_demotion.md` when a claim weakens or fails verification.

## 1. Problem Intake

Record this block before search:

```text
Original request:
Exact target:
Object types:
Domain:
Hypotheses:
Definitions:
Conclusion:
Quantifier order:
Known variants:
What would count as progress:
What would count as a solution:
Known barriers:
Likely smallest publishable product:
Relevant SOC memory:
Relevant cross-run memory:
Domain playbooks:
Erdos-level central tension:
Theorem retrieval spine:
Lean/Mathlib feasibility:
Disproof-first status:
Proof gap ledger:
Skeptic pass:
```

If the user gives only a broad ambition, choose a tractable target class and say why. Favor problems where progress can be checked inside one run.

If the task is serious or open, load `literature_triage.md`, `cross_run_memory.md`, and `domain_playbooks.md` before product selection.

If the task is Erdős-level, load `erdos_level_playbook.md` before product selection. Record the central tension, theorem retrieval spine, product ladder, and full-solution readiness criteria.

For any prove/disprove request on an open or unsolved target, load `disproof_first_protocol.md`, `proof_gap_ledger.md`, and `skeptic_pass.md`.

## 1.1 SOC Memory

Before choosing a product, create or read `runs/<task>/lovasz.soc` using `soc_memory.md`. Use it to avoid repeating dead approaches and to recover prior barriers, conjectures, reductions, and verified partials.

Update `lovasz.soc` after every loop:

- add reusable insights,
- add failed approaches with `do_not_repeat`,
- update progress counters,
- add recovery queue items.

If memory contradicts the current plan, resolve the contradiction before proceeding.

## 2. Status And Novelty Triage

Build a source table:

```markdown
| Claim | Source | Source type | Date checked | Supports | Caveats |
|---|---|---|---|---|---|
```

Source types:

- `primary`: original paper, theorem, preprint, or author-maintained manuscript.
- `survey`: expository or field overview.
- `formal_library`: Lean, Coq, Isabelle, or other maintained formal result.
- `maintained_page`: official problem list or author-maintained page.
- `pointer`: bibliography, database entry, or search result.
- `informal`: forum, blog, lecture note without stable claim support.
- `none`: no source yet.

Rules:

- Use pointers only to find stronger sources.
- Track exact variant alignment: solved, open, partially solved, false, ambiguous, or unconfirmed.
- If a claimed source solves a neighboring variant, record the mismatch instead of importing the result.
- For recent or status-sensitive claims, verify externally before treating them as current.

## 3. Research Product Selection

Choose one target product per active loop using `problem_selection.md`. For Erdős-level tasks, the selected product should come from the product ladder in `erdos_level_playbook.md`:

```text
Product type: special_case | bound | conditional_theorem | reduction | obstruction | counterexample | computation | conjecture | failed_attempt
Statement:
Why this product matters:
Verification route:
Likely WIT/Lean artifact:
Stop condition:
Selection score:
```

Good research products are narrow, falsifiable, and publishable as components. Bad products are vague: "make progress," "try induction," or "solve the whole conjecture."

## 4. Lovasz Barrier Engine

Before proof search, load `barrier_taxonomy.md` and list at least three barriers or obstructions:

```markdown
### Barrier B1: <name>
- Threatens:
- Evidence:
- Known examples:
- Test:
- Bypass mutation:
- What would defeat this barrier:
- What would prove the barrier is real:
- Status:
```

Barrier categories:

- extremal construction,
- parity or modular obstruction,
- density threshold,
- compactness or infinitary gap,
- regularity or smoothness gap,
- independence or randomness barrier,
- complexity-theoretic hardness,
- theorem precondition mismatch,
- formalization bottleneck,
- known lower/upper bound wall.

Each proposed approach must name the barrier it addresses.

### Barrier-Breaking Moves

Apply these moves when the obvious approach stalls. Use one mutation per loop.

```markdown
### Move M<N>: <name>
- Barrier attacked:
- Mutation type: strengthen_hypothesis | weaken_conclusion | change_encoding | dualize | extremalize | localize | randomize | algebraize | formalize | reduce
- New target:
- Why it may bypass the barrier:
- First decisive test:
- Failure value:
```

Canonical moves:

- **Minimal counterexample compression:** assume a smallest counterexample and derive forced local structure.
- **Extremal witness mining:** search for objects that nearly violate the claim; use them to find the true threshold.
- **Dual translation:** convert the problem to a dual framework where the blocked operation becomes native.
- **Boundary formalization:** formalize a small or finite boundary case to expose hidden assumptions.
- **Condition swap:** replace one global assumption with a local condition, or vice versa.
- **Obstruction inversion:** prove the obstacle itself as a theorem, then route around it.
- **Random construction probe:** test whether a stronger statement is false by probabilistic examples.
- **Algebraic encoding:** replace set/graph incidence with rank, polynomial, entropy, spectral, or generating-function data.
- **Reduction ladder:** prove implications among variants to locate the exact hardness frontier.

Do not keep applying the same move with cosmetic changes. If three loops hit the same barrier, either convert it into an obstruction result or choose a new product.

## 5. Approach Portfolio

Draft 3-5 approaches:

```markdown
## A1: <title>
- Product target:
- Key idea:
- Required facts:
- First experiment:
- Hard step:
- Barrier addressed:
- Barrier-breaking move:
- Falsification test:
- Expected value: HIGH | MEDIUM | LOW
- Formalization risk: LOW | MEDIUM | HIGH
- Confidence would drop if:
```

Rank by information value, not optimism. A failed approach is useful if it sharply rules out a family of methods or produces a clean obstruction.

## 6. Evidence Loop

Run in this order unless the problem dictates otherwise:

1. Read/update `.soc` memory.
2. Read/update cross-run memory.
3. Triage literature and status.
4. Select domain playbooks.
5. Classify whether the problem is Erdős-level and record central tension if so.
6. Score candidate products.
7. Run disproof-first passes.
8. Certify any counterexample candidate.
9. Degenerate and boundary cases.
10. Small exhaustive search or symbolic examples.
11. Extremal construction search.
12. Theorem candidate retrieval with precondition and formal-availability audit.
13. Choose computation backend when search is useful.
14. Backward chaining from the target product.
15. Lemma discovery and dependency minimization.
16. Convert useful conjectures into scoped lemma candidates.
17. Initialize or update proof gap ledger for candidate proofs.
18. Run distinct proof-strategy agents when proof routes are needed.
19. Full-proof campaign only when escalation criteria are met.
20. Lovasz verification gate.
21. Skeptic pass before accepting proof/disproof or high-stakes handoff.
22. Claim demotion if verification or skeptic pass fails.
23. Full-proof escalation check if the target appears globally solved.
24. Lean/Mathlib feasibility check before formalization claims.
25. Witsoc Explorer handoff for validated proof exploration.
26. WIT/Lean artifacting for the narrow claim.

Record every loop in `research.md`:

```markdown
## Loop N
- Target product:
- Mutation from prior loop:
- Action:
- Evidence:
- Outcome:
- Claim updates:
- Barrier updates:
- Verification updates:
- Disproof-first updates:
- Literature/theorem retrieval updates:
- Computation backend updates:
- Proof gap updates:
- Skeptic updates:
- SOC memory updates:
- Cross-run memory updates:
- Next mutation:
```

## 7. Lovasz Verification Gate

Before a claim is used by Witsoc Explorer or Generator, write a verification record:

```markdown
### V<N>: <claim id>
- Frozen statement:
- Variant alignment:
- Novelty/source check:
- Dependency audit:
- Boundary cases checked:
- Counterexample search:
- Computation or proof sketch:
- Independent stress test:
- Known barriers addressed:
- Remaining gaps:
- Verdict: REJECTED | FAILED_ATTEMPT | CONJECTURE | PARTIAL | PROVED_SKETCH | CHECKED | VERIFIED
```

Minimum gate by verdict:

- `CONJECTURE`: examples or computation support it, and no small counterexample was found.
- `PARTIAL`: exact scope, assumptions, evidence, remaining gap, novelty comparison, skeptic classification, and at least two closure attempts are recorded.
- `PROVED_SKETCH`: proof sketch has explicit dependencies, no circular step, and survived boundary/counterexample tests.
- `CHECKED`: deterministic computation or structural check was run and its input/output path is recorded.
- `VERIFIED`: formal/verifier receipt or equivalent checked artifact exists.

Routing:

- Explorer may receive `CONJECTURE`, `PARTIAL`, or `PROVED_SKETCH` claims.
- Generator may receive only narrow `PARTIAL`, `PROVED_SKETCH`, or `CHECKED` claims.
- `VERIFIED` claims become reusable facts with receipts.
- `REJECTED` and `FAILED_ATTEMPT` records remain in the ledger as negative evidence.

If the verdict is weaker than the proposed claim, apply `claim_demotion.md` before routing.

## 8. Claim Ledger

Every mathematical statement that matters goes in `claims.md`:

```markdown
### C<N>: <claim>
- Status: OPEN | UNCONFIRMED | CONJECTURE | PARTIAL | FAILED_ATTEMPT | PROVED_SKETCH | CHECKED | VERIFIED | REJECTED
- Product type:
- Dependencies:
- Evidence:
- Counterexample search:
- Artifact:
- Source support:
- Verification gap:
- Remaining gap statement:
- Why not full solution:
- Known result comparison:
- Novelty status: new | known | variant | unknown | not_applicable
- Closure attempts:
- Next exact experiment or lemma:
```

Use `VERIFIED` only when Witsoc's verification discipline allows it. Use `CHECKED` for deterministic structural checks or computations that are not semantic proof.

## 9. Handoff To Witsoc Explorer And Generator

Handoff only a narrow verified-or-validated claim. Include:

- frozen target statement,
- definitions and domain,
- hypotheses,
- selected proof object,
- explicit gaps,
- external facts with source and precondition audit,
- obstruction/counterexample checks,
- Lovasz verification verdict,
- target-freeze hash if available,
- expected artifact type.

Use Witsoc Explorer first when the claim still needs proof search, lemma discovery, counterexample hunting, or theorem retrieval. Use Witsoc Generator only when the target is precise enough for `.wit`/Lean artifacts.

Never hand off a famous open problem as a whole unless the ledger contains a complete candidate proof that survived adversarial review and verification gating.

Before handing off a full solution attempt for an open problem, apply `full_proof_escalation.md`. If escalation is rejected, hand off only the strongest narrow product.

Before accepting a proof/disproof or sending a full-proof target to Generator, require:

- disproof-first summary,
- proof gap ledger with no essential open gaps,
- skeptic pass verdict,
- counterexample certificate if the result is a disproof.

## 10. Research Autonomy

Lovasz mode may conduct its own research loops without waiting for the user when the target is clear:

- choose a narrow product if the original problem is too broad,
- run small computations or symbolic checks when useful,
- run disproof-first search before proof campaigns,
- generate and rank conjectures,
- reject false or stale variants,
- convert failed proofs into obstruction results,
- update `lovasz.soc` after each loop,
- ask Witsoc Explorer for proof search only after verification gating,
- ask Witsoc Generator for artifacts only after the claim is narrow.

Keep autonomy bounded by the ledger. Every target change must record the mutation, reason, and status.

## 11. Stop Conditions

Stop or re-scope when:

- source triage shows the exact target is already solved or false,
- three mutation loops hit the same barrier without new evidence,
- computation finds a counterexample,
- the selected product becomes too broad to verify,
- proof gap ledger shows an essential gap as hard as the original target,
- skeptic pass rejects the proof or disproof and no narrower product survives,
- formalization exposes a missing hypothesis that changes the theorem,
- evidence supports writing a report instead of continuing search.

The final response should preserve negative progress. A failed path with a precise reason is part of the research output.
