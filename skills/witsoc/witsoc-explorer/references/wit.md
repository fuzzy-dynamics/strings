# Wit Language Reference

Wit is the language and verifier component of the [Witsoc](../README.md) system. This is the complete specification for the wit language. The checker (`wit check`) validates files against this spec structurally. Semantic verification (whether the math is correct) is handled by an LLM.

## File Structure

A `.wit` file contains, in order:

1. Comment header (optional): `--` lines with metadata including `-- Status:`
2. `MODULE` declaration (required)
3. `IMPORT` declarations (optional)
4. `EXPORT` declarations (optional)
5. One or more top-level blocks: `DEFINE`, `THEOREM`, `LEMMA`, `PROPOSITION`, `COROLLARY`, `CONJECTURE`, `ALGORITHM`, `REDUCTION`
6. For each claim that has a proof: a `PROOF OF` block

## Comments

```
-- This is a single-line comment.
```

Comments start with `--` and extend to end of line. The status comment is special:

```
-- Status: UNVERIFIED
```

Valid statuses:

- `UNVERIFIED` — proof has not yet been run through the verifier.
- `VERIFIED` — all steps ACCEPTed by the verifier.
- `GAP` — at least one step is an explicit `GAP` (honestly incomplete); no steps were REJECTed for reasons other than GAP.
- `REJECTED` — at least one step was REJECTed by the verifier for a reason other than being a GAP.

`GAP` and `REJECTED` are distinct. `GAP` is the proof's own honesty marker — "I know this step is missing and I've written that explicitly." `REJECTED` means the verifier found an error. A proof with both GAP steps and independently-REJECTed steps has status `REJECTED` (the verifier-found error dominates).

**Note:** automatic derivation of `Status: GAP` (rather than `REJECTED`) when the only step-level rejections are explicit GAPs is pending the Language v2 code pass — see `ROADMAP.md`. Today, `wit receipt` writes `REJECTED` for any proof with ≥ 1 non-ACCEPT step, including GAP-only proofs. You can set `-- Status: GAP` manually to mark a GAP-only proof; future code will derive it automatically.

## Reference Syntax

Every `BY` clause, and every place in wit where one object refers to another, falls into one of three categories distinguished by syntax:

### 1. Structural references — bracketed, parser-validated

Use `[...]` whenever you refer to something declared in this file (or imported from another module).

- `[n]`, `[n.m]`, `[n.m.k]` — step labels (Lamport hierarchical).
- `[n.0]` — synthesized label for CASE `[n]`'s introduced hypothesis. In scope only inside `[n]`'s body.
- `[name]` — a declaration in this file: a `THEOREM`, `LEMMA`, `PROPOSITION`, `COROLLARY`, `CONJECTURE`, `DEFINE`, `ALGORITHM`, `REDUCTION`, or a named `GIVEN` hypothesis.
- `[alias.name]` — cross-module qualified ref after `IMPORT path AS [alias]`.

Names follow identifier rules: start with a letter, then alphanumerics + `_`. Purely numeric content is a step label (`[5]`), not a declaration name.

The checker validates that every `[name]` reference resolves (the declaration exists; the alias exists; the imported name is exported). A dangling bracketed reference is a structural error.

### 2. External citations — `@`-prefixed, verifier accepts as given

Use `@` to invoke knowledge that isn't declared in this file — a named theorem, a paper, a textbook result.

- `@name` — simple cite for identifier-like names: `@Cauchy-Schwarz`, `@AM-GM`.
- `@{text}` — general cite that groups arbitrary text with spaces, commas, or punctuation as one citation unit: `@{Folland, Real Analysis, Thm 5.6}`, `@{Hoeffding's inequality (1963)}`.

The `{...}` grouping is the general escape hatch: anything inside is one external-cite unit regardless of internal punctuation. Use it whenever a simple `@name` would be ambiguous.

External citations are accepted as given by the verifier (same semantics as a full `CITE` step — see below). The verifier checks only that downstream steps apply the cited result correctly, not that the citation itself is true.

### 3. Method annotations — bare text, verifier guidance

Anything in a `BY` clause that is neither bracketed nor `@`-prefixed is a method description. Examples: `algebra`, `substitution: $s = 1/2$`, `differentiation`, `induction on n`, `bound`, `Archimedean property`.

These are free-form natural language, passed to the LLM verifier as guidance on what to check. There is no forced vocabulary.

### Example

```
BY [3], [sufficiency], [other.cauchy_schwarz], @{Hoeffding, 1963}, algebra.
```

Reads: "from step 3; from the local lemma `sufficiency`; from the imported `cauchy_schwarz` theorem in module `other`; from Hoeffding's 1963 result (external); and by algebra."

