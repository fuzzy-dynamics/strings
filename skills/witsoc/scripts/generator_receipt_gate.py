#!/usr/bin/env python3
"""Validate Generator artifact receipts and status ceilings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def artifact_records(run: Path) -> list[dict[str, Any]]:
    reg = load(run / "witsoc_artifacts.json", {})
    return [x for x in reg.get("artifacts", []) if isinstance(x, dict)] if isinstance(reg, dict) else []


def validate(run: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    package = load(run / "generator_package.json", {})
    artifacts = artifact_records(run)
    wit_lean = [a for a in artifacts if str(a.get("type") or "").lower() in {"wit", "lean"}]
    if not wit_lean and not package:
        warnings.append("no WIT/Lean generator artifacts found")
    for art in wit_lean:
        if not art.get("exists"):
            errors.append(f"artifact does not exist: {art.get('path')}")
        if not art.get("target_hash"):
            warnings.append(f"artifact missing target_hash: {art.get('path')}")
    if isinstance(package, dict) and package:
        status = str(package.get("witsoc_status") or "")
        if status == "VERIFIED_LEAN":
            if package.get("lean_verified") is not True:
                errors.append("VERIFIED_LEAN package must set lean_verified=true")
            tf = package.get("target_freeze") if isinstance(package.get("target_freeze"), dict) else {}
            if tf.get("ok") is not True:
                errors.append("VERIFIED_LEAN package requires passing target_freeze")
            if not package.get("lean_path"):
                errors.append("VERIFIED_LEAN package missing lean_path")
        if status in {"VERIFIED", "VERIFIED_LEAN", "CHECKED"} and not (package.get("wit_path") or package.get("lean_path")):
            errors.append(f"{status} package requires WIT or Lean artifact path")
    result = {
        "schema": "witsoc.generator_artifact_receipt.v1",
        "run_dir": str(run),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "artifact_count": len(wit_lean),
        "package_status": package.get("witsoc_status") if isinstance(package, dict) else None,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    result = validate(args.run_dir)
    out = args.out or (args.run_dir / "generator_artifact_receipt.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
