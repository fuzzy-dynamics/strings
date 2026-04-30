# Notes

## Meta
trigger: create, read, edit, search, or organize workspace notes; convert PDFs to notes; find specific information across notes
not_for: searching indexed documents (use search tool), file storage
cost: low (except pdf_to_note: medium)
tools: notes__create_note, notes__get_notes_list, notes__read_note, notes__edit_note, notes__append_note, notes__delete_note, notes__search_notes, notes__pdf_to_note

## When to Use
- User wants to save, organize, or retrieve information in their workspace
- Writing research summaries, meeting notes, task lists, or any persistent text
- Converting a PDF (from any URL) into a readable, editable note
- NOT for reading papers or indexed documents (use search tool)

## Functions

### notes__get_notes_list
List all notes in the workspace as a tree structure.
params: (none)

### notes__read_note
Read a note's content and metadata.
params:
  - name (str, required): note name/filename
  - path (str, optional): folder path (e.g. "project/docs")

### notes__create_note
Create a new note. Content is HTML.
params:
  - name (str, required): note name/filename
  - path (str, optional): folder path
  - content (str, optional): initial HTML content

### notes__edit_note
Find-and-replace text in a note. Operates on raw HTML.
params:
  - name (str, required): note name/filename
  - old_text (str, required): text to find
  - new_text (str, required): replacement text
  - occurrence (int, optional, default=1): which occurrence to replace (1-based)
  - path (str, optional): folder path

### notes__append_note
Append HTML content to the end of a note.
params:
  - name (str, required): note name/filename
  - content (str, required): HTML content to append
  - path (str, optional): folder path

### notes__delete_note
Soft-delete a note (recoverable).
params:
  - name (str, required): note name/filename
  - path (str, optional): folder path

### notes__search_notes
Search across all notes by keyword. Returns matched snippets with surrounding context lines, not full content. Use this to find specific information across notes without reading each one.
params:
  - query (str, required): text to search for in note titles and content
  - context_lines (int, optional, default=3): number of lines to show before and after each match
  - path (str, optional): limit search to notes in this folder path

### notes__pdf_to_note
Download a PDF from any URL, convert it to formatted HTML using high-quality OCR, and save as a note. Handles math/LaTeX, tables, and images. Use when web_search finds a PDF link and you want to make its content available as a note.
params:
  - url (str, required): HTTP/HTTPS URL of the PDF
  - name (str, optional): title for the note (derived from URL filename if omitted)
  - path (str, optional): folder path

## HTML Format

Note content is HTML. Use semantic tags:
- Structure: `<h1>`–`<h4>`, `<p>`, `<blockquote>`, `<hr>`
- Lists: `<ul>/<ol>` with `<li>`, `<ul data-type="taskList">` for checklists
- Inline: `<strong>`, `<em>`, `<u>`, `<s>`, `<code>`
- Code blocks: `<pre><code>...</code></pre>`
- Tables: `<table>`, `<tr>`, `<td>`, `<th>`
- Links: `<a href="...">`

### Citations

When referencing indexed sources (papers, documents), use this link format:
`<a href="sources://<id>?startText=<text>&endText=<text>">Link Text</a>`
- `<id>` is the source/document ID
- `startText` and `endText` are plain text only (no LaTeX or special characters), max 4 words each
- Link text must be max 4 words (e.g. "Attention mechanism described")

## Examples

run(tool="notes__get_notes_list", params={})
run(tool="notes__create_note", params={"name": "Summary", "content": "<p>Key findings...</p>"})
run(tool="notes__read_note", params={"name": "Summary"})
run(tool="notes__edit_note", params={"name": "Summary", "old_text": "Key findings", "new_text": "Main results"})
run(tool="notes__append_note", params={"name": "Summary", "content": "<p>Additional note.</p>"})
run(tool="notes__search_notes", params={"query": "reasoning", "context_lines": 5})
run(tool="notes__search_notes", params={"query": "attention", "path": "papers"})
run(tool="notes__pdf_to_note", params={"url": "https://arxiv.org/pdf/2301.07041.pdf", "name": "Chain of Thought", "path": "papers"})
