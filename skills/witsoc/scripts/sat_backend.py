#!/usr/bin/env python3
"""F1 verified SAT backend — `witsoc sat`.

Computation as a proof weapon: nearly every machine-settled open problem
(Boolean Pythagorean triples, Keller dim 7, Ramsey-type bounds) was a finite
reduction plus massive verified search. This backend makes that route a
first-class witsoc service: per-domain CNF encoders, a solver chain, and
independent verification of BOTH answers:

  SAT    the witness is re-evaluated against every clause in-process
         (witness_verified) — never trusted from the solver;
  UNSAT  an external solver's DRAT proof is re-checked by drat-trim
         (kernel_tools.check_drat); the internal fallback DPLL reports
         `internal_exhaustive` instead (honest lower assurance).

Solver chain: kissat/cadical/minisat on PATH (with DRAT proof logging), else
a built-in pure-Python DPLL with a decision budget — small instances work on
a bare machine; scale needs a real solver (`refutation` says which ran).

Encoders (each instance is one finite mathematical statement with recorded
bounds):
  ramsey --n N --s S --t T   2-coloring of K_N edges with no red K_S / blue K_T
                             (UNSAT at N  =>  R(S,T) <= N)
  vdw    --n N --k K         2-coloring of [N] with no monochromatic K-term AP
                             (UNSAT at N  =>  W(2,K) <= N)
  schur  --n N               2-coloring of [N] with no monochromatic x+y=z
  graph-coloring --k K       proper K-coloring of a graph (--family
                             cycle|complete|grotzsch or --edges "0-1,1-2,...")
                             (UNSAT  =>  chromatic number > K)
  covering --moduli M1,M2..  distinct-moduli covering system: one residue per
                             modulus covering every integer mod lcm
                             (SAT witness = the covering system itself)
  dimacs --file F            raw DIMACS CNF

Cube-and-conquer (--cubes D): split on the D most frequent variables into all
2^D cubes and solve each independently. The split is exhaustive by
construction (every assignment of the chosen variables is a cube), so
all-cubes-UNSAT soundly refutes the whole instance; any SAT cube yields a
witness that is re-verified as usual.

Kernel bridge (--emit-lean / --prove): for vdw and schur the instance's
mathematical meaning is emitted as a decidable Lean statement (`∀ c : Fin n →
Bool, ∃ ...`); --prove hands it to the kernel-gated prover (close_obligation)
with `decide` in the portfolio — a finite check the kernel re-verifies becomes
VERIFIED_LEAN through the prover, never through this backend.

Trust contract: this backend emits CHECKED-grade certificates only (explicit
witness or checked refutation, bounded). Status upgrades happen exclusively
via the prover/validators.
"""

from __future__ import annotations

import argparse
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import kernel_tools  # noqa: E402

EXTERNAL_SOLVERS = ("kissat", "cadical")  # DRAT-capable, exit 10/20 convention
DEFAULT_MAX_DECISIONS = 2_000_000


# --- encoders ------------------------------------------------------------------
def encode_ramsey(n: int, s: int, t: int) -> dict:
    """Edge variables of K_n: var>0 means red. No all-red K_s, no all-blue K_t."""
    edges = {e: i + 1 for i, e in enumerate(itertools.combinations(range(n), 2))}
    clauses = []
    for sub in itertools.combinations(range(n), s):
        clauses.append([-edges[e] for e in itertools.combinations(sub, 2)])  # not all red
    for sub in itertools.combinations(range(n), t):
        clauses.append([edges[e] for e in itertools.combinations(sub, 2)])   # not all blue
    return {
        "num_vars": len(edges), "clauses": clauses,
        "statement": (f"there is a 2-coloring of the edges of K_{n} with no "
                      f"monochromatic red K_{s} and no monochromatic blue K_{t}"),
        "unsat_means": f"R({s},{t}) <= {n}",
        "sat_means": f"R({s},{t}) > {n} (explicit coloring witness)",
        "var_meaning": {str(v): f"edge {e} is red" for e, v in edges.items()},
    }


