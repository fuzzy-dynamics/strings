# The two-part knowledge DB

Witsoc's persistent mathematical knowledge is split into two stores with
opposite contracts. The split exists so that curated, always-trustable
reference material can be indexed aggressively and shipped with the skill,
while run-generated knowledge stays in one shared, append-friendly place that
every agent on this machine can read and write.

| | Part 1 — REFERENCE atlas | Part 2 — LIVE library |
|---|---|---|
| Tool | `witsoc atlas` (`scripts/theorem_atlas.py`) | `witsoc library` (`scripts/lemma_library.py`) |
| Content | Common theorems: bundled core lemmas, built Mathlib atlas, promoted lemmas | Everything deep runs establish: harvested proofs, WIT records, value model |
| Mutability | Read-only to runs (sole writer: `atlas promote`) | Read-write; deep runs push continuously |
| Location | `scripts/core_lemma_atlas.json` (bundled) + `~/.witsoc/reference/` | `~/.witsoc/global_library/lemmas.db` |
| Index | SQLite `~/.witsoc/reference/atlas_index.sqlite3` (PageRank + token index, auto-rebuilt) | SQLite, token-cosine search with trust-tier boost |
| Trust | Curated; promoted entries are kernel-verified by construction | Tiered: WIT_STRUCTURE < WIT_RECEIPT < LEAN_VERIFIED |

## Part 1: reference atlas (`witsoc atlas`)

Merged, in priority order (first definition of a module wins):

1. `WITSOC_ATLAS` env — explicit single-file override (also what the prover's
   `default_atlas()` honors).
2. `scripts/core_lemma_atlas.json` — curated core lemmas bundled with the skill.
3. `~/.witsoc/reference/*.json` — e.g. `promoted_lemma_atlas.json`, or a
   Mathlib atlas produced by `build_mathlib_atlas.py` and dropped here.
4. `~/.witsoc/mathlib_atlas.json` — legacy location, still read.

The SQLite index is rebuilt automatically whenever any source file changes
(content fingerprint over path/mtime/size), so queries are always consistent
with the JSON sources of truth and a 6MB Mathlib atlas is parsed once, not per
query. Scoring matches `mathlib_atlas.py`: `0.55*symbol_overlap + 0.35*cosine
+ 0.10*pagerank` (PageRank precomputed at index time).

```bash
witsoc atlas search --query "Nat.mul_comm multiplication commutative" --limit 5
witsoc atlas get --module core.Nat.mul_comm
witsoc atlas stats          # node counts per source, index freshness
witsoc atlas paths          # where everything lives
witsoc atlas reindex        # force rebuild
witsoc atlas export --out merged_atlas.json   # one file for WITSOC_ATLAS / the prover
witsoc atlas promote        # live -> reference (LEAN_VERIFIED only, idempotent)
```

`export` produces a single merged atlas schema-compatible with the prover:
`WITSOC_ATLAS=merged_atlas.json witsoc prove --search ...` gives the search the
whole curated reference as premise candidates.

## Part 2: live library (`witsoc library`)

One SQLite DB at `witcore.global_library()` — default
`~/.witsoc/global_library/lemmas.db`, overridable with `WITSOC_LEMMA_LIBRARY`
(or `WITSOC_HOME` to move the whole witsoc home). The CLI defaults to this
GLOBAL path, so any agent in any working directory reads and writes the same
DB — pass `--library DIR` only to use an isolated store (tests do this).

Who pushes into it:

- `witsoc prove --search --record-library` — every kernel-discharged goal.
- engine-dispatch campaigns (the research director's deep runs) — the default
  prover now runs with `--use-library --record-library` against the global
  library, so campaigns compound across runs automatically.
- `witsoc flywheel` — closure harvesting + value-model retraining (the trained
  `value_model.json` lives in the library dir).
- `witsoc package --record-library` / `witsoc lovasz-prover-dispatch
  --record-library` — generator and Lovász harvest hooks.

Who reads it: `witsoc prove --use-library` (token-similar verified proofs as
premise candidates), `proof_search.load_model` (value model), other agents via
`witsoc library search --query ...`.

## The boundary

- Harvest NEVER writes into the reference store. The only live→reference path
  is `witsoc atlas promote`, which copies lemmas whose trust tier is
  `LEAN_VERIFIED` (kernel receipt) into
  `~/.witsoc/reference/promoted_lemma_atlas.json`, idempotently keyed by
  statement hash. Lower tiers are structurally excluded.
- The reference tool has no `add`/write subcommand at all; bundled and legacy
  sources are never modified by any command.
- Status/trust semantics are unchanged by storage location: where a lemma
  lives allocates effort and retrieval rank only — it never upgrades a claim's
  status (the standing witsoc invariant).

Also under `~/.witsoc` but part of neither knowledge store: `lean_cache.json`
(content-hash verification cache — droppable, regenerates) and
`populations.sqlite3` (sketch-evolution run state).
