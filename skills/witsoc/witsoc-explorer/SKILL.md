---
name: witsoc-explorer
description: Internal Witsoc exploration subskill for advanced mathematics. Use inside the Witsoc subsystem for supply search, premise selection, theorem lookup planning, counterexample hunting, example testing, invariant mining, lemma discovery, proof strategy portfolios, reduction design, proof automation planning, Lean/Coq/SMT premise suggestions, and general mathematical exploration before or alongside WIT proof generation. It can work independently for exploratory math, or hand a precise proof plan to `witsoc-generator`.
metadata:
  skill-author: OpenScientist
category: research
---

# Witsoc Explorer

Witsoc Explorer is the discovery engine inside Witsoc. Its job is to turn an unclear or difficult mathematical task into precise targets, useful premises, candidate lemmas, counterexamples, and a proof plan that can survive skeptical verification.

Explorer may solve small problems directly. For serious proof work, it must produce a handoff package for `witsoc-generator` before any final `.wit` is written.

## Operating Principle

Explore under adversarial pressure:

- Try to break the statement before proving it.
- Track exact hypotheses and domains.
- Prefer small lemmas with explicit dependencies.
- Separate known facts, plausible facts, and unproved bridges.
- Optimize for downstream WIT/Lean formalization, not just persuasive prose.

Do not call anything `VERIFIED`; only generator receipts or formal checkers can support that status. Explorer does not write final `.wit` artifacts except for very small tasks.

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
- open problem or Erdős-style research where progress may mean partial results, conjectures, obstructions, or failed approaches,
- a general mathematical answer where no `.wit` artifact is required.

## Core Loop

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

### 2. Attack Before Proving

Run a falsification pass:

- boundary cases: empty, zero, one, equality, degenerate geometry, disconnected graph, singular matrix, non-measurable/non-compact cases,
- parity/modular tests,
- small exhaustive examples when finite,
- asymptotic extremes,
- missing positivity, finiteness, continuity, measurability, independence, or nonzero assumptions,
- known obstruction families.

If a counterexample is found, switch to disproof mode and prepare a minimal counterexample with verification.

### 3. Build A Strategy Portfolio

Generate 2-4 credible approaches, each with:

- key idea,
- required premises,
- likely hard step,
- expected proof shape,
- formalization risk,
- how to falsify the approach.

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

Pick the simplest route whose hard steps can be stated as small lemmas.

### 3.1 Recovery After Failure

When a WIT proof, verifier review, Lean build, or proof sketch fails, Explorer owns the alternate-method search. Do not simply ask Generator to repair the same route unless the repair changes a real mathematical ingredient.

Recovery protocol:

1. Read the recorded failure note or `.soc` `FAILED_APPROACHES` entry.
2. Freeze the original theorem target and identify the failure class:
   - false statement or missing hypothesis,
   - bad external theorem bridge,
   - unverifiable proof step,
   - Lean encoding mismatch,
   - automation/tactic failure,
   - search/literature dead end.
3. Produce at least two genuinely different routes before recommending final failure:
   - alternate proof strategy,
   - counterexample/obstruction search,
   - external theorem replacement,
   - stronger lemma or invariant discovery,
   - different formalization decomposition,
   - conditional or partial theorem that preserves the original target as unresolved.
4. If Plane/OpenScientist worker spawning is available, recommend or launch separate agents for the distinct routes. Each agent prompt must include what failed and what not to repeat.
5. After alternates report back, synthesize:
   - which route, if any, should replace the current plan,
   - which blocker is shared by all routes,
   - whether Generator should write a new WIT artifact, a failed-attempt artifact, or a conditional/partial artifact.

Do not count repeated local edits of the same sketch as independent attempts. Independence requires a changed method, theorem source, decomposition, formal representation, or search space.

### 4. Discover Lemmas

A useful lemma is:

- local: one mathematical move,
- explicit: all hypotheses stated,
- checkable: no hidden theorem preconditions,
- reusable: can be cited by label or theorem name,
- formalization-aware: likely representable in WIT or Lean.

