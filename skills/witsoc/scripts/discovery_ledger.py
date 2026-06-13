#!/usr/bin/env python3
"""Discovery ledger — `witsoc discoveries`: the durable record of campaign output.

One JSONL file at <witsoc home>/discoveries.jsonl. Every entry is a CLAIM with
two independent axes plus a human gate:

  trust_tier   from the trust lattice (KERNEL_VERIFIED / CHECKED / CONJECTURE /
               CERTIFICATE / REFUTED / ...). NEVER assigned here — callers pass
               what the kernel/backends established; this tool only records.
  novelty      from novelty_triage (KNOWN / KNOWN_INTERNAL / NOVEL_CANDIDATE /
               LOCALLY_NEW_UNCHECKED). Auto-run on add when not supplied.
  human_gate   false until a human marks the entry reviewed (`gate`). Nothing
               is externally claimable ("we discovered X") until BOTH
               trust_tier is kernel-grade AND novelty is NOVEL_CANDIDATE AND
               human_gate is true.

Subcommands:
  add     --claim TEXT --kind lemma|conjecture|family|certificate|counterexample
          --trust-tier T [--statement S] [--problem-id ID] [--repro CMD]
          [--sequence 1,2,3] [--evidence JSON]
  list    [--novelty N] [--kind K] [--min-trust T]
  gate    --id ID [--reviewer NAME]      (human review mark; the ONLY mutation)
  report  summary counts + the publishable set
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import novelty_triage as nt  # noqa: E402
import witcore  # noqa: E402

KINDS = {"lemma", "conjecture", "family", "certificate", "counterexample", "reduction"}
KERNEL_GRADE = {"KERNEL_VERIFIED", "VERIFIED_LEAN", "LEAN_VERIFIED"}


def ledger_path() -> Path:
    return witcore.witsoc_home() / "discoveries.jsonl"


def load_entries() -> list[dict]:
    p = ledger_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _write_all(entries: list[dict]) -> None:
    p = ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")


def publishable(e: dict) -> bool:
    return (e.get("trust_tier") in KERNEL_GRADE
            and e.get("novelty", {}).get("novelty") == "NOVEL_CANDIDATE"
            and e.get("human_gate") is True)


def add_entry(claim: str, kind: str, trust_tier: str, statement: str = "",
              problem_id: str = "", repro: str = "", sequence: list[int] | None = None,
              evidence: dict | list | None = None, novelty: dict | None = None) -> dict:
    if kind not in KINDS:
        raise SystemExit(f"unknown kind {kind!r}; choose from {sorted(KINDS)}")
    if novelty is None:
        novelty = nt.triage(statement or claim, keywords=claim.split()[:8], sequence=sequence)
    eid = nt.statement_key(f"{kind}|{statement or claim}")
    entries = load_entries()
    if any(e["id"] == eid for e in entries):
        return {"status": "duplicate", "id": eid}
    entry = {
        "id": eid, "claim": claim, "kind": kind, "trust_tier": trust_tier,
        "statement": statement, "problem_id": problem_id, "repro": repro,
        "novelty": novelty, "evidence": evidence or [],
        "human_gate": False, "created_at": time.time(),
    }
    entries.append(entry)
    _write_all(entries)
    return {"status": "added", "id": eid, "novelty": novelty.get("novelty"),
            "trust_tier": trust_tier, "publishable": publishable(entry)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("--claim", required=True)
    p_add.add_argument("--kind", required=True)
    p_add.add_argument("--trust-tier", required=True)
    p_add.add_argument("--statement", default="")
    p_add.add_argument("--problem-id", default="")
    p_add.add_argument("--repro", default="")
    p_add.add_argument("--sequence", default="")
    p_add.add_argument("--evidence", default="")

    p_list = sub.add_parser("list")
    p_list.add_argument("--novelty", default=None)
    p_list.add_argument("--kind", default=None)

    p_gate = sub.add_parser("gate")
    p_gate.add_argument("--id", required=True)
    p_gate.add_argument("--reviewer", default="human")

    sub.add_parser("report")

    args = ap.parse_args()
    if args.cmd == "add":
        seq = [int(x) for x in args.sequence.split(",") if x.strip().lstrip("-").isdigit()]
        ev = json.loads(args.evidence) if args.evidence else None
        print(json.dumps(add_entry(args.claim, args.kind, args.trust_tier, args.statement,
                                   args.problem_id, args.repro, seq, ev), indent=2, ensure_ascii=False))
        return 0
    entries = load_entries()
    if args.cmd == "list":
        sel = [e for e in entries
               if (args.novelty is None or e.get("novelty", {}).get("novelty") == args.novelty)
               and (args.kind is None or e.get("kind") == args.kind)]
        print(json.dumps(sel, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "gate":
        hit = False
        for e in entries:
            if e["id"] == args.id:
                e["human_gate"] = True
                e["reviewed_by"] = args.reviewer
                e["reviewed_at"] = time.time()
                hit = True
        _write_all(entries)
        print(json.dumps({"status": "gated" if hit else "not_found", "id": args.id}, indent=2))
        return 0 if hit else 1
    if args.cmd == "report":
        by_novelty: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        for e in entries:
            by_novelty[e.get("novelty", {}).get("novelty", "?")] = by_novelty.get(e.get("novelty", {}).get("novelty", "?"), 0) + 1
            by_tier[e.get("trust_tier", "?")] = by_tier.get(e.get("trust_tier", "?"), 0) + 1
        pub = [e for e in entries if publishable(e)]
        print(json.dumps({
            "total": len(entries), "by_novelty": by_novelty, "by_trust_tier": by_tier,
            "publishable": [{"id": e["id"], "claim": e["claim"]} for e in pub],
            "ledger": str(ledger_path()),
            "note": "publishable = kernel-grade trust AND NOVEL_CANDIDATE AND human-gated; everything else is internal progress.",
        }, indent=2, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
