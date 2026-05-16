---
name: notes-use
description: How to author, structure, and maintain workspace notes through the `OpenScientistNotes` tool so the Notion-like (TipTap) editor renders them well. Covers the tool's eight functions, the HTML the renderer actually parses (headings, lists, task lists, tables, code blocks with language, KaTeX math, highlights, source-citation links), the find-the-id flow that edit/append/delete require, the search-before-create discipline, and the line between a note (user-facing artifact) and a scratchpad (agent memory — does not belong in notes). Use whenever the user asks you to save, summarize, record, or organize anything as a note, or to update / reorganize / cite within existing notes.
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

## 1. The tool

Everything goes through one tool, `OpenScientistNotes`, dispatched by the `function` parameter. Eight functions:

| `function`              | Parameters (required **bold**)                                                       | Returns                          |
|-------------------------|---------------------------------------------------------------------------------------|----------------------------------|
| `list_notes`            | —                                                                                     | Tree of `{id, title, folder, …}` |
| `search_notes`          | **`query`**                                                                           | Snippets with note id + title    |
| `search_notes_semantic` | **`query`**                                                                           | Same shape, embedding-based      |
| `read_note`             | **`note_id`**                                                                         | Full HTML content + metadata     |
| `create_note`           | **`title`**, **`content`**, `path`                                                    | New `{id, …}`                    |
| `edit_note`             | **`note_id`**, **`old_text`**, **`new_text`**, `occurrence=1`, `suggest_mode=true`    | Updated note                     |
| `append_note`           | **`note_id`**, **`content`**                                                          | Updated note                     |
| `delete_note`           | **`note_id`**                                                                         | —                                |

Two operational facts that are easy to miss:

- **`edit_note` / `append_note` / `delete_note` all need an integer `note_id`** — not a title, not a path. Call `list_notes` or `search_notes` first to discover the id, then act.
- **`edit_note` defaults to `suggest_mode=true`** — the change appears as an in-editor suggestion the user can accept or reject, not a silent mutation. Pass `suggest_mode=false` only when the user has explicitly delegated decisions to you ("just fix it", "apply the change directly").

There is no PDF-to-note function on this tool. If the user wants the contents of a PDF as a note, summarize manually with `create_note`, or save the PDF as a source and cite it.

## 2. Search before you create

Before `create_note`, search:

```
OpenScientistNotes(function="search_notes", query="<topic>")
```

If a relevant note exists, **edit or append to it** instead of creating a sibling — the user does not want twelve notes called "Transformer notes (1)" through "(12)". Same-title creates are not deduplicated server-side. Also run `list_notes` to see the existing folder layout, so you place new notes alongside their siblings instead of at the root. `search_notes_semantic` catches "did I write anything about *X*?" questions where the user's wording and the note's wording differ.

## 3. The HTML the renderer actually understands

The editor is TipTap with a Notion-like extension set. Note content is stored as an **HTML fragment** and re-parsed on every load. That means:

- Anything outside the supported schema is **dropped or normalized** on reload (`<center>`, `<font>`, `<style>`, `<script>`, `<iframe>`, custom `class=` on `<div>`, etc.).
- Whitespace inside block tags collapses like in a browser. Indenting your HTML is for you, not the user.
- Special characters in text need escaping: `<` → `&lt;`, `>` → `&gt;`, `&` → `&amp;`. Don't escape inside `<pre><code>` — that's a code block.
- Don't wrap in `<html>` / `<body>` / `<!DOCTYPE>`. Send a fragment.
- **Markdown does not render.** `# heading`, `**bold**`, triple-backtick fences pass through as literal text inside `<p>`. If a tool returns Markdown, convert it to HTML before writing.

### 3.1 Block elements

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

### 3.2 Inline elements

| What          | Tag                                                                                       |
|---------------|-------------------------------------------------------------------------------------------|
| Bold          | `<strong>…</strong>`                                                                      |
| Italic        | `<em>…</em>`                                                                              |
| Strikethrough | `<s>…</s>`                                                                                |
| Inline code   | `<code>…</code>`                                                                          |
| Highlight     | `<mark>…</mark>` or `<mark style="background-color: #fef3c7">…</mark>` (multicolor)       |
| Superscript   | `<sup>…</sup>`                                                                            |
| Subscript     | `<sub>…</sub>`                                                                            |
| Link          | `<a href="https://…">text</a>` or `<a href="sources://…">text</a>` (see §4)               |
| Inline math   | `<span data-type="inline-math" data-latex="x^2 + y^2"></span>`                            |