def encode_vdw(n: int, k: int) -> dict:
    """Variable i+1 = color of integer i+1. No monochromatic k-term AP in [1..n]."""
    clauses = []
    for a in range(1, n + 1):
        for d in range(1, n):
            terms = [a + i * d for i in range(k)]
            if terms[-1] > n:
                break
            clauses.append([-x for x in terms])  # not all color-1
            clauses.append([x for x in terms])   # not all color-0
    return {
        "num_vars": n, "clauses": clauses,
        "statement": (f"there is a 2-coloring of [1..{n}] with no monochromatic "
                      f"{k}-term arithmetic progression"),
        "unsat_means": f"W(2,{k}) <= {n}",
        "sat_means": f"W(2,{k}) > {n} (explicit coloring witness)",
        "lean": _vdw_lean(n) if k == 3 else None,
    }


def encode_schur(n: int) -> dict:
    """Variable i = color of integer i. No monochromatic solution of x+y=z in [1..n]."""
    clauses = []
    for x in range(1, n + 1):
        for y in range(x, n + 1):
            z = x + y
            if z > n:
                break
            trip = sorted({x, y, z})
            clauses.append([-v for v in trip])
            clauses.append([v for v in trip])
    return {
        "num_vars": n, "clauses": clauses,
        "statement": f"there is a 2-coloring of [1..{n}] with no monochromatic x+y=z",
        "unsat_means": f"the 2-color Schur bound S(2) < {n} (every 2-coloring of [1..{n}] has a monochromatic x+y=z)",
        "sat_means": f"[1..{n}] admits a sum-free-style 2-coloring (explicit witness)",
        "lean": _schur_lean(n),
    }


def _vdw_lean(n: int) -> str:
    """The k=3 vdw instance as a decidable Lean statement (kernel bridge)."""
    return (f"∀ c : Fin {n} → Bool, ∃ i j k : Fin {n}, "
            "i < j ∧ j < k ∧ j.val - i.val = k.val - j.val ∧ c i = c j ∧ c j = c k")


def _schur_lean(n: int) -> str:
    """Monochromatic x+y=z (1-indexed via .val+1) as a decidable Lean statement."""
    return (f"∀ c : Fin {n} → Bool, ∃ i j k : Fin {n}, "
            "i ≤ j ∧ (i.val + 1) + (j.val + 1) = k.val + 1 ∧ c i = c j ∧ c j = c k")


def mycielskian(n: int, edges: list[tuple[int, int]]) -> tuple[int, list[tuple[int, int]]]:
    """Mycielski construction: raises chromatic number by 1, stays triangle-free."""
    out = list(edges)
    w = 2 * n
    for u, v in edges:
        out.append((u + n, v))
        out.append((v + n, u))
    for u in range(n):
        out.append((u + n, w))
    return 2 * n + 1, out


GRAPH_FAMILIES = {
    "cycle": lambda n: (n, [(i, (i + 1) % n) for i in range(n)]),
    "complete": lambda n: (n, list(itertools.combinations(range(n), 2))),
    # The Grötzsch graph: Mycielskian of C5 — triangle-free with chromatic number 4.
    "grotzsch": lambda n: mycielskian(5, [(i, (i + 1) % 5) for i in range(5)]),
}


def encode_graph_coloring(n: int, edges: list[tuple[int, int]], k: int, label: str) -> dict:
    """Vertex/color variable v*k+c+1. At least one color per vertex; adjacent
    vertices never share a color. (At-most-one per vertex is unnecessary:
    any satisfying assignment picks a proper coloring.)"""
    var = lambda v, c: v * k + c + 1
    clauses = [[var(v, c) for c in range(k)] for v in range(n)]
    for u, v in edges:
        for c in range(k):
            clauses.append([-var(u, c), -var(v, c)])
    return {
        "num_vars": n * k, "clauses": clauses,
        "statement": f"the graph {label} ({n} vertices, {len(edges)} edges) has a proper {k}-coloring",
        "unsat_means": f"chromatic number of {label} > {k}",
        "sat_means": f"chromatic number of {label} <= {k} (explicit coloring witness)",
    }


