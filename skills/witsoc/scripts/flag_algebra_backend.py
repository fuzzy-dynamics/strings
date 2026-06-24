#!/usr/bin/env python3
"""Flag-algebra / SOS certificate backend for Witsoc (exact verifier).

Extremal (Turan/Erdos-type) density bounds are routinely proved by Razborov's
flag-algebra method: an SDP produces a positive-semidefinite matrix Q such that

    (objective_form - bound)  =  <Q, flag_products>  +  nonnegative residual.

There are two halves with very different trust profiles:

  FINDING Q   -- needs a floating-point SDP solver (CSDP / SDPA / cvxpy). This is
                 numerical and untrusted on its own.
  VERIFYING Q -- given a *rational* Q and the flag identity, the check is exact
                 integer/rational arithmetic: Q is PSD and the coefficients match.
                 This is the sound part, and it is what makes a flag-algebra proof
                 machine-checkable.

This module implements the sound half completely and detects external solvers for
the finding half. The verifier is the moat: a numerically-found Q must be rounded
to rationals and pass `verify-bound` here before any bound is claimed CHECKED.

Subcommands:
  psd-check    --matrix '<json nxn rationals>'         exact PSD test
  verify-bound --certificate '<json>' [--file path]     exact SOS/flag certificate
  solvers                                                report SDP solver availability
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from fractions import Fraction
from typing import Any


def to_fraction(x: Any) -> Fraction:
    if isinstance(x, str):
        return Fraction(x)
    if isinstance(x, list) and len(x) == 2:  # [num, den]
        return Fraction(int(x[0]), int(x[1]))
    return Fraction(x)


def parse_matrix(raw: Any) -> list[list[Fraction]]:
    mat = [[to_fraction(v) for v in row] for row in raw]
    n = len(mat)
    if any(len(row) != n for row in mat):
        raise ValueError("matrix must be square")
    return mat


def is_symmetric(mat: list[list[Fraction]]) -> bool:
    n = len(mat)
    return all(mat[i][j] == mat[j][i] for i in range(n) for j in range(i + 1, n))


def is_psd_exact(mat: list[list[Fraction]]) -> dict[str, Any]:
    """Exact PSD test via symmetric Gaussian elimination over the rationals.

    A symmetric matrix is PSD iff this elimination completes with every pivot
    >= 0 and every zero pivot occurring in an all-zero remaining row/column
    (a zero pivot with a nonzero off-diagonal forces a negative 2x2 minor).
    """
    n = len(mat)
    if not is_symmetric(mat):
        return {"psd": False, "reason": "matrix is not symmetric"}
    a = [row[:] for row in mat]
    pivots: list[str] = []
    for k in range(n):
        piv = a[k][k]
        if piv < 0:
            return {"psd": False, "reason": f"negative pivot at index {k}: {piv}"}
        if piv == 0:
            # remaining row/col must be all zero
            for j in range(k, n):
                if a[k][j] != 0 or a[j][k] != 0:
                    return {"psd": False, "reason": f"zero pivot with nonzero entry ({k},{j}) -> negative minor"}
            pivots.append("0")
            continue
        pivots.append(str(piv))
        for i in range(k + 1, n):
            if a[i][k] == 0:
                continue
            factor = a[i][k] / piv
            for j in range(k, n):
                a[i][j] -= factor * a[k][j]
    return {"psd": True, "pivots": pivots, "method": "exact symmetric (LDL^T) elimination"}


def cmd_psd_check(raw: Any) -> dict[str, Any]:
    mat = parse_matrix(raw)
    result = is_psd_exact(mat)
    result["n"] = len(mat)
    result["claim_status"] = "CHECKED"
    return result


def cmd_verify_bound(cert: dict[str, Any]) -> dict[str, Any]:
    """Verify an exact SOS/flag-algebra certificate.

    Certificate schema:
      Q            : nxn rational matrix (SOS coefficient matrix)
      entry_key    : nxn matrix of monomial/flag keys; Q[i][j] contributes to entry_key[i][j]
      target       : {key: rational} coefficients of (objective_form - bound)
      nonneg_keys  : keys whose monomial/flag is known >= 0 (residual may stay >= 0)
                     all other keys must match exactly (residual == 0)
    """
    Q = parse_matrix(cert["Q"])
    entry_key = cert["entry_key"]
    n = len(Q)
    if len(entry_key) != n or any(len(r) != n for r in entry_key):
        return {"valid": False, "reason": "entry_key shape mismatch"}

    psd = is_psd_exact(Q)
    if not psd["psd"]:
        return {"valid": False, "reason": f"Q not PSD: {psd['reason']}", "psd": psd}

    contribution: dict[str, Fraction] = {}
    for i in range(n):
        for j in range(n):
            key = entry_key[i][j]
            contribution[key] = contribution.get(key, Fraction(0)) + Q[i][j]

    target = {k: to_fraction(v) for k, v in cert.get("target", {}).items()}
    nonneg = set(cert.get("nonneg_keys", []))
    keys = set(contribution) | set(target)

    violations = []
    for key in sorted(keys):
        residual = target.get(key, Fraction(0)) - contribution.get(key, Fraction(0))
        if key in nonneg:
            if residual < 0:
                violations.append({"key": key, "residual": str(residual), "rule": "must be >= 0"})
        else:
            if residual != 0:
                violations.append({"key": key, "residual": str(residual), "rule": "must be 0"})

    valid = not violations
    return {
        "valid": valid,
        "psd": psd,
        "violations": violations,
        "claim_status": "RECEIPT_ACCEPTED" if valid else "REJECTED",
        "scope": "exact verification of the flag/SOS certificate (Q PSD and exact "
                 "coefficient identity); proves the stated density bound given the "
                 "supplied flag products.",
    }


def cmd_solvers() -> dict[str, Any]:
    return {
        "external_sdp_solvers": {
            "csdp": bool(shutil.which("csdp")),
            "sdpa": bool(shutil.which("sdpa")),
            "cvxpy": importlib.util.find_spec("cvxpy") is not None,
            "numpy": importlib.util.find_spec("numpy") is not None,
        },
        "note": "Finding Q needs one of these (numerical). Verification here is exact "
                "and needs none of them. Round a numerical Q to rationals, then run "
                "`verify-bound` before claiming a flag-algebra bound.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_psd = sub.add_parser("psd-check")
    p_psd.add_argument("--matrix", required=True, help="JSON nxn matrix of rationals.")

    p_vb = sub.add_parser("verify-bound")
    p_vb.add_argument("--certificate", help="Inline JSON certificate.")
    p_vb.add_argument("--file", help="Path to JSON certificate.")

    sub.add_parser("solvers")

    args = parser.parse_args()
    if args.cmd == "psd-check":
        out = cmd_psd_check(json.loads(args.matrix))
    elif args.cmd == "verify-bound":
        if args.file:
            cert = json.loads(open(args.file, encoding="utf-8").read())
        elif args.certificate:
            cert = json.loads(args.certificate)
        else:
            parser.error("verify-bound needs --certificate or --file")
        out = cmd_verify_bound(cert)
    elif args.cmd == "solvers":
        out = cmd_solvers()
    else:
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("valid", True) and out.get("psd", True) not in (False,) else 2


if __name__ == "__main__":
    raise SystemExit(main())
