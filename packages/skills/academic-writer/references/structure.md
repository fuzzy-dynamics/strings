# Structure

## The spine

Before writing a chapter, identify its spine: the few questions whose answers determine the order. Write them down. Every section title should answer one.

A chapter without a spine becomes a list of topics. A chapter with a spine reads as one argument.

Example spine for an adiabatic-optimization chapter:
1. What is the optimization problem we are solving?
2. Why is the adiabatic approach a candidate?
3. What does the adiabatic theorem actually guarantee, and at what cost?
4. Where does the bound become tight, and where does it fail?

The chapter's sections should map to these questions in order. If a section does not answer one of them, it does not belong, or the spine is wrong.

## The skeleton

Per section, write down before any prose:

- Question. The single question this section answers.
- Definitions. The new language the section introduces.
- Statements. Theorems, lemmas, propositions, stated as claims first.
- Connections. How this section's results feed the next.

Build the full skeleton across all sections of a chapter before writing prose for any. Rearranging skeleton entries is cheap; rearranging prose is expensive.

## Section template

Every expository section has the same shape.

1. **Tension.** What does current language fail to express? What does the reader need that they do not have? Make the gap concrete. The reader should want the next move.

2. **Plain pass.** Before any formalism, explain in prose what is coming. What does the statement mean? What do its parameters control? What does it enable that was not possible before? This pass uses no symbols beyond what prior chapters established.

3. **Formal pass.** State the definition or theorem. For theorems, state proof strategy upfront ("we reduce to X, then apply Y"). Decompose proofs into lemmas matching logical moves. State each lemma as a self-contained claim, prove it, then return to the main argument.

4. **Concrete example.** Use a running example. Show the new machinery in action on something the reader has met before.

5. **Connection.** One sentence: what does this enable for the next section?

The plain pass is the step LLMs skip most often. They jump from tension straight to formalism. Do not.

## Order of writing

Write the introduction last. The introduction summarizes; you cannot summarize what is not written.

Write the abstract after the introduction, by the same logic.

Within a chapter, write the technical core first, then the framing. The final section's connection sentence often reveals what the introduction needs to say.

## Recurring examples

Pick one or two examples in Phase 1. Use them across the chapter, accumulating meaning. A reader should see the same example evolve from a curiosity in section one to a non-trivial application by section five.

Bad: each section invents a fresh toy example. The reader builds no intuition.

Good: the chapter has one or two examples that the reader meets early and re-encounters with new tools each section. By the end, the example is rich.

Choose examples that can carry the load. A two-state Hamiltonian is fine for the adiabatic theorem; it cannot carry a Grover speedup discussion. Pick examples that reach the chapter's deepest results without breaking.

## Subsection discipline

Two levels of headings, usually. Chapter and section. Use subsections only when a section genuinely contains parallel sub-arguments that each deserve a heading.

Subsection ladders are a sign that the section's spine is unclear. If you find yourself writing 4.2.3.1, restructure.

A section is not a list. A section is an argument with a beginning, middle, and end. Headings inside it interrupt the argument. Use sparingly.
