# Search Documents

## Meta
trigger: find information in indexed papers, code, or documents
not_for: adding, listing, renaming, or deleting sources (use source), searching for papers on ArXiv/OpenAlex (use arxiv or openalex), browsing world model files (use filesystem)
cost: low
tools: search__search_documents, search__get_source_content, search__get_source_file

## When to Use
- User asks about content of a paper or document already in their workspace
- Need to find specific passages, code, or sections in indexed sources
- NOT for discovering new papers (use arxiv/openalex)

## Functions

### search__search_documents
Semantic search across indexed documents in the workspace.
params:
  - query (str, required): search query
  - top_k (int, optional, default=5): number of results (max 20)
  - source_id (str, optional): limit search to a specific source
  - scope (str, optional, default="USER"): `USER` or `AGENT`

### search__get_source_content
Fetch content from an indexed source by line range.
params:
  - source_id (str, required): source ID (from search results)
  - start_line (int, optional, default=1): start line (1-indexed)
  - end_line (int, optional, default=-1): end line (-1 for end of document)
  - scope (str, optional, default="USER"): `USER` or `AGENT`

### search__get_source_file
Fetch a stored source file by source ID and extension.
params:
  - source_id (str, required): source ID
  - extension (str, optional, default="pdf"): requested file extension, with or without a leading dot
  - scope (str, optional, default="USER"): `USER` or `AGENT`

## Examples

run(tool="search__search_documents", params={"query": "attention mechanism", "top_k": 5})
run(tool="search__get_source_content", params={"source_id": "abc123", "start_line": 50, "end_line": 100})
run(tool="search__get_source_file", params={"source_id": "abc123", "extension": "pdf"})
