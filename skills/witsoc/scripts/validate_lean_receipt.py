#!/usr/bin/env python3
"""Validate that a Lean receipt can support a Witsoc claim.

This is a Witsoc-side guard for backend/tool outputs. A Lean environment check
or auto-generated placeholder may prove that Lean runs, but it is not evidence
for the mathematical claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


PLACEHOLDER_PATTERNS = (
    "placeholder_check",
    "This file just verifies Lean is working",
    "Cannot auto-translate to Lean",
    "Please provide explicit lean_statement",
)


def load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_text(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def theorem_names(lean_code: str) -> list[str]:
    return re.findall(r"^\s*(?:theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_']*)", lean_code, flags=re.MULTILINE)


def validate(receipt_path: Path, target_hash: str = "") -> dict:
    errors: list[str] = []
    try:
        receipt = load(receipt_path)
    except Exception as exc:
        return {
            "schema": "witsoc.lean_receipt_validation.v1",
            "valid": False,
            "errors": [f"cannot read receipt: {exc}"],
        }
    if not isinstance(receipt, dict):
        return {
            "schema": "witsoc.lean_receipt_validation.v1",
            "valid": False,
            "errors": ["receipt root must be an object"],
        }

    lean_code = get_text(receipt, "lean_code", "lean_statement")
    lean_path_text = get_text(receipt, "lean_path", "lean_file")
    lean_path = Path(lean_path_text) if lean_path_text else None
    if not lean_code and lean_path:
        try:
            lean_code = lean_path.read_text(encoding="utf-8")
        except Exception as exc:
            errors.append(f"could not read Lean file {lean_path}: {exc}")

    passed = receipt.get("passed")
    if passed is None:
        passed = receipt.get("exit_code") == 0
    if passed is not True:
        errors.append("Lean receipt does not record a passing checker result")

    if not lean_code.strip():
        errors.append("Lean receipt must contain lean_code/lean_statement or readable lean_path")
    elif any(pattern in lean_code for pattern in PLACEHOLDER_PATTERNS):
        errors.append("Lean receipt is ENV_CHECK_ONLY/placeholder output, not claim verification")
    elif not theorem_names(lean_code):
        errors.append("Lean code contains no theorem or lemma declaration")

    if target_hash:
        receipt_target_hash = get_text(receipt, "target_hash", "frozen_target_hash")
        if not receipt_target_hash:
            errors.append("receipt missing target_hash/frozen_target_hash")
        elif receipt_target_hash != target_hash:
            errors.append(f"receipt target hash {receipt_target_hash!r} does not match expected {target_hash!r}")

    if receipt.get("safeverify_status") not in (None, "passed", "ok", "valid"):
        errors.append("SafeVerify status is present but not passing")
    if "safeverify_status" not in receipt and "target_fidelity" not in receipt:
        errors.append("receipt must include safeverify_status or target_fidelity evidence")

    lean_hash = sha256_text(lean_code) if lean_code else ""
    if lean_path and lean_path.exists():
        file_hash = sha256_file(lean_path)
        recorded = get_text(receipt, "lean_file_sha256", "lean_hash")
        if recorded and recorded not in {file_hash, lean_hash}:
            errors.append("recorded Lean hash does not match Lean artifact")

    result = {
        "schema": "witsoc.lean_receipt_validation.v1",
        "receipt": str(receipt_path),
        "valid": not errors,
        "errors": errors,
        "theorem_names": theorem_names(lean_code) if lean_code else [],
        "lean_code_sha256": lean_hash,
        "target_hash": get_text(receipt, "target_hash", "frozen_target_hash"),
        "classification": "CLAIM_VERIFICATION" if not errors else "INVALID_OR_ENV_CHECK_ONLY",
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--target-hash", default="")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    result = validate(args.receipt, args.target_hash)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
