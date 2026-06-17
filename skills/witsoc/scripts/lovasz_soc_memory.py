#!/usr/bin/env python3
"""Maintain compact Lovasz `.soc` memory for failed approaches and progress."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SECTION_NAMES = ("CURRENT", "INSIGHTS", "PROGRESS", "FAILED_APPROACHES", "QUEUE")


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def sha_short(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def target_text(run: Path) -> str:
    manifest = load_json(run / "lovasz_run.json", {})
    if manifest.get("source_target_text"):
        return str(manifest["source_target_text"])
    handoff = load_json(run / "handoff_v1.json", {})
    for key in ("frozen_target", "target", "statement"):
        if handoff.get(key):
            return str(handoff[key])
    return "UNSPECIFIED_TARGET"


def default_soc(run: Path) -> str:
    target = target_text(run)
    return f"""-- Status: RUNNING

GOAL: {target}

CURRENT:
  Selected product: unset
  Active barrier: unset
  Active move: unset

INSIGHTS:

PROGRESS:
  - problems_since_last_progress: 0
  - total_verified: 0
  - total_partial: 0
  - total_failed_attempts: 0

FAILED_APPROACHES:

QUEUE:
  - source_triage: pending
  - barrier_map: pending
  - first_experiment: pending
"""


def ensure_soc(run: Path) -> Path:
    path = run / "lovasz.soc"
    if not path.exists():
        path.write_text(default_soc(run), encoding="utf-8")
    return path


def section_bounds(lines: list[str], section: str) -> tuple[int, int]:
    start = -1
    pattern = re.compile(rf"^{re.escape(section)}:\s*$")
    for i, line in enumerate(lines):
        if pattern.match(line):
            start = i
            break
    if start < 0:
        lines.append("")
        lines.append(f"{section}:")
        return len(lines) - 1, len(lines)
    end = len(lines)
    header = re.compile(r"^[A-Z_]+:\s*$")
    for j in range(start + 1, len(lines)):
        if header.match(lines[j]) and lines[j].rstrip(":") in SECTION_NAMES:
            end = j
            break
    return start, end


def insert_section_item(path: Path, section: str, item_lines: list[str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = section_bounds(lines, section)
    insert_at = end
    if insert_at > start + 1 and lines[insert_at - 1].strip():
        item_lines = ["", *item_lines]
    lines[insert_at:insert_at] = item_lines
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_failed_entries(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if re.match(r"^[A-Z_]+:\s*$", line):
            if current:
                entries.append(current)
                current = None
            continue
        if line.startswith("- id:"):
            if current:
                entries.append(current)
            current = {"id": line.split(":", 1)[1].strip()}
            continue
        if current is None:
            continue
        match = re.match(r"([a-zA-Z0-9_ -]+):\s*(.*)$", line)
        if match:
            key = match.group(1).strip().replace("-", "_").replace(" ", "_")
            current[key] = match.group(2).strip()
    if current:
        entries.append(current)
    return entries


def matching_failures(path: Path, statement: str, method: str) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    failures = parse_failed_entries(text)
    statement_tokens = {token for token in re.findall(r"[a-zA-Z0-9_]+", statement.lower()) if len(token) > 4}
    method_l = method.lower()
    matches = []
    for failure in failures:
        failed_method = str(failure.get("method") or "").lower()
        failed_statement = str(failure.get("statement") or "").lower()
        method_matches = bool(method_l and method_l == failed_method)
        overlap = sum(1 for token in statement_tokens if token in failed_statement)
        required_overlap = 2 if len(statement_tokens) < 8 else 3
        statement_matches = bool(statement_tokens and overlap >= required_overlap)
        if method_l and statement_tokens and method_matches and statement_matches:
            matches.append(failure)
        elif method_l and not statement_tokens and method_matches:
            matches.append(failure)
        elif statement_tokens and not method_l and statement_matches:
            matches.append(failure)
    return matches


def append_failure(args: argparse.Namespace) -> dict[str, Any]:
    path = ensure_soc(args.run_dir)
    item_id = args.id or f"approach_{sha_short(args.method + args.statement)}"
    lines = [
        f"  - id: {item_id}",
        f"    method: {args.method}",
        "    status: rejected",
        f"    statement: {args.statement}",
        f"    blocker: {args.blocker}",
        f"    evidence: {args.evidence}",
        f"    do_not_repeat: {args.do_not_repeat}",
        "    next_methods:",
    ]
    for method in args.next_method or ["change method family"]:
        lines.append(f"      - {method}")
    insert_section_item(path, "FAILED_APPROACHES", lines)
    return {"soc": str(path), "added": item_id}


def append_insight(args: argparse.Namespace) -> dict[str, Any]:
    path = ensure_soc(args.run_dir)
    evidence = f" SEE {args.evidence}" if args.evidence else ""
    insert_section_item(path, "INSIGHTS", [f"  - {args.text}.{evidence}"])
    return {"soc": str(path), "added": "insight"}


def query(args: argparse.Namespace) -> dict[str, Any]:
    path = ensure_soc(args.run_dir)
    failures = matching_failures(path, args.statement or "", args.method or "")
    return {
        "soc": str(path),
        "matching_failed_approaches": failures,
        "repeat_risk": "HIGH" if failures else "LOW",
        "guidance": "change method family or record a one-axis mutation before retrying" if failures else "no matching failed approach found",
    }


def import_failure_jsonl(args: argparse.Namespace) -> dict[str, Any]:
    path = ensure_soc(args.run_dir)
    source = args.run_dir / "failure_memory.jsonl"
    count = 0
    if source.exists():
        for line in source.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            ns = argparse.Namespace(
                run_dir=args.run_dir,
                id=item.get("id") or f"failure_{count + 1}",
                method=item.get("method_family") or "unknown_method",
                statement=item.get("statement") or item.get("statement_hash") or "unknown_statement",
                blocker=item.get("blocker_or_counterexample") or item.get("why_failed") or "unknown_blocker",
                evidence=item.get("evidence") or str(source),
                do_not_repeat=item.get("retry_condition") or "same method with no new axis",
                next_method=[item.get("next_method") or "try a distinct method family"],
            )
            append_failure(ns)
            count += 1
    return {"soc": str(path), "imported": count}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("run_dir", type=Path)

    p_failure = sub.add_parser("add-failure")
    p_failure.add_argument("run_dir", type=Path)
    p_failure.add_argument("--id", default="")
    p_failure.add_argument("--method", required=True)
    p_failure.add_argument("--statement", required=True)
    p_failure.add_argument("--blocker", required=True)
    p_failure.add_argument("--evidence", default="unrecorded")
    p_failure.add_argument("--do-not-repeat", default="same method with no new evidence or one-axis mutation")
    p_failure.add_argument("--next-method", action="append", default=[])

    p_insight = sub.add_parser("add-insight")
    p_insight.add_argument("run_dir", type=Path)
    p_insight.add_argument("--text", required=True)
    p_insight.add_argument("--evidence", default="")

    p_query = sub.add_parser("query")
    p_query.add_argument("run_dir", type=Path)
    p_query.add_argument("--statement", default="")
    p_query.add_argument("--method", default="")

    p_import = sub.add_parser("import-failure-jsonl")
    p_import.add_argument("run_dir", type=Path)

    args = parser.parse_args()
    if args.cmd == "init":
        result = {"soc": str(ensure_soc(args.run_dir)), "status": "initialized"}
    elif args.cmd == "add-failure":
        result = append_failure(args)
    elif args.cmd == "add-insight":
        result = append_insight(args)
    elif args.cmd == "query":
        result = query(args)
    elif args.cmd == "import-failure-jsonl":
        result = import_failure_jsonl(args)
    else:
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
