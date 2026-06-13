#!/usr/bin/env python3
"""witcore — the shared substrate every Witsoc tool builds on.

One place for the conventions that were drifting across scripts: JSON IO, the
status vocabulary, the `cmd:` sampler/policy bridge (was duplicated in
discovery_engine and autoformalize), a content-hash Lean verification cache (the
prover builds many tiny files — caching identical (source,lake) pairs is the main
efficiency win), and the global lemma-library path that lets results compound
across runs.

Import this instead of re-implementing helpers. It re-exports `lean_verify` /
`run_lean_check` (from lean_check) and `solve_smt` / `check_drat` (from
kernel_tools) so a tool needs only `import witcore`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import kernel_tools  # noqa: E402
from lean_check import lean_verify, run_lean_check, scan_forbidden  # noqa: E402,F401

solve_smt = kernel_tools.solve_smt
check_drat = kernel_tools.check_drat

# --- Status vocabulary -------------------------------------------------------
# Accepted = usable in a downstream proof. MACHINE = asserts a machine guarantee
# and therefore needs an independently re-checked certificate (see
# recheck_certificates / validate_proof_dag_integrity).
ACCEPTED = {"VERIFIED", "CHECKED", "PROVED_SKETCH", "PARTIAL", "CONDITIONAL"}
MACHINE_STATUS = {"VERIFIED", "CHECKED"}
UNUSABLE = {"CONJECTURE", "REJECTED", "FAILED_ATTEMPT", "GAP", "OPEN"}
# Foundation-aware outcomes (Tier D): legitimate terminal states for a target
# that cannot simply be proved or disproved in the working foundation.
FOUNDATION_OUTCOMES = {"INDEPENDENT", "RELATIVE_CONSISTENCY", "INFEASIBLE"}


# --- JSON IO -----------------------------------------------------------------
def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def records(path: Path) -> list[dict]:
    data = load_json(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def cosine(a, b) -> float:
    """Cosine similarity of two token Counters (was duplicated in five tools)."""
    if not a or not b:
        return 0.0
    import math
    dot = sum(a[k] * b.get(k, 0) for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def slug(text: str) -> str:
    """Filesystem/id-safe slug (was duplicated in three dispatch tools)."""
    import re
    s = re.sub(r"[^a-zA-Z0-9_+-]+", "-", text.strip()).strip("-").lower()
    return s or "node"


def append_record(path: Path, record: dict, dedup_key: str | None = None) -> None:
    existing = load_json(path, [])
    if not isinstance(existing, list):
        existing = []
    if dedup_key and record.get(dedup_key) is not None:
        existing = [r for r in existing if not (isinstance(r, dict) and r.get(dedup_key) == record[dedup_key])]
    existing.append(record)
    save_json(path, existing)


# --- Paths -------------------------------------------------------------------
def witsoc_home() -> Path:
    return Path(os.environ.get("WITSOC_HOME", str(Path.home() / ".witsoc")))


def global_library() -> Path:
    """LIVE knowledge store (Part 2 of the two-part DB): the shared cross-run
    lemma library deep runs harvest into, so verified lemmas compound (Tier E /
    Phase 3) and other agents can query the same DB. WITSOC_LEMMA_LIBRARY (spec
    name) takes precedence, then WITSOC_GLOBAL_LIBRARY, then the default under
    the witsoc home. See references/knowledge-stores.md."""
    for env in ("WITSOC_LEMMA_LIBRARY", "WITSOC_GLOBAL_LIBRARY"):
        if os.environ.get(env):
            return Path(os.environ[env])
    return Path(witsoc_home() / "global_library")


def default_lake_dir() -> Path | None:
    """Mathlib project used for kernel checks in MATHLIB MODE. Resolution:
    WITSOC_CORE_ONLY=1 disables; WITSOC_LAKE_DIR overrides; else ~/mathlib4
    when a built lake project exists there. Campaigns default to Mathlib mode
    (the reach unlock: ring/nlinarith/norm_num/decide); unit tests and quick
    `witsoc prove` calls stay core-Lean unless they opt in."""
    if os.environ.get("WITSOC_CORE_ONLY"):
        return None
    env = os.environ.get("WITSOC_LAKE_DIR")
    if env:
        p = Path(env)
        return p if p.exists() else None
    p = Path.home() / "mathlib4"
    if (p / "lakefile.lean").exists() or (p / "lakefile.toml").exists():
        return p
    return None


# Diagnostic signatures that mean a Lean check failed for ENVIRONMENT reasons
# (a missing/unbuilt Mathlib, a toolchain mismatch) rather than because the goal
# is hard. Classifying these lets the orchestrator distinguish "provision the
# dependency" from "this is mathematically open" instead of miscounting an env
# gap as a proof failure.
# NOTE: matched case-insensitively against lowercased diagnostics, so keep
# these signatures lowercase.
_MATHLIB_UNAVAILABLE_SIGS = (
    "unknown module prefix 'mathlib'",
    "no directory 'mathlib'",
    "file 'mathlib.olean'",
    "unknown package 'mathlib'",
)
_TOOLCHAIN_SIGS = (
    "is not compatible with",
    "wrong lean version",
    "toolchain",
)

# Tactics/terms that live in Mathlib, not core Lean. When the build fails with
# "unknown tactic"/"unknown identifier" AND the proof uses one of these, the
# failure is environmental (Mathlib not loaded), not a wrong proof — core Lean 4
# does NOT ship ring/nlinarith/linarith/etc. (it has rfl/decide/omega/simp/grind).
_MATHLIB_TACTICS = (
    "ring_nf", "ring", "nlinarith", "linarith", "polyrith", "positivity",
    "field_simp", "gcongr", "norm_num", "linear_combination", "fourier",
    "aesop", "continuity", "measurability", "mono", "bound",
)
_TACTIC_RE = re.compile(r"(?<![A-Za-z_])(" + "|".join(_MATHLIB_TACTICS) + r")(?![A-Za-z_])")


def classify_lean_env_blocker(result: "dict | str | None", source: str | None = None) -> str | None:
    """Return an environment-blocker label if a Lean failure was caused by the
    environment, else None. Conservative: only fires on clear signatures, so a
    genuine proof/elaboration error is never masked as an env blocker.

    `source` is the Lean text that failed; when a build dies on "unknown tactic"
    and that text invokes a Mathlib-only tactic, the real cause is a missing
    Mathlib, not a bad proof — so it is classified as `mathlib_unavailable`."""
    if result is None:
        return None
    if isinstance(result, dict):
        # a green build is never an env blocker
        if result.get("verified") or result.get("build_ok"):
            return None
        diag = str(result.get("diagnostics") or result.get("error") or "")
    else:
        diag = str(result)
    low = diag.lower()
    if any(sig in low for sig in _MATHLIB_UNAVAILABLE_SIGS):
        return "mathlib_unavailable"
    if "import mathlib" in low and "error" in low:
        return "mathlib_unavailable"
    # a Mathlib-only tactic that core Lean cannot find
    if ("unknown tactic" in low or "unknown identifier" in low) and source and _TACTIC_RE.search(source):
        return "mathlib_unavailable"
    if any(sig in low for sig in _TOOLCHAIN_SIGS) and "lean" in low:
        return "toolchain_mismatch"
    return None


def enable_mathlib_mode(lake_dir: Path | str | None = None) -> Path | None:
    """Resolve the lake dir and flip on WITSOC_LAKE_ENV (proof_search candidate
    narrowing + lean_check `lake env lean`) for this process AND its children
    (the prover runs as a subprocess and inherits the environment)."""
    lake = Path(lake_dir) if lake_dir else default_lake_dir()
    if lake is not None:
        os.environ.setdefault("WITSOC_LAKE_ENV", "1")
    return lake


def reference_dir() -> Path:
    """REFERENCE knowledge store (Part 1 of the two-part DB): curated, read-only
    atlases of common theorems (bundled core atlas, built Mathlib atlas, promoted
    kernel-verified library lemmas) plus their SQLite search index. Runs never
    write here except via the explicit, kernel-gated `witsoc atlas promote`."""
    return Path(os.environ.get("WITSOC_REFERENCE", str(witsoc_home() / "reference")))


# --- cmd: sampler / policy bridge (unified) ----------------------------------
def run_sampler(command: str, request: dict, timeout: float = 120.0) -> dict | None:
    """Run an external `cmd:<command>` model/sampler: write JSON request to stdin,
    parse JSON from stdout. Returns None on any failure (never raises).

    `bus:` routes the request through the Intelligence Bus instead of a
    subprocess (request_bus.py): emit-or-consume against the orchestrator
    queue — a fulfilled request returns its reply like any sampler; a freshly
    emitted one returns None, which consumers already treat as 'no
    contribution this round' and pick up after the orchestrator fulfills."""
    if command.startswith("bus:"):
        try:
            import request_bus
            return request_bus.sample_via_bus(request)
        except Exception:
            return None
    if command.startswith("cmd:"):
        command = command[4:]
    try:
        r = subprocess.run(command, shell=True, input=json.dumps(request), text=True,
                           capture_output=True, timeout=timeout, check=False)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return json.loads(r.stdout)
    except Exception:
        return None


