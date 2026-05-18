---
name: notes-use
description: How to author, structure, and maintain workspace notes through the `OpenScientistNotes` tool so the Notion-like (TipTap) editor renders them well and the user can actually use them a month later. Covers what makes a good note (lead with the claim, section it, cite externals, preserve reasoning) with shape templates per intent (paper summary, decision note, meeting note, daily log, quick observation); the tool's ten backend-backed functions and the find-the-id flow that edit/append/delete require; the HTML the renderer actually parses (headings, lists, task lists, tables, code blocks with language, KaTeX math, highlights, source-citation links); the search-before-create discipline; and the line between a note (user-facing artifact) and a scratchpad (agent memory — does not belong in notes). Required reading before any `OpenScientistNotes` write, edit, or append.
metadata:
  skill-author: OpenScientist
category: knowledge
---

# Notes Use

Notes are the *user-facing* artifact in the workspace: a Notion-like editor (TipTap) renders them, the user reads them, edits them, and shares them. They are **not** an agent scratchpad — for agent working memory, use `planning-with-files` (`.openscientist/sessions/...`). This skill is about producing notes the renderer treats well and the user can navigate later.

## 0. When to create a note (and when not to)

Create or modify a note **only when the user explicitly asks** to save, record, summarize, note, document, or remember something — or when the user is iterating on an existing note. Triggers:

- "save this as a note", "note this down", "make me a note about X"
- "summarize the paper into my notes"
- "update the methods note with the new finding"

**Do not** use notes as:

- working memory across tool calls — that's `planning-with-files` under `.openscientist/sessions/$SESSION/`
- a log of your own reasoning or progress — that's `progress.md`
- a dumping ground for raw tool output — extract the claim first, then write
- a duplicate of something already in `findings.md` / `claims.md`
- a place to track open questions to yourself — invisible to the user as notes

The test: would the user, opening this in their notes panel a week from now, recognize it as something *they* wanted? If no, it's the wrong file.

## 1. What a good note looks like

A note's job is to be useful a month from now — to the user, to you, to another agent. A single unstructured paragraph is readable for two days then becomes a stub. Apply this shape regardless of what kind of note you're writing:

- **Lead with the claim**, not the setup. The user opens the note; the first paragraph should tell them what they're looking at, not what you were doing when you found it.
- **Section it.** Even short notes benefit from 2–3 `<h2>` or `<h3>` headings — the renderer surfaces them in an outline view; flat prose can't be skimmed.
- **Cite what's external.** Every factual claim from a paper, doc, or website gets a `sources://` link (§5). If no indexed source exists, embed the URL or a verbatim quote so the user can verify the claim later.
- **Preserve the reasoning, not just the conclusion.** "We chose X" is weaker than "We chose X because Y; alternative Z would have meant W". The user re-reads notes to remember the *why*, not just the *what*.
- **Match element to data shape.** Parallel items → `<ul>` / `<ol>`. Comparison → `<table>`. Equations → KaTeX (§4.3), not prose. Action items → task list (§4.1). Code → `<pre><code class="language-…">`. Don't fall back to flat `<p>` tags for everything.
- **Length follows content.** Three sentences is fine for a quick observation; thirty paragraphs is fine for a paper summary. Avoid both extremes — the one-sentence stub the user can't reconstruct meaning from, and the bloated note where every paragraph repeats the headline.

### 1.1 Shapes by intent

Skeletons, not rigid templates. The user's actual content fills them out; skip sections that don't apply.

**Paper / artefact summary** — when asked to save or summarize a paper, blog post, or talk:

```html
<h2>What it is</h2>
<p>One paragraph: problem, approach, headline result. Cite the source:
<a href="sources://12">Vaswani et al. 2017</a>.</p>

<h2>Method</h2>
<p>The actual mechanism. Include the key equation when non-trivial:
<span data-type="inline-math" data-latex="..."></span>.</p>

<h2>Results</h2>
<ul>
  <li>Concrete metrics, with numbers.</li>
  <li>What baseline they beat, by how much.</li>
</ul>

<h2>Why it matters here</h2>
<p>Tie it to the user's current work. Skip when you don't know what
they're working on; include when you do — this is the most
user-specific section.</p>

<h2>Limitations / open questions</h2>
<ul><li>…</li></ul>
```

