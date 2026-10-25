"""Policy-candidate guards in web.evaluator and the critic's LLM role."""

import yaml
import pytest

import web.evaluator as ev


@pytest.fixture
def cand_dir(tmp_path, monkeypatch):
    d = tmp_path / "candidates"
    d.mkdir()
    monkeypatch.setattr(ev, "CANDIDATES_DIR", d)
    return d


def _err(correction, scope=()):
    return {"category": "valuation_error", "severity": "major",
            "correction": correction, "policy_scope": list(scope),
            "claim": "c", "issue": "i", "reusable_rule": True}


def _written(d):
    return [yaml.safe_load(p.read_text(encoding="utf-8")) for p in d.glob("*.yaml")]


@pytest.mark.parametrize("rule", [
    "Require a failure below $9.81 before calling exhaustion confirmed.",
    "Treat 9.59 BRL as an assumption-driven value.",
    "Verify ZS guidance from the 8-K.",
])
def test_ticker_or_price_specific_rules_not_written(cand_dir, rule):
    ev._write_policy_candidate(_err(rule), "run1", "ZS")
    assert _written(cand_dir) == []


def test_general_rule_written(cand_dir):
    ev._write_policy_candidate(_err("Label FCF after SBC distinctly from GAAP FCF."), "r", "ZS")
    [c] = _written(cand_dir)
    assert c["applies_to"] == []
    assert "unknown_scope_tags" not in c


def test_ticker_match_is_case_sensitive_word(cand_dir):
    # "ALL" ticker must not block a rule containing the word "all".
    ev._write_policy_candidate(_err("Reconcile all cash and debt lines."), "r", "ALL")
    assert len(_written(cand_dir)) == 1


def test_unknown_scope_tags_kept_and_flagged(cand_dir):
    ev._write_policy_candidate(_err("Check deposit beta.", scope=["banks", "growth_equities"]),
                               "r", "JPM")
    [c] = _written(cand_dir)
    # Not collapsed to [] (which would make it universal).
    assert c["applies_to"] == ["banks", "growth_equities"]
    assert c["unknown_scope_tags"] == ["growth_equities"]


def test_critic_prompt_lists_tag_vocabulary():
    from unittest.mock import MagicMock
    from tradingagents.agents.critics.report_critic import create_report_critic

    llm = MagicMock()
    llm.invoke.return_value.content = "ok"
    create_report_critic(llm)({"company_of_interest": "ZS"})
    prompt = llm.invoke.call_args.args[0]
    assert "Arithmetic Recheck" in prompt
    assert "financial_services" in prompt and "banks" in prompt


def test_web_defaults_include_report_critic_role():
    from web.settings import DEFAULT_WEB_SETTINGS
    assert "report_critic" in DEFAULT_WEB_SETTINGS["agent_llms"]
