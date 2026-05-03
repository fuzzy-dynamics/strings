---
name: academic-writer
description: Plan, draft, and revise long-form expository academic prose -- theses, monographs, survey chapters, expository sections of scientific papers -- where the writing has to exceed a source paper in depth and accessibility. Phase-gated workflow (plan, draft, check, revise) with hard rules against LLM-default failures: filler sentences, technique-signalling, math hallucination, silent notation drift, re-definition of established terms. Use when writing or revising a chapter, section, theorem proof, or expository passage that grounds in a published source. For journal-manuscript drafting (IMRAD, structured abstracts, reporting guidelines) use scientific-writing. For formal peer-review writing use peer-review. For citation/bibliography work use citation-management.
allowed-tools: Read Write Edit Bash
license: MIT license
metadata:
    skill-author: Alapan Chaudhuri
category: writing
---

# Academic Writer

## Overview

This skill is for long-form expository academic writing. The reader should finish with new perspective, not new facts: a chapter, monograph, or survey that is the single best source for understanding its subject. Most LLM defaults work against that goal -- filler sentences, hedged generalities, re-defined terms, hallucinated math, "to provide intuition" meta-commentary. This skill is adversarial against those defaults.

The niche is exposition that exceeds the published source. If you are writing a journal manuscript with IMRAD structure, abstract, methods, and results, use `scientific-writing` instead. If you are writing a formal peer review, use `peer-review`. This skill is for the expository core: the chapters of a thesis or monograph that motivate, contextualize, and unify a published result; the survey article that consolidates a literature; the deeply-explained section of a paper where the goal is teaching the reader, not announcing the result.

## When to Use This Skill

Trigger when the user asks to:

- Write or revise a chapter, section, theorem proof, or expository passage in a thesis, monograph, or survey.
- Expand a published paper's terse exposition into a fuller treatment.
- Restate a theorem from a source paper in a thesis chapter, with notation aligned to prior chapters.
- Revise a draft section through structured editing passes.
- Plan the spine of a chapter before writing prose.

Do not trigger for short-form prose, blog posts, code documentation, one-shot edits, abstract drafting in isolation, or generation of new mathematical results.

## Operating Principle

Outsource production, not judgment. Verify by reading. Do not script verification.

The model can produce prose at scale. It cannot replace the supervisor's eye. Every generation step in this workflow is paired with a verification step done by reading -- comparing math against the source, grepping prior chapters for prior definitions, sweeping for filler. Heuristic scripts that try to outsource judgment are excluded by design; they produce false confidence.

## Phases

The skill runs in four phases. Do not skip ahead. Pause at each gate and confirm with the user before proceeding.

### Phase 1 -- Plan

Before writing prose:

1. Read the source material. Open the source paper, prior chapters of the work in progress, and any cited references the user names. Do not write from memory.
2. Produce a one-page plan stating:
   - the tension this chapter resolves (one paragraph),
   - the main results as informal claims (3-7 lines),
   - one sentence per section in order.
3. Build a per-section skeleton: the question the section answers, the definitions it needs, the theorems and lemmas it states. No prose yet.
4. Pick one or two concrete examples that recur across the chapter. Commit to threading them through every section. Do not invent fresh examples per section later.
5. Show the plan and skeleton to the user. Stop. Do not draft until they confirm.

### Phase 2 -- Draft

One section at a time. For each section, follow the section template:

1. **Tension.** State the gap in current language that forces a new definition or theorem. The reader should want the next move before it appears.
2. **Plain pass.** Explain in prose what the upcoming statement means, what its parameters control, what it enables. No formalism yet.
3. **Formal pass.** State the definition or theorem. State proof strategy upfront. Decompose proofs into lemmas matching logical moves, not algebraic accidents.
4. **Concrete example.** Reuse one of the running examples picked in Phase 1.
5. **Connection.** One sentence: what this enables for the next section.

Before drafting any math block (theorem, lemma, equation, bound), grep the prior chapters for occurrences of the same statement. Use the citation key, the named theorem, and the key formulas as search terms. If a prior occurrence exists, follow its notation, not the source paper's. See `references/math-discipline.md` for the conflict-resolution rule.

