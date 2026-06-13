#!/usr/bin/env python3
"""Phase D: Generator packaging stage — WIT -> Lean(from WIT) -> SafeVerify.

Generator does not search for or invent proofs (that is the Prover's job). It
PACKAGES: given a WIT artifact and the formal Lean statement + a proof (ideally
the kernel-verified proof the Prover already found), it

  1. generates the final Lean draft FROM the WIT via wit_to_lean_obligation.py
     (WIT-first invariant), building it with the real toolchain;
  2. runs the SafeVerify / target-freeze check (hash provenance for the WIT claim,
     the Lean statement, and the declared frozen formal target);
  3. completes the CHECKED -> VERIFIED_LEAN upgrade that the Prover stage leaves
     pending: VERIFIED_LEAN requires PROOF_DISCHARGED (lake/lean build, sorry/axiom
     free) AND a passing target-freeze.

Honesty boundary: a discharged Lean proof certifies the SUPPLIED Lean statement.
Whether that Lean statement faithfully captures the informal WIT/frozen claim is
human/Explorer-grounded (recorded as `statement_faithfulness: human_grounded`),
never auto-asserted here.

Usage:
  generator_package.py <file.wit> --lean-statement "<Lean Prop>"
      [--proof "<Lean proof>" | --proof-file P | --prover-result R.json]
      [--name NAME] [--frozen-lean-sha256 HEX] [--lake-dir DIR]
      [--emit out.lean] [--out package.json]
Exit 0 iff VERIFIED_LEAN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import wit_to_lean_obligation as w2l  # noqa: E402  (parse_wit, no side effects beyond import)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def proof_from_prover_result(path: Path) -> tuple[str | None, str | None]:
    """Pull (proof, statement) from a close_obligation record or a Lovasz
    worker-result packet."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    rec = data
    if isinstance(data, list):
        rec = next((r for r in reversed(data) if isinstance(r, dict) and (r.get("proof") or r.get("discharged"))), data[-1] if data else {})
    if not isinstance(rec, dict):
        return None, None
    proof = rec.get("proof")
    statement = rec.get("statement")
    # worker-result packet: proof may be embedded in evidence ["proof=by ..."]
    if not proof:
        for ev in rec.get("evidence", []) or []:
            if isinstance(ev, str) and ev.startswith("proof="):
                proof = ev[len("proof="):]
                break
    return proof, statement


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wit", type=Path)
    ap.add_argument("--name", default=None, help="which WIT claim (default: first)")
    ap.add_argument("--lean-statement", default=None, help="formal Lean proposition (the target type)")
    ap.add_argument("--proof", default=None)
    ap.add_argument("--proof-file", type=Path, default=None)
    ap.add_argument("--prover-result", type=Path, default=None, help="Prover/worker result JSON to reuse its verified proof + statement")
    ap.add_argument("--frozen-lean-sha256", default=None, help="expected sha256 of the (normalized) Lean target for target-freeze")
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--emit", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--record-library", action="store_true",
                    help="harvest a VERIFIED_LEAN package into the lemma library (LEAN_VERIFIED tier)")
    ap.add_argument("--library", type=Path, default=None, help="lemma library dir (default: global)")
    ap.add_argument("--informal-target", default=None,
                    help="informal/WIT claim to faithfulness-check the Lean statement against (Layer 3.5)")
    ap.add_argument("--faithfulness-translator", action="append", default=[],
                    help="cmd:CMD independent back-translator (repeatable; need >=2)")
    ap.add_argument("--faithfulness-threshold", type=float, default=0.5)
    args = ap.parse_args()

    # Resolve statement + proof, preferring explicit flags, then the prover result.
    lean_statement = args.lean_statement
    proof = args.proof
    if args.proof_file:
        proof = args.proof_file.read_text(encoding="utf-8").strip()
    reused_from_prover = False
    if args.prover_result and (proof is None or lean_statement is None):
        p_proof, p_stmt = proof_from_prover_result(args.prover_result)
        if proof is None and p_proof:
            proof = p_proof
            reused_from_prover = True
        if lean_statement is None and p_stmt:
            lean_statement = p_stmt

    if not args.wit.exists():
        print(json.dumps({"status": "error", "reason": f"WIT not found: {args.wit}"}, indent=2))
        return 2

    wit_text = args.wit.read_text(encoding="utf-8", errors="replace")
    parsed = w2l.parse_wit(wit_text, args.name)
    wit_claim = (parsed or {}).get("claim", "") if parsed else ""

    # Generate the final Lean FROM the WIT (WIT-first), build + soundness scan.
    emit = args.emit or (args.wit.with_suffix(".lean"))
    cmd = [sys.executable, str(SCRIPT_DIR / "wit_to_lean_obligation.py"), str(args.wit),
           "--emit", str(emit), "--out-ledger", "/dev/null"]
    if args.name:
        cmd += ["--name", args.name]
    if lean_statement:
        cmd += ["--lean-statement", lean_statement]
    if proof:
        cmd += ["--proof", proof]
    if args.lake_dir:
        cmd += ["--lake-dir", str(args.lake_dir)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=False)
        bridge = json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception as exc:
        bridge = {"status": "error", "reason": str(exc)}
    record = bridge.get("record", {}) if isinstance(bridge, dict) else {}
    label = record.get("label", "UNCHECKED_NO_TOOLCHAIN")
    lean_path = record.get("lean_path")

    # SafeVerify / target-freeze provenance.
    wit_target_sha256 = sha(normalize(wit_claim)) if wit_claim else None
    lean_target_sha256 = sha(normalize(lean_statement)) if lean_statement else None
    frozen_target_sha256 = args.frozen_lean_sha256 or lean_target_sha256
    target_freeze_ok = True
    freeze_reason = "no frozen target supplied; target-freeze trivially holds"
    if args.frozen_lean_sha256:
        target_freeze_ok = (lean_target_sha256 == args.frozen_lean_sha256)
        freeze_reason = "lean target hash matches frozen target" if target_freeze_ok else "lean target hash MISMATCH frozen target -> target drift"

    # Final status: VERIFIED_LEAN only on a discharged kernel proof + passing freeze.
    if label == "UNCHECKED_NO_TOOLCHAIN":
        witsoc_status, lean_verified = "GAP", False
        reason = "no Lean toolchain; cannot package"
    elif label == "STATEMENT_DOES_NOT_TYPECHECK":
        witsoc_status, lean_verified = "REJECTED", False
        reason = "supplied Lean statement does not type-check"
    elif label != "PROOF_DISCHARGED":
        witsoc_status, lean_verified = "OPEN", False
        reason = f"Lean obligation not discharged ({label}); proof missing, blocked, or forbidden"
    elif not target_freeze_ok:
        witsoc_status, lean_verified = "REJECTED", False
        reason = freeze_reason
    else:
        witsoc_status, lean_verified = "VERIFIED_LEAN", True
        reason = "kernel proof discharged + target-freeze passed"

    package = {
        "schema": "witsoc.generator_package.v1",
        "wit_path": str(args.wit),
        "lean_path": lean_path if lean_verified or label != "UNCHECKED_NO_TOOLCHAIN" else None,
        "wit_claim": wit_claim,
        "lean_statement": lean_statement,
        "proof_reused_from_prover": reused_from_prover,
        "bridge_label": label,
        "witsoc_status": witsoc_status,
        "lean_verified": lean_verified,
        "reason": reason,
        "statement_faithfulness": "human_grounded",
        "target_freeze": {
            "ok": target_freeze_ok,
            "reason": freeze_reason,
            "wit_target_sha256": wit_target_sha256,
            "lean_target_sha256": lean_target_sha256,
            "frozen_target_sha256": frozen_target_sha256,
        },
        "artifact_block": {
            "WIT": str(args.wit),
            "Lean": lean_path if lean_verified else (lean_path or "none"),
            "Status": f"LEAN_VERIFIED={'yes' if lean_verified else 'no'}",
        },
    }

    # Layer 3.5 faithfulness gate: a kernel proof certifies the FORMAL statement;
    # if it does not faithfully capture the informal target, withdraw VERIFIED.
    if lean_verified and args.informal_target and lean_statement:
        import faithfulness_gate as fg  # noqa: E402
        faith = fg.gate(lean_statement, args.informal_target, args.faithfulness_translator, args.faithfulness_threshold)
        package["faithfulness"] = faith
        package["formal_lean_verified"] = True
        if faith["status"] == "FAITHFULNESS_GAP":
            witsoc_status, lean_verified = "FAITHFULNESS_GAP", False
            package["statement_faithfulness"] = "machine_gap"
            package["reason"] = "kernel proof discharged but informal<->formal faithfulness FAILED -> not VERIFIED"
        elif faith["status"] == "FAITHFUL":
            package["statement_faithfulness"] = "machine_evidence_plus_human_gate"
        # UNCHECKED_FAITHFULNESS: leave VERIFIED_LEAN + statement_faithfulness=human_grounded
        package["witsoc_status"] = witsoc_status
        package["lean_verified"] = lean_verified
        package["artifact_block"]["Status"] = f"LEAN_VERIFIED={'yes' if lean_verified else 'no'}"

    # Phase E harvest: a VERIFIED_LEAN package compounds into the lemma library at
    # the strongest tier, so future runs can reuse it (close_obligation --use-library).
    if args.record_library and lean_verified and lean_statement:
        import witcore  # noqa: E402
        library = args.library if args.library is not None else witcore.global_library()
        add = [sys.executable, str(SCRIPT_DIR / "lemma_library.py"), "--library", str(library), "add",
               "--statement", lean_statement, "--lean", str(lean_path), "--tier", "LEAN_VERIFIED",
               "--provenance", f"package:{proof}" if proof else "package", "--wit", str(args.wit)]
        if lean_target_sha256:
            add += ["--target-hash", lean_target_sha256]
        try:
            subprocess.run(add, capture_output=True, text=True, timeout=30, check=False)
            package["recorded_to_library"] = "LEAN_VERIFIED"
        except Exception:
            package["recorded_to_library"] = None

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(package, indent=2, ensure_ascii=False))
    return 0 if lean_verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
