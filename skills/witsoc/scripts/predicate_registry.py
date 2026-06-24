#!/usr/bin/env python3
"""W1 formalization bridge, part 1 — `witsoc predicates`.

The single registry mapping miner predicate names to faithful Lean
expansions. This closes the formalization hole at its source: every predicate
the empirical arms (conjecture_miner, empirical_miner) are allowed to use
ships its Lean form HERE, so a mined `P(n) -> Q(n)` conjecture is a real,
dispatchable Lean statement BY CONSTRUCTION — never a placeholder stub.

Two layers:
  built-ins   the arithmetic predicates the miner computes (templates with a
              `{v}` placeholder), each tagged needs_mathlib;
  user        ~/.witsoc/predicate_registry.json — register a new predicate
              with `witsoc predicates register` BEFORE the miner may use it.
              An unregistered predicate stays an honest blocker.

Faithfulness contract: a registered template must be the exact mathematical
meaning of the predicate the miner computes — registration is where that
responsibility lives. Templates are screened for forbidden tokens at load.

Consumers: conjecture_to_lemma_pipeline.formalize_form (canonical expansion)
and conjecture_miner (real lean_statement at mining time).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

_FORBIDDEN = ("sorry", "admit", "axiom ", "unsafe ", "opaque ")

_SIGMA = "(∑ d ∈ Nat.divisors {v}, d)"

# Built-in faithful expansions for every predicate conjecture_miner computes.
BUILTINS: dict[str, dict] = {
    "prime": {"lean": "Nat.Prime {v}", "needs_mathlib": True},
    "square": {"lean": "(∃ k : Nat, k * k = {v})", "needs_mathlib": False},
    "even": {"lean": "({v} % 2 = 0)", "needs_mathlib": False},
    "odd": {"lean": "({v} % 2 = 1)", "needs_mathlib": False},
    "perfect": {"lean": f"({_SIGMA} = 2 * {{v}})", "needs_mathlib": True},
    "abundant": {"lean": f"({_SIGMA} > 2 * {{v}})", "needs_mathlib": True},
    "deficient": {"lean": f"({_SIGMA} < 2 * {{v}})", "needs_mathlib": True},
    "sigma_even": {"lean": f"({_SIGMA} % 2 = 0)", "needs_mathlib": True},
    "sigma_odd": {"lean": f"({_SIGMA} % 2 = 1)", "needs_mathlib": True},
    "prime_power": {"lean": "(∃ p k : Nat, Nat.Prime p ∧ 1 ≤ k ∧ {v} = p ^ k)", "needs_mathlib": True},
    "square_or_2square": {"lean": "(∃ k : Nat, k * k = {v} ∨ 2 * (k * k) = {v})", "needs_mathlib": False},
}


def user_registry_path() -> Path:
    return witcore.witsoc_home() / "predicate_registry.json"


def _load_user() -> dict[str, dict]:
    data = witcore.load_json(user_registry_path(), {})
    if not isinstance(data, dict):
        return {}
    out = {}
    for name, entry in data.items():
        if not (isinstance(entry, dict) and entry.get("lean") and "{v}" in str(entry["lean"])):
            continue
        if any(t in str(entry["lean"]) for t in _FORBIDDEN):
            continue  # a poisoned template is silently inert, never expanded
        out[str(name)] = {"lean": str(entry["lean"]), "needs_mathlib": bool(entry.get("needs_mathlib"))}
    return out


def registry() -> dict[str, dict]:
    """Built-ins + user registrations (user entries may NOT shadow built-ins:
    the built-in meaning of a name is frozen)."""
    merged = dict(_load_user())
    merged.update(BUILTINS)
    return merged


def known(name: str) -> bool:
    return name in registry()


def lean_for(name: str, var: str = "n") -> str | None:
    entry = registry().get(name)
    return entry["lean"].replace("{v}", var) if entry else None


def needs_mathlib(name: str) -> bool:
    entry = registry().get(name)
    return bool(entry and entry["needs_mathlib"])


def implication(p: str, q: str, var: str = "n") -> tuple[str | None, str | None, bool]:
    """The canonical `P(n) -> Q(n)` expansion: (lean, blocker, needs_mathlib).
    A missing predicate is an honest blocker, not a guess."""
    missing = [x for x in (p, q) if not known(x)]
    if missing:
        return None, (f"no faithful Lean expansion for predicate(s) {missing}; "
                      f"register one with `witsoc predicates register` or keep prose-only"), False
    body = f"{lean_for(p, var)} → {lean_for(q, var)}"
    lean = f"∀ {var} : Nat, 2 ≤ {var} → {body}"
    if any(t in lean for t in _FORBIDDEN):
        return None, "expansion produced a forbidden token", False
    return lean, None, needs_mathlib(p) or needs_mathlib(q)


def register(name: str, template: str, needs_mathlib_flag: bool) -> dict:
    if name in BUILTINS:
        return {"error": f"{name!r} is a built-in; its meaning is frozen"}
    if "{v}" not in template:
        return {"error": "template must contain the variable placeholder {v}"}
    if any(t in template for t in _FORBIDDEN):
        return {"error": "template contains a forbidden token"}
    user = witcore.load_json(user_registry_path(), {})
    user = user if isinstance(user, dict) else {}
    user[name] = {"lean": template, "needs_mathlib": needs_mathlib_flag}
    witcore.save_json(user_registry_path(), user)
    return {"registered": name, "lean": template, "needs_mathlib": needs_mathlib_flag,
            "note": ("registration asserts this template is the EXACT meaning of the "
                     "predicate the miner computes — faithfulness lives here")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p_reg = sub.add_parser("register")
    p_reg.add_argument("--name", required=True)
    p_reg.add_argument("--lean", required=True, help="Lean template with a {v} placeholder")
    p_reg.add_argument("--needs-mathlib", action="store_true")
    p_exp = sub.add_parser("expand")
    p_exp.add_argument("--form", required=True, help='e.g. "prime(n) -> odd(n)"')
    args = ap.parse_args()

    if args.cmd == "list":
        reg = registry()
        print(json.dumps({"schema": "witsoc.predicate_registry.v1",
                          "builtins": sorted(BUILTINS),
                          "user": sorted(set(reg) - set(BUILTINS)),
                          "registry": {k: reg[k] for k in sorted(reg)}}, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "register":
        result = register(args.name, args.lean, args.needs_mathlib)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if result.get("error") else 0
    if args.cmd == "expand":
        import re
        m = re.match(r"^\s*([a-z_0-9]+)\(n\)\s*->\s*([a-z_0-9]+)\(n\)\s*$", args.form)
        if not m:
            print(json.dumps({"error": "form must be `p(n) -> q(n)`"}))
            return 1
        lean, blocker, needs = implication(m.group(1), m.group(2))
        print(json.dumps({"form": args.form, "lean_statement": lean, "blocker": blocker,
                          "needs_mathlib": needs}, indent=2, ensure_ascii=False))
        return 0 if lean else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
