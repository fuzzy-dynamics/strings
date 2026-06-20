---
name: witsoc-explorer
description: Internal Witsoc exploration subskill for advanced mathematics. Use inside the Witsoc subsystem for supply search, premise selection, theorem lookup planning, counterexample hunting, example testing, invariant mining, lemma discovery, proof strategy portfolios, reduction design, proof automation planning, Lean/Coq/SMT premise suggestions, and general mathematical exploration before or alongside WIT proof generation. It can work independently for exploratory math, or hand a precise proof plan to `witsoc-generator`.
metadata:
  skill-author: OpenScientist
category: research
---

# Witsoc Explorer

Witsoc Explorer is the discovery and arbitration engine inside Witsoc. Its job is to turn an unclear or difficult mathematical task into precise targets, sourced status, useful premises, candidate lemmas, counterexamples, barrier packets for Lovasz, and proof plans that can survive skeptical verification.

Explorer may solve small problems directly. For serious proof work, it must produce a handoff package for `witsoc-generator` before any final `.wit` is written.

Explorer is the first subskill for serious proof work, theorem proving, WIT/Lean generation, open problems, unsolved conjectures, and research-like targets. Lovasz is invoked only after Explorer freezes the problem and writes a barrier packet. Generator is invoked only after Explorer accepts a solved/routine proof plan or an assembled Lovasz-reviewed target.

## Codex/Claude Contract

Explorer is the front door for serious mathematics in Codex/Claude-style runs.
Use it to freeze the target, classify status, search theorem candidates, apply
counterexample pressure, rank proof paths, and emit either a Generator handoff
or a Lovasz barrier packet. The orchestrator remains in charge of strategy and
worker fanout.

Preferred commands:

```bash
python3 ~/.openscientist/skills/witsoc/witsoc.py llm-contract
python3 ~/.openscientist/skills/witsoc/witsoc.py explorer packet runs/<task>
python3 ~/.openscientist/skills/witsoc/witsoc.py spawn-template explorer --target "<problem>"
```

If the runtime is missing, repair it with:

```bash
python3 ~/.openscientist/skills/witsoc/bootstrap.py --replace
```

Use packets before long prose. Downgrade unsupported solved claims. Do not route
Generator until a frozen target and handoff exist.

Shared protocols live in the parent skill:

- `../references/core/status.md`
- `../references/core/llm_contract.md`
- `../references/core/handoff.md`
- `../references/core/failure_recovery.md`
- `../references/core/open_problem.md`
- `../references/core/repair.md`
- `../references/core/goal_cache.md`
- `../references/core/exploration_strategy.md`
- `../references/core/safeverify.md`
- `../references/schemas/handoff.schema.json`
- `../references/schemas/witsoc-handoff-schema.json`
- `../references/examples/handoff_solved_problem.json`
- `../references/examples/handoff_open_problem.json`
- `../references/examples/handoff_v1_blueprint.json`
- `../scripts/validate_handoff.py`
- `references/algorithmic_explorer.md`: advisory algorithms for theorem ranking, proof-sketch EV, handoff readiness, and Explorer decision packets.

## Operating Principle

Explore under adversarial pressure:

- Try to break the statement before proving it.
- Track exact hypotheses and domains.
- Prefer small lemmas with explicit dependencies.
- Separate known facts, plausible facts, and unproved bridges.
- Optimize for downstream WIT/Lean formalization, not just persuasive prose.

Do not call anything `VERIFIED`; only generator receipts or formal checkers can support that status. Explorer does not write final `.wit` artifacts except for very small tasks.

Explorer owns routing arbitration:

- decide whether the target is solved, open, unsolved, unconfirmed, false, under-specified, or already formalizable,
- route solved/routine/nontrivial formalization targets to Generator after a structured handoff,
- route open/unsolved/unconfirmed/frontier/blocked targets to Lovasz with a barrier packet,
- review every Lovasz return before Generator is allowed,
- send mathematical blockers from Generator back to Lovasz only after diagnosing that they are genuine barriers rather than artifact repair issues.

