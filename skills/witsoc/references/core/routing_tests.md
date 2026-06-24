# Witsoc Routing Tests

Use these examples to check routing before starting serious work.

Run:

```bash
python3 strings/skills/witsoc/scripts/route.py "<user request>"
python3 strings/skills/witsoc/scripts/test_route.py
```

The returned `announcement` must be shown before work starts. The first route
for serious math is Explorer. For open-style targets, the canonical route chain
is Explorer -> Lovasz -> Explorer; Generator appears only after Explorer
reviews Lovasz output and accepts a narrow artifact target.
The returned `research_mode` controls default worker spawning:

- `quick`: spawn only when worker spawning is useful.
- `deep`: adaptive planning/evolution; spawn every justified independent DAG node.
- `campaign`: expand only when independent DAG nodes justify it.

## Explorer First

| User request | Required announcement | Required route |
|---|---|---|
| "do a deep run trying to prove or disprove Call a number k-perfect if sigma(n)=kn, where sigma(n) is the sum of divisors of n. Must k=o(log log n)?" | `Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer.` | Explorer freezes the target and status; if open/unsolved/unconfirmed, Explorer sends a barrier packet to Lovasz and then reviews Lovasz output. A report that only says known results prove O(log log n) but not little-oh is incomplete without Lovasz barrier attack. |
| "Prove or disprove Erdős problem 1053" | `Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer.` | Explorer first; Lovasz immediately after Explorer barrier packet; Explorer review after Lovasz. |
| "Solve Erdos problem #1053 and give WIT" | `Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer.` | Explorer first despite WIT request; if open/blocked, Explorer -> Lovasz -> Explorer -> Generator. |
| "Find a counterexample to this famous conjecture" | `Using witsoc with witsoc-explorer.` | Explorer first; Lovasz if the conjecture is open/unsolved/unconfirmed. |
| "Work on this open problem from a maintained problem list" | `Using witsoc with witsoc-explorer.` | Explorer status/variant/source triage first. |
| "Can you prove or disprove this unsolved problem?" | `Using witsoc with witsoc-explorer.` | Explorer first. |
| "This is unsolved; try to prove it" | `Using witsoc with witsoc-explorer.` | Explorer first, even if no problem-list name is given. |
| "Formalize this open conjecture in Lean" | `Using witsoc with witsoc-explorer.` | Explorer first; Lovasz if open/blocked; Generator only after accepted narrow target. |
| "Prove Hall's theorem" | `Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer.` | Serious-proof guard: Explorer freezes the statement, Lovasz directs the proof campaign in solved-class mode, Explorer reviews. Explorer may skip Lovasz only by settling the target as routine with a kernel-verified proof and recording that decision. |
| "Find a counterexample to this proposed lemma" | `Using witsoc with witsoc-explorer.` | Explorer counterexample mode. |
| "Rank these proof sketches" | `Using witsoc with witsoc-explorer.` | Explorer rater mode. |
| "Write WIT for this already-stated theorem" | `Using witsoc with witsoc-explorer.` | Explorer freezes and accepts target, then Generator writes WIT. |
| "Generate WIT + Lean for a routine lemma" | `Using witsoc with witsoc-explorer.` | Explorer first; Generator after accepted proof plan. |

## Generator First

| User request | Required announcement | Required route |
|---|---|---|
| "Repair this .wit file" | `Using witsoc with witsoc-generator.` | Existing artifact repair can start at Generator. |
| "Fix the failing WIT proof in theorem.wit" | `Using witsoc with witsoc-generator.` | Existing artifact repair. |

## Lovasz Chain (Solved-Class: Olympiad / Competition / Serious Proof)

Olympiad and competition problems, and serious prove/show requests with mathematical substance, route through Lovasz mandatorily even though they are solved-class. Lovasz runs as the proof-campaign director (ideation, sketch tournament/decomposition, per-node Prover dispatch, skeptic gate); open-problem novelty ledgers are waived unless the campaign stalls.

