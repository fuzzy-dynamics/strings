#!/usr/bin/env python3
"""Tests for domain-specific barrier-lemma generation."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import domain_barrier_lemmas as dbl
import decompose_problem as dp
import lovasz_prover_dispatch as lpd

TRUSTED = {"CHECKED", "VERIFIED", "VERIFIED_LEAN", "VERIFIED_WIT", "PROVED", "PROVED_SKETCH",
           "PARTIAL", "CONDITIONAL", "CHECKED_BOUNDED"}


def types_of(lemmas):
    return {l["barrier_type"] for l in lemmas}


def assert_safe(lemmas, failures, label):
    for l in lemmas:
        if l["status"] != "OPEN_UNFALSIFIED" or l["arena"] != "SPECULATIVE":
            failures.append(f"{label}: lemma {l['barrier_type']} not OPEN_UNFALSIFIED/SPECULATIVE")
        if l["status"] in TRUSTED:
            failures.append(f"{label}: trusted status leaked: {l['status']}")
        ls = l.get("lean_statement") or ""
        if any(t in ls for t in ("sorry", "admit", "axiom", "native_decide")):
            failures.append(f"{label}: forbidden token in lean_statement of {l['barrier_type']}")


def main() -> int:
    failures: list[str] = []

    # --- number theory ---
    nt = dbl.generate_barrier_lemmas("Erdős–Straus 4/n = 1/x+1/y+1/z for all n>=2",
                                     domain="number_theory", target_hash="a" * 64)
    need = {"residue_class_split", "local_obstruction", "parametrized_witness_family", "finite_range_certificate"}
    if not need <= types_of(nt):
        failures.append(f"NT missing barrier types: {need - types_of(nt)}")
    assert_safe(nt, failures, "NT")

    # --- graph theory ---
    g = dbl.generate_barrier_lemmas("every triangle-free graph on n vertices has independence number ...",
                                    domain="graph_theory", target_hash="b" * 64)
    need_g = {"minimal_counterexample", "degree_bound", "finite_model_certificate", "forbidden_substructure"}
    if not need_g <= types_of(g):
        failures.append(f"graph missing barrier types: {need_g - types_of(g)}")
    assert_safe(g, failures, "graph")

    # --- additive combinatorics ---
    a = dbl.generate_barrier_lemmas("a subset of [N] with no 3-term AP has size O(...)",
                                    domain="additive_combinatorics", target_hash="c" * 64)
    need_a = {"density_increment", "energy_increment", "small_doubling"}
    if not need_a <= types_of(a):
        failures.append(f"additive missing barrier types: {need_a - types_of(a)}")
    assert_safe(a, failures, "additive")

    # --- general Lean Nat target: dispatchable formal family ---
    nat = dbl.generate_barrier_lemmas("for all n, P n", lean_target="∀ n : Nat, n + 0 = n",
                                      domain="other", target_hash="d" * 64)
    formal = {l["barrier_type"]: l for l in nat if l["domain"] == "formal_nat"}
    for need_b in ("base_case", "inductive_step", "even_case", "odd_case"):
        if need_b not in formal:
            failures.append(f"general Nat missing dispatchable {need_b}")
        elif not formal[need_b].get("lean_statement"):
            failures.append(f"{need_b} should carry a lean_statement")
    assert_safe(nat, failures, "nat")

    # --- failure-memory awareness ---
    fm = [{"target_hash": "a" * 64, "barrier_type": "residue_class_split"}]
    nt_fm = dbl.generate_barrier_lemmas("...", domain="number_theory", target_hash="a" * 64, failure_memory=fm)
    if any(l["barrier_type"] == "residue_class_split" and not l.get("mutated_from_failure") for l in nt_fm):
        failures.append("failure-memory: a failed boundless barrier must not be re-emitted unchanged")
    fm2 = [{"target_hash": "a" * 64, "barrier_type": "finite_range_certificate"}]
    nt_fm2 = dbl.generate_barrier_lemmas("...", domain="number_theory", target_hash="a" * 64, failure_memory=fm2)
    frc = [l for l in nt_fm2 if l["barrier_type"] == "finite_range_certificate"]
    if not frc or not frc[0].get("mutated_from_failure"):
        failures.append("failure-memory: a failed bounded barrier should be re-proposed MUTATED (stronger bound)")
    elif frc[0]["falsification_test"]["bound"] <= 10000:
        failures.append("failure-memory: mutated bound should be larger than the original")

    # --- theorem-precondition awareness ---
    ta = [{"theorem": "Hall's theorem", "missing_preconditions": ["G is connected"]}]
    g_ta = dbl.generate_barrier_lemmas("graph target", domain="graph_theory", target_hash="b" * 64, theorem_audit=ta)
    bridges = [l for l in g_ta if l["barrier_type"] == "precondition_bridge"]
    if not bridges:
        failures.append("theorem-precondition: expected a precondition_bridge lemma")
    elif "G is connected" not in bridges[0]["theorem_preconditions_to_audit"] or bridges[0]["priority"] < 90:
        failures.append("theorem-precondition: bridge must audit the missing precondition at high priority")

    # --- integration: decompose --write, DAG integrity, honest dispatch ---
    tmp = Path(tempfile.mkdtemp(prefix="witsoc_dbl_"))
    try:
        subprocess.run([sys.executable, str(SCRIPT_DIR / "decompose_problem.py"), str(tmp),
                        "--target", "for all naturals n, n + 0 = n",
                        "--lean-target", "∀ n : Nat, n + 0 = n", "--domain", "number_theory", "--write"],
                       capture_output=True, text=True, timeout=60, check=False)
        dag = json.loads((tmp / "proof_dependency_dag.json").read_text())
        queue = json.loads((tmp / "actual_lemma_queue.json").read_text())
        barrier_nodes = [n for n in dag if n.get("barrier_type")]
        if not barrier_nodes:
            failures.append("integration: DAG has no barrier nodes")
        if not any(l.get("barrier_type") for l in queue):
            failures.append("integration: queue has no barrier lemmas")
        # matching node <-> lemma ids
        node_ids = {n["node_id"] for n in barrier_nodes}
        lemma_node_ids = {l["node_id"] for l in queue if l.get("barrier_type")}
        if not node_ids <= lemma_node_ids:
            failures.append("integration: every barrier node must have a matching queue lemma")
        # DAG integrity
        r = subprocess.run([sys.executable, str(SCRIPT_DIR / "validate_proof_dag_integrity.py"), str(tmp)],
                           capture_output=True, text=True, timeout=60, check=False)
        if "VALID_PROOF_DAG_INTEGRITY" not in r.stdout:
            failures.append(f"integration: DAG integrity failed: {r.stderr[:300]}")
        # honest dispatch: a barrier node with NO lean_statement -> OPEN/theorem_precondition_gap (not progress)
        prose_node = next((n for n in barrier_nodes if not n.get("lean_statement")), None)
        if prose_node:
            pkt = lpd.packet_for_node(
                {"node_id": prose_node["node_id"], "statement": prose_node["statement"],
                 "lean_statement": None, "target_hash": prose_node["target_hash"],
                 "dependency_path_to_target": prose_node.get("dependency_path_to_target", ["T"])},
                False, None, 4, "test", tmp)
            if pkt["status"] != "OPEN" or pkt["failure_class"] != "theorem_precondition_gap":
                failures.append(f"integration: prose barrier node must dispatch as OPEN/theorem_precondition_gap, got {pkt['status']}/{pkt['failure_class']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("DOMAIN_BARRIER_LEMMAS_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