## When To Use

Use Explorer when a task needs any of:

- problem interpretation or theorem restatement,
- supply search: identities, named theorems, inequalities, constructions, reductions,
- premise selection from a large context,
- lemma discovery or subgoal decomposition,
- invariant discovery for algorithms or loops,
- counterexample search or model testing,
- proof strategy comparison,
- proof automation or tactic planning,
- repair analysis for rejected WIT/Lean steps,
- open problem or Erdős-style research where progress may mean sourced status, variant control, partial results, conjectures, obstructions, computations, or failed approaches,
- a general mathematical answer where no `.wit` artifact is required.

## Core Loop

### 0. Profile The Problem

Before theorem search or proof search, read `../references/core/exploration_strategy.md` and record Phase 0 profiling:

- object type: algebra, combinatorics, geometry, graph theory, number theory, analysis, logic, topology, probability, or algorithms,
- difficulty: `D1` through `D5`,
- proof styles: constructive, extremal, induction, contradiction, invariant, probabilistic, algebraic, geometric, analytic, or computational,
- known theorem density: `LOW`, `MEDIUM`, or `HIGH`,
- search implications.

Profiling controls the first search move. For example, an extremal graph problem should start with obstruction examples and theorem families around cuts, matchings, colorings, or containers; a number-theory divisibility problem should start with valuations, congruences, and local prime behavior.

### 1. Normalize The Target

Write the target in a precise internal form:

```text
Object types:
Domains:
Hypotheses:
Definitions:
Conclusion:
Quantifier order:
Task kind: proof | disproof | computation | reduction | algorithm correctness | formalization | audit
```

Flag ambiguity immediately. Do not silently strengthen, weaken, or change quantifiers.

After normalization, classify status as solved, open, unsolved, unconfirmed, false, under-specified, partially solved, ambiguous, or already formalizable when the task is nontrivial or named.

- If solved: run Solved Problem Reconstruction from `../references/core/exploration_strategy.md` before proof search.
- If open, unsolved, unconfirmed, frontier-level, or blocked: run the Open Problem Barrier Engine before strategy selection and prepare a Lovasz barrier packet.
- If unconfirmed: state that status is unconfirmed and still run falsification plus ontology mapping before Lovasz.

For a user request that asks to prove, disprove, solve, or deep-run an open-style target, Explorer must not end with only "open/unsupported by known results." That classification is the trigger for Lovasz. The only exception is a concrete operational blocker preventing Lovasz dispatch; record the blocker explicitly in the final report.

### 1.1 Lovasz Barrier Packet

Before invoking Lovasz, Explorer must write or include a structured barrier packet:

```json
{
  "frozen_target_statement": "exact statement with quantifiers and definitions",
  "variant_status_ledger": ["variant, status, source/evidence"],
  "source_trail": ["primary sources, surveys, maintained pages, formal facts"],
  "best_known_results": ["exact known bounds, cases, reductions, or negative facts"],
  "known_obstructions_failed_methods": ["obstruction or method and why it blocks"],
  "theorem_precondition_gaps": ["candidate theorem and missing precondition"],
  "actual_barrier_lemmas": ["lemma/reduction/obstruction that would directly move the frozen target"],
  "actual_lemma_queue_seed": ["prioritized exact lemmas with why each unlocks the target"],
  "counterexample_pressure": ["families, boundary cases, small cases to test"],
  "formalization_blockers": ["definitions, libraries, theorem availability, target drift risks"],
  "smallest_tractable_products": ["special case, conditional theorem, obstruction, computation, counterexample"],
  "lovasz_success_criteria": ["what would count as progress for this loop"]
}
```

Explorer must reject a Lovasz return that attacks only convenient weaker products without an actual barrier lemma queue, target-fidelity scores, skeptic review for accepted nodes, retry ledger for repeated methods, and final synthesis audit before Generator.

