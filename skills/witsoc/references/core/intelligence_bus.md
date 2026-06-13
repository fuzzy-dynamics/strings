# The Intelligence Bus (orchestrator-as-fleet)

Witsoc engines do not call model APIs. When an engine needs intelligence —
ideas, sketch mutations, skeptic verdicts, proof rounds, formalizations,
conjectures, rankings, literature findings — it **emits a self-contained
request** to the bus and returns. **You, the orchestrator running witsoc,
are the fleet**: you fulfill the pending requests and re-run the command.
This holds in any harness — an interactive session, a coding agent, or a
scheduled agent driving campaigns unattended. Nothing in the loop may
require a human; human gates exist only where doctrine already puts them
(solve claims, publication).

## The loop (turn discipline is the whole protocol)

```text
1. RUN      a witsoc command (e.g. `witsoc run <run_dir>`)
2. CHECK    its report for bus state: `PENDING_REQUESTS(n)` / turn["bus"]
3. FULFILL  `witsoc bus next-batch --dir <run_dir>/bus [--role R] [--max N]`
            → a packet of self-contained requests; answer each with ONE JSON
            object; submit via `witsoc bus fulfill --id <id> --reply-json '...'`
            or `witsoc bus fulfill-batch --file replies.jsonl`
4. RE-RUN   the same command — engines consume the replies and proceed
5. REPEAT   until the report shows no pending requests
```

Each of your turns stays trivially simple on purpose: run → fulfill →
re-run. Long campaigns historically die on orchestrator turn discipline,
not on mathematics — the bus is shaped so there is never a complicated
next step.

## Fulfillment patterns

- **Inline** — single judgments (one skeptic verdict, one rerank): answer
  directly from the request's `payload.instructions`.
- **Fan-out** — batches of independent same-role requests (ideation rounds,
  sketch mutations, parallel skeptics): spawn subagents, ~10 requests per
  worker, each worker gets the `next-batch` packet (it is self-contained —
  workers need no other context) and submits a `fulfill-batch` file.
  Volume is wanted: generation is deliberately wide because verification is
  the only filter. Fulfill aggressively; don't ration.
- **Tool-backed roles** — `literature_search` requests are fulfilled with
  YOUR search/browse/tool access (web search, platform research tools).
  Witsoc has no network by design; you do.

## Memory travels with the request (the compounding edge)

Generation-role requests carry a `memory_context` assembled at queue time
from the real substrates (`.soc` failure memory, the global failure/priors
sqlite, the proved-lemma library, the proof bank): failure warnings, proved
lemmas, few-shot proof examples, approach priors. USE it when fulfilling —
respect `do_not_repeat` warnings, build on proved lemmas, imitate the
examples' style. This is the one structural advantage witsoc has over
restart-every-problem systems; `witsoc memory flow` reports whether it is
actually reaching prompts. The context never affects request identity and is
attention only — never trust.

## Trust contract (non-negotiable)

Every reply enters witsoc as an OPEN_UNFALSIFIED candidate. Fulfillment
never upgrades a claim: the kernel, deterministic checkers, and skeptic
gates remain the only filters. Consequences for you as fulfiller: prefer
bold coverage over hedging (wrong candidates are free — the kernel rejects
them; missing candidates are lost reach); never fabricate verification
language in replies; the `skeptic` role tries to REFUTE and defaults to
refuted when uncertain — it never certifies.

## Mechanics

- Enable: `WITSOC_BUS_DIR=<dir>` (the campaign driver auto-sets
  `<run>/bus`) or `WITSOC_BUS=1` (defaults to `<witsoc home>/bus`);
  `WITSOC_BUS=0` force-disables. No bus and no `cmd:` fleet → engines
  degrade exactly as before (honest "no fleet" notes).
- Requests are content-hashed: duplicate emits cost nothing; a fulfilled
  request's reply is found again by any re-run (memoization).
- Ceiling: `WITSOC_BUS_CEILING` pending requests (default 500) — a
  runaway-loop backstop, not a budget; drops are recorded in
  `dropped.jsonl`, never silent.
- The legacy `cmd:` sampler fleet (`WITSOC_SAMPLER_FLEET`) still works and
  takes precedence when configured; the bus is the default backend when
  nothing else is.
- `witsoc bus gc` clears stale pending requests (48h default); fulfilled
  history is kept — it is the memoization surface.
