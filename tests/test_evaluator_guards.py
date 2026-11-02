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
    "Require a close below 9.81 before confirming exhaustion.",
    "Use the 2026-10-07 session only if complete.",
    "Treat 120 CHF as the floor.",
])
def test_ticker_or_price_specific_rules_not_written(cand_dir, rule):
    ev._write_policy_candidate(_err(rule), "run1", "ZS")
    assert _written(cand_dir) == []


def test_general_rule_written(cand_dir):
    ev._write_policy_candidate(_err("Label FCF after SBC distinctly from GAAP FCF."), "r", "ZS")
    [c] = _written(cand_dir)
    assert c["applies_to"] == []
    assert "unknown_scope_tags" not in c


def test_general_numeric_rules_still_written(cand_dir):
    for rule in ("Flag stops under 0.5x ATR as noise stops.",
                 "Label RSI above 70 as overbought."):
        ev._write_policy_candidate(_err(rule), "r", "ZS")
    assert len(_written(cand_dir)) == 2


def test_evaluate_run_requires_literal_true(tmp_path, monkeypatch, cand_dir):
    monkeypatch.setattr(ev, "EVAL_LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(ev, "CASES_DIR", tmp_path / "cases")
    monkeypatch.setattr(ev, "POLICIES_DIR", tmp_path / "pol")
    monkeypatch.setattr(ev, "POLICY_MEMORY_DIR", tmp_path)
    review = ("```yaml\nerrors:\n"
              "  - {category: echo_chamber, severity: major, correction: A rule, reusable_rule: 'yes'}\n"
              "  - {category: echo_chamber, severity: major, correction: B rule, reusable_rule: true}\n```")
    ev.evaluate_run("r", "ZS", "2026-10-23", review, "HOLD")
    assert [c["rule"] for c in _written(cand_dir)] == ["B rule"]


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
    # MOD run: differing scenario weights were rated a CRITICAL contradiction.
    assert "Differences of judgement" in prompt and "never CRITICAL" in prompt


def test_web_defaults_include_report_critic_role():
    from web.settings import DEFAULT_WEB_SETTINGS
    assert "report_critic" in DEFAULT_WEB_SETTINGS["agent_llms"]
