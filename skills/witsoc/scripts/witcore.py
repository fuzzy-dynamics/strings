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
    """Shared cross-run lemma library, so verified lemmas compound (Tier E / Phase 3).
    WITSOC_LEMMA_LIBRARY (spec name) takes precedence, then WITSOC_GLOBAL_LIBRARY,
    then the default under the witsoc home."""
    for env in ("WITSOC_LEMMA_LIBRARY", "WITSOC_GLOBAL_LIBRARY"):
        if os.environ.get(env):
            return Path(os.environ[env])
    return Path(witsoc_home() / "global_library")


# --- cmd: sampler / policy bridge (unified) ----------------------------------
def run_sampler(command: str, request: dict, timeout: float = 120.0) -> dict | None:
    """Run an external `cmd:<command>` model/sampler: write JSON request to stdin,
    parse JSON from stdout. Returns None on any failure (never raises)."""
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
    if use_cache and slim["checked"]:
        with _CACHE_LOCK:
            _ensure_mem_cache()[key] = slim
            _MEM_DIRTY += 1
            do_flush = _MEM_DIRTY >= _FLUSH_EVERY
        if do_flush:
            flush_lean_cache()
    return slim


def parallel_first(thunks: list[Callable[[], Any]], accept: Callable[[Any], bool],
                   max_workers: int = 8) -> Any | None:
    """Run thunks concurrently; return the FIRST result satisfying `accept` and
    return immediately — without blocking on slow in-flight thunks. Used by the
    prover to race candidate proofs: a reachable goal must not pay for the heavy
    tactics still grinding in other threads when an easy proof already won.

    Note: we deliberately do NOT use `with ThreadPoolExecutor(...)`, whose exit
    forces shutdown(wait=True) and would block on the in-flight builds. On a win we
    cancel queued work and shutdown(wait=False); the few running subprocesses are
    bounded by lean_check's per-build timeout and finish on their own."""
    from concurrent.futures import as_completed
    pool = ThreadPoolExecutor(max_workers=max_workers)
    try:
        futures = [pool.submit(t) for t in thunks]
        for fut in as_completed(futures):
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
