#!/usr/bin/env python3
"""Layer 3.3: Mathlib premise-index machinery.

Checks the WIRING (no live Mathlib is on this host, so closing real Mathlib goals
cannot be measured here — that path activates only with WITSOC_MATHLIB_SRC +
WITSOC_MATHLIB_ATLAS + a Mathlib lake project):

  1. build_mathlib_atlas parses a REAL Lean source tree (a synthetic fixture stands
     in for a Mathlib checkout) into {module, imports, symbols, doc}.
  2. mathlib_context turns a goal into the IMPORT lines it needs (the missing link:
     symbols used to be offered as premises without their import).
  3. close_obligation injects those imports + symbols, and is a clean NO-OP when no
     Mathlib atlas is present (backward-compatible).
  4. validate_premises classifies citations as KNOWN/SEARCH_TARGET and degrades to
     UNCHECKED without a toolchain — never a silent pass, never a hallucinated KNOWN.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import close_obligation as co
import witcore


def run(*args: str) -> dict:
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=120, check=False)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"_stdout": r.stdout, "_stderr": r.stderr, "_rc": r.returncode}


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)

        # 1. Parse a synthetic "Mathlib" source tree (exercises the real --mathlib-src
        #    path). As with a real checkout, --mathlib-src is the dir CONTAINING the
        #    library, so modules are named `MiniMathlib.<...>` relative to that root.
        root = tdp / "src"
        pkg = root / "MiniMathlib"
        (pkg / "NumberTheory").mkdir(parents=True)
        (pkg / "NumberTheory" / "Divisors.lean").write_text(
            "import MiniMathlib.Data.Finset\n/-- divisors and sigma -/\n"
            "def Nat.divisors (n : Nat) : List Nat := []\ntheorem Nat.sigma_eq : True := trivial\n",
            encoding="utf-8")
        (pkg / "Data").mkdir(parents=True)
        (pkg / "Data" / "Finset.lean").write_text(
            "/-- finite sets -/\ndef Finset := Unit\n", encoding="utf-8")
        atlas_path = tdp / "mathlib_atlas.json"
        built = run(str(SCRIPT_DIR / "build_mathlib_atlas.py"), "--mathlib-src", str(root),
                    "--out", str(atlas_path))
        if built.get("source", "").split(":")[0] != "parsed":
            failures.append(f"build_mathlib_atlas should report a parsed source, got {built.get('source')}")
        atlas_doc = witcore.load_json(atlas_path, {})
        mods = {n["module"] for n in atlas_doc.get("nodes", [])}
        if "MiniMathlib.NumberTheory.Divisors" not in mods:
            failures.append(f"parser must produce the Divisors module node, got {sorted(mods)}")
        divnode = next((n for n in atlas_doc["nodes"] if n["module"].endswith("Divisors")), {})
        if "Nat.divisors" not in (divnode.get("symbols") or []):
            failures.append("parser must extract `Nat.divisors` as a symbol of the Divisors module")
        if "MiniMathlib.Data.Finset" not in (divnode.get("imports") or []):
            failures.append("parser must extract the import edge of the Divisors module")

        # 2. Retrieval: a goal mentioning a fixture symbol yields the right import line.
        imports, syms = co.mathlib_context("∀ n : Nat, Nat.divisors n = Nat.divisors n", atlas_path)
        if not any("MiniMathlib.NumberTheory.Divisors" in i for i in imports):
            failures.append(f"mathlib_context must return the Divisors import for a divisors goal, got {imports}")
        if "Nat.divisors" not in syms:
            failures.append(f"mathlib_context must return the matched symbols, got {syms}")
        for i in imports:
            if not i.startswith("import "):
                failures.append(f"import lines must be `import <module>`, got {i!r}")

        # 3a. Seed atlas (no source) also resolves a divisors goal to a Mathlib import.
        seed = tdp / "seed.json"
        run(str(SCRIPT_DIR / "build_mathlib_atlas.py"), "--out", str(seed))
        seed_imports, _ = co.mathlib_context("sum of divisors sigma perfect Nat.divisors", seed)
        if not any("Divisors" in i for i in seed_imports):
            failures.append(f"seed atlas must map a divisors goal to a Divisors import, got {seed_imports}")

        # 3b. No Mathlib atlas => mathlib_context is a clean no-op (backward-compat).
        empty_imports, empty_syms = co.mathlib_context("∀ n : Nat, n = n", None)
        if empty_imports or empty_syms:
            failures.append("mathlib_context must be a no-op with no atlas")

        # 4. Resolution validator: graceful degradation, no hallucinated KNOWN.
        res = run(str(SCRIPT_DIR / "validate_premises.py"),
                  "--names", "Nat.mul_comm,Nat.this_lemma_does_not_exist_xyz")
        if res.get("toolchain") == "present":
            # real Lean here: a real core lemma is KNOWN, a fake one is NOT KNOWN
            if "Nat.mul_comm" not in res.get("known", []):
                failures.append(f"Nat.mul_comm should resolve KNOWN, got {res}")
            if "Nat.this_lemma_does_not_exist_xyz" in res.get("known", []):
                failures.append("a non-existent lemma must never be classified KNOWN (no hallucination)")
        else:
            # no toolchain: everything UNCHECKED, never a silent KNOWN pass
            if res.get("known"):
                failures.append("with no toolchain nothing may be KNOWN (must be UNCHECKED)")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("MATHLIB_ATLAS_WIRING_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
