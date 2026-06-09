#!/usr/bin/env python3
"""Tests for the three barrier-generator fixes:
  Fix 1 — LLM-proposed problem-specific lemmas (invention), kernel-gated.
  Fix 2 — autoformalization of prose lemmas, gated by faithfulness.
  Fix 3 — failure-memory switches to a different METHOD family, not just a bound.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import domain_barrier_lemmas as dbl


def mk(tmp: Path, name: str, body: str) -> str:
    p = tmp / name
    p.write_text(f"import sys, json\nsys.stdin.read()\n{body}\n", encoding="utf-8")
    return f"cmd:{sys.executable} {p}"


def main() -> int:
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="witsoc_bfix_"))
    try:
        # ---------- Fix 1: LLM proposer ----------
        sampler = mk(tmp, "samp.py", "print(json.dumps({'lemmas':[{'barrier_type':'clever_reduction','statement':'reduce the target to a verified special case','lean_statement':'∀ n : Nat, n + 0 = n','why':'reduction'}]}))")
        ls = dbl.generate_barrier_lemmas("some number theory target", domain="number_theory",
                                         target_hash="a" * 64, sampler=sampler)
        llm = [l for l in ls if l.get("source") == "llm"]
        if not any(l["barrier_type"] == "clever_reduction" for l in llm):
            failures.append("Fix1: model-proposed lemma not present")
        for l in llm:
            if l["status"] != "OPEN_UNFALSIFIED" or l["arena"] != "SPECULATIVE":
                failures.append("Fix1: model-proposed lemma must be OPEN_UNFALSIFIED/SPECULATIVE")
        if llm and not any(l.get("lean_statement") for l in llm):
            failures.append("Fix1: a valid model lean_statement should be kept")
        # malicious model lean with a proof token -> dropped to null, still speculative
        evil = mk(tmp, "evil.py", "print(json.dumps({'lemmas':[{'barrier_type':'sneaky','statement':'x','lean_statement':'by sorry'}]}))")
        ls_e = dbl.generate_barrier_lemmas("t", domain="number_theory", target_hash="a" * 64, sampler=evil)
        sneaky = [l for l in ls_e if l["barrier_type"] == "sneaky"]
        if sneaky and sneaky[0].get("lean_statement") is not None:
            failures.append("Fix1: a model lean with a forbidden token must be dropped to null")

        # ---------- Fix 2: autoformalization gated by faithfulness ----------
        STMT = "multiplication on naturals is commutative"
        form_mul = mk(tmp, "form.py", "print(json.dumps({'lean_statement':'∀ a b : Nat, a * b = b * a'}))")
        form_bad = mk(tmp, "formbad.py", "print(json.dumps({'lean_statement':'by sorry'}))")
        faithful = mk(tmp, "ft.py", "print(json.dumps({'nl':'for all naturals the product is commutative under multiplication'}))")
        unfaithful = mk(tmp, "uf.py", "print(json.dumps({'nl':'the weather today is sunny and warm'}))")

        lean, blk = dbl.autoformalize(STMT, form_mul, [faithful, faithful], 0.3)
        if lean is None or "a * b" not in lean:
            failures.append(f"Fix2: faithful autoformalization should be accepted, got {lean!r} ({blk})")
        lean, blk = dbl.autoformalize(STMT, form_mul, [unfaithful, unfaithful], 0.3)
        if lean is not None:
            failures.append("Fix2: faithfulness-mismatched autoformalization must be rejected")
        lean, blk = dbl.autoformalize(STMT, form_mul, [faithful], 0.3)
        if lean is not None or "back-translator" not in (blk or ""):
            failures.append("Fix2: <2 translators must be rejected (conservative)")
        lean, blk = dbl.autoformalize(STMT, form_bad, [faithful, faithful], 0.3)
        if lean is not None:
            failures.append("Fix2: a forbidden-token Lean must be rejected")
        lean, blk = dbl.autoformalize(STMT, None, [faithful, faithful], 0.3)
        if lean is not None:
            failures.append("Fix2: no formalizer -> null (never fabricate)")

        # SAFETY at generate level: a formalizer with NO translators never fabricates a lean
        ls_f = dbl.generate_barrier_lemmas("nt target", domain="number_theory", target_hash="a" * 64,
                                           formalizer=form_mul, faithfulness_translators=None)
        if any(l.get("formalized_by") for l in ls_f):
            failures.append("Fix2: without >=2 translators, no lemma may be auto-formalized")

        # ---------- Fix 3: method-family switch on failure ----------
        fm = [{"target_hash": "a" * 64, "barrier_type": "residue_class_split"}]
        ls3 = dbl.generate_barrier_lemmas("nt target", domain="number_theory", target_hash="a" * 64, failure_memory=fm)
        if any(l["barrier_type"] == "residue_class_split" and not l.get("mutated_from_failure") for l in ls3):
            failures.append("Fix3: a failed boundless method must not be re-emitted unchanged")
        switched = [l for l in ls3 if str(l.get("mutated_from_failure", "")).startswith("method_switch_from:residue_class_split")]
        if not switched:
            failures.append("Fix3: a sibling method family should be promoted as the switch target")

        # global invariant: nothing left the speculative arena
        for batch in (ls, ls_e, ls_f, ls3):
            for l in batch:
                if l["status"] != "OPEN_UNFALSIFIED" or l["arena"] != "SPECULATIVE":
                    failures.append(f"invariant: {l['barrier_type']} escaped SPECULATIVE/OPEN_UNFALSIFIED")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("BARRIER_FIXES_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
