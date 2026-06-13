#!/usr/bin/env python3
"""Wish debugger — counterexample-guided repair of dream lemmas (CEGIS for statements).

A mathematician's wishful-thinking loop: state the lemma H you WISH were true,
test it against reality, and when reality refutes it, repair the statement
minimally instead of discarding the wish ("true as stated? no — true for n ≥ 2?
for odd n?"). This automates that loop, kernel-gated end to end:

  1. BRIDGE: kernel-prove `(H) → (T)` (speculative-arena style) — is the wish
     even sufficient for the target? The conditional is a real theorem; H is
     never asserted.
  2. FALSIFY: instantiate H on bounded instances and try to kernel-prove the
     NEGATION of each instance (`decide`/`omega`/`simp`). A proof of ¬H(k) is a
     genuine counterexample witness, not a heuristic.
  3. REPAIR: one axis per round — add the weakest hypothesis that excludes every
     witness found so far (lower bound, residue exclusion, residue restriction).
     Repairs are generated WITH their Python semantics, so the next round's
     instances are drawn from values that satisfy the accumulated hypotheses
     (no vacuous "repairs" that just dodge the tested range).
  4. SURVIVOR: a wish with no witness in bounds is a CONJECTURE with bounded
     evidence and a full counterexample history — never more. An unrepairable
     wish is a FAILED_ATTEMPT whose witness ledger is reusable negative evidence.

CALIBRATION: output statuses are only CONJECTURE / FAILED_ATTEMPT / OPEN_UNFALSIFIED
(asserted structurally). The kernel gate alone upgrades anything beyond that.

Usage:
  lemma_repair.py --wish "<Lean ∀ v : Nat, ...>" [--target "<Lean T>"]
      [--max-rounds 3] [--instance-bound 6] [--instance-cap 200]
      [--imports I] [--lake-dir D] [--out repair.json]
      [--run-dir RUNS/<task> --write]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Callable

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

ALLOWED_OUT = {"CONJECTURE", "FAILED_ATTEMPT", "OPEN_UNFALSIFIED"}
FORBIDDEN = ("sorry", "admit", "axiom", "native_decide")

_FORALL_NAT = re.compile(r"^\s*∀\s*([A-Za-z_][A-Za-z0-9_']*)\s*:\s*(Nat|ℕ)\s*,\s*(.+)$", re.S)

INSTANCE_TACTICS = ("by decide", "by omega", "by simp")


def parse_wish(wish: str) -> dict | None:
    m = _FORALL_NAT.match(wish.strip())
    if not m:
        return None
    return {"var": m.group(1), "body": m.group(3).strip()}


def substitute(body: str, var: str, value: int) -> str:
    return re.sub(rf"\b{re.escape(var)}\b", str(value), body)


def _kernel_prove(statement: str, imports: str, lake_dir: Path | None) -> str | None:
    """Try a tiny tactic portfolio; return the winning proof or None."""
    header = (imports + "\n") if imports else ""
    for tac in INSTANCE_TACTICS:
        src = f"{header}theorem inst_check : {statement} := {tac}\n"
        v = witcore.lean_verify_cached(src, lake_dir)
        if v.get("verified"):
            return tac
    return None


def falsify(body: str, var: str, instances: list[int], imports: str,
            lake_dir: Path | None) -> dict:
    """Kernel-gated instance testing. A proof of `¬ (body[k])` is a witness."""
    witnesses: list[int] = []
    confirmed: list[int] = []
    undecided: list[int] = []
    for k in instances:
        inst = substitute(body, var, k)
        if _kernel_prove(f"¬ ({inst})", imports, lake_dir):
            witnesses.append(k)
            if len(witnesses) >= 3:   # enough to choose a repair axis
                break
        elif _kernel_prove(f"({inst})", imports, lake_dir):
            confirmed.append(k)
        else:
            undecided.append(k)
    return {"witnesses": witnesses, "confirmed": confirmed, "undecided": undecided,
            "instances_tested": instances[: len(witnesses) + len(confirmed) + len(undecided)]}


# --- Repair axes ---------------------------------------------------------------
# Each repair returns (lean_hypothesis, python_predicate, description) or None.
def repair_lower_bound(var: str, witnesses: list[int]) -> tuple[str, Callable[[int], bool], str] | None:
    if not witnesses or max(witnesses) > 16:
        return None
    m = max(witnesses) + 1
    return (f"{m} ≤ {var}", lambda k, m=m: k >= m, f"lower_bound: exclude {var} < {m}")


def repair_residue_exclusion(var: str, witnesses: list[int]) -> tuple[str, Callable[[int], bool], str] | None:
    for mod in (2, 3, 4, 5):
        residues = {w % mod for w in witnesses}
        if len(residues) == 1:
            r = residues.pop()
            return (f"{var} % {mod} ≠ {r}", lambda k, mod=mod, r=r: k % mod != r,
                    f"residue_exclusion: witnesses all ≡ {r} (mod {mod})")
    return None


def repair_residue_restriction(var: str, witnesses: list[int],
                               survivors: list[int]) -> tuple[str, Callable[[int], bool], str] | None:
    """Restrict to a residue class containing confirmed-true instances and no witness."""
    for mod in (2, 3, 4):
        bad = {w % mod for w in witnesses}
        good = {s % mod for s in survivors} - bad
        if good:
            r = sorted(good)[0]
            return (f"{var} % {mod} = {r}", lambda k, mod=mod, r=r: k % mod == r,
                    f"residue_restriction: keep only {var} ≡ {r} (mod {mod})")
    return None


def choose_repair(var: str, witnesses: list[int], confirmed: list[int],
                  used_axes: set[str]) -> tuple[str, str, Callable[[int], bool], str] | None:
    """One axis per round, weakest first; an axis may repeat only with a new value
    (the witness set changed, so the hypothesis differs)."""
    for axis, gen in (("residue_exclusion", lambda: repair_residue_exclusion(var, witnesses)),
                      ("lower_bound", lambda: repair_lower_bound(var, witnesses)),
                      ("residue_restriction", lambda: repair_residue_restriction(var, witnesses, confirmed))):
        got = gen()
        if got is None:
            continue
        hyp, pred, desc = got
        if (axis, hyp) in used_axes:
            continue
        return axis, hyp, pred, desc
    return None


def bridge_check(wish: str, target: str, imports: str, lake_dir: Path | None) -> dict:
    """Kernel-prove (wish) → (target). A discharge means the wish is a sufficient
    bridge — a CONDITIONAL fact; the wish itself stays unasserted."""
    cond = f"({wish}) → ({target})"
    header = (imports + "\n") if imports else ""
    for tac in ("by intro h; exact h", "by intro h; intros; apply h <;> assumption",
                "by intro h; intro n; simp [h]", "by intro h; simp [h]",
                "by intro h; intros; simp_all"):
        src = f"{header}theorem bridge_check : {cond} := {tac}\n"
        v = witcore.lean_verify_cached(src, lake_dir)
        if v.get("verified"):
            return {"conditional": cond, "sufficient": True, "proof": tac,
                    "interpretation": "kernel-verified that ASSUMING the wish proves the target; "
                                      "the wish is NOT asserted."}
    return {"conditional": cond, "sufficient": False, "proof": None}


def repair_loop(wish: str, *, target: str | None, max_rounds: int, instance_bound: int,
                instance_cap: int, imports: str, lake_dir: Path | None) -> dict:
    parsed = parse_wish(wish)
    if parsed is None:
        return {"schema": "witsoc.lemma_repair.v1", "wish": wish,
                "status": "OPEN_UNFALSIFIED",
                "reason": "wish is not a bounded-testable `∀ v : Nat, ...` statement; "
                          "route to counterexample_search.py for this shape",
                "rounds": [], "final_wish": wish}
    var, body = parsed["var"], parsed["body"]

    preds: list[Callable[[int], bool]] = []      # python semantics of added hypotheses
    hyps: list[str] = []                          # lean text of added hypotheses
    used_axes: set[tuple[str, str]] = set()
    rounds: list[dict] = []
    all_witnesses: list[int] = []
    status = "FAILED_ATTEMPT"
    current = wish

    for rnd in range(max_rounds + 1):
        # instances = first `instance_bound` values satisfying every accumulated
        # hypothesis (so a repair can never vacuously dodge the tested range)
        instances = [k for k in range(instance_cap) if all(p(k) for p in preds)][:instance_bound]
        current = f"∀ {var} : Nat, " + " → ".join(hyps + [f"({body})"]) if hyps else wish
        if not instances:
            rounds.append({"round": rnd, "wish": current, "error": "no instance satisfies the "
                           "accumulated hypotheses within the cap — repair rejected as vacuous"})
            status = "FAILED_ATTEMPT"
            break
        f = falsify(" → ".join(hyps + [f"({body})"]) if hyps else body, var, instances,
                    imports, lake_dir)
        record = {"round": rnd, "wish": current, **f}
        rounds.append(record)
        if not f["witnesses"]:
            status = "CONJECTURE"   # survived bounded falsification — evidence, never proof
            break
        all_witnesses.extend(f["witnesses"])
        if rnd == max_rounds:
            break
        got = choose_repair(var, f["witnesses"], f["confirmed"], used_axes)
        if got is None:
            record["repair"] = "no untried repair axis excludes the witnesses"
            break
        axis, hyp, pred, desc = got
        used_axes.add((axis, hyp))
        hyps.append(hyp)
        preds.append(pred)
        record["repair"] = {"axis": axis, "hypothesis_added": hyp, "description": desc}

    out = {
        "schema": "witsoc.lemma_repair.v1",
        "wish": wish,
        "final_wish": current,
        "status": status,
        "rounds": rounds,
        "repairs_applied": [r["repair"] for r in rounds if isinstance(r.get("repair"), dict)],
        "counterexample_history": sorted(set(all_witnesses)),
        "evidence_note": ("bounded kernel-checked falsification only; CONJECTURE never means proved"
                          if status == "CONJECTURE" else
                          "witness ledger is reusable negative evidence (do_not_repeat without new information)"),
    }
    if target:
        out["bridge_original"] = bridge_check(wish, target, imports, lake_dir)
        if current != wish and status == "CONJECTURE":
            out["bridge_repaired"] = bridge_check(current, target, imports, lake_dir)
    assert out["status"] in ALLOWED_OUT, f"calibration violation: {out['status']}"
    return out


def queue_entry(report: dict, target: str | None) -> dict:
    ws = report.get("counterexample_history", [])
    return {
        "statement": report["final_wish"],
        "lean_statement": report["final_wish"],
        "why_it_matters": "wish-debugger survivor: dream lemma repaired against kernel-checked counterexamples",
        "unlocks": (f"sufficient bridge for: {target[:160]}" if target and
                    report.get("bridge_repaired", report.get("bridge_original", {})).get("sufficient")
                    else "candidate stepping stone (bridge not yet kernel-verified)"),
        "known_counterexamples_or_boundary_cases":
            [f"{report['wish']} fails at {ws}" if ws else "no witness within tested bounds"],
        "failed_approaches": [f"original unrepaired wish (witnesses {ws})"] if ws else ["none yet"],
        "next_mutation": "dispatch the Prover on the repaired statement; widen falsification bounds first",
        "smallest_formalizable_subcase": report["final_wish"],
        "status": "CONJECTURE",
        "priority": 70,
        "repair_history": report.get("repairs_applied", []),
        "source": "lemma_repair",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wish", required=True, help="the dream lemma H (Lean, ∀ v : Nat, ... shape for repair)")
    ap.add_argument("--target", default=None, help="frozen Lean target T for the bridge check")
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--instance-bound", type=int, default=6, help="instances tested per round")
    ap.add_argument("--instance-cap", type=int, default=200)
    ap.add_argument("--imports", default="")
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("lemma_repair.json"))
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument("--write", action="store_true", help="merge a CONJECTURE survivor into actual_lemma_queue")
    args = ap.parse_args()

    if any(t in args.wish for t in FORBIDDEN):
        print(json.dumps({"error": "forbidden token in wish"}))
        return 2

    report = repair_loop(args.wish, target=args.target, max_rounds=args.max_rounds,
                         instance_bound=args.instance_bound, instance_cap=args.instance_cap,
                         imports=args.imports, lake_dir=args.lake_dir)
    witcore.save_json(args.out, report)

    if args.write and args.run_dir and report["status"] == "CONJECTURE":
        qpath = args.run_dir / "actual_lemma_queue.json"
        queue = witcore.load_json(qpath, [])
        if not isinstance(queue, list):
            queue = []
        if report["final_wish"] not in {e.get("statement") for e in queue if isinstance(e, dict)}:
            queue.append(queue_entry(report, args.target))
            witcore.save_json(qpath, queue)
            report["queue_added"] = True

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
