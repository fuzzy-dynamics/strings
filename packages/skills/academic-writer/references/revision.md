# Revision

Revise in passes. Do not mix passes. Each is a separate read-through with one objective. Mixing passes regresses earlier work: a clarity edit done while still moving sections will need to be redone.

## Pass 1 -- Structure

Read for shape. Ignore prose quality. Resist the urge to fix sentences.

Ask:
- Does each section answer the question its title implies?
- Are sections in the right order? Could any two be swapped without loss?
- Is anything missing -- a definition used before introduction, a step skipped in a proof, a result referenced before stated?
- Is anything redundant -- a topic covered twice, a paragraph that says what the previous paragraph said?
- Does the chapter spine show through? Could the reader, on finishing, name the questions the chapter answered?

Fixes from this pass: move sections, add missing material, cut redundant material, retitle sections to match content.

## Pass 2 -- Clarity

Read for argument. Each paragraph should have one job and do it.

Ask:
- Does the first sentence of each paragraph state its job?
- Does each subsequent sentence advance the job?
- Does the paragraph end on its result, or does it teaser the next paragraph?
- Are sentences direct? Subject-verb-object?
- Are nested clauses obscuring the main point?

Fixes from this pass: rewrite paragraph openings, split overloaded paragraphs, merge under-stuffed ones, unwind nested sentences.

## Pass 3 -- Precision

Read for math and claims. Open the source paper alongside the draft.

Ask:
- Is every theorem statement an exact match (or marked restatement) of a source?
- Is every bound explicit? Are hidden constants exposed when they matter?
- Is every dependency named? Does "for sufficiently large n" have a concrete meaning?
- Is every limitation stated? Does the reader know what the result does not do?
- Is there notation drift? Do symbols mean the same as in earlier chapters?

Fixes from this pass: re-import math from source, expose constants, state limits, fix notation.

## Pass 4 -- Style

Read for voice. Sentence by sentence.

Open `anti-patterns.md` alongside the draft. Sweep for every banned phrase. For each match, do the thing the phrase announces and delete the phrase.

Ask:
- Does every sentence carry information? Could any be removed without loss?
- Any technique-signalling left ("to provide intuition," "we will see that")?
- Any grandiose claims ("this is among the most important results")?
- Is the voice consistent across sections?

Fixes from this pass: line edits.

## Acceptance

After all four passes, answer in one sentence per section: what can the reader do after this section that they could not before?

If you cannot answer for a section, the section is not done. Return to Pass 1.

A complete chapter has one acceptance answer per section, plus one for the chapter as a whole: what does the chapter let the reader do that no prior chapter did?

## When to stop

A chapter is never finished, only abandoned. But there is a useful threshold: when each pass produces only minor edits, when the structure has held across two consecutive passes, when the math has been verified against the source twice without change. At that point, stop. Show the supervisor.

Earlier than that is premature. Later is wheel-spinning.