While drafting, follow `references/voice.md`, `references/structure.md`, and `references/math-discipline.md`.

### Phase 3 -- Check

Before showing a finished draft, run these checks. Mechanical ones are bash one-liners. Judgment ones are read-throughs.

Mechanical:

```bash
grep -nP '[^\x00-\x7F]' <file>           # non-ASCII characters
grep -n   '^---$'        <file>           # separator lines in body
grep -nE  '^\s*[-*]\s'   <file>           # bullets in body prose
```

Judgment (read and verify yourself, do not script):

- Re-read the section. Delete every sentence that survives without carrying new information.
- For each math block, open the source paper and confirm bounds, exponents, constants, and inequality directions match. Hallucination is silent.
- Grep prior chapters for every term you defined. If already defined, delete the redefinition and link.
- Sweep `references/anti-patterns.md` against the draft.
- Acceptance test: in one sentence, what can the reader do after this section that they could not before? If nothing, cut or rewrite.

### Phase 4 -- Revise

Four passes. Do not mix them. Each is a separate read-through, with one objective. See `references/revision.md` for the full protocol.

1. **Structure.** Section ordering, what is missing, what is redundant.
2. **Clarity.** One job per paragraph; direct sentences.
3. **Precision.** Bounds explicit, dependencies named, limits honest.
4. **Style.** Banned-phrase sweep against `references/anti-patterns.md`.

## Hard Rules

- Every sentence carries information. If removing a sentence loses nothing, remove it.
- No technique-signalling. Do not write *to provide intuition*, *from a philosophical standpoint*, *we will see that*, *it is important to note*, *in some sense*. Do the thing.
- No grandiose claims. Small, direct sentences.
- No bullet points in body prose. Chapters and sections, not subsection ladders.
- No re-definition of terms introduced earlier.
- No `---` in body. No non-ASCII characters in source files.
- Write the introduction last. Write the abstract after the introduction.
- Import math statements verbatim from the source paper where possible. Cite the source location next to the block.
- When the prior chapters already restate a paper's theorem with adjusted notation, follow the chapter convention, not the paper's. Mark as a restatement.
- LaTeX math uses proper delimiters: inline `\(...\)` or `$...$`, display `\[...\]` or environments. Avoid `$$...$$`.

## What This Skill Is Not For

- Short-form prose, blog posts, README files.
- Journal manuscript drafting with IMRAD/abstract/methods/results structure -> use `scientific-writing`.
- Formal peer review writing -> use `peer-review`.
- Bibliography / citation work -> use `citation-management`.
- Generating new mathematical results -- only exposition of existing ones.
- One-shot edits ("fix this typo," "change this word").

## References

- `references/voice.md` -- sentence and paragraph rules, voice characteristics, density.
- `references/structure.md` -- spine, skeleton, section template, recurring examples, subsection discipline.
- `references/math-discipline.md` -- sourcing, hallucination, notation reuse, paper-vs-prior-chapter conflict resolution, lemma decomposition, bounds and limits.
- `references/revision.md` -- four-pass editing protocol with per-pass checklists.
- `references/anti-patterns.md` -- banned-phrase list with replacement strategies.

Load these references as needed. The reference files contain concrete examples drawn from a quantum-optimization thesis context; the patterns generalize to any technical exposition.

## Integration With Other Skills

- **scientific-writing** -- for journal manuscripts (IMRAD, abstracts, reporting guidelines, citation styles).
- **peer-review** -- for writing reviews of other people's work.
- **citation-management** -- for bibliography validation and BibTeX work.
- **literature-review** -- for systematic literature reviews and meta-analyses.
- **scientific-critical-thinking** -- for evaluating the evidence behind a claim.
- **scientific-schematics** / **generate-image** -- for figures embedded in expository chapters.

The typical workflow: use `literature-review` and `scientific-critical-thinking` to ground a chapter; use `academic-writer` to write it; use `peer-review` (or external review) to evaluate it; use `citation-management` to verify references.
