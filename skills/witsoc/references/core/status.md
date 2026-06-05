# Status Discipline

Use these labels consistently across Witsoc, Explorer, Generator, proof artifacts, and final reports.

For a `.wit` file's `-- Status:` header, use only the language-level proof statuses from `references/wit.md`: `UNVERIFIED`, `VERIFIED`, `GAP`, or `REJECTED`. Broader research statuses such as `OPEN`, `PARTIAL`, `CONDITIONAL`, `CONJECTURE`, and `FAILED_ATTEMPT` belong in handoffs, reports, comments, or adjacent notes, not in the WIT header.

- `VERIFIED`: structural check passed and a complete accepted receipt covers every obligation. For Lean, the compiler/LSP/REPL check must pass and SafeVerify must pass.
- `UNVERIFIED`: structurally valid or checkable context exists, but no complete accepted semantic receipt.
- `OPEN`: the original research problem is unsolved or currently treated as unsolved.
- `PARTIAL`: a subcase, bound, lemma, obstruction, computation, reduction, or family of cases has been produced while the original target remains unresolved.
- `CONDITIONAL`: the result depends on an explicit unproved assumption, conjecture, unavailable external theorem, or unchecked precondition.
- `CONJECTURE`: a proposed statement supported by evidence or analogy, not a theorem.
- `FAILED_ATTEMPT`: a documented approach failed for a specific reason and should be preserved as negative information.
- `GAP`: an explicit unresolved obligation remains.
- `REJECTED`: structural failure, compiler failure, verifier rejection, target drift, or SafeVerify rejection.

Do not call a proof `VERIFIED` from persuasive prose, examples, `wit check`, `wit verify`, or a single unreviewed proof sketch.

In user-facing final reports, prefer mechanism-specific status flags:

- `STRUCTURE_OK`: structural checking passed.
- `CONTEXT_BUILT`: verifier context was generated; this is not semantic verification.
- `RECEIPT_ACCEPTED`: a complete accepted `.wit.receipt.json` covers the obligations.
- `LEAN_VERIFIED`: Lean/Lake passed and SafeVerify/target-freeze checks passed.

Avoid bare "verified" unless the sentence names the mechanism. For example,
write `LEAN_VERIFIED=yes` or `RECEIPT_ACCEPTED=yes`, not "the proof is
verified", unless the full acceptance contract below is satisfied.

Before reporting `VERIFIED`, enforce:

- all WIT obligations have accepted verdicts,
- the final `SHOW` is covered,
- no `GAP` or `REJECTED` labels remain,
- receipt status matches the `.wit` header,
- verifier output is complete and not suspiciously truncated,
- target-freezing checks passed,
- the prover and semantic verifier are separate agents or processes.