Explorer must also reject a Lovasz return that only restates "this is equivalent to a known open conjecture" without a campaign ledger. Known-open classification is the beginning of Lovasz work, not the end, unless a concrete operational blocker prevents dispatch. Required campaign evidence is: `actual_lemma_queue`, at least one `actual_barrier_lemma` DAG node, `barrier_attack_records`, worker results when spawning is available, skeptic review for accepted claims, and retry ledger for repeated methods.

Then announce:

```text
Using witsoc with witsoc-explorer -> witsoc-research-lovasz.
```

Lovasz receives the packet; Explorer remains responsible for reviewing the result.

The run is not complete after this packet is created. It is complete only after Lovasz returns a barrier attack result and Explorer reviews it into a verified solution, verified partial/special/conditional product, verified obstruction/counterexample/reduction, conjecture with evidence, failed attempt with failure memory, or still-open report after documented barrier attacks.

### 2. Attack Before Proving

Run the Falsification Pass Hierarchy from `../references/core/exploration_strategy.md` before generating an approach portfolio:

- trivial/degenerate: empty, zero, one, equality, identity, singleton, disconnected graph, singular matrix,
- symmetry/parity: sign changes, variable swaps, orientation changes, parity, modular classes,
- asymptotic extremes: sparse/dense, limits, large parameter behavior, singular inputs.

Also test missing positivity, finiteness, continuity, measurability, independence, compactness, smoothness, or nonzero assumptions when relevant.

Any proposed `O`, `o`, `Omega`, `Theta`, eventual inequality, or limit claim must be checked through the asymptotic analyzer before it becomes a proof path:

```bash
ASYM="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/asymptotic_analyzer.py)"
python3 "$ASYM" --expr "<asymptotic claim>" --variable n
```

If the analyzer rejects the bound, mark that approach `REJECTED`. If SymPy is unavailable or the analyzer returns `unknown`, mark the asymptotic step as a theorem-precondition gap rather than using it as evidence.

If a counterexample is found, do not stop at the single witness. Switch to disproof mode, prepare a minimal counterexample with verification, then invoke the inflation path in `../scripts/research_search.py --inflate` when the search backend supports the domain. Explorer must attempt to generalize the witness into an obstruction family and produce an obstruction-theorem target for Generator when the family is precise enough.

### 3. Map The Ontology And Search Backward

Before broad theorem search, map the target to ontology nodes and theorem families using `../references/core/exploration_strategy.md`.

Then run backward chaining from the conclusion:

1. State the conclusion as a goal.
2. Ask what sufficient conditions would imply it.
3. Recurse on those sufficient conditions until they match hypotheses, known theorem preconditions, computable checks, or candidate lemmas.
4. Convert the chain into subgoals, proof objects, and search queries.

Use ontology mappings as retrieval hints, not proof dependencies. Named theorems still require exact statements and preconditions.

Rank theorem candidates before using them. Each candidate should include theorem name, similarity, prerequisite-satisfaction score, formal availability, expected utility, missing preconditions, weakest usable form, and rank. Promote only high-ranked, precondition-audited candidates into `external_facts`.

Also record rejected theorem candidates with the exact reason they were not used. Include source, source type, date checked, claim supported, and confidence-calibration notes for all accepted theorem candidates.

### 4. Discover Obstructions

For open problems and `D4`/`D5` tasks, generate at least three obstruction candidates before trying to prove the statement. For easier tasks, run a lighter obstruction pass.

Obstruction records should include:

- construction or failure mode,
- what part of the conclusion it threatens,
- evidence or known examples,
- a concrete test or counterexample search,
- current status.

For Erdős-style problems, obstruction discovery is mandatory and should influence the approach portfolio.

For known open problems, also build a barrier map. Each proposed approach must say which barrier it hits and what single mutation tries to bypass it.

If the barrier map leaves a non-routine mathematical blocker, hand it to Lovasz rather than pretending Explorer can complete the proof by prose.

### 5. Mine Conjectures

When examples, computations, or small cases show a pattern, record ranked conjectures with evidence, scope, risk, and next test. Conjectures can guide conditional artifacts or experiments, but never upgrade status to theorem.

