#!/usr/bin/env python3
"""Bridge a .wit claim to a Lean *obligation* — the formalization scaffold.

This is the honest, bounded autoformalization step. It does NOT auto-translate
informal mathematics into a Lean statement (that is the genuinely hard, unsolved
part) and it does NOT auto-prove. What it does:

  1. Parse a .wit THEOREM/LEMMA: module, name, informal CLAIM, hypotheses.
  2. Emit a compilable Lean obligation file:
       - the informal claim preserved as a docstring,
       - a `theorem <name> : <STATEMENT> := <PROOF>` where STATEMENT is the formal
         Lean proposition you supply with --lean-statement (else a clearly-marked
         `True` placeholder), and PROOF is what you supply with --proof (else
         `sorry`).
  3. Build it with the real Lean toolchain and run the soundness scan
     (shared lean_check), so the obligation file separates three honest states:
       STATEMENT_NOT_FORMALIZED  no Lean statement was supplied yet
       OBLIGATION_OPEN           statement type-checks; proof is still `sorry`
       PROOF_DISCHARGED          statement type-checks AND proof is sorry/axiom-free
  4. Record the result in formalization_obligations.json (a list, appended).

By construction a `sorry` obligation can never be recorded as PROOF_DISCHARGED —
that ties directly to the Lean soundness guard so the bridge cannot launder an
unproved claim into a "done" one.

Usage:
  wit_to_lean_obligation.py <file.wit> [--name NAME]
      [--lean-statement "<Lean Prop>"] [--proof "<Lean proof>" | --proof-file P]
      [--lake-dir DIR] [--emit out.lean] [--out-ledger formalization_obligations.json]
      [--update-feasibility]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lean_check import lean_verify  # noqa: E402

CLAIM_KEYWORDS = ("THEOREM", "LEMMA", "PROPOSITION", "COROLLARY")
_BLOCK_RE = re.compile(
    r"^\s*(THEOREM|LEMMA|PROPOSITION|COROLLARY)\s+\[?([A-Za-z_][A-Za-z0-9_]*)\]?\s*:",
    re.MULTILINE,
)
_MODULE_RE = re.compile(r"^\s*MODULE\s+\[?([A-Za-z_][A-Za-z0-9_]*)\]?", re.MULTILINE)


def parse_wit(text: str, want: str | None) -> dict[str, Any] | None:
    module = "WitModule"
    m = _MODULE_RE.search(text)
    if m:
        module = m.group(1)
    blocks = list(_BLOCK_RE.finditer(text))
    if not blocks:
        return None
    chosen = None
    if want:
        for b in blocks:
            if b.group(2) == want:
                chosen = b
                break
        if chosen is None:
            return None
    else:
        chosen = blocks[0]

    kind, name = chosen.group(1), chosen.group(2)
    # Body of the chosen block = text from its header to the next top-level block.
    start = chosen.end()
    nexts = [b.start() for b in blocks if b.start() > chosen.start()]
    proof_at = text.find("PROOF OF", start)
    candidates = [p for p in nexts + ([proof_at] if proof_at != -1 else []) if p > start]
    end = min(candidates) if candidates else len(text)
    body = text[start:end]

    claim = _extract_section(body, "CLAIM")
    given = _extract_section(body, "GIVEN")
    return {"module": module, "kind": kind, "name": name,
            "claim": claim.strip(), "given": given.strip()}


def _extract_section(body: str, header: str) -> str:
    """Collect the indented lines following `HEADER:` until the next header/dedent."""
    lines = body.splitlines()
    out: list[str] = []
    capturing = False
    for line in lines:
        stripped = line.strip()
        if not capturing:
            if re.match(rf"^\s*{header}\s*:", line):
                capturing = True
                after = line.split(":", 1)[1].strip()
                if after:
                    out.append(after)
            continue
        # Stop at the next section keyword (CLAIM/GIVEN/QED) or a clearly new block.
        if re.match(r"^\s*(CLAIM|GIVEN|PROOF|QED|EXPORT|DEFINE)\b", line) and not out[:0]:
            if re.match(rf"^\s*{header}\s*:", line):
                continue
            break
        if stripped == "" and out:
            break
        out.append(stripped)
    return "\n".join(out)


def sanitize_ident(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not s or not (s[0].isalpha() or s[0] == "_"):
        s = "ob_" + s
    return s


def build_lean(parsed: dict, statement: str | None, proof: str | None, wit_path: Path) -> str:
    ident = sanitize_ident(parsed["name"])
    claim = parsed["claim"] or "(no CLAIM block found in source)"
    given = parsed["given"]
    stmt = statement if statement else "True"
    prf = proof if proof else "sorry"
    placeholder_note = "" if statement else (
        "-- WARNING: no --lean-statement supplied; the statement below is the\n"
        "-- placeholder `True`, NOT a formalization of the claim. This obligation\n"
        "-- only demonstrates the scaffold compiles; it proves nothing.\n"
    )
    docstring = claim.replace("/-", "(-").replace("-/", "-)")
    given_comment = ""
    if given:
        given_comment = "-- Hypotheses (informal):\n" + "".join(
            f"--   {ln}\n" for ln in given.splitlines() if ln.strip())
    return (
        f"-- Auto-generated Witsoc obligation from {wit_path}\n"
        f"-- Module: {parsed['module']}   {parsed['kind']} {parsed['name']}\n"
        f"{given_comment}{placeholder_note}"
        f"namespace WitsocObligation\n\n"
        f"/-- {docstring} -/\n"
        f"theorem {ident} : {stmt} := {prf}\n\n"
        f"end WitsocObligation\n"
    )


def classify(statement_provided: bool, proof_provided: bool,
             build_ok: bool, verified: bool, checked: bool) -> str:
    if not checked:
        return "UNCHECKED_NO_TOOLCHAIN"
    if not statement_provided:
        return "STATEMENT_NOT_FORMALIZED"
    if not build_ok:
        return "STATEMENT_DOES_NOT_TYPECHECK"
    if not proof_provided:
        return "OBLIGATION_OPEN"          # statement type-checks; proof is `sorry`
    if not verified:
        return "OBLIGATION_OPEN"          # proof present but uses sorry/axiom -> still open
    return "PROOF_DISCHARGED"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wit", type=Path)
    ap.add_argument("--name", default=None, help="which claim (default: first in file)")
    ap.add_argument("--lean-statement", default=None, help="formal Lean proposition for the theorem type")
    ap.add_argument("--proof", default=None, help="Lean proof term/tactic (default: sorry)")
    ap.add_argument("--proof-file", type=Path, default=None)
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--emit", type=Path, default=None, help="output .lean path (default: obligations/<mod>_<name>.lean)")
    ap.add_argument("--out-ledger", type=Path, default=Path("formalization_obligations.json"))
    ap.add_argument("--update-feasibility", action="store_true",
                    help="also stamp a summary label into formalization_feasibility.json")
    args = ap.parse_args()

    text = args.wit.read_text(encoding="utf-8", errors="replace")
    parsed = parse_wit(text, args.name)
    if parsed is None:
        print(json.dumps({"status": "error",
                          "reason": f"no {' / '.join(CLAIM_KEYWORDS)} named {args.name!r} found in {args.wit}"}, indent=2))
        return 2

    proof = args.proof
    if args.proof_file:
        proof = args.proof_file.read_text(encoding="utf-8").strip()
    statement_provided = args.lean_statement is not None
    proof_provided = proof is not None

    lean_src = build_lean(parsed, args.lean_statement, proof, args.wit)
    emit = args.emit or Path("obligations") / f"{sanitize_ident(parsed['module'])}_{sanitize_ident(parsed['name'])}.lean"
    emit.parent.mkdir(parents=True, exist_ok=True)
    emit.write_text(lean_src, encoding="utf-8")

    verdict = lean_verify(emit, args.lake_dir)
    checked = bool(verdict.get("checked"))
    build_ok = bool(verdict.get("build", {}).get("ok"))
    verified = bool(verdict.get("verified"))
    label = classify(statement_provided, proof_provided, build_ok, verified, checked)

    record = {
        "schema": "witsoc.formalization_obligation.v1",
        "wit": str(args.wit),
        "module": parsed["module"],
        "theorem": parsed["name"],
        "lean_path": str(emit),
        "informal_claim": parsed["claim"],
        "statement_provided": statement_provided,
        "statement_compiles": ("PASS" if build_ok else "FAIL") if checked else "UNCHECKED",
        "proof_provided": proof_provided,
        "proof_discharged": label == "PROOF_DISCHARGED",
        "forbidden_tokens": verdict.get("forbidden", []),
        "label": label,
    }

    # Append to the obligations ledger (a list).
    ledger_path = args.out_ledger
    existing = []
    if ledger_path.exists():
        try:
            data = json.loads(ledger_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                existing = data
        except Exception:
            existing = []
    existing = [r for r in existing if not (isinstance(r, dict) and r.get("lean_path") == record["lean_path"])]
    existing.append(record)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.update_feasibility:
        feas = Path("formalization_feasibility.json")
        summary = {"label": label, "lean_path": str(emit), "theorem": parsed["name"],
                   "statement_provided": statement_provided, "proof_discharged": record["proof_discharged"]}
        feas.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "record": record}, indent=2, ensure_ascii=False))
    # Exit non-zero unless the proof is genuinely discharged, so callers can gate.
    return 0 if record["proof_discharged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