# --- Lean verification cache (efficiency) ------------------------------------
def _cache_path() -> Path:
    return witsoc_home() / "lean_cache.json"


# In-process cache: load the on-disk cache once per process, keep it in memory,
# and flush periodically. The prover fires thousands of candidate builds; the old
# code re-read AND re-wrote the whole growing JSON on every call (O(file) each),
# which dominated runtime. Now lookups are dict-O(1) and disk writes are batched.
import threading  # noqa: E402

_MEM_CACHE: dict | None = None
_MEM_DIRTY = 0
_FLUSH_EVERY = 50
_CACHE_LOCK = threading.Lock()


def _ensure_mem_cache() -> dict:
    global _MEM_CACHE
    if _MEM_CACHE is None:
        loaded = load_json(_cache_path(), {})
        _MEM_CACHE = loaded if isinstance(loaded, dict) else {}
    return _MEM_CACHE


def flush_lean_cache() -> None:
    global _MEM_DIRTY
    with _CACHE_LOCK:
        if _MEM_CACHE is not None and _MEM_DIRTY:
            try:
                save_json(_cache_path(), dict(_MEM_CACHE))  # snapshot under lock
                _MEM_DIRTY = 0
            except Exception:
                pass


import atexit  # noqa: E402
atexit.register(flush_lean_cache)