def encode_covering(moduli: list[int]) -> dict:
    """Residue-choice variables x[i][r] for each modulus m_i: exactly one
    residue per modulus, and every n in [0, lcm) covered by some chosen class."""
    import math
    lcm = 1
    for m in moduli:
        lcm = lcm * m // math.gcd(lcm, m)
    var_index: dict[tuple[int, int], int] = {}
    for i, m in enumerate(moduli):
        for r in range(m):
            var_index[(i, r)] = len(var_index) + 1
    clauses = []
    for i, m in enumerate(moduli):
        choices = [var_index[(i, r)] for r in range(m)]
        clauses.append(choices)  # at least one residue
        for a, b in itertools.combinations(choices, 2):
            clauses.append([-a, -b])  # at most one residue
    for n in range(lcm):
        clauses.append([var_index[(i, n % m)] for i, m in enumerate(moduli)])
    return {
        "num_vars": len(var_index), "clauses": clauses,
        "statement": f"there is a covering system with moduli {moduli} (one residue class per modulus covering Z)",
        "unsat_means": f"no covering system exists with moduli {moduli}",
        "sat_means": f"a covering system with moduli {moduli} exists (the witness IS the system)",
        "var_meaning": {str(v): f"residue {r} chosen for modulus {moduli[i]}"
                        for (i, r), v in var_index.items()},
    }


def encode_dimacs(path: Path) -> dict:
    num_vars, clauses, cur = 0, [], []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith(("c", "%")):
            continue
        if line.startswith("p"):
            parts = line.split()
            num_vars = int(parts[2])
            continue
        for tok in line.split():
            lit = int(tok)
            if lit == 0:
                if cur:
                    clauses.append(cur)
                cur = []
            else:
                cur.append(lit)
    if cur:
        clauses.append(cur)
    return {"num_vars": num_vars, "clauses": clauses,
            "statement": f"the DIMACS instance {path.name} is satisfiable",
            "unsat_means": f"{path.name} is unsatisfiable",
            "sat_means": f"{path.name} is satisfiable (witness)"}


# --- solving -------------------------------------------------------------------
def to_dimacs(num_vars: int, clauses: list[list[int]]) -> str:
    lines = [f"p cnf {num_vars} {len(clauses)}"]
    lines += [" ".join(map(str, c)) + " 0" for c in clauses]
    return "\n".join(lines) + "\n"


def verify_witness(clauses: list[list[int]], witness: dict[int, bool]) -> bool:
    """Independent in-process check: every clause has a satisfied literal."""
    return all(any(witness.get(abs(lit), False) == (lit > 0) for lit in c) for c in clauses)


def solve_internal(num_vars: int, clauses: list[list[int]], max_decisions: int) -> dict:
    """Pure-Python DPLL with unit propagation. For small instances on a bare
    machine; exceeding the decision budget is an honest UNKNOWN."""
    stats = {"decisions": 0}

    def propagate(cls: list[list[int]], assign: dict[int, bool]):
        changed = True
        while changed:
            changed = False
            next_cls = []
            for c in cls:
                unassigned, satisfied = [], False
                for lit in c:
                    val = assign.get(abs(lit))
                    if val is None:
                        unassigned.append(lit)
                    elif val == (lit > 0):
                        satisfied = True
                        break
                if satisfied:
                    continue
                if not unassigned:
                    return None, None  # conflict
                if len(unassigned) == 1:
                    lit = unassigned[0]
                    assign[abs(lit)] = lit > 0
                    changed = True
                else:
                    next_cls.append(unassigned)
            cls = next_cls
        return cls, assign

    def search(cls: list[list[int]], assign: dict[int, bool]):
        cls, assign = propagate(cls, dict(assign))
        if cls is None:
            return None
        if not cls:
            return assign
        if stats["decisions"] >= max_decisions:
            raise TimeoutError
        stats["decisions"] += 1
        var = abs(cls[0][0])
        for value in (True, False):
            result = search(cls, {**assign, var: value})
            if result is not None:
                return result
        return None

    sys.setrecursionlimit(max(10000, num_vars * 4 + 1000))
    try:
        model = search(clauses, {})
    except TimeoutError:
        return {"result": "UNKNOWN", "solver": "internal-dpll",
                "reason": f"decision budget {max_decisions} exhausted", **stats}
    if model is None:
        return {"result": "UNSAT", "solver": "internal-dpll",
                "refutation": "internal_exhaustive", **stats}
    witness = {v: model.get(v, False) for v in range(1, num_vars + 1)}
    return {"result": "SAT", "solver": "internal-dpll", "witness": witness, **stats}