For each lemma, record:

```text
Lemma:
Role in proof:
Inputs:
Output:
Dependencies:
Proof idea:
Risk:
Automation candidates:
```

Prefer proving helper lemmas over using vague citations.

### 5. Select Premises

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

Status discipline:

- Default status is `OPEN` unless a complete proof or disproof is independently checkable.
- Use `PARTIAL` for verified progress on a subcase, bound, reduction, computation, obstruction, or lemma.
- Use `CONDITIONAL` when the progress depends on an unproved conjecture, search target, or external theorem whose preconditions are not established here.
- Use `CONJECTURE` for proposed statements supported by evidence but not proved.
- Use `FAILED_ATTEMPT` for approaches that were tried seriously and failed for a specific reason.
- Never claim that an open problem is solved from persuasive prose, examples, or a single unreviewed proof sketch.

First pass:

1. Pin the exact problem statement, including all parameters, quantifiers, and common variants.
2. Check whether the problem is known open, solved, partially solved, or ambiguous. If using web, literature, or corpus search, cite primary or authoritative sources; if no source is checked, say the status is unconfirmed.
3. Record known equivalent formulations, stronger/weaker variants, and standard obstruction families.
4. Run the normal falsification pass before attempting a proof.
5. Decide what would count as useful progress under the current budget.

Research ledger:

```text
Problem state:
Known facts:
Known variants:
Conjecture ledger:
Approach log:
Proof sketches:
Obstacle map:
Examples and computations:
Partial results:
Failed attempts:
Formal subgoals:
Next experiments:
```

Use the ledger as auditable research notes. It should expose the mathematical state and decision points without presenting private chain-of-thought. Keep entries concise, claim-focused, and checkable.

Open-problem approach portfolio:

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

When progress is found, classify it before handoff:

```text
Result type: lemma | conditional theorem | counterexample | obstruction | computation | conjecture | failed attempt
Statement:
Assumptions:
Evidence:
Proof sketch or computation:
Known gaps:
Why this helps the open problem:
Recommended WIT artifact:
```

Escalate to Generator only when there is a precise artifact target: a lemma, conditional theorem, counterexample, obstruction, computation certificate, or clearly delimited failed proof attempt. Do not ask Generator to write a WIT proof of the whole open problem unless the proof has already survived adversarial exploration.

### Proof Sketch Protocol

A proof sketch is a partial WIT/Lean-ready artifact plus its research state. It may be useful even when it does not close the theorem.

Use proof sketches when an open problem, hard proof, or failed formalization has multiple plausible routes or partial artifacts.

Sketch template:

```text
Sketch id:
Parent sketch:
Target theorem:
Current artifact:
Solved pieces:
Remaining goals:
Compiler/verifier status:
Known gaps:
Failure class, if any:
Next mutation:
Status: PARTIAL | CONDITIONAL | CONJECTURE | GAP | FAILED_ATTEMPT
```

Rules:

- A sketch is not a proof unless Generator later produces a verified artifact under the normal receipt/checker discipline.
- Preserve the original theorem target in every sketch.
- Record parent sketch and mutation so failed paths are not repeated blindly.
- Prefer small mutations over rewriting the whole proof plan.
- Promote a sketch only when it improves theorem fidelity, reduces gaps, proves a subgoal, finds a counterexample, or makes a failure more precise.
- If two sketches compete, compare them by theorem fidelity, solved pieces, gap clarity, repairability, and dependence on external facts.

### Rater Mode

Use Rater Mode when multiple proof sketches compete and no sketch is yet verified. Raters prioritize search; they do not verify mathematics.

Rater template:

```text
Sketches compared:
Ranking:
Pairwise winners:
Reason:
Risks:
Recommended parent:
```

Ranking criteria, in order:

- theorem fidelity,
- verified or structurally checked progress,
- solved subgoals,
- clarity and locality of remaining gaps,
- repairability,
- dependence on external facts,
- strategic value for later sketches.

Rules:

