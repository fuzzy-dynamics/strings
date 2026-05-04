---
name: notes-use
description: How to author, structure, and maintain workspace notes so the OpenScientist Notion-like editor renders them well and the user can navigate them later. Covers the HTML the renderer actually understands (headings, lists, task lists, code blocks with language, tables, inline + block math, highlights, source-citation links), the search-before-create discipline that prevents duplicate notes, the choice between `create` / `edit` / `append`, folder organization, and the line between a note (user-facing artifact) and a scratchpad (agent memory — does not belong in notes). Use whenever the user asks you to save, summarize, record, or organize anything as a note, or to update / reorganize / cite within existing notes.
metadata:
  skill-author: OpenScientist
category: knowledge
---

# Notes Use

Notes are the *user-facing* artifact in the workspace: a Notion-like editor renders them, the user reads them, edits them, and shares them. They are **not** an agent scratchpad — for agent working memory, use `planning-with-files` (`.openscientist/sessions/...`). This skill is about producing notes the renderer treats well and the user can actually navigate later.

## 0. When to create a note (and when not to)

Create or modify a note **only when the user explicitly asks** to save, record, summarize, note, document, or remember something — or when the user is iterating on an existing note. Triggers:

- "save this as a note", "note this down", "make me a note about X"
- "summarize the paper into my notes"
- "update the methods note with the new finding"
- "convert this PDF into a note"

**Do not** use notes as:

- working memory across tool calls — that's `planning-with-files` and lives under `.openscientist/sessions/$SESSION/`
- a log of your own reasoning or progress — that's `progress.md`
- a dumping ground for raw tool output — extract the claim first, then write
- a duplicate of something already in `findings.md` — those files exist for that
- a place to track open questions to yourself — they're invisible to the user as notes

The test: would the user, opening this in their notes panel a week from now, recognize it as something *they* wanted? If no, it's the wrong file.

## 1. The mental model

The editor is TipTap with a Notion-like flavour. The renderer treats note content as **HTML** and parses it back into a structured document on every load. That has consequences:

- **HTML is the wire format.** Plain text works, but you lose every rendering feature.
- **Schema-incompatible HTML gets dropped or normalized** when the editor reloads. If you write `<center>` or `<font color=...>` it will likely vanish.
- **Whitespace inside block tags is collapsed** like the browser does. Indentation in your HTML is for the agent, not the user.
- **Special characters need escaping** in text content: `<` → `&lt;`, `>` → `&gt;`, `&` → `&amp;`. Don't escape inside `<pre><code>` — that's already a code block.
- **Don't wrap content in `<html>` / `<body>` / `<!DOCTYPE>`** — note content is a fragment that lives inside the editor's root document.

A note also has a **title** (separate field) and a **folder path** (string like `"papers/transformers"`). Folders nest by `/`. The title is shown at the top of the rendered note and in the tree; don't repeat it as the first `<h1>`.

## 2. Search before you create

Before creating a note, search:

```
notes__search_notes(query="<topic>", context_lines=2)
```

If a relevant note exists, **edit or append to it** instead of creating a sibling — the user does not want twelve notes called "Transformer notes (1)" through "Transformer notes (12)". Two notes covering the same topic is the most common failure mode of this tool. The cost of one extra search is one tool call; the cost of a duplicate is the user having to merge them later.

Also `notes__get_notes_list` (cheap, returns the tree) before deciding on a folder, so you place the new note next to its siblings instead of at the root.

## 3. The HTML the renderer actually understands

This is what the editor (TipTap with the Notion-like extension set) parses cleanly. Anything outside this list is best avoided.

### 3.1 Block elements

| What         | Tag                                                   |
|--------------|-------------------------------------------------------|
| Headings     | `<h1>` … `<h4>`                                       |
| Paragraph    | `<p>`                                                 |
| Bullet list  | `<ul><li>...</li></ul>`                               |
| Numbered     | `<ol><li>...</li></ol>`                               |
| Task list    | `<ul data-type="taskList"><li data-checked="false"><div>text</div></li></ul>` (`data-checked="true"` for done) |
| Blockquote   | `<blockquote>...</blockquote>`                        |
| Horizontal rule | `<hr>`                                             |
| Code block   | `<pre><code class="language-python">...</code></pre>` |
| Block math   | `<div data-type="block-math" data-latex="\\int_0^1 x^2 dx"></div>` |
| Table        | `<table><tr><th>...</th></tr><tr><td>...</td></tr></table>` |

Code-block languages the renderer has a syntax highlighter for: `python` (default), `typescript`, `javascript`, `cpp`, `c`, `java`, `rust`, `go`, `bash`, `sql`, `css`, `html`, `json`, `yaml`, `markdown`. Anything else falls back to plain text — fine for short shell snippets, fine for prose. **Don't forget the `language-` prefix** on the class, otherwise highlighting silently doesn't kick in.

