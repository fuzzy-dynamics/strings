# Codex/Claude Orchestrator Contract

This contract is for Codex, Claude Code, and similar shell-capable coding
agents using Witsoc as the mathematical decision-support layer.

## Authority Boundary

Witsoc recommends; the orchestrator decides. The orchestrator owns strategy,
fanout, worker assignment, budget, reframing, and final user-facing decisions.
Witsoc owns mathematical discipline: target freeze, evidence gates, claim-status
honesty, packet structure, and recovery commands.

Witsoc may block unsupported claim-status upgrades. It must not block creative
search, alternate strategies, reframing, or additional worker fanout.

Witsoc should be used as a toolbox, not a controller. Its packets should expose
available tools, candidate moves, tradeoffs, evidence gates, creative openings,
and failure routes. The orchestrator chooses the composition. A good Witsoc
answer makes the next few useful moves visible without pretending that one move
is the only valid plan.

## Launcher

Prefer the root launcher from any working directory:

```bash
python3 ~/.openscientist/skills/witsoc/witsoc.py ...
```

Do not rely on `witsoc`, `python3 bootstrap.py`, or
`python3 scripts/witsoc.py` unless the working directory and PATH are known.

If runtime files are missing:

```bash
python3 ~/.openscientist/skills/witsoc/bootstrap.py --replace
```

If `bootstrap.py` is missing:

```bash
python3 -m pip install -U witsoc
python3 -m witsoc restore-skill --target ~/.openscientist/skills/witsoc --replace
```

## Packet-First Workflow

Use compact packets before loading long references:

```bash
python3 ~/.openscientist/skills/witsoc/witsoc.py route --field json "<task>"
python3 ~/.openscientist/skills/witsoc/witsoc.py orchestrator-plan route "<task>"
python3 ~/.openscientist/skills/witsoc/witsoc.py next-action runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py proof-workflow runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py scorecard runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py ui-summary runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py ui-summary runs/<task> --write --deep
python3 ~/.openscientist/skills/witsoc/witsoc.py explorer target-model runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py explorer packet runs/<task>
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz kernel runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz judge runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz autopsy runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz packet runs/<task>
python3 ~/.openscientist/skills/witsoc/witsoc.py generator obligations runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py generator packet runs/<task>
```

Good packets expose:

```json
{
  "recommended_next_action": "",
  "orchestrator_options": [],
  "required_evidence": [],
  "commands_to_run": [],
  "files_to_read": [],
  "spawn_suggestions": [],
  "claim_status": "unsupported|partial|verified|blocked",
  "stop_conditions": [],
  "recovery_if_blocked": []
}
```

`next-action --write` is the cheap control surface for serious runs. It should
materialize or refresh `witsoc_next_action.json`, `.soc` memory, and the status
report scaffold, then tell the orchestrator the exact gap, evaluator, success
condition, and failure route.

`proof-workflow --write` is the cheap proof-state surface. It should
materialize or refresh `proof_workflow.json` and report the current proof
phase, target hash, discovered artifacts, missing obligations, next specialist
owner, expected artifact, and proof gates that must not be skipped. Use it
whenever a run might jump between Explorer, Lovasz, and Generator.

`scorecard --write` is the cheap subsystem-readiness surface. It should
materialize or refresh `witsoc_scorecard.json`, grading Explorer target
control, Generator obligation control, Lovasz barrier diagnosis, and proof
workflow readiness. Use it before final reports and before deciding that a deep
run is merely "working" rather than missing a concrete packet.

`ui-summary --write` is the UI and report preview surface. It should
materialize or refresh `witsoc_ui_summary.json`, `reports/witsoc_preview.md`,
`reports/witsoc_report.md`, and `reports/report.md`. Use it whenever a plugin,
report preview, or user-facing checkpoint needs one readable state rather than
several specialist JSON files. For deep runs, add `--deep` so it scans all
WIT, Lean, SOC, JSON, receipt, DAG, formalization, and report artifacts.

For Lovasz runs, `.soc` is an active memory surface. Use:

```bash
python3 ~/.openscientist/skills/witsoc/witsoc.py soc-memory context runs/<task>
```

before route choice or worker dispatch. The context packet exposes current
state, active barriers, reusable insights/tools, recent failures, progress,
queue, and orchestrator notes. It guides decisions but does not own strategy.

## Subskill Boundaries

Explorer is the front door for serious mathematics. It freezes the target,
classifies status, builds a target model, searches theorem candidates, applies
counterexample pressure, ranks proof paths, and emits a Generator handoff or
Lovasz barrier packet.
It specializes in discovery and arbitration.

Lovasz is the barrier engine for open, unsolved, frontier, or blocked targets
after Explorer has prepared a barrier packet. It builds proof-DAGs, attacks
actual barrier lemmas, dispatches focused workers, records failed approaches,
clusters barrier autopsies, and returns reviewed products to Explorer.
It specializes in barrier pressure and research-state memory.

Generator is the artifact engine. It starts after Explorer accepts a frozen
target and handoff, preserves target hash, creates WIT/Lean artifacts, runs
checks, maintains an obligation graph, and reports exact verifier status
without silently changing the target.
It specializes in proof artifacts and verifier receipts.

These subskills are specialists. They do not own global strategy. The
orchestrator may call them in the default sequence, run them in parallel, skip
one for a justified reason, add outside tools, or invent a different route while
preserving Witsoc's evidence and honesty gates.

## Failure Repairs

- Missing runtime: run `python3 ~/.openscientist/skills/witsoc/bootstrap.py --replace`.
- PATH missing `witsoc`: use `python3 -m witsoc ...` or the root launcher.
- Wrong working directory: use absolute `~/.openscientist/skills/witsoc/witsoc.py`.
- Skipped Explorer on serious math: return to Explorer and freeze/classify target.
- Skipped Lovasz on open problem: create barrier packet and run Lovasz before final report.
- Generator without handoff: stop Generator and request Explorer handoff.
- Unsupported solved claim: downgrade to unsupported, partial, blocked, or gap.
- Target drift: restore the frozen target hash or record explicit target mutation.

## Report Shape

Final reports should be UI-ready:

```text
Status:
Best product:
Evidence:
Gaps:
Commands run:
Artifacts:
Next actions:
UI summary:
Preview report:
```

Prefer concise evidence-backed summaries over broad mathematical prose.
