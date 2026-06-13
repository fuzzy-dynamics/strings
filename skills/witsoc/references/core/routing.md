# Witsoc Route Advisor

Consult this before selecting a subskill. It presents candidate routes with
applicability conditions, tradeoffs, and known failure cases. The final route
selection rests with the reasoning agent; record the chosen route and the
reason in the route state (`scripts/route.py`, `scripts/validate_route_state.py`).

Two rules here are contract, not advice:

1. An open-style target the user asked to solve/attack/deep-run must reach
   Lovasz before final status, unless a concrete operational blocker is
   recorded (top-level Discovery Requirement).
2. Generator runs on nontrivial targets only with Explorer authorization.

Everything else below is advisory: defaults with track records, not mandates.

## Candidate Routes

### Direct answer

- **Fits when**: small routine calculation or proof; one main idea; no open
  status risk; no artifact requested.
- **Cost**: minimal.
- **Risks**: overclaiming on a statement that deserved adversarial pressure;
  silently answering a mutated version of the question.
- **Failure case to remember**: confident prose proofs of false statements
  that a trivial-case falsification pass would have caught.
- **Escape hatch**: any surprise (a counterexample smell, a quantifier
  subtlety, an open-status hint) upgrades to Explorer.

### Explorer only

- **Fits when**: definitions, theorem lookup, premise search, proof
  exploration, counterexample hunting, status triage; the deliverable is
  understanding or a plan rather than a verified artifact.
- **Cost**: low to moderate.
- **Risks**: stopping at literature/status classification when the user asked
  for progress (contract rule 1 applies); treating retrieval hints as proof.
- **Escape hatch**: non-routine blocker → Lovasz packet; precise accepted
  artifact target → Generator handoff.

### Explorer -> Lovasz -> Explorer

- **Fits when**: open, unsolved, unconfirmed, frontier, or blocked targets;
  serious prove/show requests with quantifiers, named structures,
  inequalities, or nontrivial case structure; olympiad/competition problems;
  any target where Explorer's triage finds a real barrier.
- **Cost**: highest; mitigated by budget gates, the escalation ladder, and
  the olympiad fast lane (bounded kernel-gated closure attempt before a full
  campaign — if the fast lane closes the exact frozen target, Explorer may
  report that mechanism and skip the campaign, recording the decision).
- **Risks**: campaign machinery on a target that a cheap kernel check would
  settle (run the fast lane first); prose-only "campaigns" (the ledger
  requirements exist to prevent this).
- **Skip condition** (record it explicitly): Explorer settles the target as
  routine with a kernel-verified or deterministically checked closure.

### Explorer -> Generator

- **Fits when**: routine accepted targets where the user wants WIT (and
  optionally Lean); Explorer has frozen and accepted the target and judged it
  routine.
- **Risks**: skipping Lovasz on a target that was not actually routine — if
  Generator work exposes a mathematical (not syntactic) blocker, route back
  through Explorer review rather than patching prose.

### Generator-first

- **Fits when**: inspection or repair of an existing `.wit`/Lean artifact;
  the blocker is plausibly syntactic or contextual.
- **Risks**: masking a mathematical blocker as a syntax issue. Route back to
  Explorer/Lovasz the moment the diagnosis turns mathematical.

## Choosing under uncertainty

When the route is unclear, surface the live candidates with one line each on
applicability and risk, choose, and record the choice. Prefer the cheapest
route whose failure mode you can detect quickly over the safest route chosen
by reflex — escalation is always available, and a recorded wrong-but-cheap
probe often buys the information the routing decision needed.

## Subskill Boundaries (separation of powers — contract)

Explorer:

- freezes target,
- triages status,
- searches premises and counterexamples,
- reviews Lovasz output,
- authorizes Generator.

Lovasz:

- decomposes barriers,
- spawns exact DAG-node workers,
- validates partial progress,
- returns structured packet to Explorer.

Generator:

- produces WIT/Lean artifacts,
- repairs artifact failures,
- does not change mathematics,
- does not upgrade claim status.

Top-level Witsoc:

- enforces contracts and production gates,
- advises on routes and capabilities,
- gives final report.

## Recovery Routing (candidate diagnoses)

A failure usually admits more than one diagnosis; pick the cheapest test that
discriminates before committing to a repair route.

- Lean syntax/import/context issue → Generator repair.
- Mathematical gap → Explorer or Lovasz repair.
- DAG integrity failure → Lovasz repair.
- Target mismatch → Explorer target-freeze repair.
- Formalization poor → Explorer/Lovasz decomposition repair.
- Worker disagreement → skeptic review and result merger.

If two consecutive repairs on the same route fail for the same reason, the
diagnosis is suspect: re-derive it rather than repeating the route
(`references/core/failure_recovery.md`).