### 3.2 Inline elements

| What            | Tag                                                                |
|-----------------|--------------------------------------------------------------------|
| Bold            | `<strong>...</strong>`                                             |
| Italic          | `<em>...</em>`                                                     |
| Underline       | `<u>...</u>`                                                       |
| Strikethrough   | `<s>...</s>`                                                       |
| Inline code     | `<code>...</code>`                                                 |
| Highlight       | `<mark>...</mark>` (or `<mark style="background-color: #fef3c7">`) |
| Superscript     | `<sup>...</sup>`                                                   |
| Subscript       | `<sub>...</sub>`                                                   |
| Link            | `<a href="https://...">text</a>`                                   |
| Inline math     | `<span data-type="inline-math" data-latex="x^2 + y^2"></span>`     |

### 3.3 Math (LaTeX, KaTeX-rendered)

The renderer uses KaTeX. Write LaTeX into `data-latex` and **escape backslashes once** for the JSON tool call (i.e. `\\int`, `\\frac{a}{b}`). The text node between the tags is ignored — the source of truth is the attribute.

```html
<p>The cross-entropy loss is
  <span data-type="inline-math" data-latex="-\\sum_i p_i \\log q_i"></span>.
</p>

<div data-type="block-math" data-latex="\\mathcal{L} = -\\frac{1}{N} \\sum_{i=1}^{N} y_i \\log \\hat{y}_i"></div>
```

Don't put `$...$` or `$$...$$` in the HTML and expect rendering — those input rules only fire while the user is typing in the editor. The persisted form is always the `data-type="…-math"` element.

### 3.4 What NOT to write

- `<style>`, `<script>`, `<iframe>` — stripped.
- `<font>`, `<center>`, deprecated HTML — normalized away.
- Custom `<div class="...">` for layout — class is dropped on reload; use the structures above.
- Markdown (`# heading`, `**bold**`, fenced code blocks) — passes through as literal text inside `<p>`. If you receive Markdown-shaped content (from a tool, a paste), convert it to HTML before calling `notes__create_note` / `notes__append_note`.

## 4. Citations: linking notes to sources

When a note references an indexed paper, document, or quote in the workspace, use the `sources://` link scheme. The frontend turns these into clickable references that scroll the source panel to the right place.

Three forms, in order of how often you'll write each:

```html
<!-- Quote citation: agent has the exact text it's citing -->
<a href="sources://12?kind=quote&exact=attention%20is%20all%20you%20need">attention head</a>

<!-- Annotation citation: agent has an annotation id from a prior tool result -->
<a href="sources://12?annotationId=ann_abc123">Section 3.2</a>

<!-- Plain source link: just opens the source -->
<a href="sources://12">Vaswani et al. 2017</a>
```

Rules:

- `<id>` is the source's integer id (from `OpenScientistSearch` results, the document panel, etc.).
- For `kind=quote`, the `exact` parameter must be **plain text only** — no LaTeX, no special characters, percent-encode spaces. Keep it short (≤ a few words) and verbatim from the source so the highlighter can find it.
- Anchor text inside the `<a>` should be **≤ 4 words** (e.g. "attention mechanism", "Vaswani §3.2") — long anchor text wraps awkwardly in the rendered note.
- Cite the *thing you're claiming*, not the source as a whole. "Vaswani et al. observed [scaling effects](sources://12?...)" reads better than "[Vaswani et al.](sources://12) observed scaling effects."

The `tools/annotation.md` doc covers building annotation ids; the wire helpers (`buildSourceReferenceUrl`) confirm the URL grammar above.

## 5. Editing: choose the right verb

Three tools modify an existing note. They are not interchangeable.

| Verb                  | Use when                                                              | Don't use when                                                            |
|-----------------------|-----------------------------------------------------------------------|---------------------------------------------------------------------------|
| `notes__edit_note`    | Replacing a specific phrase, fact, or short paragraph in place. Find-and-replace on raw HTML. | The text you want to change appears more than once and you didn't pass `occurrence` — you'll mutate the wrong copy. |
| `notes__append_note`  | Adding a new section, a new finding, a daily log entry to the bottom. | Content needs to land mid-document — append always goes to the end.       |
| `notes__create_note` (with same name + path) | Resurrecting a soft-deleted note, or starting a clearly new artifact. | The note already exists with different content — you'll create a sibling, not overwrite. Edit/append instead. |

Edit pitfalls:

- The match is on **raw HTML**, not rendered text. If the user wrote a word inside `<strong>`, the markup is between the surrounding text and your match string. Read the note first if the find-string is non-trivial.
- Whitespace and newlines count. Copy the text out of the `read_note` output, don't retype it.
- `occurrence` is 1-based and only counts exact matches. If you want to change every "GPT-3" to "GPT-4", call edit in a loop with `occurrence=1` each time, re-reading after each replacement (the document shifts).

Append pitfalls:

