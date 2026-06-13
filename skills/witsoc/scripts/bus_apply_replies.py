#!/usr/bin/env python3
"""Apply fulfilled Intelligence Bus replies to a Lovasz run.

The bus is intentionally untrusted: a fulfiller can propose a proof, sketch,
mutation, or review, but Witsoc must replay/check it before it affects run
state. This tool consumes fulfilled `prove_sketch` replies, kernel-checks the
submitted Lean proof against the original request goal, and consumes fulfilled
`formalize` replies only after Lean elaborates the proposed statement. Accepted
results are merged into worker_results.json / proof_dependency_dag.json, but a
formalization never proves a node: it only makes the node dispatchable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import request_bus as rb  # noqa: E402
import witcore  # noqa: E402
from witcore import slug  # noqa: E402


# --- formalize reply normalization -------------------------------------------
# The `formalize` gate elaborates a BARE Prop via `#check (fun h : <stmt> => h)`
# (see `_statement_check`). Fleet models routinely reply with a full Lean
# DECLARATION instead — `theorem name (binders) : Prop := proof` — which lands in
# term position and fails to parse ("unexpected token 'theorem'; expected
# term"), burning a whole orchestrator cycle on a formatting mismatch rather than
# on mathematics. This normalizer recovers the bare Prop from a declaration-shaped
# reply so the common error becomes a success. It is sound: the discarded proof
# body is irrelevant to formalization (a formalize never proves — the node stays
# OPEN, merely dispatchable), and the elaboration + forbidden-token gate still
# guards every statement that enters run state. The transformation is recorded
# transparently on the result so no target is silently reshaped.

_DECL_KEYWORDS = ("theorem", "lemma", "example", "proposition", "corollary",
                  "def", "instance", "abbrev")
_DECL_RE = re.compile(r"^(theorem|lemma|example|proposition|corollary|def|instance|abbrev)\b")
_OPEN_BRACKETS = {"(": ")", "{": "}", "[": "]", "⦃": "⦄", "⟨": "⟩"}
_CLOSE_BRACKETS = set(_OPEN_BRACKETS.values())


def _normalize_lean_statement(statement: str) -> tuple[str, bool, str]:
    """Recover a bare Prop from a declaration-shaped formalize reply.

    Returns (normalized_statement, was_normalized, note). When the reply is not a
    recognizable `<keyword> name (binders)? : <type> (:= proof)?` declaration the
    input is returned unchanged with was_normalized=False, and the elaboration
    gate judges it as-is.
    """
    s = (statement or "").strip()
    if not s:
        return statement, False, ""
    m = _DECL_RE.match(s)
    if not m:
        return statement, False, ""
    kw = m.group(1)
    n = len(s)
    i = m.end()
    while i < n and s[i].isspace():
        i += 1
    # optional declaration name (anonymous for `example`)
    name_m = re.match(r"[A-Za-z_α-ω][A-Za-z0-9_'.α-ω]*", s[i:])
    if name_m and kw != "example":
        i += name_m.end()
    # consume binder groups (balanced brackets) + whitespace until the top-level
    # type colon — a ':' at bracket-depth 0 that does not begin ':='.
    binder_start = i
    depth = 0
    type_colon = -1
    while i < n:
        c = s[i]
        if c in _OPEN_BRACKETS:
            depth += 1
        elif c in _CLOSE_BRACKETS:
            depth = max(0, depth - 1)
        elif depth == 0 and c == ":" and not s.startswith(":=", i):
            type_colon = i
            break
        i += 1
    if type_colon < 0:
        return statement, False, ""
    binders = s[binder_start:type_colon].strip()
    # the type runs to the top-level proof body (':=') or a top-level `where`.
    j = type_colon + 1
    depth = 0
    type_end = n
    while j < n:
        c = s[j]
        if c in _OPEN_BRACKETS:
            depth += 1
        elif c in _CLOSE_BRACKETS:
            depth = max(0, depth - 1)
        elif depth == 0 and s.startswith(":=", j):
            type_end = j
            break
        elif depth == 0 and re.match(r"\bwhere\b", s[j:]):
            type_end = j
            break
        j += 1
    type_str = s[type_colon + 1:type_end].strip()
    if not type_str:
        return statement, False, ""
    if binders:
        normalized = f"∀ {binders}, {type_str}"
        note = (f"normalized from `{kw}` declaration: stripped name/proof, "
                "folded binders into ∀")
    else:
        normalized = type_str
        note = f"normalized from `{kw}` declaration: stripped name/proof"
    return normalized, True, note


def _load(path: Path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if data is not None else default
    except Exception:
        return default


def _save(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _kernel_check(goal: str, imports: str, proof: str, lake_dir: Path | None) -> dict:
    try:
        import close_obligation as co
        source = co.lean_source("bus_replay", goal, imports, proof)
        checked = witcore.lean_verify_cached(source, lake_dir)
    except Exception as exc:
        return {"checked": False, "error": str(exc)}
    ok = bool(checked.get("verified"))
    # carry the source so the env-blocker classifier can see a Mathlib-only
    # tactic that core Lean rejected with "unknown tactic".
    return {"checked": ok, "raw": checked, "source": source}


def _statement_check(statement: str, imports: str, lake_dir: Path | None) -> dict:
    source = (f"{imports}\n" if imports else "") + (
        "namespace WitsocFormalization\n\n"
        f"#check (fun h : {statement} => h)\n\n"
        "end WitsocFormalization\n"
    )
    try:
        checked = witcore.lean_verify_cached(source, lake_dir)
    except Exception as exc:
        return {"elaborated": False, "error": str(exc)}
    # A statement that only "elaborates" because it contains `sorry`/`axiom`
    # (e.g. the bare type `sorry`, which type-checks as a term of any type) is
    # not a legitimate formalized goal — reject it even though the build is
    # green. The gate makes a node dispatchable; a placeholder goal must never
    # qualify.
    elaborated = bool(checked.get("verified") or (checked.get("checked") and checked.get("build_ok")))
    ok = elaborated and not checked.get("forbidden")
    return {"elaborated": ok, "raw": checked}


def _proof_packet(run: Path, req: dict, resp: dict, replay: dict) -> dict:
    payload = req.get("payload") if isinstance(req.get("payload"), dict) else {}
    node_id = str(payload.get("node_id") or req.get("id"))
    proof = resp.get("proof")
    ok = bool(replay.get("checked"))
    env_blocker = None if ok else witcore.classify_lean_env_blocker(replay.get("raw"), replay.get("source"))
    if not ok and env_blocker:
        return {
            "worker_id": f"bus-{slug(node_id)}",
            "worker_type": "FORMALIZER",
            "node_id": node_id,
            "claim": str(payload.get("statement") or payload.get("goal") or node_id),
            "target_hash": str(_load(run / "lovasz_run.json", {}).get("target_hash") or ""),
            "dependencies": [node_id, "T"],
            "artifacts": [],
            "session_id": "bus-replay",
            "proof_worktree": str(run / "worktrees" / f"witsoc-proof-bus-{slug(node_id)}"),
            # NOT a math failure — the kernel never got to judge the proof.
            "status": "ENV_BLOCKED",
            "env_blocker": env_blocker,
            "granularity": {"flag": "bus_replay", "atomic": True},
            "evidence": [f"bus_request_id={req.get('id')}",
                         f"env_blocker={env_blocker}"],
            "failure_class": "environment_blocker",
            "next_mutation": (f"orchestrator: provision {env_blocker} "
                              "(build/point WITSOC_LAKE_DIR at a matching Mathlib) "
                              "then re-dispatch — do NOT mutate the math"),
        }
    return {
        "worker_id": f"bus-{slug(node_id)}",
        "worker_type": "FORMALIZER",
        "node_id": node_id,
        "claim": str(payload.get("statement") or payload.get("goal") or node_id),
        "target_hash": str(_load(run / "lovasz_run.json", {}).get("target_hash") or ""),
        "dependencies": [node_id, "T"],
        "artifacts": [],
        "session_id": "bus-replay",
        "proof_worktree": str(run / "worktrees" / f"witsoc-proof-bus-{slug(node_id)}"),
        "status": "CHECKED" if ok else "FAILED_ATTEMPT",
        "granularity": {"flag": "bus_replay", "atomic": True},
        "evidence": [
            f"bus_request_id={req.get('id')}",
            f"kernel_replay={'passed' if ok else 'failed'}",
            *([f"proof={proof}"] if proof else []),
        ],
        "failure_class": "none" if ok else "prover_reply_failed_kernel_replay",
        "next_mutation": (
            "SafeVerify/target-freeze to upgrade CHECKED->VERIFIED_LEAN"
            if ok else "ask fulfiller for a kernel-checking proof or mutate the formal statement"
        ),
        "prover_legal_status": "CHECKED" if ok else "FAILED_ATTEMPT",
        "bus_replay": replay,
    }


def _formalization_payload(resp: dict) -> tuple[str, str, dict]:
    reply = resp if isinstance(resp, dict) else {}
    formalization = reply.get("formalization")
    if isinstance(formalization, dict):
        lean = formalization.get("lean_statement") or formalization.get("statement")
        imports = formalization.get("imports") or formalization.get("lean_imports") or reply.get("imports") or reply.get("lean_imports")
        return str(lean or ""), str(imports or ""), formalization
    return (
        str(reply.get("lean_statement") or reply.get("statement") or ""),
        str(reply.get("imports") or reply.get("lean_imports") or ""),
        reply,
    )


def _formalization_record(req: dict, reply: dict, elaboration: dict, lean_statement: str, imports: str) -> dict:
    payload = req.get("payload") if isinstance(req.get("payload"), dict) else {}
    node_id = str(payload.get("node_id") or req.get("id"))
    ok = bool(elaboration.get("elaborated"))
    # An elaboration that failed only because Mathlib/the toolchain is missing is
    # an ENV blocker, not a bad formalization — flag it so the orchestrator
    # provisions the dependency instead of blaming the fleet's statement.
    env_blocker = None if ok else witcore.classify_lean_env_blocker(elaboration.get("raw"))
    status = "FORMALIZED" if ok else ("ENV_BLOCKED" if env_blocker else "REJECTED")
    return {
        "schema": "witsoc.bus_formalization_result.v1",
        "request_id": req.get("id"),
        "node_id": node_id,
        "status": status,
        "env_blocker": env_blocker,
        "lean_statement": lean_statement if ok else "",
        "lean_imports": imports if ok else "",
        "source_statement": str(payload.get("statement") or ""),
        "elaboration": elaboration,
        "notes": reply.get("notes") if isinstance(reply, dict) else None,
    }


def _validate_extraction(reply: dict) -> tuple[bool, list[str]]:
    """A `theorem_extract` reply only counts when it carries a real extracted
    theorem: a concrete exact_statement (not a PENDING placeholder), at least one
    hypothesis, and a conclusion. A `NONE` reply (source has no usable theorem)
    is a VALID negative result but does not extract a theorem."""
    problems: list[str] = []
    stmt = str(reply.get("exact_statement") or "").strip()
    if not stmt:
        problems.append("missing exact_statement")
    elif stmt.upper().startswith(("PENDING", "TODO", "TBD")):
        problems.append("exact_statement is a placeholder, not extracted")
    elif stmt.upper() == "NONE":
        return False, ["NONE: source carries no usable theorem (recorded as negative)"]
    hyps = reply.get("hypotheses")
    if not isinstance(hyps, list) or not [h for h in hyps if str(h).strip()]:
        problems.append("missing hypotheses list")
    if not str(reply.get("conclusion") or "").strip():
        problems.append("missing conclusion")
    return (not problems), problems


def _apply_extraction_to_audit(run: Path, req: dict, reply: dict) -> dict:
    """Merge a validated theorem extraction into theorem_precondition_audit.json,
    flipping the matching row from PENDING to EXTRACTED. Untracked rows are
    appended so a standalone extraction is still recorded."""
    payload = req.get("payload") if isinstance(req.get("payload"), dict) else {}
    row_id = str(payload.get("row_id") or req.get("id"))
    ok, problems = _validate_extraction(reply if isinstance(reply, dict) else {})
    rec = {
        "schema": "witsoc.bus_extraction_result.v1",
        "request_id": req.get("id"),
        "row_id": row_id,
        "status": "EXTRACTED" if ok else "REJECTED",
        "problems": problems,
        "candidate_theorem": payload.get("candidate_theorem"),
        "source": payload.get("source"),
    }
    if not ok:
        return rec
    audit = _load(run / "theorem_precondition_audit.json", [])
    audit = audit if isinstance(audit, list) else []
    fields = {
        "extraction_status": "EXTRACTED",
        "exact_statement": str(reply.get("exact_statement")).strip(),
        "required_preconditions": [str(h).strip() for h in reply.get("hypotheses", []) if str(h).strip()],
        "conclusion": str(reply.get("conclusion") or "").strip(),
        "missing_preconditions": [str(m).strip() for m in (reply.get("missing_preconditions") or []) if str(m).strip()],
        "formal_availability": str(reply.get("formal_availability") or "unknown"),
        "source_locator": str(reply.get("source_locator") or ""),
        "use_decision": "preconditions_extracted_review_for_use",
        "extracted_by_bus": str(req.get("id")),
    }
    matched = False
    for row in audit:
        if isinstance(row, dict) and str(row.get("row_id")) == row_id:
            row.update(fields)
            matched = True
            break
    if not matched:
        audit.append({"row_id": row_id, "target_subgoal": payload.get("target"),
                      "candidate_theorem": payload.get("candidate_theorem"),
                      "source": payload.get("source"), **fields})
    _save(run / "theorem_precondition_audit.json", audit)
    rec["merged"] = True
    return rec


_SKEPTIC_CHECK_FIELDS = ("target_drift_checked", "hidden_assumptions_checked",
                         "circularity_checked", "weaker_target_checked")
_STRONG_STATUSES = {"CHECKED", "VERIFIED", "LEAN_VERIFIED", "PROVED_SKETCH",
                    "PROOF_DISCHARGED"}


def _apply_literature_search(run: Path, req: dict, reply: dict) -> dict:
    """Merge a `literature_search` reply into a per-problem source ledger so a
    subsequent `theorem-audit` finds sources and emits theorem_extract requests.
    Bootstraps research when no network triage is available. Findings are
    untrusted POINTERS — never theorem evidence until extracted + kernel-gated."""
    payload = req.get("payload") if isinstance(req.get("payload"), dict) else {}
    problem_id = str(payload.get("problem_id") or payload.get("target") or req.get("id"))
    findings = reply.get("findings") if isinstance(reply, dict) else None
    findings = findings if isinstance(findings, list) else []
    sources = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        src = str(f.get("source") or f.get("url") or f.get("arxiv_id") or "")
        title = str(f.get("title") or f.get("claim") or "untitled source")
        if not (src or title):
            continue
        sources.append({
            "title": title, "url": src, "arxiv_id": str(f.get("arxiv_id") or ""),
            "year": str(f.get("year") or ""), "authors": f.get("authors") or [],
            "source_type": "bus_literature_search",
            "claim": str(f.get("claim") or ""), "relevance": str(f.get("relevance") or ""),
        })
    written = 0
    if sources:
        try:
            import literature_engine as le
            path = le.ledger_dir() / f"{slug(problem_id)}.json"
            existing = _load(path, {})
            existing = existing if isinstance(existing, dict) and existing.get("sources") else {}
            prior = existing.get("sources", []) if isinstance(existing, dict) else []
            seen = {(s.get("title"), s.get("url")) for s in prior if isinstance(s, dict)}
            merged = list(prior) + [s for s in sources if (s["title"], s["url"]) not in seen]
            ledger = {
                "schema": "witsoc.literature_ledger.v1",
                "problem_id": problem_id,
                "queries": [{"query": str(payload.get("target") or problem_id), "source": "bus"}],
                "sources": merged,
                "note": "sources are untrusted pointers from a bus literature_search; not theorem evidence",
            }
            witcore.save_json(path, ledger)
            written = len(sources)
        except Exception as exc:
            return {"schema": "witsoc.bus_literature_result.v1", "request_id": req.get("id"),
                    "status": "REJECTED", "error": str(exc)}
    return {
        "schema": "witsoc.bus_literature_result.v1",
        "request_id": req.get("id"),
        "problem_id": problem_id,
        "status": "RECORDED" if written else "EMPTY",
        "sources_recorded": written,
        "next": "re-run `witsoc literature theorem-audit` to emit theorem_extract requests",
    }


def _apply_skeptic_to_run(run: Path, req: dict, reply: dict, dag: list[dict]) -> tuple[dict, bool]:
    """Record a bus `skeptic` reply into skeptic_reviews.json. Contract: a skeptic
    can ONLY demote/refute — it never certifies or upgrades. A bare non-refutation
    counts as light corroboration (the progress grade reads it) but does NOT by
    itself satisfy the strict MATHEMATICAL_SOLVE fleet bar: the four independent
    check fields are recorded as True only when the reply explicitly asserts them.
    Uncertainty (missing `refuted`) is treated as a refutation, conservatively."""
    payload = req.get("payload") if isinstance(req.get("payload"), dict) else {}
    node_id = str(payload.get("node_id") or payload.get("node") or "")
    refuted = reply.get("refuted")
    # conservative: anything but an explicit False is a refutation
    is_pass = (refuted is False)
    review_id = str(req.get("id"))
    review = {
        "schema": "witsoc.skeptic_review.v1",
        "review_id": review_id,
        "node_id": node_id,
        "verdict": "pass" if is_pass else "refute",
        "refuted": (not is_pass),
        "reasoning": str(reply.get("reasoning") or reply.get("reason") or ""),
        "source": "bus",
    }
    # carry per-dimension checks ONLY when the reply affirms them (no manufacture)
    for f in _SKEPTIC_CHECK_FIELDS:
        review[f] = (reply.get(f) is True) if is_pass else False

    reviews = _load(run / "skeptic_reviews.json", [])
    reviews = reviews if isinstance(reviews, list) else []
    reviews = [r for r in reviews if not (isinstance(r, dict) and str(r.get("review_id")) == review_id)]
    reviews.append(review)
    _save(run / "skeptic_reviews.json", reviews)

    changed = False
    for node in dag:
        if not isinstance(node, dict) or str(node.get("node_id")) != node_id:
            continue
        if is_pass:
            node.setdefault("skeptic_review_id", review_id)
        else:
            # demotion only: a refuted strong node drops to GAP, never upgrades
            if str(node.get("status") or "").upper() in _STRONG_STATUSES:
                node["status"] = "GAP"
                node.setdefault("evidence", []).append(f"skeptic_refuted:{review_id}")
            node["skeptic_refuted_by"] = review_id
        changed = True
    return review, changed


def _apply_formalization_to_dag(run: Path, req: dict, rec: dict, dag: list[dict]) -> bool:
    if rec["status"] != "FORMALIZED":
        return False
    payload = req.get("payload") if isinstance(req.get("payload"), dict) else {}
    node_id = str(payload.get("node_id") or req.get("id"))
    changed = False
    for node in dag:
        if not isinstance(node, dict) or str(node.get("node_id")) != node_id:
            continue
        node["lean_statement"] = rec["lean_statement"]
        if rec.get("lean_imports"):
            node["lean_imports"] = rec["lean_imports"]
        node["status"] = "OPEN"
        node["formalized_by_bus"] = str(req.get("id"))
        node.setdefault("evidence", []).append(f"bus_formalization:{req.get('id')}")
        changed = True
    queue = _load(run / "actual_lemma_queue.json", [])
    if isinstance(queue, list):
        q_changed = False
        for item in queue:
            if not isinstance(item, dict) or str(item.get("node_id")) != node_id:
                continue
            item["lean_statement"] = rec["lean_statement"]
            if rec.get("lean_imports"):
                item["lean_imports"] = rec["lean_imports"]
            item["status"] = "OPEN"
            item["formalized_by_bus"] = str(req.get("id"))
            q_changed = True
        if q_changed:
            _save(run / "actual_lemma_queue.json", queue)
            changed = True
    return changed


def apply(run: Path, lake_dir: Path | None = None) -> dict:
    lake_dir = witcore.enable_mathlib_mode(lake_dir)
    bus = run / "bus"
    reqs = rb.requests_by_id(bus)
    responses = rb.responses_by_id(bus)
    applied_path = run / "bus" / "applied.jsonl"
    applied_ids = {str(r.get("id")) for r in rb._read_jsonl(applied_path)}  # type: ignore[attr-defined]
    worker_results = _load(run / "worker_results.json", [])
    worker_results = worker_results if isinstance(worker_results, list) else []
    dag = _load(run / "proof_dependency_dag.json", [])
    dag = dag if isinstance(dag, list) else []
    dag_by_id = {str(n.get("node_id")): n for n in dag if isinstance(n, dict)}

    packets = []
    formalizations = []
    extractions = []
    skeptic_reviews = []
    literature = []
    skipped = []
    dag_changed = False
    for rid, req in reqs.items():
        if rid in applied_ids or rid not in responses:
            continue
        role = req.get("role")
        if role not in {"prove_sketch", "formalize", "theorem_extract", "skeptic", "literature_search"}:
            skipped.append({"id": rid, "role": req.get("role"), "reason": "unsupported_role"})
            continue
        payload = req.get("payload") if isinstance(req.get("payload"), dict) else {}
        reply = responses[rid].get("reply") if isinstance(responses[rid], dict) else {}
        if role == "literature_search":
            literature.append(_apply_literature_search(run, req, reply if isinstance(reply, dict) else {}))
        elif role == "skeptic":
            review, ch = _apply_skeptic_to_run(run, req, reply if isinstance(reply, dict) else {}, dag)
            skeptic_reviews.append(review)
            if ch:
                dag_changed = True
        elif role == "theorem_extract":
            extractions.append(_apply_extraction_to_audit(run, req, reply if isinstance(reply, dict) else {}))
        elif role == "prove_sketch":
            proof = reply.get("proof") if isinstance(reply, dict) else None
            goal = str(payload.get("goal") or "")
            imports = str(payload.get("imports") or "")
            if not (goal and isinstance(proof, str) and proof.strip()):
                replay = {"checked": False, "error": "missing goal or proof"}
            else:
                replay = _kernel_check(goal, imports, proof, lake_dir)
            pkt = _proof_packet(run, req, reply if isinstance(reply, dict) else {}, replay)
            packets.append(pkt)
            node = dag_by_id.get(str(pkt["node_id"]))
            if node and replay.get("checked"):
                node["status"] = "CHECKED"
                node["bus_replay_worker_id"] = pkt["worker_id"]
                node["proof"] = proof
                node.setdefault("evidence", []).append(f"bus_replay:{rid}")
                dag_changed = True
        else:
            lean_statement, imports, formalization = _formalization_payload(reply if isinstance(reply, dict) else {})
            normalized, was_normalized, norm_note = _normalize_lean_statement(lean_statement)
            if not normalized.strip():
                elaboration = {"elaborated": False, "error": "missing lean_statement"}
            else:
                elaboration = _statement_check(normalized, imports, lake_dir)
            rec = _formalization_record(req, formalization, elaboration, normalized, imports)
            if was_normalized:
                rec["normalized_from_declaration"] = True
                rec["original_reply_statement"] = lean_statement
                rec["normalization_note"] = norm_note
            formalizations.append(rec)
            if _apply_formalization_to_dag(run, req, rec, dag):
                dag_changed = True
        if role == "literature_search":
            applied_status = literature[-1]["status"]
        elif role == "skeptic":
            applied_status = skeptic_reviews[-1]["verdict"]
        elif role == "theorem_extract":
            applied_status = extractions[-1]["status"]
        elif role == "prove_sketch":
            applied_status = packets[-1]["status"]
        else:
            applied_status = formalizations[-1]["status"]
        rb._append_jsonl(applied_path, {  # type: ignore[attr-defined]
            "schema": "witsoc.bus_applied.v1",
            "id": rid,
            "node_id": str(payload.get("node_id") or rid),
            "role": role,
            "status": applied_status,
        })

    if packets or formalizations or extractions or skeptic_reviews or literature or dag_changed:
        replace = {(p["node_id"], p["worker_type"]) for p in packets}
        worker_results = [
            w for w in worker_results
            if not (isinstance(w, dict) and (w.get("node_id"), w.get("worker_type")) in replace)
        ]
        worker_results.extend(packets)
        if packets:
            _save(run / "worker_results.json", worker_results)
        if formalizations:
            existing = _load(run / "formalization_results.json", [])
            existing = existing if isinstance(existing, list) else []
            ids = {r["request_id"] for r in formalizations}
            existing = [r for r in existing if not (isinstance(r, dict) and r.get("request_id") in ids)]
            existing.extend(formalizations)
            _save(run / "formalization_results.json", existing)
        _save(run / "proof_dependency_dag.json", dag)
        try:
            import run_ledger
            run_ledger.auto_ingest(run)
        except Exception:
            pass

    return {
        "schema": "witsoc.bus_apply_replies.v1",
        "run_dir": str(run),
        "applied": len(packets) + len(formalizations) + len(extractions) + len(skeptic_reviews) + len(literature),
        "checked": sum(1 for p in packets if p["status"] == "CHECKED"),
        "failed": sum(1 for p in packets if p["status"] == "FAILED_ATTEMPT"),
        "formalized": sum(1 for r in formalizations if r["status"] == "FORMALIZED"),
        "formalization_rejected": sum(1 for r in formalizations if r["status"] == "REJECTED"),
        "env_blocked": (sum(1 for p in packets if p["status"] == "ENV_BLOCKED")
                        + sum(1 for r in formalizations if r["status"] == "ENV_BLOCKED")),
        "extracted": sum(1 for r in extractions if r["status"] == "EXTRACTED"),
        "extraction_rejected": sum(1 for r in extractions if r["status"] == "REJECTED"),
        "skeptic_pass": sum(1 for r in skeptic_reviews if r["verdict"] == "pass"),
        "skeptic_refute": sum(1 for r in skeptic_reviews if r["verdict"] == "refute"),
        "literature_recorded": sum(r.get("sources_recorded", 0) for r in literature),
        "skipped": skipped,
        "packets": packets,
        "formalizations": formalizations,
        "extractions": extractions,
        "skeptic_reviews": skeptic_reviews,
        "literature": literature,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--lake-dir", type=Path, default=None)
    args = ap.parse_args()
    print(json.dumps(apply(args.run_dir, args.lake_dir), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
