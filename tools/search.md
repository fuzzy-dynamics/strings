# Search Documents

## Meta
trigger: find information in indexed papers, code, or documents
not_for: searching for papers on ArXiv/OpenAlex (use arxiv or openalex tools), browsing world model files (use filesystem)
cost: low
tools: search__search_documents, search__get_source_content, search__get_document_structure

## When to Use
- User asks about content of a paper or document already in their workspace
- Need to find specific passages, code, or sections in indexed sources
- Want to understand the structure of an indexed document
- NOT for discovering new papers (use arxiv/openalex)

## Functions

### search__search_documents
Semantic search across indexed documents in the workspace.
params:
  - query (str, required): search query
  - top_k (int, optional, default=2): number of results (max 20)
  - source_id (str, optional): limit search to a specific source

### search__get_source_content
Fetch content from an indexed source by line range.
params:
  - source_id (str, required): source ID (from search results)
  - start_line (int, optional, default=1): start line (1-indexed)
  - end_line (int, optional, default=-1): end line (-1 for end of document)

### search__get_document_structure
Get table of contents / section structure of a source.
params:
  - source_id (str, required): source ID

## Examples

run(tool="search__search_documents", params={"query": "attention mechanism", "top_k": 5})
run(tool="search__get_document_structure", params={"source_id": "abc123"})
run(tool="search__get_source_content", params={"source_id": "abc123", "start_line": 50, "end_line": 100})
