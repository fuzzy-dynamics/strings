# Cross-Run Research Memory

Use cross-run memory to carry reusable mathematical lessons across Lovasz runs.

## Tooling (R4 — this is implemented, not aspirational)

The global store is `~/.witsoc/knowledge.sqlite3` (`witsoc memory`,
`scripts/knowledge_store.py`):

- **Write**: `witsoc memory sync-run runs/<task>` lifts a run's failure memory
  (`lovasz.soc` + `failure_memory.jsonl`) into the global store. The driver's
  `--finalize` and `explorer_return_packet.py` do this automatically.
- **Read**: `witsoc memory query --statement "..." --method "..."` —
  `lovasz_worker_dispatch` consults it automatically alongside the per-run
  `.soc`, so a method that failed in ANOTHER run raises repeat risk here.
- **Priors (L5)**: campaign outcomes are recorded per goal signature;
  `engine_dispatch` campaigns start from `witsoc memory priors --target "..."`
  automatically.

A prose `runs/witsoc_research_memory.soc` may still hold narrative lessons;
the machine-matched memory above is authoritative for repeat-risk decisions.
This complements per-task `runs/<task>/lovasz.soc`.

## Read Before

Read cross-run memory before:

- selecting a domain playbook,
- choosing theorem families,
- repeating a known failed method,
- launching a proof campaign,
- declaring a barrier new.

## Write After

Write reusable entries for:

- successful proof patterns,
- dead methods,
- domain-specific barriers,
- useful theorem retrievals,
- reusable counterexample families,
- formalization pitfalls,
- benchmark-like solved subproblems.

## Entry Format

```text
INSIGHTS:
  - [domain] reusable statement. SEE runs/<task>/...

FAILED_APPROACHES:
  - id: <domain_method_date>
    method: <method>
    blocker: <blocker>
    do_not_repeat: <condition>
    reusable_lesson: <lesson>
```

Keep entries concise and point to detailed run files.
