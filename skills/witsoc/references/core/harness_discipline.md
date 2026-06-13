# Harness Discipline

Load this protocol when Witsoc runs under an external harness — a benchmark
driver, plane/orchestrator session, eval runner, or any system that snapshots
artifacts and captures a "final message" on its own schedule.

Why this exists: in the 2026-06-05 miniF2F plane run, 14 of 26 tasks were
finished by the harness while a delegated proof worker was still running. The
harness captured mid-flight narration ("the verifier is still running; I'm
waiting...") as the final message and the first stable `.lean` file as the
artifact. Kernel re-checking later showed every one of the 12 tasks that
delivered a real final report had a valid proof, while 7 of the 14 cut-off
tasks had broken artifacts and 1 had none. The math was fine; the turn
discipline was not.

## Rules

1. **Never end a turn with delegated work in flight.** The harness treats the
   orchestrator's turn end as task completion. If a proof worker, verifier, or
   critic is still running, poll or block until it finishes or the budget is
   spent. Delegation is not progress until its result is collected.

2. **Every message must be snapshot-safe.** Any message you emit may be
   captured as the final one. Never emit bare narration ("I'm waiting for the
   verifier"). Every message states: current status label, artifacts so far,
   and what evidence exists right now. If the run is cut at that instant, the
   message must still be an honest report.

3. **Report files are written incrementally, not at the end.** Keep the
   required report/sketch file updated as work proceeds, starting with an
   honest skeleton (`status: OPEN, verification: not yet run`). A snapshot at
   any moment then contains a true state instead of nothing.

4. **An artifact on disk is a claim.** Harnesses collect whatever file
   matches the artifact pattern the moment it stabilizes. Do not park an
   unverified draft `.lean`/`.wit` at the deliverable path and walk away: keep
   drafts at a scratch path (or clearly statused), verify, then move the
   verified artifact into place. When the deliverable must exist early, its
   header comment carries the honest status (`-- Status: UNVERIFIED`) until
   the verifier passes.

5. **Verification leaves a receipt next to the artifact.** When a verifier
   script or `lake` build is run, write its stdout/stderr and exit code to
   `<artifact>.verify.log`. "Verified, exit 0" in prose without the log is not
   a receipt.

6. **The final message is a self-contained report.** Status label from
   `references/core/status.md`, artifact paths, verification mechanism and
   exit code, and remaining gaps. Assume the reader sees nothing else.

7. **Budget endgame.** When the task timeout approaches and work is
   unfinished, stop starting new work; spend the remaining time writing the
   honest current state: best artifact, its exact verification status, and
   the concrete blocker. A true `FAILED_ATTEMPT`/`GAP` report outscores a
   broken artifact captured mid-edit.