### 6. Build Proof Objects And Strategy Portfolio

Generate 2-4 credible approaches, each with:

- key idea,
- required premises,
- likely hard step,
- expected proof shape,
- formalization risk,
- how to falsify the approach.

Represent each promising route as a proof object with target, dependencies, subgoals, confidence, gap count, theorem fidelity, and formalization risk. Proof objects should feed `sketches[*]` in `handoff.json`.

Common strategy families:

- direct proof by definitions,
- contradiction or contrapositive,
- induction or well-founded descent,
- invariant/monovariant,
- extremal choice,
- compactness/limit argument,
- algebraic normalization,
- generating functions,
- probabilistic method,
- spectral/linear algebra method,
- graph cut/flow/matching duality,
- reduction/gadget construction,
- local-to-global patching,
- canonical form/classification.

Pick the highest expected-value route whose hard steps can be stated as small lemmas and whose theorem fidelity remains high.

For open problems, pick exactly one open-product target before Generator handoff: finite counterexample, obstruction lemma, or conditional step.

Before Generator handoff, run proof compression: remove unused detours and heavyweight theorem branches while preserving target fidelity and explicit gaps.

### 6.1 Recovery After Failure

When a WIT proof, verifier review, Lean check, or proof sketch fails, Explorer owns alternate-method search. Use `../references/core/failure_recovery.md`: read the recorded failure, keep the target frozen, produce distinct routes, and avoid repeating the failed method unless a real mathematical ingredient changes.

Apply the Mutation Tracker from `../references/core/exploration_strategy.md`: mutate exactly one dimension, such as strengthening the induction hypothesis, domain weakening, or duality/transformation shift.

If the failure is a mathematical barrier, construct a new Lovasz barrier packet from the failure. If the failure is artifact syntax, missing labels, Lean library friction, or local proof repair, send it back to Generator with the target unchanged.

### 6.2 Lovasz Return Review

Lovasz must return to Explorer, not directly to Generator, with:

- barriers resolved,
- barriers still open,
- claims with status: `REJECTED`, `FAILED_ATTEMPT`, `CONJECTURE`, `PARTIAL`, `PROVED_SKETCH`, `CHECKED`, or `VERIFIED`,
- evidence and source links,
- counterexample/search results,
- proof gaps,
- next recommended target.

Explorer must review the return and choose exactly one:

- `LOVASZ_AGAIN`: another barrier packet is needed.
- `DEMOTE`: mark the target `CONJECTURE`, `FAILED_ATTEMPT`, `REJECTED`, `OPEN`, `PARTIAL`, or `CONDITIONAL`.
- `GENERATOR_READY`: a solved/routine proof plan, verified partial result, checked computation/counterexample, conditional theorem, or formalizable narrow lemma is ready.
- `HONEST_STOP`: no defensible progress path remains.

Generator may run only from `GENERATOR_READY`.

Do not choose `HONEST_STOP` for a prove/disprove deep run merely because literature review found the target open. `HONEST_STOP` requires Lovasz attempts, recorded barrier attacks, or a concrete inability to run Lovasz.

### 7. Discover Lemmas

A useful lemma is:

- local: one mathematical move,
- explicit: all hypotheses stated,
- checkable: no hidden theorem preconditions,
- reusable: can be cited by label or theorem name,
- formalization-aware: likely representable in WIT or Lean.
- economical: unlocks enough goals to justify proof complexity.

For each lemma, record:

```json
{
  "id": "lemma_1",
  "statement": "precise lemma statement",
  "role": "why this lemma is needed",
  "inputs": ["hypothesis or definition"],
  "outputs": ["conclusion supplied"],
  "dependencies": ["prior lemma or external fact"],
  "proof_idea": "short proof idea",
  "risk": "main verification risk",
  "automation_candidates": ["Lean/WIT/tactic hint"],
  "economics": {
    "goals_unlocked": 3,
    "proof_complexity": 2,
    "lemma_value": 1.5
  }
}
```

