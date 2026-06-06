#!/usr/bin/env python3
"""Witsoc session artifact registry.

The registry is intentionally small JSON so shell scripts, plugin servers, and
validators can share one source of truth for generated WIT/Lean/SOC artifacts.
Filesystem scanning remains useful as a fallback, but production flows should
register artifacts as they are created.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REGISTRY_SCHEMA = "witsoc.artifacts.v1"


def default_registry_path() -> Path:
    explicit = os.environ.get("WITSOC_ARTIFACT_REGISTRY")
    if explicit:
        return Path(explicit)
    for env_name in ("PLANE_SESSION_DIR", "OSCI_SESSION_DIR", "KIMI_WORK_DIR"):
        value = os.environ.get(env_name)
        if value:
            return Path(value) / "witsoc_artifacts.json"
    return Path.cwd() / "witsoc_artifacts.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def artifact_type(path: Path, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    suffix = path.suffix.lower()
    if suffix == ".wit":
        return "wit"
    if suffix == ".lean":
        return "lean"
    if suffix == ".soc":
        return "soc"
    if suffix == ".json":
        return "json"
    if suffix in {".log", ".txt"}:
        return "log"
    return "file"


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": REGISTRY_SCHEMA, "artifacts": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": REGISTRY_SCHEMA, "artifacts": []}
    if not isinstance(data, dict):
        return {"schema": REGISTRY_SCHEMA, "artifacts": []}
    data.setdefault("schema", REGISTRY_SCHEMA)
    data.setdefault("artifacts", [])
    if not isinstance(data["artifacts"], list):
        data["artifacts"] = []
    return data


def save_registry(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def register_artifact(
    *,
    registry_path: Path,
    artifact_path: Path,
    type_: str | None = None,
    owner_phase: str = "",
    status: str = "created",
    target_hash: str = "",
    proof_worktree: str = "",
    worktree_status: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = artifact_path.resolve()
    data = load_registry(registry_path)
    artifacts = data["artifacts"]
    existing = None
    for item in artifacts:
        if isinstance(item, dict) and item.get("path") == str(resolved):
            existing = item
            break
    record = existing if existing is not None else {}
    created_at = record.get("created_at") or now_iso()
    record.update({
        "path": str(resolved),
        "name": resolved.name,
        "type": artifact_type(resolved, type_),
        "owner_phase": owner_phase,
        "status": status,
        "target_hash": target_hash,
        "proof_worktree": proof_worktree,
        "worktree_status": worktree_status,
        "exists": resolved.exists(),
        "sha256": sha256_file(resolved),
        "created_at": created_at,
        "updated_at": now_iso(),
        "metadata": metadata or record.get("metadata") or {},
    })
    if existing is None:
        artifacts.append(record)
    data["artifacts"] = sorted(artifacts, key=lambda item: (str(item.get("type", "")), str(item.get("path", ""))))
    save_registry(registry_path, data)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Witsoc artifact registry.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_register = sub.add_parser("register")
    p_register.add_argument("path", type=Path)
    p_register.add_argument("--registry", type=Path, default=None)
    p_register.add_argument("--type", default=None)
    p_register.add_argument("--owner-phase", default=os.environ.get("WITSOC_OWNER_PHASE", ""))
    p_register.add_argument("--status", default="created")
    p_register.add_argument("--target-hash", default="")
    p_register.add_argument("--proof-worktree", default=os.environ.get("WITSOC_PROOF_WORKTREE", ""))
    p_register.add_argument("--worktree-status", default="")
    p_register.add_argument("--metadata-json", default="{}")

    p_list = sub.add_parser("list")
    p_list.add_argument("--registry", type=Path, default=None)
    p_list.add_argument("--type", default=None)

    p_path = sub.add_parser("path")
    p_path.add_argument("--registry", type=Path, default=None)

    args = parser.parse_args()
    registry = args.registry or default_registry_path()

    if args.cmd == "path":
        print(registry)
        return 0

    if args.cmd == "register":
        try:
            metadata = json.loads(args.metadata_json)
            if not isinstance(metadata, dict):
                metadata = {"value": metadata}
        except Exception:
            metadata = {"raw": args.metadata_json}
        record = register_artifact(
            registry_path=registry,
            artifact_path=args.path,
            type_=args.type,
            owner_phase=args.owner_phase,
            status=args.status,
            target_hash=args.target_hash,
            proof_worktree=args.proof_worktree,
            worktree_status=args.worktree_status,
            metadata=metadata,
        )
        print(json.dumps({"ok": True, "registry": str(registry), "artifact": record}, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "list":
        data = load_registry(registry)
        artifacts = [a for a in data.get("artifacts", []) if isinstance(a, dict)]
        if args.type:
            artifacts = [a for a in artifacts if a.get("type") == args.type]
        print(json.dumps({"registry": str(registry), "artifacts": artifacts}, indent=2, ensure_ascii=False))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
