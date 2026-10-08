"""Shared policy store: paths + approved policy retrieval.

The policy_memory/ directory lives at the repo root:
  policy_memory/
    evaluation_log.jsonl   — one record per run
    candidates/            — pending YAML files (status: pending)
    policies/              — approved YAML files (status: approved)
    cases/                 — per-run case JSON for outcome tracking

Import from here in both tradingagents/ and web/ code so the root-relative
path calculation lives in exactly one place.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).parent.parent  # tradingagents/ → repo root
POLICY_MEMORY_DIR = _REPO_ROOT / "policy_memory"
POLICIES_DIR = POLICY_MEMORY_DIR / "policies"
CANDIDATES_DIR = POLICY_MEMORY_DIR / "candidates"
CASES_DIR = POLICY_MEMORY_DIR / "cases"
EVAL_LOG = POLICY_MEMORY_DIR / "evaluation_log.jsonl"

_SEVERITY_ORDER = {"critical": 0, "major": 1, "moderate": 2, "minor": 3}


def load_approved_policies(
    applies_to: list[str] | None = None,
    max_policies: int = 10,
) -> str:
    """Return approved policies as a formatted markdown block, or empty string.

    ``applies_to`` — sector/context tags from the ticker's resolved identity
    (e.g. ``["utilities"]``). Universal policies (``applies_to: []``) are
    always included. Sector-specific policies are included only when their tag
    overlaps. Returns empty string when no approved policies exist so callers
    never need to guard against a noisy preamble.
    """
    if not POLICIES_DIR.exists():
        return ""

    policies: list[dict] = []
    for p in POLICIES_DIR.glob("*.yaml"):
        try:
            with p.open(encoding="utf-8") as f:
                policy = yaml.safe_load(f)
            if not policy or policy.get("status") != "approved":
                continue
            scope: list[str] = policy.get("applies_to") or []
            if not scope or not applies_to or any(s in applies_to for s in scope):
                policies.append(policy)
        except Exception:
            continue

    if not policies:
        return ""

    policies.sort(key=lambda p: _SEVERITY_ORDER.get(p.get("severity", "moderate"), 2))
    policies = policies[:max_policies]

    lines = ["**Standing Research Quality Rules (approved from prior analyses):**\n"]
    for i, pol in enumerate(policies, 1):
        scope_str = ", ".join(pol.get("applies_to") or []) or "all analyses"
        rule = (pol.get("rule") or "").strip()
        sev = (pol.get("severity") or "").upper()
        lines.append(f"{i}. [{sev}] {rule}  *(scope: {scope_str})*")

    return "\n".join(lines) + "\n"
