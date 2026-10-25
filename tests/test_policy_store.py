"""Tests for sector-scoped policy loading and slot allocation."""

import yaml
import pytest

import tradingagents.policy_store as ps


def _write(dirpath, pid, *, scope=(), category="missing_source", severity="critical",
           rule=None, status="approved"):
    data = {
        "policy_id": pid,
        "applies_to": list(scope),
        "category": category,
        "severity": severity,
        "rule": rule or f"Rule text for {pid}.",
        "status": status,
    }
    (dirpath / f"{pid}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


@pytest.fixture
def policies_dir(tmp_path, monkeypatch):
    d = tmp_path / "policies"
    d.mkdir()
    monkeypatch.setattr(ps, "POLICIES_DIR", d)
    return d


class TestPolicyTags:
    def test_software_company(self):
        tags = ps.policy_tags_for_identity(
            {"sector": "Technology", "industry": "Software - Infrastructure"}
        )
        assert "technology" in tags
        assert "software" in tags
        assert "saas" in tags
        assert "banks" not in tags

    def test_regional_bank(self):
        tags = ps.policy_tags_for_identity(
            {"sector": "Financial Services", "industry": "Banks - Regional"}
        )
        assert {"financial_services", "banks", "banks_regional"} <= set(tags)

    def test_unresolved_identity_has_no_tags(self):
        assert ps.policy_tags_for_identity({}) == []
        assert ps.policy_tags_for_identity(None) == []

    def test_crypto(self):
        assert ps.policy_tags_for_identity({}, asset_type="crypto") == ["crypto"]

    def test_vocabulary_covers_aliases(self):
        for tag in ("banks", "software", "technology", "crypto"):
            assert tag in ps.POLICY_TAG_VOCABULARY


class TestScoping:
    def test_bank_rule_excluded_for_software(self, policies_dir):
        _write(policies_dir, "UNIVERSAL", scope=())
        _write(policies_dir, "BANKS", scope=["banks"])
        out = ps.load_approved_policies(applies_to=["technology", "software"])
        assert "UNIVERSAL" in out
        assert "BANKS" not in out

    def test_bank_rule_included_for_bank(self, policies_dir):
        _write(policies_dir, "BANKS", scope=["banks"])
        assert "BANKS" in ps.load_approved_policies(applies_to=["banks"])

    def test_unresolved_identity_excludes_scoped_rules(self, policies_dir):
        # Regression: the old loader treated "no tags" as "include everything".
        _write(policies_dir, "UNIVERSAL", scope=())
        _write(policies_dir, "BANKS", scope=["banks"])
        for tags in (None, []):
            out = ps.load_approved_policies(applies_to=tags)
            assert "UNIVERSAL" in out
            assert "BANKS" not in out

    def test_pending_and_rejected_ignored(self, policies_dir):
        _write(policies_dir, "PENDING", status="pending")
        _write(policies_dir, "REJECTED", status="rejected")
        assert ps.load_approved_policies() == ""

    def test_missing_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ps, "POLICIES_DIR", tmp_path / "nope")
        assert ps.load_approved_policies() == ""


class TestSlotAllocation:
    def test_one_category_cannot_take_every_slot(self, policies_dir):
        for i in range(12):
            _write(policies_dir, f"MS{i:02d}", category="missing_source", severity="critical")
        _write(policies_dir, "TECH", category="technical_misclassification", severity="moderate")
        _write(policies_dir, "ECHO", category="echo_chamber", severity="minor")
        out = ps.load_approved_policies(max_policies=5)
        assert "TECH" in out
        assert "ECHO" in out
        assert out.count("[CRITICAL]") == 3

    def test_severity_wins_within_category(self, policies_dir):
        _write(policies_dir, "LOW", category="valuation_error", severity="minor")
        _write(policies_dir, "HIGH", category="valuation_error", severity="critical")
        out = ps.load_approved_policies(max_policies=1)
        assert "HIGH" in out
        assert "LOW" not in out

    def test_duplicate_rule_text_kept_once(self, policies_dir):
        _write(policies_dir, "A", rule="Trace each claim to its source.")
        _write(policies_dir, "B", rule="Trace  each claim to its SOURCE.", category="echo_chamber")
        out = ps.load_approved_policies()
        assert out.count("Trace") == 1

    def test_respects_max(self, policies_dir):
        for i in range(20):
            _write(policies_dir, f"P{i:02d}", category=f"cat{i % 4}")
        out = ps.load_approved_policies(max_policies=7)
        assert sum(1 for line in out.splitlines() if line[:1].isdigit()) == 7