| User request | Required announcement | Required route |
|---|---|---|
| "IMO 2019 shortlist: determine all functions f : Z -> Z such that f(2a)+2f(b)=f(f(a+b))" | `Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer.` | Explorer freezes; Lovasz conjectures the answer set first (bounded search), then proves the characterization via dispatch; Explorer reviews. |
| "This Putnam inequality looks hard, give it a try" | `Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer.` | Olympiad guard; deep research mode. |
| "Prove that every triangle-free graph on n vertices has at most n^2/4 edges" | `Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer.` | Serious-proof guard (quantified statement over a named object class). |
| "prove 1+1=2" | `Using witsoc with witsoc-explorer.` | Triviality guard: no mathematical-substance marker; light Explorer path. |
| "what is 2+2" | `Using witsoc.` | Simple/direct guard. |

## Lovasz Chain

When Explorer determines the target is open, unsolved, unconfirmed, frontier-level, or blocked, it must immediately create the Lovasz barrier packet, invoke Lovasz, and announce the chain:

```text
Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer.
```

Only after Lovasz returns and Explorer accepts the assembled target should the chain become:

```text
Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer -> witsoc-generator.
```

## Priority Rule

Explorer-first guards outrank artifact requests. If the user asks for WIT/Lean on an unsolved, open, Erdős, or problem-list item, the first route is still Explorer:

```text
Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer.
```

Generator may not decide open-problem truth or upgrade claim status.

## Completion Guard

For prove/disprove/deep-run prompts, these outputs are incomplete unless Lovasz ran or a concrete Lovasz dispatch blocker is recorded:

- "open/unsupported by known results",
- "Gronwall/Robin only prove O(log log n)",
- "requires a new structural theorem",
- "literature did not locate a proof",
- "computations are inconclusive."

The k-perfect prompt must therefore proceed:

```text
witsoc-explorer status triage -> witsoc-research-lovasz barrier packet/attack -> explorer review -> final status
```

## Script Checks

Expected routes:

```text
route.py "Prove or disprove Erdős problem 1053" -> witsoc-explorer
route.py "do a deep run trying to prove or disprove Call a number k-perfect if sigma(n)=kn. Must k=o(log log n)?" -> witsoc-explorer
route.py "This is unsolved; try to prove it" -> witsoc-explorer
route.py "Formalize this open conjecture in Lean" -> witsoc-explorer
route.py "Prove Hall's theorem" -> witsoc-explorer
route.py "Write WIT for this already-stated theorem" -> witsoc-explorer
route.py "Repair this .wit file" -> witsoc-generator
```

Expected chain fields:

```text
route.py --field chain "generate WIT for RH" -> witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer -> witsoc-generator
route.py --field chain "skip exploration and use Lovasz" -> witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer
route.py --field chain "Write WIT for this already-stated theorem" -> witsoc-explorer -> witsoc-generator
```

The router also writes `witsoc_route_state.json` when `PLANE_SESSION_DIR`,
`OSCI_SESSION_DIR`, `KIMI_WORK_DIR`, `WITSOC_ROUTE_STATE`, or `--state-out` is
available. `generator_authorized: false` means Generator must wait for Explorer
handoff or Explorer review after Lovasz.

Expected mode fields:

```text
route.py "Prove or disprove Erdős problem 1053" -> research_mode campaign
route.py "do a deep run trying to prove or disprove ..." -> research_mode deep
route.py "Prove Hall's theorem" -> research_mode quick
route.py "Repair this .wit file" -> research_mode quick
```

## Completion Guard Regression Cases

These reports must be rejected as incomplete for prove/disprove deep runs:

- "The target is equivalent to the triangle-free Gyarfas-Sumner conjecture and open" with only a prose Lovasz barrier note.
- "Known results do not prove the requested asymptotic" with no Lovasz proof-DAG, actual lemma queue, worker results, or dispatch blocker.
- "No lemma found" with no attempted lemma schemas, direct attacks, counterexample pressure, theorem-precondition gap, or next exact attempt.

For induced-tree triangle-free high-chromatic runs, use:

```bash
TEMPLATE="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lovasz_campaign_template.py)"
python3 "$TEMPLATE" --template induced-tree-triangle-free
```

The run is not shippable until Explorer reviews a Lovasz campaign ledger or records a concrete operational blocker.