**Decision / methods note** — capturing why a choice was made:

```html
<h2>Decision</h2>
<p>What we landed on, in one sentence.</p>

<h2>Why</h2>
<p>The reasoning, citing constraints and evidence.</p>

<h2>Alternatives considered</h2>
<ul>
  <li><strong>Option B</strong> — rejected because …</li>
</ul>

<h2>Revisit when</h2>
<ul><li>Conditions under which the decision should be re-examined.</li></ul>
```

**Meeting note**:

```html
<h2>Decisions</h2>
<ul><li>…</li></ul>

<h2>Action items</h2>
<ul data-type="taskList">
  <li data-type="taskItem" data-checked="false"><p>…</p></li>
</ul>

<h2>Open questions</h2>
<ul><li>…</li></ul>
```

**Daily log entry** — appended via `append_note`:

```html
<h3>YYYY-MM-DD</h3>
<p>One-line frame for the day.</p>
<ul>
  <li>Accomplished X (<a href="sources://17?…">citation</a>).</li>
  <li>Blocked on Y; trying Z tomorrow.</li>
</ul>
```

**Quick observation** — user said "save this thought":

```html
<p><strong>Claim:</strong> the headline thought, in one sentence.</p>
<p>Context — where it came from, why it matters.</p>
<p>Optional: what to try next, or who would care.</p>
```

If the user's request doesn't fit any of these, default to: an H1-less HTML fragment, 2–3 `<h2>` sections (start with the claim, then context/evidence, then implication or next-action), and a `sources://` link for anything external.

## 2. The tool

Everything goes through one tool, `OpenScientistNotes`, dispatched by the `function` parameter. Ten functions, matching the backend `NotesTool.get_metadata()` names:

| `function`                 | Parameters (required **bold**)                                                    | Returns                          |
|----------------------------|------------------------------------------------------------------------------------|----------------------------------|
| `get_notes_list`           | —                                                                                  | Tree of `{id, title, folder, …}` |
| `get_notes_summary`        | **`titles`**, `top_k=3`                                                            | Candidate note IDs by title      |
| `search_notes_text`        | **`query`**, `limit=10`                                                            | Snippets with note id + title    |
| `search_notes_semantic`    | **`query`**, `limit=10`                                                            | Matching chunks with scores      |
| `get_note_chunks_by_ids`   | **`chunk_ids`**                                                                    | Exact chunk text by chunk id     |
| `read_note`                | **`note_id`**                                                                      | Full HTML content + metadata     |
| `create_note`              | **`name`**, `content`, `path`                                                      | New `{id, …}`                    |
| `edit_note`                | **`note_id`**, **`old_text`**, **`new_text`**, `occurrence=1`, `suggest_mode=true` | Updated note                     |
| `append_note`              | **`note_id`**, **`content`**                                                       | Updated note                     |
| `delete_note`              | **`note_id`**                                                                      | —                                |

Two operational facts that are easy to miss:

- **`edit_note` / `append_note` / `delete_note` all need an integer `note_id`** — not a title, not a path. Call `get_notes_list`, `get_notes_summary`, or `search_notes_text` first to discover the id, then act.
- **`edit_note` defaults to `suggest_mode=true`** — the change appears as an in-editor suggestion the user can accept or reject, not a silent mutation. Pass `suggest_mode=false` only when the user has explicitly delegated decisions to you ("just fix it", "apply the change directly").

There is no PDF-to-note function on this tool. If the user wants the contents of a PDF as a note, summarize manually with `create_note`, or save the PDF as a source and cite it.

## 3. Search before you create

Before `create_note`, search:

```
OpenScientistNotes(function="search_notes_text", query="<topic>")
```