**No underline.** The renderer does not load `@tiptap/extension-underline`; `<u>` is stripped on reload. Use `<em>` or `<mark>` for emphasis instead.

### 3.3 Math (KaTeX)

LaTeX lives in the `data-latex` attribute; the text node inside the tag is ignored. **Escape backslashes once** for the JSON tool call (`\\int`, `\\frac{a}{b}`).

```html
<p>The cross-entropy loss is
  <span data-type="inline-math" data-latex="-\\sum_i p_i \\log q_i"></span>.</p>

<div data-type="block-math"
  data-latex="\\mathcal{L} = -\\frac{1}{N} \\sum_{i=1}^{N} y_i \\log \\hat{y}_i"></div>
```

`$...$` and `$$...$$` only work as input rules while the user types — they are not the persisted format. Always emit the `data-type="…-math"` element.

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

- The path segment is the source's integer id (from `OpenScientistSearch` results, the document panel, etc.).
- `exact` must be **plain text**, percent-encoded, verbatim from the source so the highlighter can find it. Keep it short (a few words). Optional `prefix=` / `suffix=` params disambiguate when the same phrase appears multiple times.
- The parser treats any link with `annotationId` as an annotation reference and any link with `exact` as a quote reference. `kind=quote` is decorative — `exact` is what triggers quote handling.
- Anchor text inside `<a>` should be **≤ 4 words** (e.g. "attention mechanism", "Vaswani §3.2"). Long anchor text wraps awkwardly inline.
- Cite the *thing you're claiming*, not the source as a whole. "Vaswani et al. observed [scaling effects](sources://12?...)" reads better than "[Vaswani et al.](sources://12) observed scaling effects."

`tools/annotation.md` covers building annotation ids.

## 5. Editing: choose the right verb

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

## 6. Folder organization

Folders are flat strings with `/` as the separator (`"papers/transformers"`), passed via the `path` parameter on `create_note`. They render in the tree as nested directories.

Conventions that have worked:

- Top-level folders by *kind*: `papers/`, `meetings/`, `experiments/`, `daily/`, `inbox/`.
- Within `papers/`, sub-folder by topic or author surname: `papers/diffusion/`, `papers/scaling-laws/`.
- Use `inbox/` for "I don't know where this goes yet" — better than the root.
- **The user's existing structure beats every convention.** Always `list_notes` first and place new notes next to siblings.

When the user asks you to "organize my notes", don't move folders unprompted — ask which target structure they want. Bulk reorganization is destructive-feeling; confirm scope before acting.

## 7. Search inside notes

`search_notes` returns matched snippets with surrounding context, not full content. Use it as the *first* step whenever the user asks a question their notes can answer ("what did I write about RoPE?", "did I take notes on the meeting last week?"). `search_notes_semantic` is for concept-level queries where the user's wording and the note's wording diverge.

Don't read every matched note in full — read the one or two whose snippets directly answer the user's question. The user's notes are theirs; reading more than needed wastes context and risks surfacing private content the user didn't ask about.

## 8. Anti-patterns

- **Duplicating notes** because you skipped the search step. *Always* `search_notes` (or `list_notes`) before `create_note`.
- **Treating notes as agent memory.** If you're the only consumer, write under `.openscientist/sessions/$SESSION/` — not the user's tree.
- **Markdown as content.** The renderer doesn't parse it; convert to HTML first.
- **Citing "the paper" without a `sources://` link.** A claim without a citation reachable from this workspace is a claim the user can't verify in one click.
- **Long `<a>` anchor text** — keep it ≤ 4 words.
- **Using `<u>` for emphasis** — underline isn't loaded. Use `<em>` or `<mark>`.
- **Block math via `$$...$$` literal in HTML** — input rule only. Use `<div data-type="block-math" data-latex="…">`.
- **Editing or appending by title.** Those calls require an integer `note_id` — discover it via `list_notes` / `search_notes` first.
- **Bulk-overwriting via same-title `create_note`.** Creates a sibling, doesn't overwrite. Use `edit` / `append`.
- **Reorganizing folders without asking.** Notes are the user's filing system; touching it without permission breaks trust fast.

## 9. Quick reference

```python
# Search-then-create
hits = OpenScientistNotes(function="search_notes", query="transformer scaling")
if not hits:
    OpenScientistNotes(
        function="create_note",
        title="Transformer scaling — survey",
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

# Append a dated entry (need the note's id)
notes = OpenScientistNotes(function="list_notes")
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

Three facts to remember on every call: **search first**, **HTML out**, **edit/append/delete need `note_id`**.
