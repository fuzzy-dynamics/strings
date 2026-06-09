#!/usr/bin/env python3
"""Unit tests for Phases 2-4 (curriculum, flywheel infra, interestingness).

Run: python3 test_phase24.py   (exit 0 = all pass). Requires the Lean toolchain.
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


class TestCurriculum(unittest.TestCase):
    def test_ladder_beats_direct(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "c.json"
            run("curriculum.py", "--target", "three facts",
                "--target-lean", "(2 + 2 = 4) ∧ (∀ n : Nat, n + 0 = n) ∧ (∀ n : Nat, fdouble n = n + n)",
                "--preamble", "def fdouble (n : Nat) : Nat := n + n",
                "--budget", "20,80,300", "--out", str(out))
            rep = json.loads(out.read_text())
            # partial credit: more kernel-verified intermediate nodes than the single direct node
            self.assertGreater(rep["verified_intermediate_nodes"], rep["direct_attack_verified_nodes"])
            self.assertTrue(rep["ladder_beats_direct"])


class TestInterestingness(unittest.TestCase):
    def test_ranks_and_cannot_create_solve(self):
        with tempfile.TemporaryDirectory() as d:
            conj = Path(d) / "conj.json"
            run("conjecture_miner.py", "number_theory", "--range", "2", "2000", "--falsify", "4000", "--out", str(conj))
            out = Path(d) / "int.json"
            r = run("interestingness.py", "--conjectures", str(conj), "--range-size", "2000", "--out", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)  # the calibration assert did not fire
            rep = json.loads(out.read_text())
            # every ranked item stays a conjecture (no status became a solve)
            self.assertTrue(all(x["status"] == "OPEN_UNFALSIFIED" for x in rep["ranked"]))
            # trivial forms are killed
            killed = {k["form"] for k in rep["killed"]}
            self.assertIn("prime(n) -> prime_power(n)", killed)


class TestFlywheelInfra(unittest.TestCase):
    def test_one_iteration_runs_and_stays_calibrated(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "fly.json"
            r = run("flywheel.py", "--iterations", "1", "--library", str(Path(d) / "lib"),
                    "--out", str(out), timeout=900)
            self.assertEqual(r.returncode, 0, r.stderr)
            rep = json.loads(out.read_text())
            self.assertEqual(len(rep["log"]), 1)
            # calibration must hold every iteration (no fake solves under the flywheel)
            self.assertTrue(rep["log"][0]["calibration_clean"])
            self.assertIn(rep["verdict"], ("FLYWHEEL_TURNS", "PLATEAU"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
