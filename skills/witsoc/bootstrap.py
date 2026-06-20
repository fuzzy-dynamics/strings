#!/usr/bin/env python3
"""Restore Witsoc runtime files from the PyPI package.

This file intentionally lives at the Witsoc skill root, not under `scripts/` or
`src/`, so it can recover a checkout where those directories were removed.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PACKAGE = "witsoc"
DEFAULT_SKILL_DIR = Path.home() / ".openscientist" / "skills" / "witsoc"
ROOT_FILES = ("bootstrap.py", "witsoc.py", "README.md", "SKILL.md", "pyproject.toml")


def skill_root() -> Path:
    return Path(__file__).resolve().parent


def runtime_ok(root: Path) -> bool:
    return (root / "scripts" / "witsoc.py").exists() and (root / "src" / "witsoc" / "cli.py").exists()


def install_package(target: Path, *, package: str, upgrade: bool) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(target)]
    if upgrade:
        cmd.append("--upgrade")
    cmd.append(package)
    subprocess.check_call(cmd)


def copy_tree(src: Path, dst: Path, *, replace: bool) -> None:
    if not src.exists():
        raise FileNotFoundError(f"missing packaged path: {src}")
    if dst.exists():
        if not replace:
            return
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def copy_file(src: Path, dst: Path, *, replace: bool) -> None:
    if not src.exists():
        return
    if dst.exists() and not replace:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_package_modules(pkg: Path, dst: Path, *, replace: bool) -> None:
    if not pkg.exists():
        raise FileNotFoundError(f"missing installed package: {pkg}")
    dst.mkdir(parents=True, exist_ok=True)
    for path in pkg.glob("*.py"):
        target = dst / path.name
        if target.exists() and not replace:
            continue
        shutil.copy2(path, target)


def restore(root: Path, *, package: str = PACKAGE, replace: bool = False, upgrade: bool = True, keep_cache: bool = False) -> dict:
    cache = root / ".witsoc_pypi_cache"
    install_package(cache, package=package, upgrade=upgrade)
    pkg = cache / "witsoc"
    copy_tree(pkg / "scripts", root / "scripts", replace=replace)
    copy_package_modules(pkg, root / "src" / "witsoc", replace=replace)
    for name in ("references", "witsoc-explorer", "witsoc-generator", "witsoc-research-lovasz"):
        src = pkg / name
        dst = root / name
        if src.exists() and (replace or not dst.exists()):
            copy_tree(src, dst, replace=replace)
    for name in ROOT_FILES:
        copy_file(pkg / name, root / name, replace=replace)
    if not keep_cache:
        shutil.rmtree(cache, ignore_errors=True)
    return {
        "root": str(root),
        "scripts": str(root / "scripts"),
        "src": str(root / "src" / "witsoc"),
        "package": package,
        "runtime_ok": runtime_ok(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default=PACKAGE, help="PyPI package spec to install, e.g. witsoc or witsoc==X.Y.Z")
    parser.add_argument("--replace", action="store_true", help="replace existing runtime directories")
    parser.add_argument("--no-upgrade", action="store_true", help="do not pass --upgrade to pip")
    parser.add_argument("--keep-cache", action="store_true", help="keep .witsoc_pypi_cache after restore")
    parser.add_argument("--target", type=Path, default=None, help="skill directory to restore; defaults to this bootstrap's folder")
    parser.add_argument("--default-target", action="store_true", help="restore ~/.openscientist/skills/witsoc")
    parser.add_argument("--check", action="store_true", help="only check whether local runtime files exist")
    args = parser.parse_args()

    root = DEFAULT_SKILL_DIR if args.default_target else (args.target.expanduser() if args.target else skill_root())
    if args.check:
        ok = runtime_ok(root)
        print("OK" if ok else "MISSING")
        return 0 if ok else 1
    result = restore(
        root,
        package=args.package,
        replace=args.replace,
        upgrade=not args.no_upgrade,
        keep_cache=args.keep_cache,
    )
    print(f"Restored Witsoc runtime from {result['package']}")
    print(f"scripts: {result['scripts']}")
    print(f"src: {result['src']}")
    print(f"runtime_ok: {result['runtime_ok']}")
    return 0 if result["runtime_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
