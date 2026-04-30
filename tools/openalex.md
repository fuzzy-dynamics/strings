# OpenAlex

## Meta
trigger: search academic works, explore citations, references, or related papers
not_for: downloading paper PDFs (use arxiv), peer reviews (use openreview)
cost: low
tools: openalex__search_papers, openalex__get_paper, openalex__get_references, openalex__get_citations, openalex__find_related

## When to Use
- User wants to explore citation graphs (who cites whom)
- Need to find papers related to a known paper
- Looking up a paper by DOI
- Building a literature map around a topic
- NOT for downloading/indexing papers (use arxiv)

## Functions

### openalex__search_papers
Semantic search for papers.
params:
  - query (str, required): search query
  - limit (int, optional, default=5): max results (max 20)

### openalex__get_paper
Get paper metadata by DOI.
params:
  - doi (str, required): paper DOI (e.g. "10.1038/nature12373")

### openalex__get_references
Get papers referenced by a given paper.
params:
  - openalex_id (str, required): OpenAlex ID (e.g. "W2194775991")

### openalex__get_citations
Get papers that cite a given paper.
params:
  - openalex_id (str, required): OpenAlex ID
  - limit (int, optional, default=10): max results (max 50)

### openalex__find_related
Find semantically related papers via HNSW index.
params:
  - openalex_id (str, required): OpenAlex ID
  - limit (int, optional, default=5): max results (max 20)

## Examples

run(tool="openalex__search_papers", params={"query": "graph neural networks"})
run(tool="openalex__get_paper", params={"doi": "10.1038/nature12373"})
run(tool="openalex__get_references", params={"openalex_id": "W2194775991"})
run(tool="openalex__get_citations", params={"openalex_id": "W2194775991", "limit": 20})
run(tool="openalex__find_related", params={"openalex_id": "W2194775991"})