Prefer high-value helper lemmas over vague citations or low-value detours. A lemma that unlocks five subgoals at proof complexity one should outrank a lemma that unlocks one subgoal at proof complexity twenty, unless the low-value lemma is necessary for target fidelity.

### 8. Select Premises

Minimize dependencies:

- assumptions from the problem,
- definitions introduced locally,
- previously proved lemmas,
- exact external theorems,
- computational facts or exhaustive checks.

For named theorems, list preconditions separately. Example:

```text
Theorem candidate: Hall's marriage theorem
Needed preconditions: finite bipartite graph; all subsets satisfy neighborhood bound
Where preconditions are proved: Lemma 2 and Lemma 3
```

Never write “by standard theorem” as if it were enough. Name the theorem or mark it as a search target.

## Specialized Modes

### Open Problem Mode

Use this mode for known open problems, Erdős-style problems, conjectures, and research questions where a complete solution may be unrealistic in one session.

For named open problems, Erdős problems, conjectures, or problem-list items, read `../references/core/open_problem.md` and `references/open_problems.md` before doing deep work. These define source triage, status ledgers, variant discipline, progress targets, and artifact handoff criteria.

Status discipline:

- Default status is `OPEN` unless a complete proof or disproof is independently checkable.
- Use `PARTIAL` for verified progress on a subcase, bound, reduction, computation, obstruction, or lemma.
- Use `CONDITIONAL` when the progress depends on an unproved conjecture, search target, or external theorem whose preconditions are not established here.
- Use `CONJECTURE` for proposed statements supported by evidence but not proved.
- Use `FAILED_ATTEMPT` for approaches that were tried seriously and failed for a specific reason.
- Never claim that an open problem is solved from persuasive prose, examples, or a single unreviewed proof sketch.

First pass:

1. Pin the exact problem statement, including all parameters, quantifiers, and common variants.
2. Check whether the problem is known open, solved, partially solved, or ambiguous. For current status, use authoritative sources where available: original problem lists, maintained problem pages, author notes, survey papers, arXiv/publisher pages, or theorem prover libraries for formal availability. Treat OEIS, MathWorld, Wikipedia, blogs, and forums as pointers unless they cite a primary source. Cite sources used; if no source is checked, say the status is unconfirmed.
3. Record known equivalent formulations, stronger/weaker variants, and standard obstruction families.
4. Run the normal falsification pass before attempting a proof.
5. Decide what would count as useful progress under the current budget.

Research ledger:

```text
Problem state:
Problem profile:
Ontology map:
Known facts:
Known variants:
Conjecture ledger:
Obstruction map:
Approach log:
Proof sketches:
Examples and computations:
Partial results:
Failed attempts:
Formal subgoals:
Next experiments:
```

Use the ledger as auditable research notes. It should expose the mathematical state and decision points without presenting private chain-of-thought. Keep entries concise, claim-focused, and checkable.

Open-problem approach portfolio:

- Explain the main obstruction families.
- Direct attack on the original statement.
- Prove a meaningful special case.
- Prove a conditional result under a named conjecture or extra hypothesis.
- Isolate a formal subgoal that could be proved in WIT or Lean.
- Improve or rederive a known bound.
- Find counterexamples to stronger variants.
- Build computational evidence or exhaustive checks for small parameters.
- Reduce the problem to a cleaner subproblem.
- Identify an obstruction explaining why a naive route fails.
- Repair or mutate a promising proof sketch without changing the target theorem.

For each approach, record:

```text
Approach:
Target progress:
Required facts:
Experiment or proof attempt:
Failure mode to watch:
Status: active | partial | failed | blocked
```

Open-problem search discipline:

- Start from `OPEN` unless the problem is independently known solved and the exact solution is available.
- Prefer formal subgoals, special cases, obstruction lemmas, and counterexamples to broad prose claims.
- Treat every failed formal sketch as information: record where it broke and what it rules out.
- Separate evidence from proof. Computations, examples, and analogies may motivate `CONJECTURE`, but do not prove universal claims.
- Mutate one variable at a time when repairing a sketch: theorem route, lemma order, external fact, case split, or tactic/formalization strategy.
- Never let a partial sketch drift into a weaker theorem unless the status is explicitly `PARTIAL` or `CONDITIONAL` and the original target remains recorded as open.