If a relevant note exists, **edit or append to it** instead of creating a sibling — the user does not want twelve notes called "Transformer notes (1)" through "(12)". Same-title creates are not deduplicated server-side. Also run `get_notes_list` to see the existing folder layout, so you place new notes alongside their siblings instead of at the root. `search_notes_semantic` catches "did I write anything about *X*?" questions where the user's wording and the note's wording differ.

## 4. The HTML the renderer actually understands

The editor is TipTap with a Notion-like extension set. Note content is stored as an **HTML fragment** and re-parsed on every load. That means:

- Anything outside the supported schema is **dropped or normalized** on reload (`<center>`, `<font>`, `<style>`, `<script>`, `<iframe>`, custom `class=` on `<div>`, etc.).
- Whitespace inside block tags collapses like in a browser. Indenting your HTML is for you, not the user.
- Special characters in text need escaping: `<` → `&lt;`, `>` → `&gt;`, `&` → `&amp;`. Don't escape inside `<pre><code>` — that's a code block.
- Don't wrap in `<html>` / `<body>` / `<!DOCTYPE>`. Send a fragment.
- **Markdown does not render.** `# heading`, `**bold**`, triple-backtick fences pass through as literal text inside `<p>`. If a tool returns Markdown, convert it to HTML before writing.

### 4.1 Block elements

| What            | Tag                                                                                          |
|-----------------|----------------------------------------------------------------------------------------------|
| Headings        | `<h1>` … `<h6>` (h1–h3 typical)                                                              |
| Paragraph       | `<p>`                                                                                        |
| Bullet list     | `<ul><li>…</li></ul>` (nestable)                                                             |
| Numbered list   | `<ol><li>…</li></ol>` (nestable)                                                             |
| Task list       | `<ul data-type="taskList"><li data-type="taskItem" data-checked="false"><p>text</p></li></ul>` (`data-checked="true"` = done; both `data-type` attrs are required for the parser to match) |
| Blockquote      | `<blockquote>…</blockquote>`                                                                 |
| Horizontal rule | `<hr>`                                                                                       |
| Code block      | `<pre><code class="language-python">…</code></pre>`                                          |
| Block math      | `<div data-type="block-math" data-latex="\\int_0^1 x^2 dx"></div>`                           |
| Table           | `<table><tr><th>…</th></tr><tr><td>…</td></tr></table>`                                      |
| Image           | `<img src="https://…" alt="…">`                                                              |
| Text alignment  | `<p style="text-align: center">…</p>` (only on `<p>` and `<h1>`–`<h6>`)                      |

Code-block languages with syntax highlighting: `python` (default), `typescript`, `javascript`, `cpp`, `c`, `java`, `rust`, `go`, `bash`, `sql`, `css`, `html`, `json`, `yaml`, `markdown`. Anything else falls back to plain text. **The `language-` prefix is mandatory** — `class="python"` alone won't highlight.

### 4.2 Inline elements

| What          | Tag                                                                                       |
|---------------|-------------------------------------------------------------------------------------------|
| Bold          | `<strong>…</strong>`                                                                      |
| Italic        | `<em>…</em>`                                                                              |
| Strikethrough | `<s>…</s>`                                                                                |
| Inline code   | `<code>…</code>`                                                                          |
| Highlight     | `<mark>…</mark>` or `<mark style="background-color: #fef3c7">…</mark>` (multicolor)       |
| Superscript   | `<sup>…</sup>`                                                                            |
| Subscript     | `<sub>…</sub>`                                                                            |
| Link          | `<a href="https://…">text</a>` or `<a href="sources://…">text</a>` (see §5)               |
| Inline math   | `<span data-type="inline-math" data-latex="x^2 + y^2"></span>`                            |

**No underline.** The renderer does not load `@tiptap/extension-underline`; `<u>` is stripped on reload. Use `<em>` or `<mark>` for emphasis instead.

### 4.3 Math (KaTeX)

LaTeX lives in the `data-latex` attribute; the text node inside the tag is ignored. **Escape backslashes once** for the JSON tool call (`\\int`, `\\frac{a}{b}`).

