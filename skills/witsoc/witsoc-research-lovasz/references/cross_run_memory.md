# Cross-Run Research Memory

Use cross-run memory to carry reusable mathematical lessons across Lovasz runs.

## File

Maintain:

```text
runs/witsoc_research_memory.soc
```

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