- Theorem fidelity beats elegance.
- A sketch with a small precise gap is usually better than a broad persuasive sketch.
- A rater verdict cannot upgrade status to `VERIFIED`.
- If all sketches share the same missing bridge, mark the bridge as the central blocker instead of repeatedly ranking variants.

### Goal Cache Protocol

Use this protocol for repeated formal subgoals, tactic failures, or proof steps that look structurally familiar.

Cache entry:

```text
Goal:
Normalized context:
Successful tactic/proof step:
Required premises:
Source sketch:
Failure count:
Success count:
```

Rules:

- Search prior solved goals or recorded proof steps before inventing a new tactic or lemma route.
- Save successful tactics, proof snippets, and WIT steps with their required premises.
- If a cached tactic or proof route fails in the current context, record why and increment the failure count rather than retrying blindly.
- Do not use a cached step unless its hypotheses, domains, and target shape match the current goal.

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

### Stop Conditions

Stop the current search branch and report `GAP`, `PARTIAL`, or `FAILED_ATTEMPT` when:

- the same failure class repeats three times without reducing the obligation,
- all active sketches depend on the same unproved bridge,
- the next step requires an external theorem that is unavailable or unformalized within budget,
- counterexample pressure shows the current statement is probably false or missing a hypothesis,
- repairing the sketch would require changing the original theorem target,
- the user or run budget is exhausted.

Failure report template:

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

### Supply Search

Goal: find facts that could solve the target.

Output:

- candidate theorem/fact,
- exact statement needed,
- hypotheses to verify,
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
- minimality if relevant.

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
- specify construction,
- prove forward direction,
- prove reverse direction,
- prove polynomial/resource bound,
- identify preserved property,
- test gadget edge cases.

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

1. Restate the rejected target.
2. List exactly cited premises.
3. Determine whether the inference is:
   - valid but too compressed,
   - missing a premise,
   - using an unstated theorem,
   - false as stated,
   - out of scope,
   - target drift.
4. Return one of:
   - split into sublemmas,
   - add a legitimate missing hypothesis,
   - cite/prove a missing theorem,
   - weaken the step,
   - mark `GAP`,
   - produce counterexample.

For Lean/compiler failures, use the Repair Diagnosis Protocol before proposing edits:

```text
Failure class:
Compiler/verifier evidence:
Likely cause:
Minimal repair:
Risk:
```

Allowed failure classes:

- wrong_tactic
- wrong_theorem
- missing_hypothesis
- unknown_identifier
- type_mismatch
- coercion_issue
- unsolved_goal
- target_drift
- forbidden_escape
- import_missing
- vacuous_proof
- missing premise
- theorem precondition not proved
- algebra/logic error
- quantifier or domain mismatch
- out-of-scope reference
- case not closed
- step too compressed
- false statement

## Handoff To Witsoc Generator

When a `.wit` artifact is needed for a nontrivial problem, hand off:

```text
Result type:
Target:
Definitions:
Hypotheses:
Conclusion:
Proof strategy:
Lemma sequence:
Dependency graph:
External facts to CITE:
Theorem preconditions to prove:
External theorem replacements:
Recommended case split:
Known gaps:
Counterexamples checked:
Recommended WIT structure:
Lean/formalization notes:
```

For open-problem progress, use this expanded handoff:

```text
Open problem:
Current status: OPEN | PARTIAL | CONDITIONAL | CONJECTURE | FAILED_ATTEMPT
Sketch id:
Parent sketch:
Artifact target:
Result type: lemma | conditional theorem | counterexample | obstruction | computation | failed attempt
Statement:
Assumptions:
Evidence:
Proof sketch or computation:
Known gaps:
Why this helps the open problem:
Definitions:
Hypotheses:
Conclusion:
Dependency graph:
External facts to CITE:
Theorem preconditions to prove:
External theorem replacements:
Counterexamples checked:
Recommended WIT structure:
Lean/formalization notes:
```

Keep the handoff concise enough that generator can turn it into labeled WIT steps without redoing exploration. If a repair needs broad theorem search, Generator should return here with the rejected label, cited premises, and verifier reason.

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
