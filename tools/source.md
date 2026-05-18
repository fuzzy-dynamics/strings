# Source Documents

## Meta
trigger: add, list, rename, or delete indexed documents in the current space
not_for: searching document contents (use search), discovering papers (use arxiv or openalex)
cost: low-medium
tools: source__download_and_index_document, source__list_documents, source__rename_source, source__delete_sources

## When to Use
- User wants to add a document or webpage URL to the current space
- User asks which documents are available in the current space
- User wants to rename or remove an indexed source
- NOT for searching inside indexed documents (use search)

## Functions

### source__download_and_index_document
Download a document or webpage from a URL into the current space and index it.
params:
  - url (str, required): URL of the document to download
  - scope (str, optional, default="USER"): `USER` or `AGENT`

### source__list_documents
List all documents in the current space at the given scope.
params:
  - scope (str, optional, default="USER"): `USER` or `AGENT`

### source__rename_source
Rename a source within the current space.
params:
  - source_id (str, required): source ID to rename
  - new_name (str, required): new display name for the source

### source__delete_sources
Delete one or more sources from the current space.
params:
  - source_ids (list[str], required): source IDs to remove from the current space

## Examples

run(tool="source__download_and_index_document", params={"url": "https://example.com/paper.pdf"})
run(tool="source__list_documents", params={"scope": "USER"})
run(tool="source__rename_source", params={"source_id": "abc123", "new_name": "Paper notes"})
run(tool="source__delete_sources", params={"source_ids": ["abc123"]})
