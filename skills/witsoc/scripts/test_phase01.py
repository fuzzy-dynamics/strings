#!/usr/bin/env python3
"""Unit + integration tests for the Phase 0/1 work (eval harness, proof search,
status-lattice terminal outcomes) and one real problem threaded end-to-end.

Run: python3 test_phase01.py   (exit 0 = all pass)
Requires the Lean toolchain (lean/lake) for the proof tests.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(script: str, *args: str, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HERE / script), *args],
                          capture_output=True, text=True, timeout=timeout, check=False)


class TestStatusLattice(unittest.TestCase):
    def test_independent_is_human_gated(self):
        with tempfile.TemporaryDirectory() as d:
            dag = Path(d) / "proof_dependency_dag.json"
            # auto (no human gate) must be rejected
            dag.write_text(json.dumps([{"node_id": "n1", "status": "INDEPENDENT", "previous_status": "CONJECTURE"}]))
            r = run("status_lattice.py", d, "--json")
            self.assertFalse(json.loads(r.stdout)["valid"])
            # human-gated with argument + evidence accepted
            dag.write_text(json.dumps([{"node_id": "n1", "status": "INDEPENDENT", "previous_status": "CONJECTURE",
                                        "human_gate": True, "independence_argument": "forcing sketch",
                                        "evidence": "forcing.md", "target_hash": "h"}]))
            r = run("status_lattice.py", d, "--json")
            self.assertTrue(json.loads(r.stdout)["valid"])

    def test_terminal_no_upgrade(self):
        r = run("status_lattice.py", "--from-status", "INDEPENDENT", "--to-status", "VERIFIED_LEAN")
        self.assertFalse(json.loads(r.stdout)["allowed"])


class TestProofSearch(unittest.TestCase):
    def test_closes_multistep_goal(self):
        # ∀ n, f n = n+n with f opaque: needs `intro` + a finisher (portfolio can't).
        r = run("proof_search.py", "--lean-statement", "∀ n : Nat, fdouble n = n + n",
                "--imports", "def fdouble (n : Nat) : Nat := n + n")
        out = json.loads(r.stdout)
        self.assertTrue(out["discharged"], out)
        self.assertIn("intro", out["proof"])

    def test_does_not_fake_solve_false_goal(self):
        # a false statement must NOT be discharged
        r = run("proof_search.py", "--lean-statement", "∀ n : Nat, n = n + 1", "--max-nodes", "120")
        self.assertFalse(json.loads(r.stdout)["discharged"])


class TestEvalHarness(unittest.TestCase):
    def test_runs_and_calibration_clean(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.json"
            r = run("eval_harness.py", "--mode", "search", "--out", str(out))
            rep = json.loads(out.read_text())
            self.assertTrue(rep["calibration_clean"], rep["calibration_violations"])
            self.assertGreaterEqual(rep["capability_score"], 0.9)


class TestIntegrationThread(unittest.TestCase):
    """One real problem: Erdős–Straus witness (n=3) -> formal Lean identity ->
    search-close -> kernel re-check certificate. discover -> formalize -> prove -> certify."""

    def test_erdos_straus_n3_end_to_end(self):
        # 1. discover the witness with the exact NT backend: 4/3 = 1/1 + 1/4 + 1/12
        r = run("number_theory_backend.py", "erdos-straus", "--range", "3", "3")
        w = json.loads(r.stdout)["sample_witnesses"][0]
        x, y, z, n = w["x"], w["y"], w["z"], w["n"]
        self.assertTrue(w["verified"])
        # 2. formalize as the cleared-denominator Nat identity (faithful by construction)
        stmt = (f"4 * ({x} * {y} * {z}) = {n} * ({y} * {z}) + {n} * ({x} * {z}) + {n} * ({x} * {y})")
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            lean = d / "es.lean"
            # 3. search-close
            r = run("close_obligation.py", "--lean-statement", stmt, "--name", "es",
                    "--search", "--emit", str(lean), "--out-ledger", str(d / "led.json"))
            out = json.loads(r.stdout)
            self.assertTrue(out["discharged"], out)
            # 4. certify: build a DAG node with the lean cert and re-check it
            (d / "proof_dependency_dag.json").write_text(json.dumps([{
                "node_id": "es3", "status": "CHECKED", "statement": stmt, "evidence": out["proof"],
                "target_hash": "es3", "dependency_path_to_target": "direct", "dependencies": [],
                "skeptic_review_id": "r1", "certificate": {"kind": "lean", "lean_path": str(lean)}}]))
            (d / "skeptic_reviews.json").write_text(json.dumps([{"review_id": "r1"}]))
            r = run("recheck_certificates.py", str(d))
            rc = json.loads((d / "certificate_recheck.json").read_text())
            self.assertEqual(rc["pass"], 1, rc)
            self.assertEqual(rc["fail"], 0, rc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
