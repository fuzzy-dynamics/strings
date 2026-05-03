# Math discipline

## Sourcing

Import mathematical statements verbatim from the source paper where possible. Theorem and lemma statements, key equations, named constants come from the paper, not from your synthesis.

When you import, cite the source location in a comment next to the math block:

```latex
% paper/main.tex, Theorem 3.2 (page 14)
\begin{theorem}\label{thm:adiabatic-bound}
    ...
\end{theorem}
```

If you must restate, mark it as a restatement and explain what changed:

```latex
% Restatement of paper/main.tex Theorem 3.2 with notation aligned to Chapter 2.
\begin{theorem}
    ...
\end{theorem}
```

Never silently rephrase a theorem. The supervisor will read both.

## When prior chapters already restate the paper

If a theorem, equation, or bound appears in both the source paper and earlier chapters of the work in progress, **the prior-chapter convention wins**. Follow the chapters' notation, not the paper's. Mark the import as a restatement, cite the paper, and align symbols to whatever earlier chapters committed to.

This rule overrides "import verbatim" whenever the two conflict. The reader should see one consistent work, not a thesis or monograph that flips between conventions whenever a result is imported.

Procedure before writing any math block:

1. Open the source paper and identify the statement.
2. Grep the chapter directory for prior occurrences. Search at least:
   - the named theorem ("Main Result 1")
   - the citation key (`\cite{paperKey}`)
   - the key formulas -- the running time expression, the bound, the inequality
3. If a prior occurrence exists, read the surrounding prose and adopt its notation.
4. Mark the block as a restatement, cite the paper.

Worked example, drawn from a quantum-optimization thesis:

The paper states the AQO running time as

```latex
T = O\left(\frac{1}{\varepsilon}\cdot\frac{\sqrt{A_2}}{A_1^2 \Delta^2}\cdot \sqrt{\frac{2^n}{d_0}}\right).
```

The thesis uses

```latex
T = O\left(\frac{1}{\varepsilon}\cdot\frac{\sqrt{A_2}}{A_1(A_1+1) \Delta^2}\cdot \sqrt{\frac{N}{d_0}}\right).
```

The two differ in two places: `A_1^2` versus `A_1(A_1+1)`, and `2^n` versus `N`. They agree to leading order for large `A_1` and `N=2^n`; the thesis form is sharper under the regularity condition derived in Chapter 5.

When restating this theorem in any chapter, use the chapter form. Do not silently revert to `A_1^2` because that is what the paper writes. The reader expects every running-time expression in the work to be the same expression.

If your draft contains math that earlier chapters already state differently, you have failed the grep step. Run it before drafting, not after.

## Self-check claim

Do not write phrases like "uses notation that the chapter has already introduced" unless you have actually grepped the chapter. Saying it without checking is worse than not saying it: it tells the supervisor the consistency check passed when it did not.

## Hallucination is invisible

A wrong exponent, a missing log factor, a flipped inequality, a dropped threshold condition -- none of these will trigger a syntactic error. The reader will not notice. The supervisor will. Treat every math block as load-bearing.

When the paper states `O(1/Delta^2)`, do not rewrite as `O(1/Delta)` because it reads cleaner.

When a bound holds for `t > T_0`, do not drop the threshold.

When a theorem assumes the Hamiltonian is gapped uniformly, do not paraphrase as "for sufficiently nice Hamiltonians."

The rule: if the LaTeX changed, the meaning may have changed. Verify against the source.

## Notation reuse

Before introducing a symbol, grep prior chapters for it. Build a private list of the symbols your work has already committed to and consult it before introducing new ones. The cost of a redefinition is invisible at the point of writing and severe at the point of reading: the reader has to hold two meanings for the same letter and figure out which the current passage intends.

Illustrative offenders from a quantum-optimization thesis context -- these are the kinds of symbols that get redefined silently when chapters are written out of order:

- `H` -- Hamiltonian (versus a generic operator)
- `H_0`, `H_1` -- initial and final Hamiltonians (versus dummy indices)
- `Delta` (`\Delta`) -- spectral gap (versus a generic difference)
- `epsilon` (`\epsilon`) -- error tolerance (versus a small parameter)
- `T` -- total evolution time (versus temperature, transpose, or generic time)
- `|0>`, `|1>` -- basis states (versus the integers, or ground-state labels)

The pattern transfers to any technical field: identify the half-dozen symbols your work uses heavily and which have other natural meanings, and grep for them before each new chapter. In machine learning the offenders are `\theta`, `\phi`, `L`, `D`, `x`, `y`. In statistics they are `\mu`, `\sigma`, `n`, `p`, `X`. The work itself dictates which.

If a prior chapter defined the symbol, reuse it. Do not redefine. Do not introduce a parallel symbol for the same object.

If you must override prior notation because the paper under discussion uses a different convention, say so explicitly and locally:

```latex
In this chapter we follow the convention of \cite{paper}, writing
$\eta$ for the schedule rather than $s$ as in Chapter 2.
```

Do not silently switch.

## Lemma decomposition

Decompose proofs by logical moves, not algebraic accidents.

Bad: Lemma 1 covers the first three lines of a calculation, Lemma 2 covers the next four. The split is arbitrary; the reader gains nothing.

Good: Lemma 1 is "the operator is bounded," Lemma 2 is "the bound is tight." Each lemma is a claim that stands alone, has its own brief proof, and contributes one logical step to the main theorem.

State proof strategy at the top of the main theorem:

> *Proof strategy.* We prove the bound in three steps. First, we show that the perturbation is bounded uniformly in the schedule (Lemma 4.1). Second, we show that the resulting error accumulates at most linearly in time (Lemma 4.2). Finally, we combine the two to recover the stated bound.

This is one of the highest-value moves in academic writing. The reader knows where the proof is going before the technical work starts. They can verify the strategy is plausible before checking the algebra.

## Bounds and limits

State bounds explicitly. `O(...)` hides constants; when the constant matters, give it. When the bound is tight, say so. When it is not, say so.

State dependencies. A bound that "holds for sufficiently large n" should say what "sufficient" means or cite where it is shown. The reader cannot use a result they cannot apply.

State limitations. If a result holds only for a class of Hamiltonians, name the class. If a technique fails outside a regime, name the regime. Honesty about scope is part of correctness.

A useful pattern when stating a theorem:

```latex
\begin{theorem}[Adiabatic bound, informal]
For Hamiltonians satisfying [assumptions], if [conditions], then
[conclusion] with [explicit bound].
\end{theorem}
```

Followed by a "Remarks" paragraph naming where each assumption is essential, where it is technical, and what is known about removing it.
