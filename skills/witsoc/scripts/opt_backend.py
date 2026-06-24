#!/usr/bin/env python3
"""W4 optimization backend — `witsoc opt`.

The last roadmap drivers: ILP and SDP on the same certificate discipline as
the SAT backend — exact arithmetic, honest budgets, independent verification,
graceful degradation when industrial solvers are absent.

  ilp        EXACT integer linear programming over bounded variables: a
             pure-Python branch-and-bound (integer arithmetic only, interval
             pruning on constraints and the objective bound) for small
             instances on a bare machine; a node budget makes exhaustion an
             honest UNKNOWN. Optima carry the assignment AND an exhaustive
             optimality claim only when the search completed. External MILP
             solvers (pulp/scipy/mip) are reported by `solvers` and slot in
             when installed.
  sdp-round  the witsoc half of the SDP-discovery chain designed in W4:
             take ANY numeric candidate matrix (cvxpy/CSDP/SDPA output),
             round to rationals (bounded denominators), and verify PSD
             EXACTLY via flag_algebra_backend's rational elimination — the
             numeric solver proposes, the exact check disposes.
  solvers    what is installed (cvxpy/scipy/pulp/mip), with the activation
             chain for each.

Trust: ilp optima are CHECKED-grade certificates (re-verifiable by replay);
sdp-round emits an exactly-verified PSD certificate or an honest rejection.
"""

from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from flag_algebra_backend import is_psd_exact  # noqa: E402

DEFAULT_NODE_BUDGET = 200_000


# --- exact ILP --------------------------------------------------------------------
def _constraint_range(coeffs: dict[str, int], assigned: dict[str, int],
                      bounds: dict[str, tuple[int, int]]) -> tuple[int, int]:
    lo = hi = 0
    for var, c in coeffs.items():
        if var in assigned:
            lo += c * assigned[var]
            hi += c * assigned[var]
        else:
            a, b = bounds[var]
            lo += min(c * a, c * b)
            hi += max(c * a, c * b)
    return lo, hi


def _feasible_partial(constraints: list[dict], assigned: dict[str, int],
                      bounds: dict[str, tuple[int, int]]) -> bool:
    for con in constraints:
        lo, hi = _constraint_range(con["coeffs"], assigned, bounds)
        op, rhs = con["op"], con["rhs"]
        if op == "<=" and lo > rhs:
            return False
        if op == ">=" and hi < rhs:
            return False
        if op == "==" and (lo > rhs or hi < rhs):
            return False
    return True


def solve_ilp(spec: dict, node_budget: int = DEFAULT_NODE_BUDGET) -> dict:
    """Branch-and-bound over bounded integer variables. Exact by construction;
    completing the search makes the optimum an EXHAUSTIVE claim, a budget stop
    is an honest UNKNOWN with the incumbent."""
    bounds = {str(v): (int(lo), int(hi)) for v, (lo, hi) in spec["vars"].items()}
    constraints = [{"coeffs": {str(k): int(c) for k, c in con["coeffs"].items()},
                    "op": str(con["op"]), "rhs": int(con["rhs"])}
                   for con in spec.get("constraints", [])]
    objective = spec.get("objective")
    sense = str(objective.get("sense", "max")) if objective else "max"
    obj_coeffs = ({str(k): int(c) for k, c in objective["coeffs"].items()}
                  if objective else {})
    order = sorted(bounds, key=lambda v: bounds[v][1] - bounds[v][0])  # smallest domain first
    state = {"nodes": 0, "best": None, "best_value": None, "exhausted": True}

    def obj_value(assigned: dict[str, int]) -> int:
        return sum(c * assigned[v] for v, c in obj_coeffs.items())

    def obj_bound(assigned: dict[str, int]) -> int:
        """Optimistic bound for pruning."""
        lo, hi = _constraint_range(obj_coeffs, assigned, bounds)
        return hi if sense == "max" else lo

    def better(value: int) -> bool:
        if state["best_value"] is None:
            return True
        return value > state["best_value"] if sense == "max" else value < state["best_value"]

    def search(idx: int, assigned: dict[str, int]) -> None:
        state["nodes"] += 1
        if state["nodes"] > node_budget:
            state["exhausted"] = False
            return
        if not _feasible_partial(constraints, assigned, bounds):
            return
        if obj_coeffs and state["best_value"] is not None and not better(obj_bound(assigned)):
            return
        if idx == len(order):
            value = obj_value(assigned) if obj_coeffs else 0
            if better(value):
                state["best"] = dict(assigned)
                state["best_value"] = value
            return
        var = order[idx]
        a, b = bounds[var]
        values = range(b, a - 1, -1) if (sense == "max" and obj_coeffs.get(var, 0) > 0) else range(a, b + 1)
        for val in values:
            if state["nodes"] > node_budget:
                state["exhausted"] = False
                return
            assigned[var] = val
            search(idx + 1, assigned)
            del assigned[var]

    search(0, {})
    if state["best"] is None:
        verdict = "INFEASIBLE" if state["exhausted"] else "UNKNOWN"
    else:
        verdict = ("OPTIMAL" if state["exhausted"] else "INCUMBENT") if obj_coeffs else "FEASIBLE"
    return {
        "schema": "witsoc.ilp_certificate.v1",
        "verdict": verdict,
        "assignment": state["best"],
        "objective_value": state["best_value"],
        "nodes_explored": state["nodes"],
        "search_exhausted": state["exhausted"],
        "trust": ("CHECKED" if verdict in ("OPTIMAL", "FEASIBLE", "INFEASIBLE") else "OPEN"),
        "note": ("OPTIMAL/INFEASIBLE are exhaustive claims (the search completed); "
                 "INCUMBENT/UNKNOWN are honest budget stops — install a MILP solver "
                 "(`witsoc opt solvers`) for scale"),
    }


