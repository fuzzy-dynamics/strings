# Tooling Discipline

Prefer explicit, deterministic tools over model-written shell incantations.

## WIT Tooling

Preferred future interface:

- `run_wit_init`
- `run_wit_check`
- `run_wit_audit`
- `run_wit_context`
- `run_wit_verify`
- `run_wit_receipt`
- `run_wit_status`
- `run_wit_cycle`
- `run_target_freeze_check`
- `run_handoff_validate`
- `run_proof_dag_validate`
- `run_toolchain_check`
- `run_research_search`
- `run_empirical_miner`
- `run_finite_graph_backend`
- `run_smt_synthesizer`
- `run_lean_tactic_scan`
- `run_mathlib_atlas`
- `run_asymptotic_analyzer`

When typed API tools are unavailable, use the existing deterministic scripts or native `wit` CLI. Do not use an LLM for structural checking, context building, status parsing, receipt parsing, or target-freeze checks.

## CLI Consolidation Target

The shell scripts are a compatibility layer. Long term, consolidate WIT cycle behavior into a single typed CLI, preferably Rust or Go, so multiline mathematical content, structured handoffs, target hashes, receipts, and verifier contexts are handled deterministically.

Suggested shape:

```text
witsoc init --handoff runs/task/handoff.json --out runs/task/artifact.wit
witsoc check runs/task/artifact.wit
witsoc cycle runs/task/artifact.wit --handoff runs/task/handoff.json --out runs/task/
witsoc freeze-check runs/task/artifact.wit --handoff runs/task/handoff.json
witsoc handoff validate runs/task/handoff.json
witsoc receipt runs/task/artifact.wit --from verifier.txt
witsoc toolchain check --strict
witsoc research-search number-theory -- --mode multiperfect --limit 10000
witsoc empirical-mine --domain graphs --max-n 5 --limit 1000
witsoc finite-graph --n 6 --triangle-free --tree path:4 --omit-induced-tree --min-chromatic 3
witsoc smt-synthesize --file runs/task/reduction.smt2
witsoc lean-tactic-scan --file runs/task/frozen_lean_target.lean
witsoc mathlib-atlas --query "finite set cardinality" --signature "Finset.card"
witsoc asymptotic-analyze --expr "log(n) = o(n)" --variable n
witsoc olympiad profile --statement "∀ n : Nat, n + 0 = n"
witsoc olympiad prove --statement "∀ n : Nat, n + 0 = n"
witsoc olympiad eval --suite benchmarks/olympiad_suite.json --mode fast
witsoc open-rungs build --target "Erdos-Straus conjecture" --domain number_theory
witsoc rung-saturation --target "Erdos-Straus conjecture" --domain number_theory --top 24
witsoc barrier-attack init runs/erdos-straus --target "Erdos-Straus conjecture" --domain number_theory
witsoc lovasz-top-tier prepare runs/erdos-straus --target "Erdos-Straus conjecture" --domain number_theory
witsoc lovasz-top-tier audit runs/erdos-straus
witsoc lovasz-agent-packets template --role Builder
witsoc open-frontier run --target "Erdos-Straus conjecture" --domain number_theory --run-dir runs/erdos-straus --mode both
```

Until such a binary exists, report the exact script or CLI command used and its status.

## Current Deterministic Helpers

Use these through `skill-which` plus `python3`:

```bash
TOOLCHAIN="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/toolchain_check.py)"
python3 "$TOOLCHAIN"

SEARCH="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/research_search.py)"
python3 "$SEARCH" number-theory -- --mode multiperfect --limit 10000
python3 "$SEARCH" --inflate graph -- --n 6 --predicate triangle_free --limit 50
python3 "$SEARCH" graph -- --n 5 --predicate triangle_free --limit 20
python3 "$SEARCH" finite-model -- --arity 3 --domain 5 --predicate 'sum(x) == 6'

MINER="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/empirical_miner.py)"
python3 "$MINER" --domain graphs --max-n 5 --limit 1000
python3 "$MINER" --domain graphs --graph-family mycielski --iterations 3
python3 "$MINER" --domain graphs --graph-family cycles --max-n 20

GRAPH="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/finite_graph_backend.py)"
python3 "$GRAPH" --n 6 --triangle-free --tree path:4 --omit-induced-tree --min-chromatic 3 --limit 10
python3 "$GRAPH" --n 7 --triangle-free --tree star:3 --omit-induced-tree --min-chromatic 3 --limit 10

SMT="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/smt_synthesizer.py)"
python3 "$SMT" --file runs/task/reduction_constraints.smt2 --pretty

TACTIC_SCAN="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lean_tactic_scan.py)"
python3 "$TACTIC_SCAN" --file runs/task/frozen_lean_target.lean

ATLAS="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/mathlib_atlas.py)"
python3 "$ATLAS" --query "finite set cardinality" --signature "Finset.card"

ASYM="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/asymptotic_analyzer.py)"
python3 "$ASYM" --expr "log(n) = o(n)" --variable n

CAMPAIGN="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lovasz_campaign_template.py)"
python3 "$CAMPAIGN" --template induced-tree-triangle-free
python3 "$CAMPAIGN" --template divisor-sum-asymptotic

WITSOC="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/witsoc.py)"
python3 "$WITSOC" services                                   # the witsoc/Lovasz service boundary registry
python3 "$WITSOC" gap-feedback runs/task                     # L1: classify failures, propose one-axis mutations
python3 "$WITSOC" barrier-attack init runs/task --target "..." --domain number_theory
python3 "$WITSOC" barrier-attack mutate runs/task
python3 "$WITSOC" lovasz-top-tier prepare runs/task --target "..." --domain number_theory
python3 "$WITSOC" lovasz-top-tier audit runs/task
```

`toolchain_check.py` is diagnostic by default. Use `--strict` only when the run must fail if WIT, Lean/Lake, or local Witsoc scripts are missing.

`research_search.py` is for bounded falsification, counterexample pressure, and certificate candidates. Its output is `CHECKED` evidence at most; it never proves a general mathematical theorem by itself.

`finite_graph_backend.py` is the exact bounded graph checker for small graph-theory targets. Use it when the barrier concerns chromatic number, triangle-freeness, and induced containment. Its chromatic-number and induced-subgraph tests are exact on the enumerated finite scope, but the output is still only `CHECKED` bounded evidence unless a separate WIT/Lean proof generalizes the result.

`lovasz_campaign_template.py` provides reusable Lovasz campaign seeds for recurring open-problem shapes. Use it to prevent runs from stopping at "known open" without an actual lemma queue, proof-DAG seed, and worker plan.

`barrier_attack.py` is the default open-problem preflight for Lovasz V2. It
creates named barrier records, saturates partial rungs, merges dispatchable
obligations into `proof_dependency_dag.json`, and appends corresponding lemma
queue entries. `campaign_driver.py` runs this preparation automatically before
dispatch; manual invocation is useful for inspection and review.

`lovasz_top_tier.py` is the high-level readiness bar for serious open-problem
runs. `prepare` materializes barrier/rung/role/success artifacts; `audit`
checks items 2-12 as deterministic conditions; `benchmark` runs the
rediscovery benchmark path. A top-tier run should pass this audit before any
claim is reported outside the campaign.
