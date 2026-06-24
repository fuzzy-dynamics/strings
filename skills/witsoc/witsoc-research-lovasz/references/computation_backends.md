# Computation Backends

Use this to choose the right computation backend and artifact format.

## Backend Selection

```markdown
### Computation Backend
- Problem type:
- Backend: exhaustive_python | random_search | SAT | SMT | ILP | graph_search | number_theory_search | finite_model | CAS
- Completeness: complete | bounded | heuristic
- Certificate type:
- Replay command:
- Output path:
```

## Available Local Scripts

- `scripts/experiments/graph_search.py`: enumerate small graphs and simple graph invariants.
- `scripts/experiments/number_theory_search.py`: exact arithmetic for divisor sums, multiplicative ratios, valuations, and bounded searches.
- `scripts/experiments/finite_model_search.py`: generic finite tuple/model search from a Python predicate module.
- `scripts/sat_backend.py` (`witsoc sat`): the verified SAT backend — per-domain encoders (`ramsey`, `vdw`, `schur`, `graph-coloring` with cycle/complete/grotzsch families or explicit edge lists, `covering` systems, raw `dimacs`), cube-and-conquer splitting (`--cubes D`: all 2^D assignments of the most frequent variables — exhaustive by construction, so all-cubes-UNSAT is a sound refutation), solver chain (kissat/cadical with DRAT proof logging when installed, built-in DPLL with a decision budget otherwise), and independent verification of BOTH answers: SAT witnesses are re-evaluated in-process, UNSAT proofs are re-checked by drat-trim (external) or honestly labeled `internal_exhaustive` (built-in). `--prove` hands the instance's decidable Lean form to the kernel-gated prover — the only path above CHECKED. Inside an engine-dispatch campaign, set `context['finite_reduction'] = {encoder, params}` and the `finite_reduction` bandit arm runs it (L2 on a checked certificate); with no explicit encoding the arm self-seeds via `reduction_hunt.detect`.
- `scripts/opt_backend.py` (`witsoc opt`): W4 ILP/SDP — exact pure-Python branch-and-bound ILP over bounded integer variables (`OPTIMAL`/`INFEASIBLE` are exhaustive claims; budget stops are honest `UNKNOWN`/`INCUMBENT`); `sdp-round` completes the SDP-discovery chain (any numeric solver's candidate matrix → bounded-denominator rationals → exact PSD verification via the flag-algebra rational elimination); `solvers` reports installed external backends (cvxpy/scipy/pulp/mip) and the activation chain.
- `scripts/tactic_ngrams.py` (`witsoc tactics`): W3 — tactic sequences mined from every verified proof by goal signature; the prover races them automatically.
- `scripts/reduction_hunt.py` (`witsoc reduction-hunt`): the reduction-hunting mode — deterministic signature scan over the frozen target/barrier text for finite-reducible shapes (Ramsey, van der Waerden, Schur, chromatic number, covering systems), then an upward instance scan per family: verified SAT witnesses are lower bounds, the first checked UNSAT closes the bracket, budget stops emit `next_escalation` (rerun with a real SAT solver or a higher budget). Emits `computational_certificate` DAG node drafts with `proposed_status` only. Run it as a standing step on any open target whose domain admits finite instances: `python3 reduction_hunt.py --run-dir runs/<task>`.

Run Python tools with `python3` explicitly. Replay commands and research notes
must not use bare `python`.

## Certificate Rules

- Every computation must write machine-readable output.
- Bounded searches must state bounds.
- Random searches must state seed.
- Counterexamples must be minimized when feasible.
- Repro commands go in `research.md`.
- Certificates go in `runs/<task>/experiments/`.
