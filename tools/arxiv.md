# ArXiv

## Meta
trigger: search or download academic papers from ArXiv
not_for: papers already indexed in workspace (use search tool), citation graphs (use openalex)
cost: medium (search is fast, download_and_index is slow)
tools: arxiv__search_papers, arxiv__get_paper, arxiv__search_by_author, arxiv__download_and_index_paper

## When to Use
- User wants to find papers on a topic
- Need details about a specific ArXiv paper
- Want to find papers by a particular author
- Need to download and index a paper for deeper reading
- NOT for citation/reference graphs (use openalex)
- NOT for peer reviews (use openreview)

## Functions

### arxiv__search_papers
Semantic search over ArXiv titles and abstracts.
params:
  - query (str, required): search query
  - top_k (int, optional, default=10): number of results (max 50)
  - categories (list[str], optional): ArXiv categories to filter (e.g. ["cs.LG", "cs.AI"])

### arxiv__get_paper
Get full details for a specific paper.
params:
  - arxiv_id (str, required): ArXiv ID (e.g. "2301.07041")

### arxiv__search_by_author
Find papers by author name (partial match supported).
params:
  - author_name (str, required): author name
  - top_k (int, optional, default=20): number of results (max 100)

### arxiv__download_and_index_paper
Download a paper PDF and add it to the workspace's searchable index. After indexing, use the search tool to query its contents.
params:
  - arxiv_id (str, required): ArXiv ID to download

## Examples

run(tool="arxiv__search_papers", params={"query": "vision transformers", "top_k": 5})
run(tool="arxiv__search_papers", params={"query": "RLHF", "categories": ["cs.LG"]})
run(tool="arxiv__get_paper", params={"arxiv_id": "2301.07041"})
run(tool="arxiv__search_by_author", params={"author_name": "Yann LeCun"})
run(tool="arxiv__download_and_index_paper", params={"arxiv_id": "2301.07041"})
