# Notes

## Meta
trigger: create, read, edit, search, or organize workspace notes
not_for: searching indexed documents (use search), source lifecycle management (use source), file storage
cost: low
tools: notes__create_note, notes__get_notes_list, notes__get_notes_summary, notes__search_notes_text, notes__search_notes_semantic, notes__get_note_chunks_by_ids, notes__read_note, notes__edit_note, notes__append_note, notes__delete_note

## When to Use
- User wants to save, organize, or retrieve information in their workspace
- Writing research summaries, meeting notes, task lists, or any persistent text
- Searching existing notes by keyword or semantic similarity
- NOT for reading papers or indexed documents (use search)

## Functions

### notes__create_note
Create a new note in a space at a specific folder path with a given name.
params:
  - name (str, required): note name/title
  - path (str, optional): folder path
  - content (str, optional): initial content

### notes__get_notes_list
Get the complete notes tree structure for a space.
params: (none)

### notes__get_notes_summary
Resolve one or more note titles to summary matches in the current space.
params:
  - titles (list[str], required): note titles to resolve
  - top_k (int, optional, default=3): maximum candidate matches per input title

### notes__search_notes_text
Run keyword/full-text search across note titles and note content.
params:
  - query (str, required): keyword or full-text search query
  - limit (int, optional, default=10): maximum matches to return

### notes__search_notes_semantic
Run semantic search across indexed note chunks.
params:
  - query (str, required): semantic search query
  - limit (int, optional, default=5): maximum matches to return

### notes__get_note_chunks_by_ids
Fetch specific note chunks by chunk ID.
params:
  - chunk_ids (list[str], required): note chunk IDs to fetch

### notes__read_note
Read a note's content and metadata by note ID.
params:
  - note_id (int, required): note ID

### notes__edit_note
Find-and-replace text in a note by note ID.
params:
  - note_id (int, required): note ID
  - old_text (str, required): exact text to find
  - new_text (str, required): replacement text
  - occurrence (int, optional, default=1): occurrence to replace; use -1 for all
  - suggest_mode (bool, optional, default=true): write suggestion markup instead of applying directly

### notes__append_note
Append HTML content to the end of an existing note.
params:
  - note_id (int, required): note ID
  - content (str, required): HTML content to append

### notes__delete_note
Soft-delete a note from the space by note ID.
params:
  - note_id (int, required): note ID

## HTML Format

Note content is HTML. Use semantic tags:
- Structure: `<h1>`-`<h4>`, `<p>`, `<blockquote>`, `<hr>`
- Lists: `<ul>/<ol>` with `<li>`, `<ul data-type="taskList">` for checklists
- Inline: `<strong>`, `<em>`, `<s>`, `<code>`, `<mark>`
- Code blocks: `<pre><code>...</code></pre>`
- Tables: `<table>`, `<tr>`, `<td>`, `<th>`
- Links: `<a href="...">`

## Examples

run(tool="notes__get_notes_list", params={})
run(tool="notes__search_notes_text", params={"query": "experiment results"})
run(tool="notes__search_notes_semantic", params={"query": "ideas about sparse attention"})
run(tool="notes__read_note", params={"note_id": 42})
