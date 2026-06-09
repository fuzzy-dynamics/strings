#!/usr/bin/env python3
"""Test Phase C: lovasz_prover_dispatch.py dispatches the Prover per DAG node and
emits schema-conforming, honesty-gated worker-result packets.

Uses the real Lean toolchain when present (a formalizable node should discharge
to CHECKED); skips the live-prover assertion gracefully if Lean is absent.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA = json.loads((SCRIPT_DIR / ".." / "references" / "schemas" / "lovasz-worker-result.schema.json").read_text())
REQUIRED = SCHEMA["required"]
STATUS_ENUM = set(SCHEMA["properties"]["status"]["enum"])
WORKER_ENUM = set(SCHEMA["properties"]["worker_type"]["enum"])
FAILURE_ENUM = set(SCHEMA["properties"]["failure_class"]["enum"])

HAVE_LEAN = shutil.which("lean") is not None


def main() -> int:
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="witsoc_phasec_"))
    try:
        dag = [
            {"node_id": "n-formalizable", "statement": "n plus zero equals n",
             "lean_statement": "∀ n : Nat, n + 0 = n", "target_hash": "a" * 64},
            {"node_id": "n-prose-only", "statement": "some unformalized barrier lemma",
             "target_hash": "b" * 64},
        ]
        (tmp / "proof_dependency_dag.json").write_text(json.dumps(dag), encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "lovasz_prover_dispatch.py"), str(tmp),
             "--session-id", "test"],
            capture_output=True, text=True, timeout=300, check=False)
        if proc.returncode != 0:
            failures.append(f"dispatch exited {proc.returncode}: {proc.stderr[:400]}")

        results = json.loads((tmp / "worker_results.json").read_text())
        if not isinstance(results, list) or len(results) != 2:
            failures.append(f"expected 2 worker results, got {results!r}")

        by_id = {r.get("node_id"): r for r in results if isinstance(r, dict)}

        # Schema conformance for every packet.
        for r in results:
            for k in REQUIRED:
                if k not in r:
                    failures.append(f"{r.get('node_id')}: missing required field {k!r}")
            if r.get("status") not in STATUS_ENUM:
                failures.append(f"{r.get('node_id')}: bad status {r.get('status')!r}")
            if r.get("worker_type") not in WORKER_ENUM:
                failures.append(f"{r.get('node_id')}: bad worker_type {r.get('worker_type')!r}")
            if r.get("failure_class") not in FAILURE_ENUM:
                failures.append(f"{r.get('node_id')}: bad failure_class {r.get('failure_class')!r}")
            if not (isinstance(r.get("evidence"), list) and r["evidence"]):
                failures.append(f"{r.get('node_id')}: evidence must be a non-empty list")

        # The prose-only node must be honestly OPEN (no formalized goal => not progress).
        prose = by_id.get("n-prose-only", {})
        if prose.get("status") != "OPEN":
            failures.append(f"prose-only node should be OPEN, got {prose.get('status')!r}")
        if prose.get("failure_class") != "theorem_precondition_gap":
            failures.append(f"prose-only node failure_class should be theorem_precondition_gap, got {prose.get('failure_class')!r}")

        # The formalizable node: with real Lean it must reach CHECKED (kernel proof,
        # SafeVerify pending) and must NOT over-claim VERIFIED_LEAN here.
        form = by_id.get("n-formalizable", {})
        if HAVE_LEAN:
            if form.get("status") != "CHECKED":
                failures.append(f"formalizable node with Lean should be CHECKED, got {form.get('status')!r} (legal={form.get('prover_legal_status')})")
            if form.get("status") == "VERIFIED_LEAN":
                failures.append("formalizable node must NOT reach VERIFIED_LEAN without SafeVerify")
        else:
            if form.get("status") not in {"GAP", "OPEN", "FAILED_ATTEMPT", "CHECKED"}:
                failures.append(f"formalizable node without Lean: unexpected status {form.get('status')!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print(f"PHASE_C_TESTS_PASS (lean={'yes' if HAVE_LEAN else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
