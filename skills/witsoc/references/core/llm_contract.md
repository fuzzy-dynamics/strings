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
python3 ~/.openscientist/skills/witsoc/witsoc.py explorer packet runs/<task>
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz packet runs/<task>
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

## Subskill Boundaries

Explorer is the front door for serious mathematics. It freezes the target,
classifies status, searches theorem candidates, applies counterexample pressure,
ranks proof paths, and emits a Generator handoff or Lovasz barrier packet.

Lovasz is the barrier engine for open, unsolved, frontier, or blocked targets
after Explorer has prepared a barrier packet. It builds proof-DAGs, attacks
actual barrier lemmas, dispatches focused workers, records failed approaches,
and returns reviewed products to Explorer.

Generator is the artifact engine. It starts after Explorer accepts a frozen
target and handoff, preserves target hash, creates WIT/Lean artifacts, runs
checks, and reports exact verifier status without silently changing the target.

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
```

Prefer concise evidence-backed summaries over broad mathematical prose.