### Backward compatibility

Legacy proofs written without brackets on declaration names (e.g., `THEOREM grover_constant:`) continue to parse. Legacy `BY` clauses with bare names (e.g., `BY sufficiency, algebra`) also continue to parse, with the intended disambiguation (once the Language v2 parser ships — see `ROADMAP.md`):

- If a bare name matches a declaration in the current file or an imported alias, the checker will emit a warning suggesting the bracketed form.
- Otherwise, bare names are treated as external citations (as they are today).

This spec describes the **target language**. The parser update to recognize `[name]`/`@name` structurally and emit the legacy-syntax warnings is listed as **Language v2 code** in `ROADMAP.md §Most Important`. Until that lands, legacy syntax continues to work exactly as it does today; the verifier still disambiguates names by reading the whole `BY` clause. New proofs that adopt the bracketed / `@`-prefixed forms parse and check unchanged today and will gain structural validation once the code ships.

## Module Declaration

```
MODULE [<name>]
```

Every file must have exactly one `MODULE` declaration. The name should match the file name (without extension). Legacy unbracketed form `MODULE <name>` is accepted.

## Imports

```
IMPORT <path> AS [<alias>]
```

Declares a dependency on another module. The alias is used to reference exported results via `[alias.theorem_name]` in `BY` justifications.

The checker resolves imports by loading the target `.wit` file from the same directory. If the target has `EXPORT` declarations, only exported names are available for citation.

Legacy unbracketed form `IMPORT <path> AS <alias>` is accepted.

## Exports

```
EXPORT [<name1>], [<name2>]
```

Lists which theorems, lemmas, algorithms, or reductions from this module are available for import by other modules.

If no `EXPORT` is declared, all claims are available to importers. Legacy unbracketed `EXPORT <name1>, <name2>` is accepted.

## Definitions

```
DEFINE [<name>] :=
  <natural language or mathematical definition>
```

Introduces a named concept that can be referenced in subsequent steps via `[<name>]`. Legacy unbracketed form is accepted.

## Claims

### Theorem / Lemma / Proposition / Corollary

```
THEOREM [<name>]:
  GIVEN:
    - [<hyp_name>]: <hypothesis 1>
    - <hypothesis 2>
  CLAIM:
    <precise statement of what is being proved>
```

`LEMMA`, `PROPOSITION`, and `COROLLARY` have identical syntax. The distinction is semantic (importance/role in the argument).

The `GIVEN` block lists all hypotheses. Each hypothesis starts with `- `. A hypothesis may optionally be named (`- [<hyp_name>]: <hypothesis>`); named hypotheses are citable via `BY [<hyp_name>]` within the proof body. Unnamed hypotheses are collectively available via `BY hypothesis` (free-form method annotation) or by their content.

The `CLAIM` block states the conclusion.

A claim without a `GIVEN` block is permitted (for unconditional results).

Legacy unbracketed header `THEOREM <name>:` is accepted.

### Conjecture

```
CONJECTURE [<name>]:
  GIVEN:
    - <hypothesis>
  CLAIM:
    <statement>
```

Same syntax as `THEOREM` but marks an unproved claim. Conjectures cannot be imported by other modules.

## Proofs

```
PROOF OF [<name>]:

  <steps>

  QED BY <final step refs>.
```

The `<name>` must match a previously declared claim in the same file. The proof consists of numbered steps and ends with `QED`. Legacy `PROOF OF <name>:` without brackets is accepted.

### Steps

Every step has:

1. A **label**: `[n]` for top-level steps, `[n.m]` for sub-steps.
2. A **keyword**: `HAVE`, `SHOW`, `ASSUME`, `LET`, `CONSIDER`, `SUFFICES`, `CASE`, `CITE`, `GAP`.
3. A **claim**: natural language, optionally with LaTeX math in `$...$`.
4. A **justification**: `BY` followed by references and reasoning.

```
[1] HAVE <statement>.
    BY <justification>.
```

The justification line must start with `BY`.

### Step Keywords

**HAVE**: Establishes an intermediate fact.
```
[2] HAVE $g(s)^2 = (2s-1)^2(1-1/N) + 1/N$.
    BY [1], algebra.
```

**SHOW**: Proves the current goal (typically the last step before QED).
```
[7] SHOW $C = 1$.
    BY [4], [5], [6].
```

**ASSUME**: Introduces a hypothesis within the proof.
```
[1] ASSUME $\phi$ is a SAT instance on $n$ variables.
    BY hypothesis.
```

**LET**: Introduces a variable, notation, or abbreviation.
```
[1] LET $\mu_0 = d_0/N$.
    BY definition.
```