def solve_external(binary: str, num_vars: int, clauses: list[list[int]], timeout: float) -> dict:
    """Run a DRAT-capable solver; on UNSAT, independently re-check the proof."""
    with tempfile.TemporaryDirectory() as td:
        cnf = Path(td) / "instance.cnf"
        drat = Path(td) / "proof.drat"
        cnf.write_text(to_dimacs(num_vars, clauses), encoding="utf-8")
        cmd = [binary, str(cnf), str(drat)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return {"result": "UNKNOWN", "solver": binary, "reason": f"timeout {timeout}s"}
        if r.returncode == 10:  # SAT
            witness: dict[int, bool] = {}
            for line in r.stdout.splitlines():
                if line.startswith("v"):
                    for tok in line[1:].split():
                        lit = int(tok)
                        if lit:
                            witness[abs(lit)] = lit > 0
            return {"result": "SAT", "solver": binary, "witness": witness}
        if r.returncode == 20:  # UNSAT
            check = kernel_tools.check_drat(cnf, drat) if drat.exists() else \
                {"available": False, "ok": False, "reason": "solver wrote no DRAT proof"}
            return {"result": "UNSAT", "solver": binary,
                    "refutation": "drat_verified" if check.get("ok") else "drat_unverified",
                    "drat_check": check}
        return {"result": "UNKNOWN", "solver": binary,
                "reason": f"unexpected exit code {r.returncode}", "stderr": r.stderr[-400:]}


def solve_cubes(mode: str, solver: str, num_vars: int, clauses: list[list[int]],
                depth: int, max_decisions: int, timeout: float) -> dict:
    """Cube-and-conquer over the `depth` most frequent variables. Sound by
    construction: the 2^depth cubes are ALL assignments of those variables, so
    every cube UNSAT refutes the whole instance; a SAT cube yields a witness."""
    freq: dict[int, int] = {}
    for c in clauses:
        for lit in c:
            freq[abs(lit)] = freq.get(abs(lit), 0) + 1
    split_vars = [v for v, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:depth]]
    if not split_vars:
        return {"result": "UNKNOWN", "solver": solver, "reason": "no variables to split on"}

    refutations: list[str] = []
    cubes_unknown = 0
    for bits in itertools.product((True, False), repeat=len(split_vars)):
        cube_units = [[v if bit else -v] for v, bit in zip(split_vars, bits)]
        cube_clauses = clauses + cube_units
        if mode == "external":
            outcome = solve_external(solver, num_vars, cube_clauses, timeout)
        else:
            outcome = solve_internal(num_vars, cube_clauses, max_decisions)
        if outcome["result"] == "SAT":
            return {**outcome, "cube": {str(v): b for v, b in zip(split_vars, bits)},
                    "cubes_total": 2 ** len(split_vars)}
        if outcome["result"] == "UNSAT":
            refutations.append(str(outcome.get("refutation")))
        else:
            cubes_unknown += 1
    if cubes_unknown:
        return {"result": "UNKNOWN", "solver": solver,
                "reason": f"{cubes_unknown}/{2 ** len(split_vars)} cubes exhausted their budget"}
    all_checked = all(r in ("drat_verified", "internal_exhaustive") for r in refutations)
    return {"result": "UNSAT", "solver": solver,
            "refutation": "cube_and_conquer" if all_checked else "cube_and_conquer_unchecked",
            "cubes": {"total": len(refutations), "split_vars": split_vars,
                      "per_cube_refutations": sorted(set(refutations))}}


