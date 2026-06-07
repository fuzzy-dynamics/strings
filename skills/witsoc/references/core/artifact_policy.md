# Artifact Policy

Use this protocol for every WIT, Lean, receipt, SOC, log, proof worktree, report, and generated JSON packet.

## Registry First

Every artifact should be registered in `witsoc_artifacts.json` with:

- path,
- type,
- owner phase,
- target hash,
- status,
- worktree path and cleanup status when applicable.

The plugin and final report should read the registry first and use filesystem scanning only as fallback.

## Required Artifact Metadata

Artifacts tied to proof claims must record:

```json
{
  "artifact_id": "",
  "type": "wit | lean | receipt | log | report | soc | proof_worktree | json",
  "path": "",
  "target_hash": "",
  "claim_id": "",
  "owner_phase": "witsoc-explorer | witsoc-research-lovasz | witsoc-generator",
  "status": "created | checked | verified | failed | stale",
  "created_by": "",
  "worktree_status": ""
}
```

## Stale Artifact Rule

An artifact is stale if its target hash differs from the frozen target hash and no target mutation record explains the difference. Stale artifacts may be cited as failed attempts or historical context, not as evidence.

## Worktree Rule

WIT/Lean proof artifacts for nontrivial claims must be generated in a session-scoped proof worktree. Preserve proof files, logs, receipts, SafeVerify records, and reports. Clean temporary Lean projects when allowed, but keep evidence artifacts.
