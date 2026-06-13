#!/usr/bin/env python3
"""Ω1 tiered proving with pluggable SOTA adapters — `witsoc tiered-prove`.

Seed-Prover's test-time-scaling lesson: computation should match difficulty
(light/medium/heavy), not be uniform. Nexus's lesson: external provers belong
in the loop as TOOLS on subgoals. This module is both:

  TIERS    light   = deterministic portfolio only (seconds)
           medium  = + compound search + adapters(medium) + 2 Nexus rounds
           heavy   = + big search budget + adapters(heavy) + 6 Nexus rounds
  ADAPTERS external SOTA provers (Seed/Goedel/DeepSeek-class, local or API)
           plug in via the cmd: protocol — request {task: "external_prove",
           lean_statement, imports, tier} -> {proof}; configured by
           WITSOC_PROVER_FLEET ('id=cmd:...' entries, ';;'-separated) or
           ~/.witsoc/prover_adapters.json.

Trust contract unchanged: every adapter proof is REPLAYED through the kernel;
an adapter is a candidate generator, never an authority. Consumers:
blueprint dispatch (--tier), lemma pool, the campaign driver.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

TIERS = {
    "light": {"search": False, "search_max_nodes": 0, "nexus_rounds": 0, "adapters": False},
    "medium": {"search": True, "search_max_nodes": 120, "nexus_rounds": 2, "adapters": True},
    "heavy": {"search": True, "search_max_nodes": 500, "nexus_rounds": 6, "adapters": True},
}
FORBIDDEN = ("sorry", "admit", "axiom")


def adapters() -> list[dict]:
    out: list[dict] = []
    env = os.environ.get("WITSOC_PROVER_FLEET", "").strip()
    if env:
        for i, entry in enumerate(e.strip() for e in env.split(";;") if e.strip()):
            m = re.match(r"^([A-Za-z0-9_-]+)=(cmd:.*)$", entry)
            if m:
                out.append({"id": m.group(1), "command": m.group(2)})
            elif entry.startswith("cmd:"):
                out.append({"id": f"prover{i + 1}", "command": entry})
        return out
    cfg = witcore.load_json(witcore.witsoc_home() / "prover_adapters.json", [])
    for i, e in enumerate(c for c in (cfg if isinstance(cfg, list) else []) if isinstance(c, dict)):
        if e.get("command"):
            out.append({"id": str(e.get("id") or f"prover{i + 1}"), "command": str(e["command"])})
    return out


def _try_adapters(goal: str, imports: str, tier: str, lake_dir: Path | None,
                  name: str) -> dict | None:
    """Every adapter proof is kernel-REPLAYED; the adapter is never trusted."""
    import close_obligation as co
    for adapter in adapters():
        reply = witcore.run_sampler(adapter["command"], {
            "task": "external_prove", "lean_statement": goal, "imports": imports,
            "tier": tier, "rules": "Return {proof: \"by ...\"} — a complete Lean 4 proof."},
            timeout=600 if tier == "heavy" else 240)
        proof = str((reply or {}).get("proof") or "").strip()
        if not proof or any(t in proof for t in FORBIDDEN):
            continue
        if not proof.startswith("by"):
            proof = "by " + proof
        if witcore.lean_verify_cached(co.lean_source(name, goal, imports, proof),
                                      lake_dir).get("verified"):
            return {"discharged": True, "proof": proof, "via": f"adapter:{adapter['id']}"}
    return None


def prove(goal: str, *, tier: str = "light", imports: str = "",
          lake_dir: Path | None = None, theory: dict | None = None,
          name: str = "tiered") -> dict:
    """The tiered escalation: deterministic saturation -> external adapters ->
    Nexus fleet, all bounded by the tier. Returns the close_goal-style record
    plus `tier` and `via`."""
    spec = TIERS[tier]
    import close_obligation as co
    record = co.close_goal(goal, name=name, imports=imports, lake_dir=lake_dir,
                           search=spec["search"],
                           search_max_nodes=spec["search_max_nodes"] or 300)
    if record.get("discharged"):
        return {**record, "tier": tier, "via": "deterministic"}
    if spec["adapters"]:
        hit = _try_adapters(goal, imports, tier, lake_dir, name)
        if hit:
            return {**record, **hit, "discharged": True, "label": "PROOF_DISCHARGED", "tier": tier}
    if spec["nexus_rounds"] > 0:
        try:
            import nexus_loop as nx
            fr = nx.fleet_prove(goal, imports=imports, theory=theory,
                                rounds=spec["nexus_rounds"], lake_dir=lake_dir,
                                deterministic_first=False, name=name)
            if fr.get("discharged"):
                return {**record, "discharged": True, "proof": fr["proof"],
                        "label": "PROOF_DISCHARGED", "via": fr["via"], "tier": tier}
        except Exception:
            pass
    return {**record, "tier": tier, "via": "exhausted"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lean-statement", required=True)
    ap.add_argument("--tier", choices=sorted(TIERS), default="light")
    ap.add_argument("--imports", default="")
    ap.add_argument("--run-dir", type=Path, default=None)
    args = ap.parse_args()
    theory = None
    if args.run_dir is not None:
        try:
            import problem_theory as pt
            if pt.theory_path(args.run_dir).exists():
                theory = pt.prompt_context(args.run_dir)
        except Exception:
            pass
    record = prove(args.lean_statement, tier=args.tier, imports=args.imports, theory=theory)
    print(json.dumps({k: record.get(k) for k in ("discharged", "proof", "label", "tier", "via")},
                     indent=2, ensure_ascii=False))
    return 0 if record.get("discharged") else 1


if __name__ == "__main__":
    raise SystemExit(main())