When progress is found, classify it before handoff in `runs/<task>/handoff.json` using `../references/schemas/handoff.schema.json`.

Escalate to Generator only when there is a precise artifact target: a lemma, conditional theorem, counterexample, obstruction, computation certificate, or clearly delimited failed proof attempt. Do not ask Generator to write a WIT proof of the whole open problem unless the proof has already survived adversarial exploration.

### Proof Sketch Protocol

A proof sketch is a partial WIT/Lean-ready artifact plus its research state. It may be useful even when it does not close the theorem.

Use proof sketches when an open problem, hard proof, or failed formalization has multiple plausible routes or partial artifacts.

Sketches must be represented as structured JSON inside `handoff.json`:

```json
{
  "sketch_id": "sketch_1",
  "parent_sketch_id": null,
  "target_theorem": "exact theorem target",
  "proof_strategy": "method family and plan",
  "current_artifact": "optional path",
  "proof_objects": [],
  "lemmas": [],
  "solved_pieces": [],
  "remaining_goals": [],
  "known_gaps": [],
  "failure_class": "",
  "next_mutation": "",
  "status": "PARTIAL",
  "ev": {
    "theorem_fidelity": 0.9,
    "probability_of_completion": 0.5,
    "verifier_friendliness": 0.7,
    "expected_value": 0.315
  }
}
```

Rules:

- A sketch is not a proof unless Generator later produces a verified artifact under the normal receipt/checker discipline.
- Preserve the original theorem target in every sketch.
- Record parent sketch and mutation so failed paths are not repeated blindly.
- Prefer small mutations over rewriting the whole proof plan.
- Promote a sketch only when it improves theorem fidelity, reduces gaps, proves a subgoal, finds a counterexample, or makes a failure more precise.
- If two sketches compete, compare them by expected value plus theorem fidelity, solved pieces, gap clarity, repairability, and dependence on external facts.

### Rater Mode

Use Rater Mode when multiple proof sketches compete and no sketch is yet verified. Raters prioritize search; they do not verify mathematics.

Rater output should update the `sketches[*].ev` fields in `handoff.json`.

Ranking criteria:

- Primary score: `expected_value = theorem_fidelity * probability_of_completion * verifier_friendliness`.
- Tie breakers: checked progress, solved subgoals, clarity/locality of gaps, repairability, dependence on external facts, strategic value for later sketches.

Rules:

- Theorem fidelity beats elegance.
- Never let high completion probability compensate for low theorem fidelity unless the artifact is explicitly `PARTIAL` or `CONDITIONAL`.
- A sketch with a small precise gap is usually better than a broad persuasive sketch.
- A rater verdict cannot upgrade status to `VERIFIED`.
- If all sketches share the same missing bridge, mark the bridge as the central blocker instead of repeatedly ranking variants.

### Goal Cache Protocol

Use `../references/core/goal_cache.md` for repeated formal subgoals, tactic failures, or proof steps that look structurally familiar.

### External Theorem Replacement Policy

When a proof route depends on a large named theorem, paper result, or uncertain library fact, pin the dependency before using it.

Template:

```text
External theorem:
Exact needed statement:
Preconditions:
Where preconditions are proved:
Formal availability:
Fallback plan:
```

Policy:

- Separate known theorem, candidate theorem, and unavailable theorem.
- Name exact preconditions; do not hide them under “standard assumptions.”
- If formal availability is unknown, mark it as a search target, not a proof dependency.
- Prefer a local weaker lemma that is enough for the current proof over an opaque broad theorem.
- If the external theorem is essential and unavailable, return `CONDITIONAL` or `GAP` rather than pretending it is proved.
- Complete the External Verification record from `../references/core/exploration_strategy.md` before handoff: source/library availability, exact statement needed, local replacement plan, and downstream risk.

