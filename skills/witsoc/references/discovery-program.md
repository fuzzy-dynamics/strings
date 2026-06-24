# The discovery program: sustained Lovász campaigns on open problems

How witsoc is pointed at mathematical discovery and open problems as an
ongoing program rather than one-off runs. Built 2026-06-12 on top of the
two-part knowledge DB ([knowledge-stores.md](knowledge-stores.md)).

## What "discovery" means here (the honesty frame)

A discovery is a claim that is **verified** (trust lattice: kernel receipt or
explicit certificate), **new** (novelty triage), and **human-gated** before
any external claim. These are independent axes — a kernel-verified textbook
fact is not a discovery; an unverified new conjecture is not a result. The
credible steady-state output is a stream of verified lemmas, whole-class
witness families, special cases, refuted conjectures, certificates, and
well-tested novel conjectures; full solves of named open problems are tail
events the system is positioned for, never promised. Calibration sentinels
(genuinely open problems frozen in every portfolio) must stay unsolved — one
violation fails the whole campaign run.

## The pieces

| Piece | Tool | Role |
|---|---|---|
| Portfolio | `witsoc portfolio` / `benchmarks/research_portfolio.json` | curated attackable problems: tiers `frozen_calibration` / `research_target` / `reachable_research` (oracle-proof truth-checked) / `experimental` (backend specs) |
| Lean track | `witsoc campaign` (autonomous_campaign) | research-director bandit per problem, MATHLIB MODE by default, harvest + value model compound into the live library |
| Experimental track | `witsoc research-campaign` adapters | formula-synthesis witness families (whole-class Lean statement via exact residue substitution `n = m·t + (m+r)`, then the kernel-gated prover), research-search certificates; unadapted backends reported `backend_pending`, never dropped |
| Novelty | `witsoc novelty` | live-library + reference-atlas + external `WITSOC_NOVELTY_CMD` checks; external absent → honestly `LOCALLY_NEW_UNCHECKED` |
| Ledger | `witsoc discoveries` | `~/.witsoc/discoveries.jsonl`; `publishable` = kernel-grade ∧ NOVEL_CANDIDATE ∧ human-gated |
| Runner | `witsoc research-campaign` | one nightly pass: validate → lean track → experiments → ledger → report under `~/.witsoc/campaigns/<stamp>/` |

## Mathlib mode (the reach unlock)

Campaign entry points call `witcore.enable_mathlib_mode()`: with a built
`~/mathlib4` (or `WITSOC_LAKE_DIR`), kernel checks run `lake env lean` and the
prover narrows to retrieval + Mathlib-strength candidates (`ring`,
`nlinarith`, `norm_num`, `decide`, plus the Mathlib induction family with
`ring`/`nlinarith [ih]` succ-closers for cubic+ residuals over recursive
defs). `WITSOC_CORE_ONLY=1` opts out (tests, quick `witsoc prove` calls stay
core-Lean). Measured unlock: `rh-ring-square` and `pp-cubic-sum` — both
formerly honest headroom — now close kernel-verified.

## Running it

```bash
witsoc portfolio validate            # honesty contract
witsoc portfolio verify-truth        # kernel-check reachable rungs' oracle proofs
witsoc research-campaign --iterations 1 --max-steps 6
witsoc discoveries report            # what came out; publishable set
witsoc atlas promote                 # lift LEAN_VERIFIED harvest into the reference store
```

Nightly: schedule `witsoc research-campaign` (it is script-driven end-to-end —
the miniF2F lesson is that long campaigns fail on orchestrator turn
discipline, not math; the chat agent reads `~/.witsoc/campaigns/<stamp>/report.json`
and steers the portfolio instead of driving the loop by hand).

## Steering the portfolio (the human/agent loop)

After each run: retire rungs that closed (they live in the library now), add
the next rung toward the same open problem, check `ledger_additions` for
NOVEL_CANDIDATE/LOCALLY_NEW_UNCHECKED entries worth an external novelty check,
and `gate` anything worth publishing after review. Portfolio edits must keep
`witsoc portfolio validate` green — in particular the two frozen calibration
sentinels (Erdős–Straus general, odd-perfect) are non-negotiable.

## Current portfolio (2026-06-12)

Calibration: Erdős–Straus (general), odd perfect. Research targets: ES on
n ≡ 1 (mod 4). Reachable rungs (all oracle-verified TRUE): ES even/mult-3
whole-class families, Nicomachus, sum-of-odds, 6 | n(n+1)(2n+1). Experimental:
ES new-residue-family synthesis (mod 12/24), multiperfect mining, graceful
small trees (backend pending), odd-distinct covering systems (backend pending).