**CONSIDER**: Introduces an existential witness.
```
[3] CONSIDER $s^*$ such that $g(s^*) = g_{\min}$.
    BY [2], existence of minimum on compact set.
```

**SUFFICES**: Reduces the current goal to a simpler one.
```
[5] SUFFICES $\mu(\{g \leq x\})/x \leq 1$ for all $x > 0$.
    BY definition of $C$.
```

**CASE**: Introduces a branch in case analysis. The case's condition is citable as `[n.0]` within the case body:
```
[5] CASE $x > 1$:
  [5.1] HAVE $x^2 > x$.
        BY [5.0], algebra.      -- [5.0] cites the case condition "x > 1"
  [5.2] HAVE ...
  [5] QED BY [5.1], [5.2].
```

`[5.0]` is synthesized by the parser; it is not a real step in the sequence and does not appear in receipts. Sub-steps continue to number from `[5.1]`. Outside `[5]`'s body, `[5]` (unsubscripted) refers to the CASE's conclusion (its QED target).

**CITE**: Imports an external result as a whole-step given. The verifier accepts the claim as true and only checks that downstream steps apply it correctly. The prover takes responsibility for citation accuracy.
```
[1] CITE @{Schipperus's Theorem, 2010}: $\omega^{\omega^\beta} \to (\omega^{\omega^\beta}, 3)^2$ when $\beta$ is a sum of at most two indecomposable ordinals.
    BY @{Schipperus, Annals of Pure and Applied Logic 161(10):1195-1215, 2010, Theorem 1.3}.
```

Downstream references use the CITE step's label (`BY [1]`). Inline `@`-prefixed citations in a BY clause are a lighter-weight alternative for one-off invocations; `CITE` is preferred when the cited result is used at multiple points.

**GAP**: Marks an unresolved step. The proof is incomplete but honest about where. Two forms:

```
[4] GAP: cannot bound the cross term when $s$ is near $s^*$.
```

Plain GAP — free-form description of what is missing.

```
[4] GAP EXPECTING [strong_bound]: cannot yet bound the cross term; expected
    lemma is a sharp estimate of the form $|T(s)| \leq \epsilon(n)$.
```

Structured GAP — names the missing sub-problem as `[strong_bound]`. An orchestrator can enqueue `[strong_bound]` as a named soc sub-problem for a future iteration, closing the sketch-first → detail loop. Both forms are valid; use `EXPECTING` whenever the missing content is a specific lemma that could be proved separately.

### Labels

Labels use Lamport hierarchical numbering:

- Top-level: `[1]`, `[2]`, `[3]`, ...
- Sub-steps: `[2.1]`, `[2.2]`, `[2.3]`, ...
- Deeper: `[2.1.1]`, `[2.1.2]`, ...

Labels must be sequential within their scope. `[1]`, `[2]`, `[3]` is valid. `[1]`, `[3]` is not.

The reserved `[n.0]` slot names CASE `[n]`'s introduced hypothesis (see CASE above). `[n.0]` is synthesized and does not count toward the sequential numbering of `[n]`'s sub-steps.

### Scoping Rules

A step can reference:

- **Siblings**: steps at the same level within the same parent. `[5.2]` can cite `[5.1]`.
- **Ancestors**: steps at a higher level. `[5.2]` can cite `[3]` or `[4]`.
- **The parent's QED**: a parent `CASE` or proof block's `QED` summarizes its contents, and is referenced as the parent's label.
- **Own CASE's hypothesis** (`[n.0]`): from anywhere inside `[n]`'s body.
- **Named declarations in the file** (`[name]`): from anywhere in the file.
- **Imported results** (`[alias.name]`): from anywhere after the IMPORT declaration.

A step **cannot** reference:

