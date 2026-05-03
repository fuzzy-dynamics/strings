# Anti-patterns

The phrases below mark moments where the model is narrating instead of doing, or hedging instead of committing. Sweep them out in revision Pass 4.

For each, the fix is the same: do the thing the phrase announces, then delete the phrase.

## Technique-signalling

These phrases announce what the next sentence will do. The next sentence should just do it.

- "To provide intuition, ..." -- Provide it. Delete the opener.
- "From a philosophical standpoint, ..." -- Make the philosophical point. Delete the opener.
- "Roughly speaking, ..." -- State the rough version. Delete the opener.
- "Intuitively, ..." -- Be intuitive. Delete the opener.
- "Heuristically, ..." -- Same.
- "Loosely, ..." -- Same.
- "In some sense, ..." -- Either state the sense precisely or cut.
- "More or less, ..." -- State the precise version.
- "It can be shown that ..." -- Either show, cite where shown, or state without the hedge.
- "One can verify that ..." -- Either verify, leave to reader explicitly with a brief sketch, or cite.

## Meta-commentary

Narration of the writing itself. The structure of the document does this job; the prose should not.

- "In this section, we will ..." -- The section title does this job.
- "We now turn to ..." -- The next section's title does this job.
- "The rest of this chapter is organized as follows ..." -- Sometimes earned in long chapters. Default: cut.
- "As mentioned earlier, ..." -- Either the reader remembers or you should restate cleanly.
- "Recall that ..." -- If the reader needs a reminder, restate. The "recall" prefix is filler.
- "Note that ..." -- Make the point. The "note that" is filler.
- "It is worth noting that ..." -- Stronger filler. Always cut.
- "Importantly, ..." -- Show why it is important. Don't claim importance.
- "Interestingly, ..." -- Show why it is interesting. Don't claim interest.
- "Crucially, ..." -- Same.
- "Notably, ..." -- Same.

## Hedges

- "Very", "quite", "rather", "somewhat", "fairly" -- almost always cut.
- "Actually", "basically", "essentially" -- almost always cut.
- "It seems that ..." -- either state with confidence or state the uncertainty precisely.
- "One might say that ..." -- say it or do not.
- "Arguably, ..." -- make the argument or cut.
- "In general, ..." -- name the generality or cut.
- "Typically, ..." -- state the typical case or the bound.

## Grandiosity

- "This is one of the most important results in ..." -- show the consequences. Don't rank.
- "A profound insight ..." -- give the insight.
- "This sheds new light on ..." -- say what light.
- "This opens up a new direction ..." -- name the direction.
- "Remarkable", "elegant", "beautiful" -- let the work speak.
- "Powerful technique" -- show the power.

## Empty connectives

These are sometimes load-bearing; usually they are not. Default: cut and see if anything is lost.

- "Furthermore, ..." -- usually unnecessary; the next sentence already follows.
- "Moreover, ..." -- same.
- "Indeed, ..." -- usually unnecessary.
- "Thus, ..." -- fine when there is a logical step; filler when there is not.
- "Therefore, ..." -- same.
- "Hence, ..." -- same.
- "In particular, ..." -- sometimes earned, often filler.

## Filler verbs

- "We can see that ..." -- show the seeing.
- "It is easy to see that ..." -- if it is, state without the editorial. If not, justify.
- "It is clear that ..." -- same.
- "It is straightforward to ..." -- if it is, do it briefly without announcing.
- "It is well known that ..." -- cite or state without the prefix.

## Self-referential filler

- "Our novel approach ..." -- describe the approach. Let novelty speak.
- "We propose ..." -- fine in moderation; do not repeat each section.
- "To the best of our knowledge ..." -- fine when accurate; cut when reflexive.
- "In what follows, ..." -- what follows will follow whether announced or not.

## Forbidden in math contexts

- "Some" before a quantity that should be named. "Some constant C" without saying which constant or where it comes from is a hole in the argument.
- "Sufficiently" without a threshold. "For sufficiently large n" needs to either be made precise or cite where it is made precise.
- "Standard" as a hand-wave. "By a standard argument" needs a citation.
- "Without loss of generality" with no justification of the loss. State why no generality is lost.

## Sweep procedure

In Pass 4, do this:

1. For each phrase in this file, grep for it (case-insensitive) in the chapter.
2. For each match, decide: does the phrase add information? If not, delete it. If the sentence depended on the phrase, rewrite the sentence.
3. Read the result. Does the surrounding paragraph still hold together?

This is a high-yield pass. A typical first draft has dozens of these phrases. Cutting them shrinks the chapter by 5-15% and dramatically increases density.
