#!/usr/bin/env python3
"""Generate a human-readable open-problem research report from Witsoc ledgers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


from witcore import records  # noqa: E402  -- shared substrate, was a local copy

def bullet(lines: list[str], text: str) -> None:
    lines.append(f"- {text}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    run = args.run_dir
    summary = load(run / "lovasz_summary.json", {})
    lemmas = records(run / "actual_lemma_queue.json")
    disproof = records(run / "disproof_first.json")
    products = records(run / "product_selection.json")
    theorem_audit = records(run / "theorem_precondition_audit.json")
    mutations = records(run / "mutation_ledger.json")
    workers = records(run / "worker_results.json")
    artifacts = load(run / "witsoc_artifacts.json", {}).get("artifacts", [])
    if not artifacts:
        artifacts = load(Path.cwd() / "witsoc_artifacts.json", {}).get("artifacts", [])
    handoff = load(run / "handoff.json", {})
    if not handoff:
        handoff = load(run.parent / "handoff.json", {})
    citations = [c for c in handoff.get("source_citations", []) if isinstance(c, dict)]

    lines: list[str] = []
    lines.append("# Witsoc Open-Problem Report")
    lines.append("")
    lines.append("## Status")
    lines.append("")
    bullet(lines, f"Run directory: `{run.resolve()}`")
    if summary:
        bullet(lines, f"DAG nodes: {summary.get('dag_nodes', 0)}")
        bullet(lines, f"Worker results: {summary.get('worker_results', 0)}")
        bullet(lines, f"Status counts: `{summary.get('status_counts', {})}`")
    lines.append("")

    lines.append("## Key Sources")
    lines.append("")
    # Load-bearing sources only: pointer/informal entries stay in the handoff ledger.
    key_sources = [c for c in citations if c.get("source_type") in ("primary", "survey", "preprint", "formal_library", "maintained_page")]
    if not key_sources:
        bullet(lines, "No checked sources recorded; status claims are unconfirmed." if not citations else "Only pointer/informal sources recorded; status claims are unconfirmed.")
    for citation in key_sources[:8]:
        bullet(lines, f"{citation.get('source', '(missing source)')} ({citation.get('source_type', 'unknown')}): {citation.get('claim_supported', '(claim not recorded)')}")
    if len(key_sources) > 8:
        bullet(lines, f"{len(key_sources) - 8} further sources recorded in `handoff.json`.")
    lines.append("")

    lines.append("## Actual Barrier Lemmas")
    lines.append("")
    if not lemmas:
        bullet(lines, "No actual barrier lemmas recorded.")
    for lemma in lemmas:
        bullet(lines, str(lemma.get("statement") or lemma.get("lemma") or lemma))
        if lemma.get("why_it_matters"):
            lines.append(f"  - Why it matters: {lemma['why_it_matters']}")
        if lemma.get("next_mutation"):
            lines.append(f"  - Next mutation: {lemma['next_mutation']}")
    lines.append("")

    lines.append("## Disproof-First Pressure")
    lines.append("")
    if not disproof:
        bullet(lines, "No disproof-first records.")
    for item in disproof:
        bullet(lines, f"{item.get('pass_type', 'pass')}: {item.get('outcome', 'unknown')} on {item.get('search_domain', 'unspecified domain')}")
        if item.get("next_search"):
            lines.append(f"  - Next search: {item['next_search']}")
    lines.append("")

    lines.append("## Theorem-Precondition Audit")
    lines.append("")
    if not theorem_audit:
        bullet(lines, "No theorem audit records.")
    for item in theorem_audit:
        bullet(lines, f"{item.get('candidate_theorem', 'unnamed theorem')}: decision `{item.get('use_decision', 'unknown')}`")
        missing = item.get("missing_preconditions")
        if missing:
            lines.append(f"  - Missing preconditions: {missing}")
    lines.append("")

    lines.append("## Selected Research Products")
    lines.append("")
    selected = [p for p in products if p.get("selected") is True] or products[:3]
    if not selected:
        bullet(lines, "No research product selected.")
    for product in selected:
        bullet(lines, f"{product.get('kind', 'product')}: {product.get('statement', '(missing statement)')}")
        if product.get("why_this_helps_original"):
            lines.append(f"  - Why this helps: {product['why_this_helps_original']}")
        if product.get("dependency_path_to_target"):
            lines.append(f"  - Path to target: {product['dependency_path_to_target']}")
    lines.append("")

    lines.append("## Failed Routes And Mutations")
    lines.append("")
    if not mutations:
        bullet(lines, "No mutation ledger entries.")
    for mutation in mutations[:10]:
        bullet(lines, f"{mutation.get('axis_changed', 'axis')}: {mutation.get('what_changed', '(missing change)')}")
        if mutation.get("result"):
            lines.append(f"  - Result: {mutation['result']}")
    lines.append("")

    lines.append("## Worker Outcomes")
    lines.append("")
    if not workers:
        bullet(lines, "No worker results.")
    for worker in workers[:10]:
        bullet(lines, f"{worker.get('worker_id', 'worker')} [{worker.get('status', 'UNKNOWN')}]: {worker.get('claim', '')}")
    lines.append("")

    lines.append("## Artifacts")
    lines.append("")
    artifact_records = [a for a in artifacts if isinstance(a, dict)]
    if not artifact_records:
        bullet(lines, "No artifacts registered.")
    for artifact in artifact_records[:20]:
        bullet(lines, f"{artifact.get('type', 'file')}: `{artifact.get('path')}` status={artifact.get('status', '')}")
    lines.append("")

    lines.append("## Next Exact Lemmas")
    lines.append("")
    next_items = [lemma.get("next_mutation") or lemma.get("next_exact_lemma") for lemma in lemmas if lemma.get("next_mutation") or lemma.get("next_exact_lemma")]
    if not next_items:
        bullet(lines, "No next exact lemma recorded.")
    for item in next_items[:3]:
        bullet(lines, str(item))
    lines.append("")

    out = args.out or (run / "open_problem_report.md")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
