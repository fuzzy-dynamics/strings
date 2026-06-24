#!/usr/bin/env python3
"""Independent certificate re-checker for Witsoc/Lovasz proof DAGs.

A proof DAG node may *claim* a machine-checkable status (VERIFIED / CHECKED).
This script does not trust that claim: for every such node it locates the
attached certificate and re-runs the appropriate independent checker from
scratch, then writes a PASS / FAIL / UNCHECKED verdict per node into
`certificate_recheck.json`. The DAG integrity validator consumes that ledger and
refuses to pass a node that claims a machine status without a re-checked PASS.

This is the "kernel in the loop" piece: truth comes from a checker that re-runs,
not from an LLM (or an earlier tool) asserting the result.

Certificate kinds (node["certificate"]["kind"], or inferred):
  lean            {lean_path, lake_dir?}            -> lean_check.lean_verify (build + sorry/axiom scan)
  number_theory   {identity:{type,...}}             -> exact integer/Fraction re-evaluation (this file)
  discovery       {evaluator, params, object}       -> discovery_evaluators.<E>.verify (independent scan)
  python_assert   {code}                            -> run asserts in a subprocess (best-effort)
  sat             {dimacs, drat}                     -> drat-trim if installed, else UNCHECKED
  smt             {smtlib, expect:"unsat"}           -> z3 if installed, else UNCHECKED

Inference when no explicit certificate: a node whose artifacts include a `.lean`
file is treated as a lean certificate.

Results:
  PASS        the checker re-ran and confirmed the claim
  FAIL        the checker re-ran and refuted the claim (or the cert is malformed)
  UNCHECKED   no re-checkable certificate, or the required external tool is absent
              (never a silent pass — UNCHECKED is a visible non-pass)

Caching: expensive checks (Lean builds) are memoised by a content hash in
`<run>/.recheck_cache.json`; only nodes that claim a machine status or carry a
certificate are ever checked.

Usage:
  recheck_certificates.py <run_dir> [--no-cache] [--out certificate_recheck.json]
Exit code: 0 if no FAILs, 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kernel_tools  # noqa: E402  -- SMT/SAT kernels with graceful degradation
from lean_check import lean_verify  # noqa: E402

# Statuses that assert a machine-level guarantee and therefore REQUIRE a
# re-checked certificate. Softer accepted statuses (PROVED_SKETCH, PARTIAL,
# CONDITIONAL) are honest about being non-mechanical and are not gated here.
MACHINE_STATUS = {"VERIFIED", "CHECKED"}

PASS, FAIL, UNCHECKED = "PASS", "FAIL", "UNCHECKED"


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------
def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


from witcore import records  # noqa: E402  -- shared substrate, was a local copy

def node_id(node: dict) -> str:
    return str(node.get("node_id") or node.get("id") or "")


# ---------------------------------------------------------------------------
# Independent number-theory re-check (reimplemented here on purpose, so it does
# not trust the producer's arithmetic — only Python integers and Fractions).
# ---------------------------------------------------------------------------
_MR_BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    for p in _MR_BASES:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for a in _MR_BASES:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def recheck_number_theory(identity: dict) -> tuple[str, str]:
    t = str(identity.get("type") or "")
    try:
        if t == "erdos_straus":
            n, x, y, z = (int(identity[k]) for k in ("n", "x", "y", "z"))
            if min(x, y, z) <= 0 or n < 2:
                return FAIL, "erdos_straus: non-positive denominator"
            lhs = Fraction(1, x) + Fraction(1, y) + Fraction(1, z)
            ok = lhs == Fraction(4, n)
            return (PASS if ok else FAIL), f"1/{x}+1/{y}+1/{z} {'==' if ok else '!='} 4/{n}"
        if t == "factorization":
            n = int(identity["n"])
            factors = {int(p): int(e) for p, e in dict(identity["factors"]).items()}
            prod = 1
            for p, e in factors.items():
                prod *= p ** e
            if prod != n:
                return FAIL, f"product of factors {prod} != n {n}"
            bad = [p for p in factors if not _is_prime(p)]
            if bad:
                return FAIL, f"composite 'prime' factors {bad}"
            return PASS, f"product equals {n} and all factors prime"
        if t == "sigma":
            n = int(identity["n"])
            factors = {int(p): int(e) for p, e in dict(identity["factors"]).items()}
            prod = 1
            sigma = 1
            for p, e in factors.items():
                prod *= p ** e
                sigma *= (p ** (e + 1) - 1) // (p - 1)
            if prod != n:
                return FAIL, f"factorization product {prod} != n {n}"
            if int(identity.get("sigma", -1)) != sigma:
                return FAIL, f"claimed sigma {identity.get('sigma')} != recomputed {sigma}"
            return PASS, f"sigma({n}) = {sigma} recomputed from factorization"
        if t == "linear_identity":  # generic: sum(coeff*term) == rhs over the rationals
            lhs = sum(Fraction(str(c)) for c in identity.get("lhs_terms", []))
            rhs = Fraction(str(identity.get("rhs", 0)))
            ok = lhs == rhs
            return (PASS if ok else FAIL), f"lhs {lhs} {'==' if ok else '!='} rhs {rhs}"
    except (KeyError, ValueError, ZeroDivisionError, TypeError) as exc:
        return FAIL, f"malformed number_theory certificate: {exc}"
    return UNCHECKED, f"unknown number_theory identity type {t!r}"


# ---------------------------------------------------------------------------
# Independent discovery re-check (re-runs the deterministic evaluator's verify).
# ---------------------------------------------------------------------------
def recheck_discovery(cert: dict) -> tuple[str, str]:
    try:
        from discovery_evaluators import get_evaluator
    except Exception as exc:  # pragma: no cover
        return UNCHECKED, f"discovery_evaluators unavailable: {exc}"
    try:
        ev = get_evaluator(str(cert["evaluator"]))
        result = ev.verify(cert["object"], dict(cert.get("params", {})))
    except SystemExit as exc:
        return FAIL, f"unknown evaluator: {exc}"
    except (KeyError, TypeError, ValueError) as exc:
        return FAIL, f"malformed discovery certificate: {exc}"
    if result.get("ok"):
        return PASS, f"{cert['evaluator']} verify: {result.get('method', 'ok')}"
    return FAIL, f"{cert['evaluator']} verify rejected: {result.get('reason')}"


# ---------------------------------------------------------------------------
# python_assert re-check (best-effort; not a hostile-code sandbox).
# ---------------------------------------------------------------------------
def recheck_python_assert(cert: dict) -> tuple[str, str]:
    code = cert.get("code")
    if not isinstance(code, str) or "assert" not in code:
        return FAIL, "python_assert certificate missing code or has no assert"
    try:
        proc = subprocess.run([sys.executable, "-I", "-c", code], text=True,
                              capture_output=True, timeout=float(cert.get("timeout", 30)), check=False)
    except subprocess.TimeoutExpired:
        return FAIL, "python_assert timed out"
    if proc.returncode == 0:
        return PASS, "python asserts passed"
    return FAIL, f"python asserts failed: {proc.stderr.strip().splitlines()[-1:] or ''}"


# ---------------------------------------------------------------------------
# External-tool re-checks (graceful UNCHECKED when the tool is absent).
# ---------------------------------------------------------------------------
def recheck_sat(cert: dict, run: Path) -> tuple[str, str]:
    dimacs = _resolve_path(cert.get("dimacs"), run)
    drat = _resolve_path(cert.get("drat"), run)
    if not (dimacs and drat and dimacs.exists() and drat.exists()):
        return FAIL, "sat certificate missing dimacs/drat file"
    res = kernel_tools.check_drat(dimacs, drat)
    if not res.get("available"):
        return UNCHECKED, res.get("reason", "drat-trim not installed")
    return (PASS if res.get("ok") else FAIL), res.get("detail", "drat-trim")


def recheck_smt(cert: dict, run: Path) -> tuple[str, str]:
    smt = cert.get("smtlib")
    expect = str(cert.get("expect", "unsat")).lower()
    inp = None
    if isinstance(smt, str) and "\n" in smt:
        inp = smt
    else:
        p = _resolve_path(smt, run)
        if p and p.exists():
            inp = p.read_text(encoding="utf-8")
    if inp is None:
        return FAIL, "smt certificate missing smtlib text/file"
    res = kernel_tools.solve_smt(inp, expect)
    if not res.get("available"):
        return UNCHECKED, res.get("reason", "no SMT kernel; run setup_kernels.sh")
    return (PASS if res.get("ok") else FAIL), f"{res.get('backend')} said {res.get('verdict')!r}, expected {expect!r}"


def _resolve_path(value: Any, run: Path) -> Path | None:
    if not value:
        return None
    p = Path(str(value))
    return p if p.is_absolute() else (run / p)


# ---------------------------------------------------------------------------
# Certificate resolution + dispatch
# ---------------------------------------------------------------------------
def resolve_certificate(node: dict, run: Path) -> dict | None:
    cert = node.get("certificate")
    if isinstance(cert, dict) and cert.get("kind"):
        return cert
    cert_file = node.get("certificate_file")
    if cert_file:
        loaded = load(_resolve_path(cert_file, run) or Path(str(cert_file)), None)
        if isinstance(loaded, dict) and loaded.get("kind"):
            return loaded
    # Inference: a .lean artifact is a lean certificate even without an explicit block.
    for artifact in node.get("artifacts") or []:
        if str(artifact).endswith(".lean"):
            return {"kind": "lean", "lean_path": str(artifact)}
    return None


def cert_cache_key(cert: dict, run: Path) -> str:
    payload = json.dumps(cert, sort_keys=True, ensure_ascii=False)
    h = hashlib.sha256(payload.encode("utf-8"))
    # For Lean, fold in file content so editing the proof invalidates the cache.
    if cert.get("kind") == "lean":
        lp = _resolve_path(cert.get("lean_path"), run)
        if lp and lp.exists():
            h.update(lp.read_bytes())
    return h.hexdigest()


def run_certificate(cert: dict, run: Path) -> tuple[str, str, str]:
    """Return (result, checker, detail) for one certificate."""
    kind = str(cert.get("kind"))
    if kind == "lean":
        lp = _resolve_path(cert.get("lean_path"), run)
        if not lp or not lp.exists():
            return FAIL, "lean", f"lean_path missing: {cert.get('lean_path')}"
        ld = _resolve_path(cert.get("lake_dir"), run) if cert.get("lake_dir") else None
        res = lean_verify(lp, ld)
        if res.get("verified"):
            return PASS, "lean", "lake/lean build green and sorry/axiom-free"
        if not res.get("checked"):
            return UNCHECKED, "lean", res.get("reason", "lean toolchain absent")
        return FAIL, "lean", res.get("reason", "lean verification failed")
    if kind == "number_theory":
        result, detail = recheck_number_theory(dict(cert.get("identity") or cert))
        return result, "number_theory", detail
    if kind == "discovery":
        result, detail = recheck_discovery(cert)
        return result, "discovery", detail
    if kind == "python_assert":
        result, detail = recheck_python_assert(cert)
        return result, "python_assert", detail
    if kind == "sat":
        result, detail = recheck_sat(cert, run)
        return result, "sat", detail
    if kind == "smt":
        result, detail = recheck_smt(cert, run)
        return result, "smt", detail
    return UNCHECKED, "none", f"unknown certificate kind {kind!r}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--out", type=Path, default=None, help="default: <run_dir>/certificate_recheck.json")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    run = args.run_dir
    out = args.out or (run / "certificate_recheck.json")
    dag = records(run / "proof_dependency_dag.json")

    cache_path = run / ".recheck_cache.json"
    cache: dict[str, Any] = load(cache_path, {}) if not args.no_cache else {}

    verdicts: list[dict] = []
    for node in dag:
        nid = node_id(node)
        if not nid:
            continue
        status = str(node.get("status") or "")
        cert = resolve_certificate(node, run)
        machine = status in MACHINE_STATUS
        if cert is None:
            if machine:
                verdicts.append({"node_id": nid, "status": status, "kind": "none",
                                 "result": UNCHECKED, "checker": "none",
                                 "detail": "node claims a machine status but has no re-checkable certificate"})
            continue
        key = cert_cache_key(cert, run)
        if key in cache:
            cached = cache[key]
            result, checker, detail = cached["result"], cached["checker"], cached["detail"] + " (cached)"
        else:
            result, checker, detail = run_certificate(cert, run)
            cache[key] = {"result": result, "checker": checker, "detail": detail}
        verdicts.append({"node_id": nid, "status": status, "kind": cert.get("kind"),
                         "result": result, "checker": checker, "detail": detail})

    if not args.no_cache:
        try:
            cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception:
            pass

    summary = {
        "schema": "witsoc.certificate_recheck.v1",
        "run_dir": str(run),
        "checked": len(verdicts),
        "pass": sum(1 for v in verdicts if v["result"] == PASS),
        "fail": sum(1 for v in verdicts if v["result"] == FAIL),
        "unchecked": sum(1 for v in verdicts if v["result"] == UNCHECKED),
        "machine_status_nodes": sum(1 for n in dag if str(n.get("status") or "") in MACHINE_STATUS),
        "verdicts": verdicts,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "verdicts"}, indent=2))
    return 1 if summary["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
