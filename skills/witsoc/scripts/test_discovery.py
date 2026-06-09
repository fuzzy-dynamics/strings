#!/usr/bin/env python3
"""Self-contained tests for the Witsoc discovery engine and learning loop.

Run: python3 test_discovery.py    (exit 0 = all pass)

Covers: evaluator soundness (positive + negative), the island-model engine
actually improving bounds, the external-sampler (LLM plug-point) bridge, the
exact flag-algebra/SOS verifier, verified number-theory certificates, the lemma
library tiering, and the reward-labelled trace harvester.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import discovery_evaluators as DE  # noqa: E402
import flag_algebra_backend as FA  # noqa: E402
import number_theory_backend as NT  # noqa: E402


def run(script: str, *args: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HERE / script), *args], text=True, capture_output=True, check=False, **kw)


class TestEvaluators(unittest.TestCase):
    def test_cap_set_validity(self):
        ev = DE.EVALUATORS["cap_set"]
        good = ev.seed({"d": 4}, DE.random.Random(0))
        self.assertTrue(ev.evaluate(good, {"d": 4})["valid"])
        # a full line {(0,..),(1,..),(2,..)} along axis 0 is NOT a cap
        bad = [[0, 0, 0, 0], [1, 0, 0, 0], [2, 0, 0, 0]]
        self.assertFalse(ev.verify(bad, {"d": 4})["ok"])

    def test_no_three_ap_negative(self):
        ev = DE.EVALUATORS["no_three_ap"]
        self.assertFalse(ev.verify([0, 2, 4], {"n": 40})["ok"])
        self.assertTrue(ev.verify([0, 1, 5], {"n": 40})["ok"])

    def test_sidon_negative(self):
        ev = DE.EVALUATORS["sidon_set"]
        # 1+4 == 2+3 -> not Sidon
        self.assertFalse(ev.verify([1, 2, 3, 4], {"n": 40})["ok"])
        self.assertTrue(ev.verify([1, 2, 5, 11], {"n": 40})["ok"])


class TestEngine(unittest.TestCase):
    def test_engine_improves_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "ap"
            self.assertEqual(run("discovery_engine.py", "init", str(d), "--evaluator", "no_three_ap",
                                 "--params", '{"n":60}', "--seed", "1").returncode, 0)
            before = json.loads(run("discovery_engine.py", "status", str(d)).stdout)["best_score"]
            run("discovery_engine.py", "run", str(d), "--generations", "120")
            after = json.loads(run("discovery_engine.py", "status", str(d)).stdout)["best_score"]
            self.assertGreater(after, before, "evolution should beat the greedy seed")
            best = json.loads(run("discovery_engine.py", "best", str(d)).stdout)
            self.assertTrue(best["independent_verification"]["ok"])
            self.assertEqual(best["claim_status"], "CHECKED")

    def test_external_sampler_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "cap"
            run("discovery_engine.py", "init", str(d), "--evaluator", "cap_set", "--params", '{"d":4}', "--seed", "3")
            sampler = f"cmd:{sys.executable} {HERE / 'discovery_sampler_example.py'}"
            res = run("discovery_engine.py", "run", str(d), "--generations", "8", "--sampler", sampler)
            self.assertEqual(res.returncode, 0, res.stderr)
            payload = json.loads(res.stdout)
            self.assertEqual(payload["sampler"], "external")
            # every kept candidate is evaluator-verified, so the best is valid
            best = json.loads(run("discovery_engine.py", "best", str(d)).stdout)
            self.assertTrue(best["independent_verification"]["ok"])


class TestFlagAlgebra(unittest.TestCase):
    def test_psd(self):
        self.assertTrue(FA.is_psd_exact(FA.parse_matrix([[2, -1], [-1, 2]]))["psd"])
        self.assertFalse(FA.is_psd_exact(FA.parse_matrix([[1, 2], [2, 1]]))["psd"])

    def test_sos_certificate(self):
        cert = {"Q": [[1, -1], [-1, 1]], "entry_key": [["c", "t"], ["t", "t2"]],
                "target": {"c": "1", "t": "-2", "t2": "1"}, "nonneg_keys": ["t2"]}
        self.assertTrue(FA.cmd_verify_bound(cert)["valid"])
        cert["target"]["t"] = "-3"  # tamper
        self.assertFalse(FA.cmd_verify_bound(cert)["valid"])


class TestNumberTheory(unittest.TestCase):
    def test_factor_certificate(self):
        out = NT.cmd_factor(600851475143)
        self.assertTrue(out["certificate"]["equals_n"])
        self.assertEqual(out["factorization"], {"71": 1, "839": 1, "1471": 1, "6857": 1})

    def test_perfect_number(self):
        self.assertEqual(NT.cmd_sigma(28)["class"], "perfect")

    def test_erdos_straus(self):
        out = NT.cmd_erdos_straus(2, 200)
        self.assertEqual(out["no_bounded_witness"], [])
        self.assertTrue(out["all_verified"])


class TestLearningLoop(unittest.TestCase):
    def test_library_and_harvest(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp) / "lib"
            run("lemma_library.py", "--library", str(lib), "add", "--statement",
                "largest sidon set in interval", "--wit", "/tmp/s.wit")
            run("lemma_library.py", "--library", str(lib), "add", "--statement",
                "two plus two equals four", "--wit", "/tmp/t.wit")
            lean = Path(tmp) / "T.lean"
            lean.write_text("theorem t : 2 + 2 = 4 := rfl\n", encoding="utf-8")
            up = json.loads(run("lemma_library.py", "--library", str(lib), "verify-lean",
                                "--id", "2", "--lean", str(lean)).stdout)
            self.assertEqual(up["status"], "upgraded")
            # Lean-verified lemma must outrank an equal-similarity WIT lemma
            s = json.loads(run("lemma_library.py", "--library", str(lib), "search",
                               "--query", "two plus two four").stdout)
            self.assertEqual(s["matches"][0]["trust_tier"], "LEAN_VERIFIED")
            # require-lean filter
            rl = json.loads(run("lemma_library.py", "--library", str(lib), "search",
                                "--query", "two", "--require-lean").stdout)
            self.assertTrue(all(m["trust_tier"] == "LEAN_VERIFIED" for m in rl["matches"]))
            # harvest reward-labelled traces
            traces = Path(tmp) / "tr.jsonl"
            h = json.loads(run("trace_harvester.py", "harvest", "--library", str(lib),
                               "--out", str(traces)).stdout)
            self.assertEqual(h["traces"], 2)
            recs = [json.loads(x) for x in traces.read_text().splitlines()]
            self.assertEqual(max(r["reward"] for r in recs), 1.0)  # the Lean lemma


if __name__ == "__main__":
    unittest.main(verbosity=2)