def lean_verify_cached(source: str, lake_dir: Path | None = None, use_cache: bool = True) -> dict:
    """lean_verify on Lean *source text*, memoised by content hash. The prover
    fires many candidate builds; identical (source, lake) pairs return instantly."""
    import tempfile
    global _MEM_DIRTY
    key = hashlib.sha256((source + "||" + str(lake_dir or "")).encode("utf-8")).hexdigest()
    if use_cache:
        with _CACHE_LOCK:
            cache = _ensure_mem_cache()
            if key in cache:
                return {**cache[key], "cached": True}
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as fh:
        fh.write(source)
        tmp = Path(fh.name)
    try:
        verdict = lean_verify(tmp, lake_dir)
    finally:
        tmp.unlink(missing_ok=True)
    slim = {"verified": verdict.get("verified"), "checked": verdict.get("checked"),
            "forbidden": verdict.get("forbidden", []), "reason": verdict.get("reason"),
            "build_ok": verdict.get("build", {}).get("ok")}
    # Keep the compiler's own error text for FAILED candidates: error-guided repair
    # (proof_search.repair_mutations) needs the residual-goal / unknown-identifier
    # message, and the old slim record threw it away. Bounded so the cache stays small.
    if not slim["verified"]:
        build = verdict.get("build", {}) or {}
        diag = (str(build.get("stdout", "")) + "\n" + str(build.get("stderr", ""))).strip()
        if diag:
            slim["diagnostics"] = diag[:1200]
    if use_cache and slim["checked"]:
        with _CACHE_LOCK:
            _ensure_mem_cache()[key] = slim
            _MEM_DIRTY += 1
            do_flush = _MEM_DIRTY >= _FLUSH_EVERY
        if do_flush:
            flush_lean_cache()
    return slim


def parallel_first(thunks: list[Callable[[], Any]], accept: Callable[[Any], bool],
                   max_workers: int = 8, deadline: float | None = None) -> Any | None:
    """Run thunks concurrently; return the FIRST result satisfying `accept` and
    return immediately — without blocking on slow in-flight thunks. Used by the
    prover to race candidate proofs: a reachable goal must not pay for the heavy
    tactics still grinding in other threads when an easy proof already won.

    `deadline` (epoch seconds from time.monotonic): once passed, stop waiting on
    in-flight results and return None. The measured fact this serves: a
    deterministic goal that is going to close, closes FAST; one still grinding
    after the wall-clock budget will not close — so the bus should engage
    instead of the engine burning minutes. Per-build WITSOC_LEAN_TIMEOUT still
    bounds each subprocess; this bounds the WHOLE race.

    Note: we deliberately do NOT use `with ThreadPoolExecutor(...)`, whose exit
    forces shutdown(wait=True) and would block on the in-flight builds. On a win we
    cancel queued work and shutdown(wait=False); the few running subprocesses are
    bounded by lean_check's per-build timeout and finish on their own."""
    import time as _time
    from concurrent.futures import as_completed
    pool = ThreadPoolExecutor(max_workers=max_workers)
    try:
        futures = [pool.submit(t) for t in thunks]
        for fut in as_completed(futures):
            if deadline is not None and _time.monotonic() >= deadline:
                pool.shutdown(wait=False, cancel_futures=True)
                return None
            try:
                res = fut.result()
            except Exception:
                continue
            if accept(res):
                for f in futures:
                    f.cancel()
                pool.shutdown(wait=False, cancel_futures=True)
                return res
        return None
    finally:
        # Open case (no win): let queued work drain but don't hang the process.
        pool.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    print(json.dumps({
        "witsoc_home": str(witsoc_home()),
        "global_library": str(global_library()),
        "lean_cache": str(_cache_path()),
        "status_vocab": {"accepted": sorted(ACCEPTED), "machine": sorted(MACHINE_STATUS),
                         "unusable": sorted(UNUSABLE), "foundation": sorted(FOUNDATION_OUTCOMES)},
    }, indent=2))