def pick_solver(requested: str) -> tuple[str, str]:
    """-> (mode, binary_or_label)."""
    if requested == "internal":
        return "internal", "internal-dpll"
    if requested != "auto":
        path = shutil.which(requested)
        if not path:
            raise SystemExit(f"requested solver {requested!r} not on PATH")
        return "external", path
    for name in EXTERNAL_SOLVERS:
        path = shutil.which(name)
        if path:
            return "external", path
    return "internal", "internal-dpll"


# --- certificate ---------------------------------------------------------------
def run_instance(encoder: str, enc: dict, args: argparse.Namespace) -> dict:
    mode, solver = pick_solver(args.solver)
    if args.cubes > 0:
        outcome = solve_cubes(mode, solver, enc["num_vars"], enc["clauses"],
                              args.cubes, args.max_decisions, args.timeout)
    elif mode == "external":
        outcome = solve_external(solver, enc["num_vars"], enc["clauses"], args.timeout)
    else:
        outcome = solve_internal(enc["num_vars"], enc["clauses"], args.max_decisions)

    witness_verified = None
    if outcome.get("result") == "SAT":
        witness_verified = verify_witness(enc["clauses"], outcome.get("witness") or {})

    if outcome["result"] == "SAT" and witness_verified:
        meaning, trust = enc["sat_means"], "CHECKED"
    elif outcome["result"] == "SAT":
        meaning, trust = "INVALID: solver witness fails in-process verification", "REJECTED"
    elif outcome["result"] == "UNSAT":
        meaning = enc["unsat_means"]
        trust = "CHECKED" if outcome.get("refutation") in (
            "drat_verified", "internal_exhaustive", "cube_and_conquer") else "OPEN"
    else:
        meaning, trust = "no verdict under the stated budget", "OPEN"

    cert: dict[str, Any] = {
        "schema": "witsoc.sat_certificate.v1",
        "encoder": encoder,
        "params": {k: v for k, v in vars(args).items()
                   if k in ("n", "s", "t", "k", "file", "family", "edges", "moduli", "cubes")
                   and v not in (None, "", 0)},
        "instance_statement": enc["statement"],
        "num_vars": enc["num_vars"],
        "num_clauses": len(enc["clauses"]),
        "result": outcome["result"],
        "solver": outcome.get("solver"),
        "witness_verified": witness_verified,
        "refutation": outcome.get("refutation"),
        "drat_check": outcome.get("drat_check"),
        "cubes": outcome.get("cubes"),
        "decisions": outcome.get("decisions"),
        "reason": outcome.get("reason"),
        "mathematical_meaning": meaning,
        "trust": trust,
        "trust_note": ("CHECKED-grade bounded evidence only: an explicit re-verified witness or a "
                       "checked refutation of THIS finite instance. Never VERIFIED here; the kernel "
                       "bridge (--prove) is the only upgrade path."),
        "repro": f"witsoc sat {encoder} " + " ".join(
            f"--{k} {v}" for k, v in vars(args).items()
            if k in ("n", "s", "t", "k", "file", "family", "edges", "moduli", "cubes")
            and v not in (None, "", 0)),
    }
    if outcome.get("result") == "SAT" and witness_verified and not args.no_witness:
        cert["witness"] = {str(k): v for k, v in sorted((outcome.get("witness") or {}).items())}

    # Kernel bridge: the instance's mathematical meaning as a decidable Lean goal.
    if args.emit_lean or args.prove:
        lean = enc.get("lean")
        if not lean:
            cert["lean"] = {"available": False,
                            "reason": f"no decidable Lean form implemented for encoder {encoder!r}"}
        else:
            cert["lean"] = {"available": True, "statement": lean,
                            "note": ("the Lean statement asserts the UNSAT direction "
                                     "(every coloring contains the forbidden structure)")}
            if args.prove:
                cmd = [sys.executable, str(SCRIPT_DIR / "close_obligation.py"),
                       "--lean-statement", lean, "--name", f"sat_{encoder}",
                       "--out-ledger", "/dev/null", "--search"]
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True,
                                       timeout=args.timeout, check=False)
                    prover = json.loads(r.stdout) if r.stdout.strip() else {}
                except Exception as exc:
                    prover = {"error": str(exc)}
                cert["lean"]["prover"] = {"discharged": bool(prover.get("discharged")),
                                          "label": prover.get("label"),
                                          "proof": prover.get("proof")}
    return cert


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="encoder", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--solver", default="auto",
                        help="auto (external if installed, else internal) | internal | <binary name>")
    common.add_argument("--timeout", type=float, default=600.0)
    common.add_argument("--max-decisions", type=int, default=DEFAULT_MAX_DECISIONS)
    common.add_argument("--out", type=Path, default=None)
    common.add_argument("--no-witness", action="store_true", help="omit the witness from the certificate")
    common.add_argument("--emit-lean", action="store_true", help="include the decidable Lean form when implemented")
    common.add_argument("--prove", action="store_true",
                        help="hand the Lean form to the kernel-gated prover (decide portfolio)")
    common.add_argument("--cubes", type=int, default=0,
                        help="cube-and-conquer split depth (2^D cubes over the D most frequent variables)")

    p = sub.add_parser("ramsey", parents=[common])
    p.add_argument("--n", type=int, required=True)
    p.add_argument("--s", type=int, default=3)
    p.add_argument("--t", type=int, default=3)
    p = sub.add_parser("vdw", parents=[common])
    p.add_argument("--n", type=int, required=True)
    p.add_argument("--k", type=int, default=3)
    p = sub.add_parser("schur", parents=[common])
    p.add_argument("--n", type=int, required=True)
    p = sub.add_parser("graph-coloring", parents=[common])
    p.add_argument("--k", type=int, required=True, help="number of colors")
    p.add_argument("--family", choices=sorted(GRAPH_FAMILIES), default=None)
    p.add_argument("--n", type=int, default=0, help="family size parameter (cycle/complete)")
    p.add_argument("--edges", default="", help='explicit edge list, e.g. "0-1,1-2,2-0"')
    p = sub.add_parser("covering", parents=[common])
    p.add_argument("--moduli", required=True, help='comma-separated moduli, e.g. "2,3,4,6,12"')
    p = sub.add_parser("dimacs", parents=[common])
    p.add_argument("--file", type=Path, required=True)

    args = ap.parse_args()
    if args.encoder == "ramsey":
        enc = encode_ramsey(args.n, args.s, args.t)
    elif args.encoder == "vdw":
        enc = encode_vdw(args.n, args.k)
    elif args.encoder == "schur":
        enc = encode_schur(args.n)
    elif args.encoder == "graph-coloring":
        if args.family:
            n, edges = GRAPH_FAMILIES[args.family](args.n)
            label = f"{args.family}({args.n})" if args.family != "grotzsch" else "grotzsch"
        elif args.edges:
            edges = [tuple(int(x) for x in e.split("-")) for e in args.edges.split(",")]
            n = max(max(e) for e in edges) + 1
            label = "explicit-edge-list"
        else:
            raise SystemExit("graph-coloring needs --family or --edges")
        enc = encode_graph_coloring(n, edges, args.k, label)
    elif args.encoder == "covering":
        moduli = [int(m) for m in args.moduli.split(",")]
        enc = encode_covering(moduli)
    else:
        enc = encode_dimacs(args.file)

    cert = run_instance(args.encoder, enc, args)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(cert, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(cert, indent=2, ensure_ascii=False))
    return 0 if cert["result"] in ("SAT", "UNSAT") and cert["trust"] == "CHECKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
