"""Post-analysis evaluation pipeline.

After each run the Report Critic emits markdown with an embedded YAML block.
This module:
  1. Extracts and parses that YAML
  2. Appends a structured record to ``policy_memory/evaluation_log.jsonl``
  3. Writes pending policy candidate YAML files for human review
  4. Writes a case memory JSON for outcome tracking at fixed horizons
  5. Exposes ``load_approved_policies()`` — called at run start to inject
     standing rules into every agent via ``research_policies`` state field

Directory layout (repo-root/policy_memory/):
  evaluation_log.jsonl    — one JSON line per run
  candidates/             — pending YAML files (status: pending)
  policies/               — approved YAML files (status: approved)
  cases/                  — per-run case JSON for outcome tracking
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date as date_type, datetime, timedelta
from typing import Any

import yaml

from tradingagents.policy_store import (
    CANDIDATES_DIR,
    CASES_DIR,
    EVAL_LOG,
    POLICIES_DIR,
    POLICY_MEMORY_DIR,  # re-exported so callers can import from either module
    POLICY_TAG_VOCABULARY,
)

_SEVERITY_ORDER = {"critical": 0, "major": 1, "moderate": 2, "minor": 3}


def _ensure_dirs() -> None:
    for d in (POLICY_MEMORY_DIR, CANDIDATES_DIR, POLICIES_DIR, CASES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _extract_yaml(text: str) -> dict:
    """Pull the first ```yaml ... ``` fence out of critic markdown."""
    match = re.search(r"```yaml\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except Exception:
        return {}


_PRICE_RE = re.compile(r"[$€£¥]\s?\d|\b\d+(?:\.\d+)?\s?(?:BRL|USD|EUR|GBP)\b")


def _is_ticker_specific(rule: str, ticker: str) -> bool:
    """True when a proposed rule names the ticker or a concrete price level.

    Such rules (e.g. "require a failure below $9.81") only make sense for the
    run that produced them; approved as universal they leak into every later
    analysis.
    """
    if ticker and re.search(rf"\b{re.escape(ticker)}\b", rule):
        return True
    return bool(_PRICE_RE.search(rule))


def _write_policy_candidate(error: dict, run_id: str, ticker: str) -> None:
    rule = error.get("correction", "") or ""
    if _is_ticker_specific(rule, ticker):
        return

    scope = [str(t) for t in (error.get("policy_scope") or [])]
    unknown = [t for t in scope if t not in POLICY_TAG_VOCABULARY]

    short = str(uuid.uuid4())[:8].upper()
    cat = error.get("category", "rule").upper().replace("_", "-")
    policy_id = f"{cat}-{short}"

    candidate: dict[str, Any] = {
        "policy_id": policy_id,
        # Unknown tags are kept (not dropped to []), so the rule stays inert
        # rather than silently becoming universal; flagged for review.
        "applies_to": scope,
        "category": error.get("category", ""),
        "severity": error.get("severity", "moderate"),
        "rule": rule,
        "example_claim": error.get("claim", ""),
        "example_issue": error.get("issue", ""),
        "created_from": run_id,
        "example_ticker": ticker,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    if unknown:
        candidate["unknown_scope_tags"] = unknown

    path = CANDIDATES_DIR / f"{policy_id}.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(candidate, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _write_case(
    run_id: str,
    ticker: str,
    date: str,
    decision_block: dict,
    final_decision_text: str,
) -> None:
    try:
        d = date_type.fromisoformat(date)
    except ValueError:
        d = date_type.today()

    case: dict[str, Any] = {
        "case_id": run_id,
        "ticker": ticker,
        "date": date,
        "original_action": decision_block.get("original_action", ""),
        "required_before_upgrade": decision_block.get("required_before_upgrade", []),
        "review_dates": [
            (d + timedelta(days=30)).isoformat(),
            (d + timedelta(days=90)).isoformat(),
            (d + timedelta(days=365)).isoformat(),
        ],
        "outcomes": {},
        "final_decision_text": final_decision_text,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    path = CASES_DIR / f"{run_id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(case, f, indent=2, ensure_ascii=False)


def evaluate_run(
    run_id: str,
    ticker: str,
    date: str,
    analyst_review: str,
    final_decision_text: str,
) -> dict:
    """Parse critic output; write evaluation log, policy candidates, case memory.

    Returns the parsed evaluation record dict (useful for API responses).
    Failures are silently swallowed so a bad critic parse never breaks the SSE
    stream — callers should wrap in try/except if they want to surface errors.
    """
    _ensure_dirs()

    parsed = _extract_yaml(analyst_review)
    summary = parsed.get("run_summary") or {}
    errors = parsed.get("errors") or []
    decision_block = parsed.get("decision") or {}

    record: dict[str, Any] = {
        "run_id": run_id,
        "ticker": ticker,
        "date": date,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "overall_verdict": summary.get("overall_verdict", "unknown"),
        "confidence_in_report": summary.get("confidence_in_report"),
        "confidence_in_recommendation": summary.get("confidence_in_recommendation"),
        "error_count": len(errors),
        "critical_count": sum(1 for e in errors if e.get("severity") == "critical"),
        "errors": errors,
        "decision": decision_block,
    }

    with EVAL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    for error in errors:
        if error.get("reusable_rule"):
            _write_policy_candidate(error, run_id, ticker)

    _write_case(run_id, ticker, date, decision_block, final_decision_text)

    return record


# load_approved_policies is imported from tradingagents.policy_store above
# and re-exported for callers that import from this module.

# ── Policy management (used by API endpoints) ─────────────────────────────


def list_candidates() -> list[dict]:
    """Return all pending policy candidates."""
    _ensure_dirs()
    result = []
    for p in sorted(CANDIDATES_DIR.glob("*.yaml")):
        try:
            with p.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data and data.get("status") == "pending":
                result.append(data)
        except Exception:
            continue
    return result


def list_approved() -> list[dict]:
    """Return all approved policies."""
    _ensure_dirs()
    result = []
    for p in sorted(POLICIES_DIR.glob("*.yaml")):
        try:
            with p.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data:
                result.append(data)
        except Exception:
            continue
    return result


def approve_candidate(policy_id: str) -> bool:
    """Promote a pending candidate to approved. Returns True on success."""
    src = CANDIDATES_DIR / f"{policy_id}.yaml"
    if not src.exists():
        return False
    try:
        with src.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        data["status"] = "approved"
        data["approved_at"] = datetime.utcnow().isoformat() + "Z"
        dst = POLICIES_DIR / f"{policy_id}.yaml"
        with dst.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        src.unlink()
        return True
    except Exception:
        return False


def reject_candidate(policy_id: str) -> bool:
    """Mark a candidate as rejected (updates status in-place). Returns True on success."""
    src = CANDIDATES_DIR / f"{policy_id}.yaml"
    if not src.exists():
        return False
    try:
        with src.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        data["status"] = "rejected"
        with src.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except Exception:
        return False


def list_evaluations(limit: int = 20) -> list[dict]:
    """Return the most recent evaluation log entries (newest first)."""
    if not EVAL_LOG.exists():
        return []
    try:
        lines = EVAL_LOG.read_text(encoding="utf-8").strip().splitlines()
        records = []
        for line in lines:
            try:
                records.append(json.loads(line))
            except Exception:
                continue
        return list(reversed(records))[:limit]
    except Exception:
        return []