- Always wrap your appended content in block-level tags (`<h2>`, `<p>`, `<ul>`, …). Bare text appended to a note that ended in a `<p>` will *not* merge into that paragraph cleanly on the next reload — it will become a separate paragraph at best, lost at worst.
- For dated entries, lead with a heading: `<h3>2026-05-04</h3>`. The user can collapse and scan.

## 6. Folder organization

Folders are flat strings with `/` as the separator (`"papers/transformers"`). They render in the tree as nested directories. Conventions that have worked:

- Top-level folders by *kind*: `papers/`, `meetings/`, `experiments/`, `daily/`, `inbox/`.
- Within `papers/`, sub-folder by topic or by author surname for review-heavy researchers: `papers/diffusion/`, `papers/scaling-laws/`.
- Use `inbox/` for "I don't know where this goes yet" — better than putting it at the root and forgetting it.
- The user's existing structure beats every convention. **Always `notes__get_notes_list` first** and place new notes alongside siblings, not next to the root.

When the user asks you to "organize my notes", don't move folders unprompted — ask which target structure they want, then move via `notes__edit_note` for the `folder` field (the API supports it on `updateNote`). Bulk reorganization is destructive-feeling to the user; confirm scope before acting.

## 7. PDFs and external content

`notes__pdf_to_note` is the right tool when the user wants the *full content* of a PDF as a note — it OCR's, preserves math/tables/images, and produces editable HTML. Use cases:

- "Save this paper to my notes": `notes__pdf_to_note(url=..., name=..., path="papers/...")`.
- A `web_search` returned a PDF link that the user wants to read inside the notes editor.

Don't use it for:

- A single fact you can extract and cite — that's a 3-line note with a `sources://` link, not a 40-page transcription.
- Pages that are HTML (the tool expects a PDF URL specifically). For HTML, fetch + summarize manually.

The PDF conversion is the only "medium-cost" notes tool. Run it once per PDF; the result is editable like any other note.

## 8. Search inside notes

`notes__search_notes` returns matched snippets with surrounding lines, not full content. Use it as the *first* step whenever the user asks a question their notes can answer ("what did I write about RoPE?", "did I take notes on the meeting last week?"). Tune `context_lines`:

- `context_lines=2` for keyword scans across many notes.
- `context_lines=10` when you need enough context to actually answer without a follow-up `read_note`.
- `path="papers"` to scope when the workspace has hundreds of notes and the keyword is generic.

Don't read every matched note in full — read the one or two whose snippets directly answer the user's question. The user's notes are theirs; reading more than needed wastes context and risks surfacing private content the user didn't ask about.

## 9. Anti-patterns

- **Duplicating notes** because you skipped the search step. *Always* `search_notes` (or `get_notes_list`) before `create_note`.
- **Treating notes as agent memory.** If the only consumer is you, write to `.openscientist/sessions/$SESSION/` instead — the user does not want your scratch in their tree.
- **Markdown as content.** The renderer doesn't parse it; convert to HTML first.
- **Citing "the paper" without a `sources://` link.** A claim without a citation reachable from this workspace is a claim the user can't verify in one click.
- **Long `<a>` anchor text** (`<a href="sources://12">Vaswani 2017 Attention is All You Need section 3.2</a>`) — the rendered note has these inline; keep them ≤ 4 words.
- **Block math via `$$...$$` literal in HTML** — that's an input rule, not the persisted form. Use `<div data-type="block-math" data-latex="...">`.
- **Bulk-overwriting a long note via `create_note` of the same name.** The API creates siblings; the user ends up with two. Use `edit` / `append`.
- **Reorganizing folders without asking.** Notes are the user's filing system; touching it without permission breaks trust faster than almost anything else.

## 10. Quick reference

```python
# Search-then-create
hits = notes__search_notes(query="transformer scaling", context_lines=2)
if not hits:
    notes__create_note(
        name="Transformer scaling — survey",
        path="papers/scaling-laws",
        content=(
            "<h2>Setup</h2>"
            "<p>Survey of scaling-law work since "
            "<a href='sources://12'>Kaplan 2020</a>.</p>"
            "<h2>Key claims</h2>"
            "<ul><li>Loss ∝ N<sup>-α</sup> with "
            "<span data-type='inline-math' data-latex='\\\\alpha \\\\approx 0.076'></span>.</li></ul>"
        ),
    )

# Append a dated entry
notes__append_note(
    name="Daily log",
    path="daily",
    content="<h3>2026-05-04</h3><p>Reproduced result from <a href='sources://17?kind=quote&exact=Table%202'>Table 2</a>.</p>",
)

# Targeted edit
notes__edit_note(
    name="Methods",
    old_text="<p>Used GPT-3.</p>",
    new_text="<p>Used GPT-4 (initial draft used GPT-3 — see daily log 2026-05-04).</p>",
)
```

Two facts to remember on every call: **search first**, **HTML out**.
