# Witsoc Architecture (R0/R1)

The structural map of the system. `python3 scripts/witsoc.py map` prints the
machine-readable version; this file explains it.

## Layout rule

Files stay **flat on disk** under `scripts/` — the external
`skill-which witsoc/scripts/<name>.py` resolution contract (orchestrators,
SKILL.md command blocks) depends on stable flat paths. The *logical* structure
is the `GROUPS` registry in `witsoc.py`: every tool belongs to exactly one
group, the flat CLI is derived from the registry (a collision is a startup
error), and `witsoc <group> <cmd>` / `witsoc <group>` / `witsoc map` expose
the grouping.

## The five groups

| Group | Role | Boundary rule |
|---|---|---|
| `engines` | Strategy-free services: input in, certificate/result out | Never assign trust, never choose the next move |
| `campaign` | Lovasz-owned solver machinery: loops, dispatch, budgets, evolution, scheduling | Campaign entry points need a run context or explicit `--standalone` |
| `knowledge` | The stores: atlases, libraries, ledgers, registries | Trust tiers + provenance mandatory; metadata never upgrades a claim |
| `gates` | Honesty: validators, skeptics, audits, claim protocols | Demote-only; a gate never upgrades |
| `core` | Run substrate: WIT cycle, routing, artifacts, the run ledger | Deterministic; no LLM |

`witsoc services` remains the boundary-contract registry (a curated subset of
the map with per-service contracts).

## R1: the unified run ledger

The historical design scattered one run's state across ~15 JSON ledgers
(`proof_dependency_dag.json`, `worker_results.json`, `gap_feedback.json`,
`blueprint.json`, `actual_lemma_queue.json`, `skeptic_reviews.json`, handoffs,
`lovasz.soc`, failure/retry/mutation ledgers…), with the same fact stored in
several files and a fleet of validators checking cross-file consistency.

`run_ledger.py` (`witsoc ledger`) is the replacement substrate: **one
`run.sqlite3` per run, the DAG node as the single entity.** Worker results,
gap feedback, blueprint obligations, and skeptic reviews are records attached
to nodes; "blueprint status" and "gap class" are computed views, not files.

- `ingest <run>` — read every legacy JSON ledger into the database
  (idempotent upserts; safe to re-run after any tool writes).
- `status <run>` — the single-pane view that previously required reading ten
  files: phase, budget, node counts, ready frontier, gaps, attempts.
- `consistency <run>` — the cross-ledger validators as QUERIES: accepted
  nodes need reviews and evidence, dependencies resolve to accepted nodes,
  no cycles, failed nodes carry gap feedback, statuses legal.
- `export <run>` — regenerate the legacy JSON ledgers from the database, so
  current consumers keep working during migration.
- `nodes <run>` — the node-centric joined view (node + attempts + reviews +
  gaps + blueprint state in one record).

### Migration path

1. **Now (R1):** the ledger is a derived index — tools keep writing JSON;
   `ingest` after each phase gives the unified view and query-based
   consistency. The E2E and validators run on either representation.
2. **Next (R1.5):** high-traffic readers (reports, return packets, manifests)
   read from the ledger; writers dual-write through a small witcore API.
3. **Then (R2):** the ledger is the only store; `export` exists solely for
   archival/interop; the redundant per-fact files and their cross-file
   validators are retired.

## Deferred (explicitly)

- Physical file moves into package directories — blocked on the skill-which
  flat-path contract; revisit only with a coordinated orchestrator change.
- `witcore.py` split into submodules — cosmetic until R3's batch/session
  engine room work, where it pays for itself.