### Stop Conditions

Use stop conditions and failure output from `../references/core/failure_recovery.md`.

### Supply Search

Goal: find facts that could solve the target.

Output:

- ranked candidate theorem/fact,
- exact statement needed,
- similarity score,
- hypotheses to verify,
- percentage of prerequisites satisfied,
- formal availability,
- expected utility,
- why it helps,
- confidence,
- fallback if unavailable.

For external theorems, also return the External Theorem Replacement Policy template fields.

If using web/corpus/search tools, rely on primary or authoritative sources for technical claims. If no source is checked, say “candidate fact” rather than presenting it as established.

### Premise Selection

Goal: choose the smallest set of premises that implies a step.

Procedure:

1. Identify the target claim.
2. List all available premises.
3. Remove premises one by one unless the inference breaks.

Mathlib Atlas rule:

- Before adding any external theorem or Lean/Mathlib dependency to `handoff.json`, Explorer must verify formal availability and exact module path with `../scripts/mathlib_atlas.py`.
- The atlas query must include the semantic theorem description and, where possible, the Lean-ish type signature.
- Record atlas status, returned module path, symbols, and import list in the external verification record.
- If the atlas is missing or returns no match, mark formal availability `UNKNOWN` and keep the theorem as a search target, not an accepted proof dependency.

```bash
ATLAS="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/mathlib_atlas.py)"
python3 "$ATLAS" --query "<theorem meaning>" --signature "<Lean type shape>" --limit 5
```
4. Add missing bridge lemmas explicitly.
5. Return a minimal or near-minimal dependency set.

Output:

```text
Target step:
Required premises:
Unused premises:
Missing bridge, if any:
Recommended BY clause:
```

### Counterexample Hunting

Goal: disprove or stress-test a statement.

Use:

- small finite search,
- boundary parameters,
- random instances,
- known obstruction families,
- weakening/strengthening comparisons,
- dimensional or type mismatch checks.

A counterexample report must include:

- exact object,
- verification that hypotheses hold,
- verification that conclusion fails,
- minimality if relevant,
- inflation attempt command and output,
- obstruction family candidate, or a reason inflation failed,
- WIT obstruction-theorem target when the generalized negative space is precise enough.

### Invariant Mining

For algorithms, processes, recurrences, or games:

- identify state variables,
- list preserved quantities,
- list monotone quantities,
- identify termination measure,
- separate partial correctness from termination and complexity,
- test invariant on initialization, preservation, and exit.

Handoff to generator should include `REQUIRES`, `ENSURES`, invariants, termination measure, and complexity claim.

### Reduction Design

For complexity or equivalence reductions:

- define source and target problem precisely,
- specify construction as strict SMT-LIB constraints whenever the gadget boundary is finite or finitely parameterized,
- prove forward direction,
- prove reverse direction,
- prove polynomial/resource bound,
- identify preserved property,
- test gadget edge cases.

Do not construct finite reduction gadgets by prose alone. Explorer must write strict SMT-LIB constraints for:

- source object variables,
- target gadget variables,
- preservation laws,
- forward/backward correctness boundary,
- forbidden target drift,
- size/resource bounds when finite.

Then invoke:

```bash
SMT="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/smt_synthesizer.py)"
python3 "$SMT" --file runs/<task>/reduction_constraints.smt2 --pretty
```

Use `sat` output only as a candidate gadget requiring proof. Use `unsat` plus unsat core as obstruction evidence. Generator receives a reduction artifact only after Explorer records the SMT input hash, solver status, model/core, and proof obligations.

Handoff to generator should include `REDUCTION`, `FROM`, `TO`, `PRESERVING`, and a lemma plan.

### Proof Automation Planning

For Lean/Coq/SMT-adjacent work:

- infer the likely formal statement shape,
- identify library theorem names if known,
- suggest induction variables or recursion principle,
- identify simplification normal forms,
- list algebraic rewrites,
- separate automation-friendly lemmas from human lemmas,
- warn about propositions likely hard for automation.

