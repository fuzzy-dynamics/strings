# OpenAlex

## Meta
trigger: search academic works or fetch OpenAlex paper metadata by OpenAlex ID
not_for: downloading paper PDFs (use arxiv), peer reviews (use openreview)
cost: low
tools: openalex__search_papers, openalex__get_paper_by_openalex_id

## When to Use
- User wants to search broad academic literature
- User has an OpenAlex ID and needs paper metadata
- NOT for downloading/indexing papers (use arxiv)

## Functions

### openalex__search_papers
Semantic search for papers.
params:
  - query (str, required): search query
  - limit (int, optional, default=5): max results (max 20)

### openalex__get_paper_by_openalex_id
Get paper metadata by OpenAlex ID.
params:
  - openalex_id (str, required): OpenAlex ID (e.g. "W2194775991")

## Examples

run(tool="openalex__search_papers", params={"query": "graph neural networks"})
run(tool="openalex__get_paper_by_openalex_id", params={"openalex_id": "W2194775991"})
