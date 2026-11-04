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

import re
from collections.abc import Mapping
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).parent.parent  # tradingagents/ → repo root
POLICY_MEMORY_DIR = _REPO_ROOT / "policy_memory"
POLICIES_DIR = POLICY_MEMORY_DIR / "policies"
CANDIDATES_DIR = POLICY_MEMORY_DIR / "candidates"
CASES_DIR = POLICY_MEMORY_DIR / "cases"
EVAL_LOG = POLICY_MEMORY_DIR / "evaluation_log.jsonl"

_SEVERITY_ORDER = {"critical": 0, "major": 1, "moderate": 2, "minor": 3}

# Tags derived from yfinance sector names (slugified).
SECTOR_TAGS = (
    "basic_materials",
    "communication_services",
    "consumer_cyclical",
    "consumer_defensive",
    "energy",
    "financial_services",
    "healthcare",
    "industrials",
    "real_estate",
    "technology",
    "utilities",
)

# Industry keyword -> extra tags. Matched case-insensitively against the
# yfinance industry string ("Banks - Regional", "Software - Infrastructure").
_INDUSTRY_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("bank", ("banks",)),
    ("software", ("software", "saas")),
    ("semiconductor", ("semiconductors",)),
    ("insurance", ("insurance",)),
    ("reit", ("reits",)),
    ("biotech", ("biotech",)),
    ("utilities", ("utilities",)),
)

# The closed vocabulary the Report Critic may use for ``policy_scope``.
POLICY_TAG_VOCABULARY = tuple(
    sorted(set(SECTOR_TAGS) | {t for _, tags in _INDUSTRY_ALIASES for t in tags} | {"crypto"})
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def policy_tags_for_identity(
    identity: Mapping[str, str] | None,
    asset_type: str = "stock",
) -> list[str]:
    """Map a resolved instrument identity to policy scope tags.

    Returns the slugified sector, the slugified industry, and any industry
    aliases (e.g. ``Banks - Regional`` -> ``banks``). Empty when the identity
    could not be resolved, in which case only universal policies apply.
    """
    tags: set[str] = set()
    if asset_type == "crypto":
        tags.add("crypto")
    identity = identity or {}
    sector = identity.get("sector") or ""
    industry = identity.get("industry") or ""
    if sector:
        tags.add(_slug(sector))
    if industry:
        tags.add(_slug(industry))
        lowered = industry.lower()
        for keyword, extra in _INDUSTRY_ALIASES:
            if keyword in lowered:
                tags.update(extra)
    return sorted(tags)


def _select_diverse(policies: list[dict], max_policies: int) -> list[dict]:
    """Pick up to ``max_policies`` round-robin across categories.

    Within a category, higher severity wins. Round-robin stops one crowded
    category (e.g. eighteen ``critical`` missing-source rules) from taking
    every slot. Rules with identical text are kept once.
    """
    seen_rules: set[str] = set()
    by_category: dict[str, list[dict]] = {}
    for pol in sorted(
        policies, key=lambda p: _SEVERITY_ORDER.get(p.get("severity", "moderate"), 2)
    ):
        key = " ".join((pol.get("rule") or "").lower().split())
        if not key or key in seen_rules:
            continue
        seen_rules.add(key)
        by_category.setdefault(pol.get("category") or "other", []).append(pol)

    # Order categories by their best rule's severity so the first pass is stable.
    queues = sorted(
        by_category.values(),
        key=lambda q: _SEVERITY_ORDER.get(q[0].get("severity", "moderate"), 2),
    )
    selected: list[dict] = []
    while len(selected) < max_policies and any(queues):
        for queue in queues:
            if queue and len(selected) < max_policies:
                selected.append(queue.pop(0))
    return selected


def load_approved_policies(
    applies_to: list[str] | None = None,
    max_policies: int = 25,
) -> str:
    """Return approved policies as a formatted markdown block, or empty string.

    ``applies_to`` — scope tags from the ticker's resolved identity (see
    :func:`policy_tags_for_identity`). Universal policies (``applies_to: []``)
    are always included. Scoped policies are included only when one of their
    tags overlaps ``applies_to``; when ``applies_to`` is empty or ``None``
    (identity unresolved) no scoped policy is included. Returns empty string
    when no approved policies apply so callers never need to guard against a
    noisy preamble.
    """
    if not POLICIES_DIR.exists():
        return ""

    wanted = set(applies_to or [])
    policies: list[dict] = []
    for p in POLICIES_DIR.glob("*.yaml"):
        try:
            with p.open(encoding="utf-8") as f:
                policy = yaml.safe_load(f)
            if not policy or policy.get("status") != "approved":
                continue
            scope: list[str] = policy.get("applies_to") or []
            if not scope or wanted.intersection(scope):
                policies.append(policy)
        except Exception:
            continue

    if not policies:
        return ""

    # Scoped rules matched this instrument specifically, so they go first.
    scoped = [p for p in policies if p.get("applies_to")]
    universal = [p for p in policies if not p.get("applies_to")]
    policies = _select_diverse(scoped, max_policies)
    policies += _select_diverse(universal, max_policies - len(policies))

    lines = ["**Standing Research Quality Rules (approved from prior analyses):**\n"]
    for i, pol in enumerate(policies, 1):
        scope_str = ", ".join(pol.get("applies_to") or []) or "all analyses"
        rule = (pol.get("rule") or "").strip()
        sev = (pol.get("severity") or "").upper()
        lines.append(f"{i}. [{sev}] {rule}  *(scope: {scope_str})*")

    return "\n".join(lines) + "\n"
