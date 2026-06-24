#!/usr/bin/env python3
"""External decision-procedure kernels for Witsoc certificate re-checking.

Locates and drives SMT/SAT kernels so that a `sat`/`smt` certificate can be
*independently re-decided* instead of trusted. Every entry point degrades
gracefully: if no kernel is available it reports `available: False` with a
reason, and the caller records UNCHECKED (a visible non-pass), never a silent
pass.

z3 resolution order (first hit wins):
  1. WITSOC_KERNEL_PYTHON  — a python with the `z3` module (set by setup_kernels.sh)
  2. ~/.witsoc/kernels-venv/bin/python — the default kernel venv
  3. a `z3` CLI on PATH
  4. the current interpreter, if `import z3` works

SAT (DRAT) resolution: a `drat-trim` binary on PATH.

CLI:
  kernel_tools.py status                     -> JSON of what is installed
  kernel_tools.py smt --expect unsat < f.smt -> decide an SMT-LIB problem
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_KERNEL_VENV = Path.home() / ".witsoc" / "kernels-venv"

# Driver run *inside* a kernel python: read SMT-LIB on stdin, print the verdict.
_Z3_DRIVER = (
    "import sys, z3\n"
    "s = z3.Solver()\n"
    "s.from_string(sys.stdin.read())\n"
    "print(str(s.check()))\n"
)


def _python_with_z3() -> tuple[str, str] | None:
    """Return (python_path, source_label) for an interpreter that imports z3."""
    candidates: list[tuple[str | None, str]] = [
        (os.environ.get("WITSOC_KERNEL_PYTHON"), "WITSOC_KERNEL_PYTHON"),
        (str(DEFAULT_KERNEL_VENV / "bin" / "python"), "kernel-venv"),
        (sys.executable, "current-interpreter"),
    ]
    for py, label in candidates:
        if not py or not Path(py).exists():
            continue
        try:
            r = subprocess.run([py, "-c", "import z3"], capture_output=True, timeout=20, check=False)
        except Exception:
            continue
        if r.returncode == 0:
            return py, label
    return None


def have_z3() -> dict[str, Any]:
    cli = shutil.which("z3")
    py = _python_with_z3()
    return {"cli": cli, "python": (py[0] if py else None), "python_source": (py[1] if py else None),
            "available": bool(cli or py)}


def solve_smt(smtlib: str, expect: str = "unsat", timeout: float = 120.0) -> dict[str, Any]:
    """Independently decide an SMT-LIB problem. Returns available/verdict/ok/backend."""
    expect = expect.lower().strip()
    # Prefer the Python module (most portable across z3 builds); fall back to CLI.
    py = _python_with_z3()
    if py:
        try:
            r = subprocess.run([py[0], "-c", _Z3_DRIVER], input=smtlib, text=True,
                               capture_output=True, timeout=timeout, check=False)
            verdict = (r.stdout.strip().splitlines() or [""])[-1].strip().lower()
            if verdict in ("sat", "unsat", "unknown"):
                return {"available": True, "verdict": verdict, "ok": verdict == expect,
                        "backend": f"z3-python ({py[1]})"}
        except subprocess.TimeoutExpired:
            return {"available": True, "verdict": "timeout", "ok": False, "backend": "z3-python"}
        except Exception:
            pass
    cli = shutil.which("z3")
    if cli:
        try:
            r = subprocess.run([cli, "-in"], input=smtlib, text=True,
                               capture_output=True, timeout=timeout, check=False)
            verdict = (r.stdout.strip().splitlines() or [""])[0].strip().lower()
            if verdict in ("sat", "unsat", "unknown"):
                return {"available": True, "verdict": verdict, "ok": verdict == expect, "backend": "z3-cli"}
        except subprocess.TimeoutExpired:
            return {"available": True, "verdict": "timeout", "ok": False, "backend": "z3-cli"}
        except Exception:
            pass
    return {"available": False, "verdict": None, "ok": False,
            "backend": None, "reason": "no z3 (run setup_kernels.sh)"}


def check_drat(cnf: Path, drat: Path, timeout: float = 300.0) -> dict[str, Any]:
    """Independently check a DRAT UNSAT proof against its DIMACS CNF."""
    tool = shutil.which("drat-trim")
    if not tool:
        return {"available": False, "ok": False, "reason": "drat-trim not installed"}
    try:
        r = subprocess.run([tool, str(cnf), str(drat)], text=True,
                           capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"available": True, "ok": False, "reason": "drat-trim timeout"}
    ok = "s VERIFIED" in r.stdout
    return {"available": True, "ok": ok, "backend": "drat-trim",
            "detail": "VERIFIED" if ok else "not verified"}


def toolchain_status() -> dict[str, Any]:
    return {
        "z3": have_z3(),
        "cvc5": {"cli": shutil.which("cvc5")},
        "drat_trim": {"cli": shutil.which("drat-trim")},
        "sat_solvers": {name: shutil.which(name) for name in ("cadical", "kissat", "minisat")},
        "pari_gp": {"cli": shutil.which("gp")},
        "lean": {"cli": shutil.which("lean"), "lake": shutil.which("lake")},
        "kernel_venv": str(DEFAULT_KERNEL_VENV) if DEFAULT_KERNEL_VENV.exists() else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p_smt = sub.add_parser("smt")
    p_smt.add_argument("--expect", default="unsat")
    p_smt.add_argument("--file", type=Path, default=None)
    args = ap.parse_args()

    if args.cmd == "status":
        print(json.dumps(toolchain_status(), indent=2))
        return 0
    if args.cmd == "smt":
        text = args.file.read_text(encoding="utf-8") if args.file else sys.stdin.read()
        result = solve_smt(text, args.expect)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