```html
<p>The cross-entropy loss is
  <span data-type="inline-math" data-latex="-\\sum_i p_i \\log q_i"></span>.</p>

<div data-type="block-math"
  data-latex="\\mathcal{L} = -\\frac{1}{N} \\sum_{i=1}^{N} y_i \\log \\hat{y}_i"></div>
```

`$...$` and `$$...$$` only work as input rules while the user types — they are not the persisted format. Always emit the `data-type="…-math"` element.

## 5. Citations: linking notes to sources

When a note references an indexed paper, document, or quote in the workspace, use the `sources://` link scheme. The frontend turns these into clickable references that scroll the source panel to the right place.

Two forms, in order of how often you'll write each:

```html
<!-- Quote citation: agent has the exact text it's citing -->
<a href="sources://12?kind=quote&exact=attention%20is%20all%20you%20need">attention head</a>

<!-- Plain source link: just opens the source -->
<a href="sources://12">Vaswani et al. 2017</a>
```

Rules:

- The path segment is the source's integer id (from `OpenScientistSearch` results, the document panel, etc.).
- `exact` must be **plain text**, percent-encoded, verbatim from the source so the highlighter can find it. Keep it short (a few words). Optional `prefix=` / `suffix=` params disambiguate when the same phrase appears multiple times.
- The parser treats any link with `exact` as a quote reference. `kind=quote` is decorative — `exact` is what triggers quote handling.
- Anchor text inside `<a>` should be **≤ 4 words** (e.g. "attention mechanism", "Vaswani §3.2"). Long anchor text wraps awkwardly inline.
- Cite the *thing you're claiming*, not the source as a whole. "Vaswani et al. observed [scaling effects](sources://12?...)" reads better than "[Vaswani et al.](sources://12) observed scaling effects."

## 6. Editing: choose the right verb

Three functions modify an existing note. They are not interchangeable.

| Function      | Use when                                                                                       | Don't use when                                                                                                                              |
|---------------|------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| `edit_note`   | Replacing a specific phrase, fact, or short paragraph in place. Find-and-replace on raw HTML.   | The text appears more than once and you didn't pass `occurrence` — you'll mutate the wrong copy.                                            |
| `append_note` | Adding a new section, finding, or daily-log entry to the bottom.                                | Content needs to land mid-document — append always goes to the end.                                                                         |
| `create_note` | Starting a clearly new artifact (or resurrecting a soft-deleted one).                           | The note already exists with different content — `create_note` will produce a same-titled sibling, not overwrite. Use edit / append instead. |

`edit_note` pitfalls:

- The match is on **raw HTML**, not rendered text. If a word lives inside `<strong>`, the markup is between the surrounding text and your `old_text`. **Always `read_note` first** when the match is non-trivial — copy the string out of the response rather than retyping it.
- Whitespace and newlines count.
- `occurrence` is 1-based; `occurrence=-1` replaces all. To rewrite every "GPT-3" → "GPT-4", either pass `occurrence=-1` once, or loop with `occurrence=1` re-reading between iterations (positions shift).
- `suggest_mode=true` (the default) shows the change as a suggestion the user can accept/reject in the editor. For background updates the user has delegated, pass `suggest_mode=false`.

`append_note` pitfall:

- Always wrap appended content in block-level tags (`<h2>`, `<p>`, `<ul>`, …). Bare text doesn't merge cleanly into the previous paragraph on reload. For dated entries, lead with a heading: `<h3>2026-05-04</h3>`.

## 7. Folder organization

Folders are flat strings with `/` as the separator (`"papers/transformers"`), passed via the `path` parameter on `create_note`. They render in the tree as nested directories.

Conventions that have worked:

- Top-level folders by *kind*: `papers/`, `meetings/`, `experiments/`, `daily/`, `inbox/`.
- Within `papers/`, sub-folder by topic or author surname: `papers/diffusion/`, `papers/scaling-laws/`.
- Use `inbox/` for "I don't know where this goes yet" — better than the root.
- **The user's existing structure beats every convention.** Always `get_notes_list` first and place new notes next to siblings.

When the user asks you to "organize my notes", don't move folders unprompted — ask which target structure they want. Bulk reorganization is destructive-feeling; confirm scope before acting.