- **Steps inside a different sub-proof**: `[6.1]` cannot cite `[5.2]`. Use `[5]` (the CASE block's QED) instead.
- **A sibling CASE's hypothesis**: `[6.1]` cannot cite `[5.0]`.
- **Steps that come after it**: no forward references within a proof. (Declarations may forward-reference declarations in the same file — the file's top-level declaration order does not constrain reference order.)

These rules prevent using facts established under incompatible assumptions (e.g., referencing something proved inside "CASE $x > 0$" from inside "CASE $x < 0$").

### Justification

The `BY` clause is composed of comma-separated items, each belonging to one of the three categories defined in **Reference Syntax** above:

- **Structural references** (bracketed): `[1]`, `[3.2]`, `[5.0]`, `[sufficiency]`, `[other.cauchy_schwarz]`
- **External citations** (`@`-prefixed): `@Cauchy-Schwarz`, `@{Hoeffding, 1963}`, `@{Folland, Real Analysis, Thm 5.6}`
- **Method annotations** (bare text): `algebra`, `substitution: $s = 1/2$`, `differentiation`, `induction on n`, `bound`

Example combining all three:

```
BY [3], [sufficiency], @{Hoeffding, 1963}, algebra.
```

Legacy bare-name citations continue to parse (see **Backward compatibility** in Reference Syntax).

### Computational steps

A step may be verified by executable Python code. Write `BY computation` on its own line, immediately followed by a fenced Python code block:

```
[N] HAVE: <claim>.
    BY computation.
    ```python
    <code that asserts the claim>
    ```
```

The checker validates that the code parses as Python (a syntax error is a structural error). A warning is issued if the code contains no `assert` statement — a computation with no assertions verifies nothing.

Before the LLM verifier sees the step, the CLI runs the code in a sandboxed subprocess. The verifier receives three additional fields in its context:

- `CODE` — the Python source
- `EXECUTION RESULT` — `PASS` or `FAIL` (with the last line of stderr on failure)
- `SCOPE` — a best-effort description of what the code exhausts, extracted from the outermost `for ... in range(...)` loop, or from a `# scope: <description>` comment at the top of the code block

**Claim-code alignment** (enforced by the verifier): the code proves exactly what it exhausts, no more.
- Claim scope equals code scope → ACCEPT.
- Claim scope broader than code scope (e.g., claim covers "for all n ∈ ℕ" but code tests only `[1, 10^6]`) → REJECT. The prover must weaken the claim to match, combine with an analytical step extending to the full domain, or mark the uncovered case as `GAP`.
- Claim scope narrower than code scope (code proves more than the claim states) → ACCEPT.

**Sandbox constraints**:
- Allowed imports: `math`, `sympy`, `numpy`, `itertools`, `fractions`, `functools`, `collections`, `decimal`, `statistics`.
- Blocked: process spawning, network I/O, filesystem writes outside `/tmp`, `os.system`, `subprocess`.
- Timeout: 30 seconds wall-clock. Exceeding triggers a FAIL.
- Determinism: seed any randomness; unseeded randomness produces non-reproducible verdicts.

**Security note**: the sandbox catches common accidents — not adversarial code. An attacker inside the subprocess can remove the audit hook. For hostile inputs, use a containerized runtime.

### QED

Every `PROOF OF` block must end with `QED`. Every `CASE` block must end with a `QED` at the parent label level.

```
[5] CASE $x > 1$:
  [5.1] HAVE ...
  [5] QED BY [5.1].
```

The final `QED` of a proof:

```
QED BY [7].
```

`QED BY` clauses follow the same item grammar as any `BY` clause (bracketed refs, `@` cites, method annotations).

## Algorithms

```
ALGORITHM [<name>]:
  INPUT: <description>
  OUTPUT: <description>
  REQUIRES: <preconditions>
  ENSURES: <postconditions>

  [1] <step>
  [2] <step>
  ...

  COMPLEXITY:
    RUNTIME: <bound>
    SPACE: <bound>
```

Algorithm steps use the same labeling and keyword system as proofs. The algorithm's steps are referenced as `[<name>.n]` (e.g., `BY [quicksort.3]`) from a separate correctness proof.

`REQUIRES` and `ENSURES` are optional but recommended. `COMPLEXITY` is optional. Legacy unbracketed `ALGORITHM <name>:` is accepted.

A correctness proof for an algorithm is a separate `THEOREM` + `PROOF OF` block.

## Reductions

```
REDUCTION [<name>]:
  FROM: <source problem>
  TO: <target problem>
  PRESERVING: <what property is preserved>

PROOF OF [<name>]:
  <steps>
  QED BY <refs>.
```

The `PRESERVING` line states the key property (e.g., polynomial-time equivalence, satisfiability). Legacy unbracketed form is accepted.

## Output Tags

All tool output uses consistent `TAG:` prefixes (always with colon):

| Tag | Source | Meaning |
|-----|--------|---------|
| `OK:` | Checker | Structural check passed |
| `ERROR:` | Checker | Structural error |
| `WARN:` | Checker | Non-fatal issue (including legacy-syntax suggestions) |
| `ACCEPT:` | LLM verifier | Step is correct |
| `REJECT:` | LLM verifier | Step has a problem (free-form explanation follows) |
| `VERIFIED:` | LLM verifier | All steps accepted |
| `REJECTED:` | LLM verifier | One or more steps rejected |
| `GAP:` | LLM verifier (step-level) or header (file-level) | Step is an explicit GAP / proof has honestly-acknowledged incompleteness |
