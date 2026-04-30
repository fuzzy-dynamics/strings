# OpenReview

## Meta
trigger: look up peer reviews or acceptance decisions for conference papers
not_for: general paper search (use arxiv or openalex), paper content (use search)
cost: low
tools: openreview__search_paper, openreview__get_reviews, openreview__get_decision

## When to Use
- User wants to see peer reviews of a paper
- Need to check if a paper was accepted/rejected and why
- Want the meta-review or final decision
- NOT for searching papers by topic (use arxiv/openalex)

## Functions

### openreview__search_paper
Search for a paper on OpenReview by title.
params:
  - title (str, required): paper title

### openreview__get_reviews
Get peer reviews for a paper.
params:
  - forum_id (str, required): OpenReview forum ID (from search results)

### openreview__get_decision
Get the final decision and meta-review.
params:
  - forum_id (str, required): OpenReview forum ID

## Examples

run(tool="openreview__search_paper", params={"title": "Attention Is All You Need"})
run(tool="openreview__get_reviews", params={"forum_id": "abc123"})
run(tool="openreview__get_decision", params={"forum_id": "abc123"})
