# Goal Cache

Use cached subgoals, tactics, or WIT proof snippets only when their context matches.

Cache entry:

```json
{
  "goal": "normalized target",
  "normalized_context": {
    "domains": [],
    "hypotheses": [],
    "definitions": [],
    "imports": []
  },
  "successful_step": "tactic/proof step/WIT label",
  "required_premises": [],
  "source_sketch_id": "sketch_1",
  "failure_count": 0,
  "success_count": 1
}
```

Rules:

- Search prior solved goals before inventing a new tactic, helper lemma, or WIT step.
- Reuse only when hypotheses, domains, coercions, definitions, imports, and target shape match.
- If a cached route fails, record the failure class and do not retry it unchanged.
- Successful cache entries are evidence for verifier-friendliness, not semantic verification.
