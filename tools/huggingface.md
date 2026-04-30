# HuggingFace

## Meta
trigger: find ML models, datasets, or implementations of papers
not_for: academic paper search (use arxiv/openalex), paper reviews (use openreview)
cost: low
tools: huggingface__search_models, huggingface__search_datasets, huggingface__get_model, huggingface__get_dataset, huggingface__list_popular_models, huggingface__list_popular_datasets, huggingface__find_models_for_paper, huggingface__find_datasets_for_paper

## When to Use
- User wants to find a model for a specific task (text-generation, image-classification, etc.)
- Looking for datasets for training or evaluation
- Need details about a specific model or dataset
- Want to find implementations of a paper
- Exploring what's popular in a task category

## Functions

### huggingface__search_models
Full-text search over model cards.
params:
  - query (str, required): search query
  - limit (int, optional, default=10): max results (max 100)

### huggingface__search_datasets
Full-text search over dataset cards.
params:
  - query (str, required): search query
  - limit (int, optional, default=10): max results (max 100)

### huggingface__get_model
Get detailed info about a specific model.
params:
  - repo_id (str, required): model repo ID (e.g. "google-bert/bert-base-uncased")

### huggingface__get_dataset
Get detailed info about a specific dataset.
params:
  - repo_id (str, required): dataset repo ID (e.g. "rajpurkar/squad")

### huggingface__list_popular_models
List popular models sorted by downloads.
params:
  - task (str, optional): filter by pipeline tag (e.g. "text-generation", "image-classification")
  - author (str, optional): filter by author/organization
  - limit (int, optional, default=10): max results

### huggingface__list_popular_datasets
List popular datasets sorted by downloads.
params:
  - task (str, optional): filter by task category
  - author (str, optional): filter by author/organization
  - limit (int, optional, default=10): max results

### huggingface__find_models_for_paper
Find models that implement or cite an ArXiv paper.
params:
  - arxiv_id (str, required): ArXiv ID (e.g. "1706.03762")
  - limit (int, optional, default=20): max results (max 100)

### huggingface__find_datasets_for_paper
Find datasets associated with an ArXiv paper.
params:
  - arxiv_id (str, required): ArXiv ID (e.g. "1706.03762")
  - limit (int, optional, default=20): max results (max 100)

## Examples

run(tool="huggingface__search_models", params={"query": "code generation"})
run(tool="huggingface__list_popular_models", params={"task": "text-generation", "limit": 5})
run(tool="huggingface__get_model", params={"repo_id": "meta-llama/Llama-2-7b-hf"})
run(tool="huggingface__find_models_for_paper", params={"arxiv_id": "1706.03762"})
run(tool="huggingface__search_datasets", params={"query": "instruction tuning"})
