#!/usr/bin/env python3
"""Shared Lean kernel checking + soundness scanning for Witsoc.

Single source of truth for "did the Lean toolchain actually verify this, with no
cheating?" used by the lemma library, the certificate re-checker, and the
wit->Lean obligation bridge.

The subtlety this module exists to handle: `lake build` / `lean file.lean`
returns exit code 0 even when a declaration is closed by `sorry` (it is only a
*warning*). So "build is green" is NOT the same as "proof is sound". A file that
contains `sorry`, `admit`, the `sorryAx` axiom, a locally-declared `axiom`,
`constant`, `opaque`, or `unsafe` declaration must never be counted as
machine-verified. `scan_forbidden` enforces that.

Functions:
  run_lean_check(lean_path, lake_dir) -> dict   build/type-check via the real toolchain
  scan_forbidden(text)                -> list   forbidden soundness-breaking tokens in Lean source
  lean_verify(lean_path, lake_dir)    -> dict   build AND soundness scan combined (the gate)

Every function degrades gracefully when the toolchain is absent: it returns
`ok=False` with `reason="lean/lake not found"` and tool="absent" so callers can
record UNCHECKED rather than a silent pass.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

# Tokens that make a "successful" Lean build unsound as a proof of its own claim.
#   sorry / admit  : leave a hole the kernel fills with `sorryAx`.
#   sorryAx        : the underlying axiom, sometimes written directly.
# Local declarations that make a generated proof unsound as evidence for its
# target are handled separately because a proof file must not simply assume or
# hide the claim.
_FORBIDDEN = (
    (re.compile(r"(?<![A-Za-z0-9_])sorry(?![A-Za-z0-9_])"), "sorry"),
    (re.compile(r"(?<![A-Za-z0-9_])admit(?![A-Za-z0-9_])"), "admit"),
    (re.compile(r"(?<![A-Za-z0-9_])sorryAx(?![A-Za-z0-9_])"), "sorryAx"),
)
_ESCAPE_DECLS = (
    (re.compile(r"^\s*axiom\s+[A-Za-z_]", re.MULTILINE), "axiom"),
    (re.compile(r"^\s*constant\s+[A-Za-z_]", re.MULTILINE), "constant"),
    (re.compile(r"^\s*opaque\s+[A-Za-z_]", re.MULTILINE), "opaque"),
    (re.compile(r"^\s*unsafe\s+(?:def|theorem|opaque|axiom)\s+[A-Za-z_]", re.MULTILINE), "unsafe"),
)

# Lean's own warning when a declaration is closed by a hole. Caught from build
# output as a belt-and-suspenders signal in addition to the source scan, since a
# proof term elaborated from a tactic may introduce `sorry` the source never spells.
_SORRY_WARNING = re.compile(r"declaration uses ['`]sorry['`]")


def _strip_comments(text: str) -> str:
    """Remove Lean comments so a `sorry` mentioned in a doc/comment is not a false positive."""
    text = re.sub(r"/-.*?-/", " ", text, flags=re.DOTALL)  # block comments (incl. /-- docstrings -/)
    text = re.sub(r"--[^\n]*", " ", text)                   # line comments
    return text


def scan_forbidden(text: str) -> list[str]:
    """Return the sorted list of soundness-breaking tokens present in Lean *code*.

    Comments and docstrings are stripped first, so prose that merely mentions
    "sorry" does not trip the guard; only real code holes do.
    """
    code = _strip_comments(text)
    found: set[str] = set()
    for pattern, name in _FORBIDDEN:
        if pattern.search(code):
            found.add(name)
    for pattern, name in _ESCAPE_DECLS:
        if pattern.search(code):
            found.add(name)
    return sorted(found)


# Per-build wall-clock cap. A reachable proof type-checks in well under a second;
# the only builds that run long are tactics (omega/simp/aesop on a hard goal)
# grinding before they fail. Without a cap a single open goal can burn minutes in
# search. A tactic that has not closed the goal in this budget is treated as a
# failed candidate. Override via WITSOC_LEAN_TIMEOUT.
import os as _os
_DEFAULT_TIMEOUT = float(_os.environ.get("WITSOC_LEAN_TIMEOUT", "12"))


def run_lean_check(lean_path: Path, lake_dir: Path | None = None,
                   timeout: float | None = None) -> dict[str, Any]:
    """Type-check a Lean file/project with the real toolchain (no soundness scan)."""
    timeout = _DEFAULT_TIMEOUT if timeout is None else timeout
    if lake_dir:
        lake = shutil.which("lake")
        if not lake:
            return {"ok": False, "tool": "absent", "reason": "lake not found"}
        # SOUNDNESS: `lake build` builds the PROJECT'S OWN targets — it never
        # looks at a file outside the project. Checking an external candidate
        # file that way is vacuous: a prebuilt project returns exit 0 for any
        # proof text whatsoever. So `lake build` is legal ONLY when the file
        # actually lives inside the lake project (the generator's
        # self-contained-project flow). For any external file — the prover's
        # tempfile candidates above all — the only sound check is
        # `lake env lean <file>` (project deps on LEAN_PATH, project
        # toolchain), regardless of whether WITSOC_LAKE_ENV is set.
        try:
            inside = Path(lean_path).resolve().is_relative_to(Path(lake_dir).resolve())
        except Exception:
            inside = False
        if _os.environ.get("WITSOC_LAKE_ENV") or not inside:
            cmd, tool = [lake, "env", "lean", str(lean_path)], "lake env lean"
        else:
            cmd, tool = [lake, "build"], "lake build"
        try:
            proc = subprocess.run(cmd, cwd=str(lake_dir), text=True,
                                  capture_output=True, check=False, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"ok": False, "tool": tool, "returncode": 124, "reason": "timeout",
                    "stdout": "", "stderr": "timeout"}
        return {"ok": proc.returncode == 0, "tool": tool,
                "returncode": proc.returncode,
                "stdout": proc.stdout.strip()[-2000:],
                "stderr": proc.stderr.strip()[-2000:]}
    lean = shutil.which("lean")
    if not lean:
        return {"ok": False, "tool": "absent", "reason": "lean not found"}
    try:
        proc = subprocess.run([lean, str(lean_path)], text=True, capture_output=True,
                              check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "tool": "lean", "returncode": 124, "reason": "timeout",
                "stdout": "", "stderr": "timeout"}
    return {"ok": proc.returncode == 0, "tool": "lean",
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip()[-2000:],
            "stderr": proc.stderr.strip()[-2000:]}


def lean_verify(lean_path: Path, lake_dir: Path | None = None) -> dict[str, Any]:
    """Build AND soundness-scan: the gate that decides LEAN_VERIFIED.

    Returns a dict with:
      verified : bool   -- True iff build is green AND no forbidden tokens
      build    : dict   -- raw run_lean_check result
      forbidden: list   -- soundness-breaking tokens found (source scan + build warning)
      reason   : str    -- present when not verified
    """
    build = run_lean_check(lean_path, lake_dir)
    if build.get("tool") == "absent":
        return {"verified": False, "checked": False, "build": build,
                "forbidden": [], "reason": build.get("reason", "toolchain absent")}

    forbidden: set[str] = set()
    try:
        forbidden |= set(scan_forbidden(Path(lean_path).read_text(encoding="utf-8", errors="replace")))
    except Exception:
        pass
    blob = (build.get("stdout", "") + "\n" + build.get("stderr", ""))
    if _SORRY_WARNING.search(blob):
        forbidden.add("sorry")

    if not build.get("ok"):
        return {"verified": False, "checked": True, "build": build,
                "forbidden": sorted(forbidden), "reason": "lean build failed"}
    if forbidden:
        return {"verified": False, "checked": True, "build": build,
                "forbidden": sorted(forbidden),
                "reason": f"build succeeded but contains {sorted(forbidden)} (unsound as a proof)"}
    return {"verified": True, "checked": True, "build": build, "forbidden": []}


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Lean kernel check + soundness scan.")
    ap.add_argument("lean", type=Path)
    ap.add_argument("--lake-dir", type=Path, default=None)
    args = ap.parse_args()
    result = lean_verify(args.lean, args.lake_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result.get("verified") else 1)