## 8. Search inside notes

`search_notes_text` returns matched snippets with surrounding context, not full content. Use it as the *first* step whenever the user asks a question their notes can answer ("what did I write about RoPE?", "did I take notes on the meeting last week?"). `search_notes_semantic` is for concept-level queries where the user's wording and the note's wording diverge.

Don't read every matched note in full — read the one or two whose snippets directly answer the user's question. The user's notes are theirs; reading more than needed wastes context and risks surfacing private content the user didn't ask about.

## 9. Anti-patterns

- **Writing a note as a single unstructured paragraph.** Apply §1's shape — sectioned, cited, reasoning preserved. Plain wall-of-text notes are unreadable a week later and are the most common failure mode this skill exists to prevent.
- **Duplicating notes** because you skipped the search step. *Always* `search_notes_text` (or `get_notes_list`) before `create_note`.
- **Treating notes as agent memory.** If you're the only consumer, write under `.openscientist/sessions/$SESSION/` — not the user's tree.
- **Markdown as content.** The renderer doesn't parse it; convert to HTML first.
- **Citing "the paper" without a `sources://` link.** A claim without a citation reachable from this workspace is a claim the user can't verify in one click.
- **Long `<a>` anchor text** — keep it ≤ 4 words.
- **Using `<u>` for emphasis** — underline isn't loaded. Use `<em>` or `<mark>`.
- **Block math via `$$...$$` literal in HTML** — input rule only. Use `<div data-type="block-math" data-latex="…">`.
- **Editing or appending by title.** Those calls require an integer `note_id` — discover it via `get_notes_list`, `get_notes_summary`, or `search_notes_text` first.
- **Bulk-overwriting via same-title `create_note`.** Creates a sibling, doesn't overwrite. Use `edit` / `append`.
- **Reorganizing folders without asking.** Notes are the user's filing system; touching it without permission breaks trust fast.

## 10. Quick reference

```python
# Search-then-create
hits = OpenScientistNotes(function="search_notes_text", query="transformer scaling")
if not hits:
    OpenScientistNotes(
        function="create_note",
        name="Transformer scaling — survey",
        path="papers/scaling-laws",
        content=(
            "<h2>What it is</h2>"
            "<p>Survey of scaling-law work since "
            "<a href='sources://12'>Kaplan 2020</a>; covers the "
            "loss-vs-N power law and its breakdown at small data.</p>"
            "<h2>Key claims</h2>"
            "<ul><li>Loss ∝ N<sup>-α</sup> with "
            "<span data-type='inline-math' data-latex='\\\\alpha \\\\approx 0.076'></span> "
            "(<a href='sources://12?kind=quote&exact=alpha%20approx%200.076'>Kaplan §3</a>).</li>"
            "<li>Breaks down below ~10M params — see "
            "<a href='sources://14'>Hoffmann 2022</a>.</li></ul>"
            "<h2>Why it matters here</h2>"
            "<p>Constrains the compute-vs-data tradeoff for the "
            "next experiment.</p>"
        ),
    )

# Append a dated entry (need the note's id)
notes = OpenScientistNotes(function="get_notes_list")
daily_id = next(n["id"] for n in notes if n["title"] == "Daily log")
OpenScientistNotes(
    function="append_note",
    note_id=daily_id,
    content="<h3>2026-05-04</h3><p>Reproduced result from "
            "<a href='sources://17?kind=quote&exact=Table%202'>Table 2</a>.</p>",
)

# Targeted edit (read first so old_text matches the raw HTML exactly)
note = OpenScientistNotes(function="read_note", note_id=42)
OpenScientistNotes(
    function="edit_note",
    note_id=42,
    old_text="<p>Used GPT-3.</p>",
    new_text="<p>Used GPT-4 (initial draft used GPT-3 — see daily log 2026-05-04).</p>",
    suggest_mode=True,  # default; user accepts/rejects in the editor
)
```

Four facts to remember on every call: **shape it** (§1), **search first**, **HTML out**, **edit/append/delete need `note_id`**.
