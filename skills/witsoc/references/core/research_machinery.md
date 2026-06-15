# Research Machinery

This protocol turns Lovasz from a prose strategy into an executable research loop.

## Pipeline

```text
Explorer freeze
-> Lovasz proof-DAG decomposition
-> counterexample/falsification engines
-> theorem retrieval with precondition audit
-> parallel proof-style workers
-> skeptic workers
-> WIT + Lean + SafeVerify per accepted node
-> DAG assembly checker
-> final Generator WIT + Lean + SafeVerify
```

## Subproblem Selector

Lovasz scores every candidate subproblem before dispatch:

```text
score =
  4 * actual_barrier_lemma_leverage
+ 3 * relevance_to_original
+ 2 * formalization_feasibility
+ 2 * lean_mathlib_availability
+ 2 * counterexample_resistance
+ 1 * novelty_potential
- 2 * dependency_count
- 2 * target_drift_risk
- 1 * expected_proof_length
- 4 * weaker_variant_drift
```

Use a 0-5 scale for each term. Prefer high-score subproblems that attack the actual missing barrier lemma and have a clear WIT/Lean target. A weaker variant with high tractability but low actual-barrier leverage should lose to a harder lemma that directly unlocks the frozen target.

## Counterexample Engine

Before proving a node, run the strongest available falsification:

- small finite model search,
- graph search,
- SAT/SMT encoding,
- finite algebra/model enumeration,
- number-theory brute force,
- randomized construction search,
- boundary and degeneracy cases.

If a counterexample appears, minimize it and mark the proof node `REJECTED` or turn it into a verified counterexample target.

## Theorem Retrieval Audit

Every external theorem candidate must record:

- exact statement,
- source,
- required hypotheses,
- conclusion,
- formal availability in Lean/mathlib,
- missing preconditions,
- whether it actually applies to the frozen target.

Do not promote a theorem into `external_facts` unless its preconditions are satisfied or an explicit subproblem covers them.

## Lean/Mathlib Feasibility Scout

Before assigning a formal proof worker to a difficult node, run a feasibility scout when possible:

- identify mathlib definitions and namespace choices,
- locate theorem names and import paths,
- check whether required concepts are already formalized,
- estimate tactic/library difficulty,
- identify local definitions that would reduce formalization risk,
- report whether the node is `FORMALIZATION_READY`, `NEEDS_LOCAL_DEFINITIONS`, `NEEDS_MATHLIB_THEOREM_SEARCH`, or `POOR_FORMALIZATION_TARGET`.

Lovasz should avoid elegant informal lemmas that are poor formalization targets unless they are mathematically necessary.

## Worker Families

For serious targets, use distinct worker families when available:

- extremal or minimal counterexample,
- algebraic or spectral,
- probabilistic,
- constructive or algorithmic,
- induction or descent,
- reduction or gadget,
- computational search,
- formalization-first.

Workers must not share proof assumptions unless the handoff declares them.

Every worker receives target-freeze hashes for the original statement, canonical target, definitions, hypotheses, and conclusion. Any mismatch is `REJECTED: target_drift`.

Every proof worker also receives a session-scoped dedicated proof worktree path. WIT and Lean files must be generated there, never in the coordinator root or another proof target's worktree. Record the proof worktree in `proof_worktrees.json` and `worker_results.json`, then preserve artifacts/logs/receipts outside the worktree before cleanup.

## DAG-Coverage Spawning

Lovasz may prepare independent worker packets when the DAG, target, and
artifact justify it. Witsoc is the math skill; it does not decide or hardcode
subagent fanout. The Plane/theater orchestrator chooses how many packets to
launch concurrently under its worker policy. Use these defaults as lower-bound
coverage guidance, not hard caps:

- `quick`: spawn only when worker spawning is useful.
- `deep`: expand over every justified independent DAG node.
- `campaign`: spawn by DAG coverage,
  falsification need, computation, formalization, and skeptic-review demand.

Every spawned worker packet must still validate as exact with target hashes,
forbidden drift, expected artifact, and stop condition. More workers are useful
only when they cover distinct DAG nodes, method families, counterexample
pressures, formalization blockers, or skeptic obligations.

## Skeptic Workers

Every promising nontrivial node needs a skeptic pass before synthesis:

