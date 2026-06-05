#!/usr/bin/env python3
"""Quality lint for WIT proof artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


STEP_RE = re.compile(r"^\s*\[(?P<label>[\d.]+)\]\s+(?P<kw>HAVE|SHOW|ASSUME|LET|CONSIDER|SUFFICES|CASE|CITE|GAP)\b(?P<body>.*)$")
BY_RE = re.compile(r"^\s*BY\s+(?P<by>.*)$")
CLAIM_RE = re.compile(r"^\s*(THEOREM|LEMMA|PROPOSITION|COROLLARY|CONJECTURE)\s+(?P<name>[A-Za-z_][\w]*)")
PROOF_RE = re.compile(r"^\s*PROOF\s+OF\s+(?P<name>[A-Za-z_][\w]*)")
REF_RE = re.compile(r"\[(\d+(?:\.\d+)*)\]")
VAGUE_RE = re.compile(r"\b(obvious|clearly|trivial|straightforward|standard|well-known|classical)\b", re.I)


def parse(path: Path) -> tuple[list[dict], list[str], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    claims: list[str] = []
    proofs: list[str] = []
    steps: list[dict] = []
    current = None
    for idx, line in enumerate(lines, start=1):
        if m := CLAIM_RE.match(line):
            claims.append(m.group("name"))
        if m := PROOF_RE.match(line):
            proofs.append(m.group("name"))
        if m := STEP_RE.match(line):
            current = {
                "label": m.group("label"),
                "keyword": m.group("kw"),
                "body": m.group("body").strip(),
                "by": "",
                "line": idx,
            }
            steps.append(current)
            continue
        if current and (m := BY_RE.match(line)):
            current["by"] = (current["by"] + " " + m.group("by").strip()).strip()
    return steps, claims, proofs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wit", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    steps, claims, proofs = parse(args.wit)
    findings: list[dict] = []
    labels = {s["label"] for s in steps}
    cited: set[str] = set()

    for step in steps:
        label = step["label"]
        by = step.get("by") or ""
        body = step.get("body") or ""
        if step["keyword"] == "GAP":
            findings.append({"severity": "error", "kind": "gap", "line": step["line"], "label": label, "message": "GAP step remains"})
        if step["keyword"] == "CITE" and not by:
            findings.append({"severity": "warning", "kind": "unsupported_cite", "line": step["line"], "label": label, "message": "CITE step lacks BY/source details"})
        if by and VAGUE_RE.search(by):
            findings.append({"severity": "warning", "kind": "vague_by", "line": step["line"], "label": label, "message": "BY justification is vague"})
        if by.strip() in {"", ".", "definition", "algebra"} and step["keyword"] not in {"ASSUME", "LET", "GAP"}:
            findings.append({"severity": "warning", "kind": "thin_by", "line": step["line"], "label": label, "message": "BY justification may be too thin"})
        refs = REF_RE.findall(by)
        for ref in refs:
            cited.add(ref)
            if ref == label:
                findings.append({"severity": "error", "kind": "self_reference", "line": step["line"], "label": label, "message": "step cites itself"})
            if ref not in labels:
                findings.append({"severity": "error", "kind": "missing_reference", "line": step["line"], "label": label, "message": f"cites missing step [{ref}]"})
        if re.search(r"\b(sorry|admit|todo|fixme)\b", body + " " + by, re.I):
            findings.append({"severity": "error", "kind": "placeholder", "line": step["line"], "label": label, "message": "placeholder proof text remains"})

    for step in steps:
        if step["keyword"] in {"HAVE", "CITE"} and step["label"] not in cited:
            findings.append({"severity": "info", "kind": "unused_step", "line": step["line"], "label": step["label"], "message": "step is not cited later"})
    for claim in claims:
        if claim not in proofs:
            findings.append({"severity": "warning", "kind": "claim_without_proof", "line": 0, "label": "", "message": f"claim {claim!r} has no PROOF OF block"})

    result = {
        "ok": not any(f["severity"] == "error" for f in findings),
        "file": str(args.wit),
        "findings": findings,
        "counts": {
            "errors": sum(1 for f in findings if f["severity"] == "error"),
            "warnings": sum(1 for f in findings if f["severity"] == "warning"),
            "info": sum(1 for f in findings if f["severity"] == "info"),
        },
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            print(f"{f['severity'].upper()}:{f['line']} [{f['label']}] {f['kind']}: {f['message']}")
        print("WIT_QUALITY_PASS" if result["ok"] else "WIT_QUALITY_FAIL")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