# --- SDP rounding + exact verification ----------------------------------------------
def sdp_round(matrix: list[list[Any]], max_denominator: int = 1000) -> dict:
    """Numeric candidate -> rational matrix (bounded denominators, symmetrized)
    -> EXACT PSD verdict. The numeric solver proposes; the exact check disposes."""
    n = len(matrix)
    rational = [[Fraction(matrix[i][j]).limit_denominator(max_denominator)
                 for j in range(n)] for i in range(n)]
    for i in range(n):  # symmetrize the rounding noise away
        for j in range(i + 1, n):
            avg = (rational[i][j] + rational[j][i]) / 2
            rational[i][j] = rational[j][i] = avg
    verdict = is_psd_exact(rational)
    return {
        "schema": "witsoc.sdp_round_certificate.v1",
        "size": n,
        "max_denominator": max_denominator,
        "rational_matrix": [[str(x) for x in row] for row in rational],
        "psd_exact": bool(verdict.get("psd")),
        "detail": verdict,
        "trust": "CHECKED" if verdict.get("psd") else "REJECTED",
        "note": ("an exactly-PSD rational matrix is certificate-grade; feed it to "
                 "flag_algebra_backend verify-bound for a full SOS/flag certificate. "
                 "A rejection means round tighter (--max-denominator) or re-solve."),
    }


def solver_status() -> dict:
    out = {}
    for mod, role in (("cvxpy", "SDP solve (discovery half of the chain)"),
                      ("scipy", "LP relaxations / numeric linear algebra"),
                      ("pulp", "MILP at scale"), ("mip", "MILP at scale")):
        try:
            __import__(mod)
            out[mod] = {"installed": True, "role": role}
        except ImportError:
            out[mod] = {"installed": False, "role": role,
                        "install": f"pip install {mod}"}
    return {"schema": "witsoc.opt_solvers.v1", "solvers": out,
            "chain": ("numeric solve (cvxpy/CSDP/external) -> `witsoc opt sdp-round` "
                      "(rational + exact PSD) -> flag_algebra verify-bound; "
                      "ILP: built-in exact B&B for small instances, MILP solver for scale")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_i = sub.add_parser("ilp")
    p_i.add_argument("--spec-json", default=None, help="inline spec JSON")
    p_i.add_argument("--spec-file", type=Path, default=None)
    p_i.add_argument("--node-budget", type=int, default=DEFAULT_NODE_BUDGET)
    p_s = sub.add_parser("sdp-round")
    p_s.add_argument("--matrix-json", required=True, help="numeric matrix as JSON rows")
    p_s.add_argument("--max-denominator", type=int, default=1000)
    sub.add_parser("solvers")
    args = ap.parse_args()

    if args.cmd == "ilp":
        if args.spec_json:
            spec = json.loads(args.spec_json)
        elif args.spec_file:
            spec = json.loads(args.spec_file.read_text(encoding="utf-8"))
        else:
            raise SystemExit("ilp needs --spec-json or --spec-file")
        result = solve_ilp(spec, args.node_budget)
    elif args.cmd == "sdp-round":
        result = sdp_round(json.loads(args.matrix_json), args.max_denominator)
    else:
        result = solver_status()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("trust") != "OPEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