- search for counterexamples,
- detect hidden assumptions,
- compare WIT and Lean targets,
- check target-freeze hashes,
- reject circular dependencies,
- identify missing theorem preconditions.

Skeptic failure sends the node back to Lovasz as `REJECTED`, `FAILED_ATTEMPT`, or `GAP`. A node cannot become `PROVED_SKETCH`, `CHECKED`, or `VERIFIED` unless `skeptic_review_id` points to a passing skeptic review.

## Actual Lemma Queue

Maintain `actual_lemma_queue` for every open/unsolved/unconfirmed run:

- exact lemma statement,
- which barrier it attacks,
- what part of the frozen target it unlocks,
- priority and target-fidelity estimate,
- current status,
- next exact attempt.

Lovasz workers should pull from this queue before selecting weaker products. If a weaker product is selected, its record must explain how it helps a queued actual lemma.

## Retry Ledger

Every repeated method family against the same target hash must record what changed. Repeating a method with no new theorem, encoding, invariant, counterexample information, or formalization change is invalid.

## Target Fidelity And Provenance

Every worker result and final Generator artifact records:

- `target_fidelity` on a 0-1 scale,
- `skeptic_review_id`,
- `wit_target_sha256`,
- `lean_target_sha256`,
- `frozen_target_sha256`.

Accepted non-partial claims require target fidelity at least `0.8`. `VERIFIED` claims require WIT, Lean, and frozen target hashes to match.

## Verified Lemma Library

Record reusable verified nodes with:

- statement,
- domain and definitions,
- dependencies,
- WIT path,
- Lean path,
- proof strategy,
- tags,
- source run,
- target-freeze hashes.

Lovasz should reuse verified lemmas across runs only when definitions and hypotheses match exactly.

Store per-run entries in `runs/<task>/verified_lemma_library.md`. Also append machine-readable cross-run entries to `runs/witsoc_verified_lemma_library.jsonl` when available. Each JSONL record must include `statement`, `definitions_hash`, `hypotheses_hash`, `target_hash`, `wit_path`, `lean_path`, `safeverify_status`, `source_run`, and `status`.

## Failure Memory

Record failures with:

- exact failed claim,
- method family,
- why it failed,
- counterexample or Lean diagnostic if any,
- theorem-precondition gap,
- target-drift evidence,
- route to avoid unless new information appears.

Store per-run failures in `runs/<task>/failure_memory.md`. Also append cross-run failures to `runs/witsoc_failure_memory.jsonl` when available. Do not repeat a failed method family against the same frozen target unless a later record states the new information that changes the route.

## Typed Search Entry Points

Use deterministic bounded search helpers before proof workers spend time on fragile lemmas:

```bash
SEARCH="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/research_search.py)"
python3 "$SEARCH" number-theory -- --mode multiperfect --limit 10000
python3 "$SEARCH" graph -- --n 6 --predicate triangle_free --limit 50
python3 "$SEARCH" finite-model -- --arity 3 --domain 6 --predicate 'sum(x) == 7'
```

Every search output must be logged with exact command, bounds, predicate, date, and target-freeze hash. Treat bounded search as `CHECKED` evidence only for the searched finite domain, or as counterexample evidence if it returns a witness against the frozen target.

## Assembly Checker

Before final Generator:

- every proof-DAG node has an exact statement and status,
- every edge points to an existing dependency,
- there are no dependency cycles,
- all assumptions propagate to the final target,
- every external theorem precondition is discharged,
- no node depends on the final theorem,
- no conjecture is used as a theorem,
- local lemmas compose into the original frozen target or an explicitly narrower target,
- target-freeze hashes match across workers,
- all accepted `VERIFIED` nodes have WIT + Lean + SafeVerify evidence.
- `final_synthesis_audit` passes before final Generator runs.

For Lovasz run directories, run:

```bash
VALIDATE="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_lovasz_run.py)"
python3 "$VALIDATE" "$PLANE_SESSION_DIR/lovasz-run" --mode deep
```

Use `--mode quick`, `--mode deep`, or `--mode campaign` to match the route
classification. The validator is a completion gate: if it rejects missing
ledgers, empty DAGs, missing worker results, missing skeptic reviews, or partial
results without remaining barriers, the run is not shippable.
