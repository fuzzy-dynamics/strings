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

Valid statuses: `UNVERIFIED`, `VERIFIED`, `REJECTED`.

## Module Declaration

```
MODULE <name>
```

Every file must have exactly one `MODULE` declaration. The name should match the file name (without extension).

## Imports

```
IMPORT <path> AS <alias>
```

Declares a dependency on another module. The alias is used to reference exported results from that module in `BY` justifications.

The checker resolves imports by loading the target `.wit` file from the same directory. If the target has `EXPORT` declarations, only exported names are available for citation.

## Exports

```
EXPORT <name1>, <name2>
```

Lists which theorems, lemmas, algorithms, or reductions from this module are available for import by other modules.

If no `EXPORT` is declared, all claims are available to importers.

## Definitions

```
DEFINE <name> :=
  <natural language or mathematical definition>
```

Introduces a named concept that can be referenced in subsequent steps.

## Claims

### Theorem / Lemma / Proposition / Corollary

```
THEOREM <name>:
  GIVEN:
    - <hypothesis 1>
    - <hypothesis 2>
  CLAIM:
    <precise statement of what is being proved>
```

`LEMMA`, `PROPOSITION`, and `COROLLARY` have identical syntax. The distinction is semantic (importance/role in the argument).

The `GIVEN` block lists all hypotheses. Each hypothesis starts with `- `. The `CLAIM` block states the conclusion.

A claim without a `GIVEN` block is permitted (for unconditional results).

### Conjecture

```
CONJECTURE <name>:
  GIVEN:
    - <hypothesis>
  CLAIM:
    <statement>
```

Same syntax as `THEOREM` but marks an unproved claim. Conjectures cannot be imported by other modules.

## Proofs

```
PROOF OF <name>:

  <steps>

  QED BY <final step refs>.
```

The `<name>` must match a previously declared claim in the same file. The proof consists of numbered steps and ends with `QED`.

### Steps

Every step has:

1. A **label**: `[n]` for top-level steps, `[n.m]` for sub-steps
2. A **keyword**: `HAVE`, `SHOW`, `ASSUME`, `LET`, `CONSIDER`, `SUFFICES`, `CASE`, `CITE`, `GAP`
3. A **claim**: natural language, optionally with LaTeX math in `$...$`
4. A **justification**: `BY` followed by references and reasoning

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

**CASE**: Introduces a branch in case analysis.
```
[5] CASE $x > 1$:
  [5.1] HAVE ...
  [5] QED BY [5.1].
```

**CITE**: Imports an external result as a given. The verifier accepts the claim as true and only checks that downstream steps apply it correctly. The prover takes responsibility for citation accuracy.
```
[1] CITE Schipperus's Theorem (2010): $\omega^{\omega^\beta} \to (\omega^{\omega^\beta}, 3)^2$ when $\beta$ is a sum of at most two indecomposable ordinals.
    BY Schipperus, Annals of Pure and Applied Logic 161(10):1195-1215, 2010, Theorem 1.3.
```

**GAP**: Marks an unresolved step. The proof is incomplete but honest about where.
```
[4] GAP: cannot bound the cross term when $s$ is near $s^*$.
```

### Labels

Labels use Lamport hierarchical numbering:

- Top-level: `[1]`, `[2]`, `[3]`, ...
- Sub-steps: `[2.1]`, `[2.2]`, `[2.3]`, ...
- Deeper: `[2.1.1]`, `[2.1.2]`, ...

Labels must be sequential within their scope. `[1]`, `[2]`, `[3]` is valid. `[1]`, `[3]` is not.

### Scoping Rules

A step can reference:

- **Siblings**: steps at the same level within the same parent. `[5.2]` can cite `[5.1]`.
- **Ancestors**: steps at a higher level. `[5.2]` can cite `[3]` or `[4]`.
- **The parent's QED**: a parent `CASE` or proof block's `QED` summarizes its contents.

A step **cannot** reference:

- **Steps inside a different sub-proof**: `[6.1]` cannot cite `[5.2]`. Use `[5]` (the CASE block's QED) instead.
- **Steps that come after it**: no forward references.

These rules prevent using facts established under incompatible assumptions (e.g., referencing something proved inside "CASE $x > 0$" from inside "CASE $x < 0$").

### Justification

The `BY` clause is free-form. It can contain:

- **Step references**: `[1]`, `[3.2]`, `[5]`
- **Import references**: `module_alias.theorem_name`
- **Named results**: `Cauchy-Schwarz`, `Hoeffding's inequality`, `spectral theorem`
- **Method descriptions**: `algebra`, `substitution: $s = 1/2$`, `differentiation`, `bound`
- **Citations**: `(Paper, Proposition 4.2)`, `Tseitin (1968)`
- **Any combination**: `BY [2], [3], Hoeffding's inequality, algebra.`

There is no forced vocabulary. Write what a mathematician would write to justify the step.

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

## Algorithms

```
ALGORITHM <name>:
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

Algorithm steps use the same labeling and keyword system as proofs.

`REQUIRES` and `ENSURES` are optional but recommended. `COMPLEXITY` is optional.

A correctness proof for an algorithm is a separate `THEOREM` + `PROOF OF` block.

## Reductions

```
REDUCTION <name>:
  FROM: <source problem>
  TO: <target problem>
  PRESERVING: <what property is preserved>

PROOF OF <name>:
  <steps>
  QED BY <refs>.
```

The `PRESERVING` line states the key property (e.g., polynomial-time equivalence, satisfiability).

## Output Tags

All tool output uses consistent `TAG:` prefixes (always with colon):

| Tag | Source | Meaning |
|-----|--------|---------|
| `OK:` | Checker | Structural check passed |
| `ERROR:` | Checker | Structural error |
| `WARN:` | Checker | Non-fatal issue |
| `ACCEPT:` | LLM verifier | Step is correct |
| `REJECT:` | LLM verifier | Step has a problem (free-form explanation follows) |
| `VERIFIED:` | LLM verifier | All steps accepted |
| `REJECTED:` | LLM verifier | One or more steps rejected |
