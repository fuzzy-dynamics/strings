#!/usr/bin/env python3
"""Create or update a Generator artifact manifest and register artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import artifacts as artifact_registry


def sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": "witsoc.generator_artifacts.v1", "artifacts": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"schema": "witsoc.generator_artifacts.v1", "artifacts": []}
    except Exception:
        return {"schema": "witsoc.generator_artifacts.v1", "artifacts": []}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, action="append", default=[])
    parser.add_argument("--type", action="append", default=[])
    parser.add_argument("--target-hash", default="")
    parser.add_argument("--route-state", type=Path, default=None)
    parser.add_argument("--proof-worktree", default="")
    parser.add_argument("--check-status", default="")
    parser.add_argument("--receipt-status", default="")
    parser.add_argument("--lean-status", default="")
    parser.add_argument("--registry", type=Path, default=None)
    args = parser.parse_args()

    data = load(args.manifest)
    data.setdefault("schema", "witsoc.generator_artifacts.v1")
    data.setdefault("target_hash", args.target_hash)
    if args.target_hash and data.get("target_hash") and data.get("target_hash") != args.target_hash:
        raise SystemExit("target hash drift detected in generator manifest")
    data["target_hash"] = args.target_hash or data.get("target_hash", "")
    data["route_state"] = str(args.route_state.resolve()) if args.route_state else data.get("route_state")
    data["proof_worktree"] = args.proof_worktree or data.get("proof_worktree", "")
    data["check_status"] = args.check_status or data.get("check_status", "")
    data["receipt_status"] = args.receipt_status or data.get("receipt_status", "")
    data["lean_status"] = args.lean_status or data.get("lean_status", "")

    artifacts = {item.get("path"): item for item in data.get("artifacts", []) if isinstance(item, dict) and item.get("path")}
    for i, path in enumerate(args.artifact):
        typ = args.type[i] if i < len(args.type) else None
        resolved = path.resolve()
        record = {
            "path": str(resolved),
            "name": resolved.name,
            "type": typ or resolved.suffix.lower().lstrip(".") or "file",
            "exists": resolved.exists(),
            "sha256": sha256_file(resolved),
        }
        artifacts[str(resolved)] = record
        artifact_registry.register_artifact(
            registry_path=args.registry or artifact_registry.default_registry_path(),
            artifact_path=resolved,
            type_=record["type"],
            owner_phase="witsoc-generator",
            status="generated",
            target_hash=data["target_hash"],
            proof_worktree=args.proof_worktree,
            worktree_status="preserved" if args.proof_worktree else "",
        )
    data["artifacts"] = sorted(artifacts.values(), key=lambda item: item["path"])
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