Do not claim formal success without a checker run.

## Repair Mode

When generator or a verifier rejects a step:

Use `../references/core/repair.md`. Return a structured repair diagnosis with rejected target, cited premises, evidence, failure class, minimal repair, risk, and whether Explorer or Generator owns the next step.

## Handoff To Witsoc Generator

When a `.wit` artifact is needed for a nontrivial problem, write both:

- `runs/<task>/handoff.json`: rich research state conforming to `../references/schemas/handoff.schema.json`.
- `runs/<task>/handoff_v1.json`: strict Generator blueprint conforming to `../references/schemas/witsoc-handoff-schema.json`.

Set the research state to `HANDOFF_READY` only after both validate.

Use `../references/examples/handoff_solved_problem.json`, `../references/examples/handoff_open_problem.json`, and `../references/examples/handoff_v1_blueprint.json` as shape examples. Run these when local execution is available before asking Generator to consume the handoff:

```bash
VALIDATOR="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_handoff.py)"
python3 "$VALIDATOR" runs/<task>/handoff.json
python3 "$VALIDATOR" runs/<task>/handoff_v1.json
```

The blueprint `lemma_plan` must be a DAG. Every `depends_on` value must reference an earlier `step_id`, and every external theorem used in `method` must appear in `external_dependencies`.

Required handoff contents:

- Phase 0 problem profile,
- search budget and stop conditions,
- solved-problem map if the problem is known solved,
- source citations for solved/open status and theorem claims,
- ontology map and theorem-family retrieval hints,
- ranked theorem retrieval candidates,
- rejected theorem candidates,
- backward chaining graph,
- falsification pass results,
- obstruction candidates,
- barrier map and selected open-product target for open problems,
- ranked conjectures,
- frozen target and target-freeze hashes,
- artifact target and status,
- proof objects and proof sketches with EV fields,
- confidence calibration notes inside theorem candidates and sketch/proof-object scoring,
- selected sketch id,
- lemma sequence as structured arrays,
- lemma economics,
- obligation graph,
- external facts with preconditions and fallback plans,
- external verification records for major theorems,
- mutation tracker entries after failures,
- proof compression record,
- counterexamples checked,
- recommended WIT structure in `wit_notes`,
- Lean/formalization notes when relevant.

Keep the handoff concise enough that Generator can turn it into labeled WIT steps without redoing exploration. If a repair needs broad theorem search, Generator should return here with a structured repair diagnosis.

## Output Templates

For exploratory work:

```text
Interpretation:
Counterexample pressure:
Approach portfolio:
Selected route:
Lemma plan:
Premises/external facts:
Risks or gaps:
Next step:
```

For open-problem work:

```text
Interpretation:
Known status:
Problem state:
Known facts and variants:
Conjectures:
Approach log:
Best proof sketch:
Partial results:
Failed attempts:
Obstacles or gaps:
Recommended artifacts:
Next experiments:
Status: OPEN | PARTIAL | CONDITIONAL | CONJECTURE | FAILED_ATTEMPT
```

For stopped or blocked work:

```text
Status: GAP | FAILED_ATTEMPT | PARTIAL
Target:
Best sketch:
Where it failed:
Failure class:
What was tried:
Why it did not close:
Reusable lesson:
Next useful mutation:
```

For direct small answers:

```text
Claim:
Solution:
Checks/edge cases:
Status: informal answer, not WIT-verified
```

## Quality Bar

Explorer succeeds when it:

- narrows ambiguity,
- catches false statements early,
- reduces proof search to checkable lemmas,
- minimizes premise sets,
- exposes missing theorem preconditions,
- gives generator a clear WIT-ready path.

Explorer fails when it:

- invents theorem names,
- hides uncertainty,
- overclaims progress on open problems,
- treats examples as universal proof,
- skips edge cases,
- silently changes the theorem,
- produces broad prose that cannot be converted into WIT labels.
