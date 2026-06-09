#!/usr/bin/env python3
"""Phase 5: faithfulness-gated acceptance (deterministic mock back-translators).

The killer demonstration: the FAITHFUL `even ↔ ∃k` and the WRONG-BUT-TRUE `even → ∃k`
are BOTH valid theorems the kernel verifies — yet the pipeline accepts the first as
VERIFIED_LEAN_FAITHFUL and flags the second as FAITHFULNESS_GAP. Faithfulness catches
what the kernel cannot, so nothing is emitted VERIFIED while proving the wrong thing."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import faithfulness_pipeline as fp
import witcore

INFORMAL = ("A natural number n is even if and only if there exists a natural number k "
            "with n equals 2 times k")
FAITHFUL = "∀ n : Nat, (n % 2 = 0) ↔ (∃ k : Nat, n = 2 * k)"
DISTRACTOR = "∀ n : Nat, (n % 2 = 0) → (∃ k : Nat, n = 2 * k)"   # wrong-but-true (drops the reverse)

TR1 = r'''import json,sys,re
d=json.load(sys.stdin); s=d.get("lean","")
for a,b in [("↔"," if and only if "),("→"," implies "),("∃"," there exists "),("∀"," for all "),
            ("%"," mod "),("="," equals "),("*"," times ")]:
    s=s.replace(a,b)
print(json.dumps({"nl": re.sub(r"[^a-zA-Z0-9 ]"," ",s)}))
'''
TR2 = r'''import json,sys,re
d=json.load(sys.stdin); s=d.get("lean","")
for a,b in [("↔"," iff if and only if equivalent "),("→"," implies only if "),
            ("∃"," exists there is some "),("∀"," every for all "),("%"," modulo mod "),
            ("="," is equals "),("*"," product times ")]:
    s=s.replace(a,b)
print(json.dumps({"nl": re.sub(r"[^a-zA-Z0-9 ]"," ",s)}))
'''


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        t1 = Path(td) / "tr1.py"; t1.write_text(TR1, encoding="utf-8")
        t2 = Path(td) / "tr2.py"; t2.write_text(TR2, encoding="utf-8")
        translators = [f"cmd:{sys.executable} {t1}", f"cmd:{sys.executable} {t2}"]

        # 1. Faithful + kernel-verified => VERIFIED_LEAN_FAITHFUL.
        f = fp.accept(INFORMAL, FAITHFUL, translators, kernel_verified=True)
        if f["final_status"] != "VERIFIED_LEAN_FAITHFUL" or not f["emits_verified"]:
            failures.append(f"faithful+kernel should emit VERIFIED_LEAN_FAITHFUL, got {f['final_status']}")

        # 2. THE POINT: the distractor is ALSO kernel-verified (a true theorem) but the
        #    pipeline flags FAITHFULNESS_GAP and refuses to emit VERIFIED.
        d = fp.accept(INFORMAL, DISTRACTOR, translators, kernel_verified=True)
        if d["final_status"] != "FAITHFULNESS_GAP":
            failures.append(f"wrong-but-true distractor must be FAITHFULNESS_GAP, got {d['final_status']}")
        if d["emits_verified"]:
            failures.append("a kernel proof of a non-faithful statement must NOT emit VERIFIED")

        # 3. Fewer than 2 independent translators => UNCHECKED => at most CHECKED_NEEDS_HUMAN.
        u = fp.accept(INFORMAL, FAITHFUL, translators[:1], kernel_verified=True)
        if u["final_status"] != "CHECKED_NEEDS_HUMAN" or u["emits_verified"]:
            failures.append(f"<2 translators must be CHECKED_NEEDS_HUMAN (never VERIFIED), got {u['final_status']}")

        # 4. Not kernel-verified => OPEN regardless of faithfulness.
        o = fp.accept(INFORMAL, FAITHFUL, translators, kernel_verified=False)
        if o["final_status"] != "OPEN" or o["emits_verified"]:
            failures.append(f"without a kernel proof the status must be OPEN, got {o['final_status']}")

    # 5. Confirm the premise of the demo: BOTH formalizations are genuinely true theorems
    #    (so the kernel cannot distinguish them — only faithfulness can). Needs Lean.
    proofs = {
        FAITHFUL: "by intro n; refine ⟨fun h => ⟨n / 2, by omega⟩, ?_⟩; rintro ⟨k, rfl⟩; omega",
        DISTRACTOR: "by intro n h; exact ⟨n / 2, by omega⟩",
    }
    if witcore.lean_verify_cached("#check @Nat.mul_comm\n", None).get("checked"):
        for label, lean in (("faithful", FAITHFUL), ("distractor", DISTRACTOR)):
            src = f"theorem t : {lean} := {proofs[lean]}\n"
            if not witcore.lean_verify_cached(src, None).get("verified"):
                failures.append(f"the {label} formalization should be a true theorem (kernel) — demo premise")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("FAITHFULNESS_PIPELINE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
