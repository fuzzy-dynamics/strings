#!/usr/bin/env python3
"""Validate a Prover (close_obligation.py) result and map it to a legal Witsoc
status — the honesty gate at the PROVER_ATTEMPT integration boundary.

The Prover's own soundness gate (lean_verify, sorry/axiom-free) already decides
`PROOF_DISCHARGED` vs `OBLIGATION_OPEN` vs `UNCHECKED_NO_TOOLCHAIN`. This script
enforces, at the witsoc level, that nobody can claim a status stronger than the
evidence supports:

  - A kernel proof (PROOF_DISCHARGED + verified receipt) is `CHECKED`-grade on its
    own; it only reaches `VERIFIED` once SafeVerify / target-freeze also passes
    (status.md: LEAN_VERIFIED bundles SafeVerify).
  - OBLIGATION_OPEN is `OPEN` (or `FAILED_ATTEMPT` if search actually ran).
  - UNCHECKED_NO_TOOLCHAIN is `GAP` — no claim may be made.

Usage:
  validate_prover_result.py result.json
  validate_prover_result.py result.json --safeverify-passed
  validate_prover_result.py result.json --safeverify safeverify.json
  validate_prover_result.py result.json --frozen-target-sha256 <hex>
  validate_prover_result.py result.json --assert-status VERIFIED   # exit 1 if unmet
Exit 0 iff the record is internally consistent and (if given) the asserted status
is supported by the evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


# Status ordering for the assertion check (higher index = stronger claim).
STATUS_RANK = ["GAP", "OPEN", "FAILED_ATTEMPT", "CHECKED", "VERIFIED"]


def rank(status: str) -> int:
    return STATUS_RANK.index(status) if status in STATUS_RANK else -1


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def receipt_verified(record: dict) -> bool:
    """A kernel receipt is present and positive. close_obligation records
    `discharged`/`proof`; a wrapper may also carry an explicit `verified` or
    nested `receipt`."""
    if record.get("verified") is True:
        return True
    receipt = record.get("receipt")
    if isinstance(receipt, dict) and receipt.get("verified") is True:
        return True
    # close_obligation.v1: discharged with a concrete proof string == kernel pass.
    return bool(record.get("discharged")) and bool(record.get("proof"))


def safeverify_ok(args: argparse.Namespace) -> bool:
    if args.safeverify_passed:
        return True
    if args.safeverify:
        try:
            data = load_json(Path(args.safeverify))
        except Exception:
            return False
        return bool(data.get("passed") or data.get("safeverify_passed"))
    return False


def legal_status(record: dict, args: argparse.Namespace) -> tuple[str, dict]:
    label = record.get("label")
    reasons: list[str] = []
    flags = {
        "kernel_proof": False,
        "safeverify_passed": safeverify_ok(args),
        "lean_verified": False,
        "toolchain_missing": False,
    }

    if label == "UNCHECKED_NO_TOOLCHAIN":
        flags["toolchain_missing"] = True
        reasons.append("no Lean toolchain available; no claim may be made")
        return "GAP", flags | {"reasons": reasons}

    if label == "BUDGET_EXHAUSTED":
        flags["budget_exhausted"] = True
        reasons.append(f"search consumed its node budget ({record.get('search_max_nodes')}) without a proof -> FAILED_ATTEMPT (length/resource-blocked finding, not a hang)")
        return "FAILED_ATTEMPT", flags | {"reasons": reasons}

    if label == "OBLIGATION_OPEN" or not record.get("discharged"):
        if int(record.get("search_nodes") or 0) > 0:
            reasons.append("search ran and closed nothing -> FAILED_ATTEMPT")
            return "FAILED_ATTEMPT", flags | {"reasons": reasons}
        reasons.append("not discharged -> OPEN")
        return "OPEN", flags | {"reasons": reasons}

    if label == "PROOF_DISCHARGED":
        if not receipt_verified(record):
            reasons.append("label PROOF_DISCHARGED but no kernel receipt/proof present -> cannot exceed OPEN")
            return "OPEN", flags | {"reasons": reasons}
        flags["kernel_proof"] = True
        # optional target-freeze cross-check
        if args.frozen_target_sha256:
            stmt = record.get("statement") or ""
            stmt_hash = hashlib.sha256(stmt.encode("utf-8")).hexdigest()
            tgt = record.get("frozen_target_sha256") or stmt_hash
            if tgt != args.frozen_target_sha256:
                reasons.append("frozen target hash mismatch -> target drift; demote to FAILED_ATTEMPT")
                return "FAILED_ATTEMPT", flags | {"reasons": reasons}
        if flags["safeverify_passed"]:
            flags["lean_verified"] = True
            reasons.append("kernel proof + SafeVerify -> VERIFIED (LEAN_VERIFIED)")
            return "VERIFIED", flags | {"reasons": reasons}
        reasons.append("kernel proof present but SafeVerify not confirmed -> CHECKED (not yet VERIFIED)")
        return "CHECKED", flags | {"reasons": reasons}

    reasons.append(f"unrecognized prover label {label!r}")
    return "GAP", flags | {"reasons": reasons}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("result", type=Path, help="Prover result JSON (close_obligation schema or wrapper).")
    ap.add_argument("--safeverify-passed", action="store_true", help="Assert SafeVerify/target-freeze passed.")
    ap.add_argument("--safeverify", default=None, help="Path to a SafeVerify result JSON ({passed: true}).")
    ap.add_argument("--frozen-target-sha256", default=None, help="Expected frozen target hash for drift check.")
    ap.add_argument("--assert-status", default=None, choices=STATUS_RANK, help="Exit 1 unless the evidence supports at least this status.")
    args = ap.parse_args()

    try:
        record = load_json(args.result)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"cannot read result: {exc}"}, indent=2))
        return 2

    status, detail = legal_status(record, args)
    out = {
        "schema": "witsoc.prover_validation.v1",
        "input_label": record.get("label"),
        "legal_status": status,
        "flags": {k: v for k, v in detail.items() if k != "reasons"},
        "reasons": detail.get("reasons", []),
        "ok": True,
    }

    asserted_ok = True
    if args.assert_status:
        asserted_ok = rank(status) >= rank(args.assert_status)
        out["assert_status"] = args.assert_status
        out["assert_satisfied"] = asserted_ok

    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if asserted_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
