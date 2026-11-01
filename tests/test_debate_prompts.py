"""Debate prompts keep their roles and discourage repetition."""

from unittest.mock import MagicMock

from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator


def _llm():
    llm = MagicMock()
    llm.invoke.return_value.content = "arg"
    return llm


def _state(**debate):
    base = {"company_of_interest": "ZS", "market_report": "", "sentiment_report": "",
            "news_report": "", "fundamentals_report": "", "trader_investment_plan": "HOLD"}
    base["investment_debate_state"] = {"history": "", "bull_history": "", "bear_history": "",
                                       "current_response": "", "count": 0, **debate}
    base["risk_debate_state"] = {"history": "", "aggressive_history": "", "count": 0, **debate}
    return base


def _prompt(llm):
    return llm.invoke.call_args.args[0]


def test_bear_engages_and_sees_own_history():
    llm = _llm()
    create_bear_researcher(llm)(_state(bear_history="MY EARLIER BEAR POINT",
                                       current_response="BULL SAYS X"))
    p = _prompt(llm)
    assert "point by point" in p
    assert "MY EARLIER BEAR POINT" in p
    assert "BULL SAYS X" in p


def test_bull_engages_and_sees_own_history():
    llm = _llm()
    create_bull_researcher(llm)(_state(bull_history="MY EARLIER BULL POINT",
                                       current_response="BEAR SAYS Y"))
    p = _prompt(llm)
    assert "point by point" in p
    assert "MY EARLIER BULL POINT" in p
    assert "BEAR SAYS Y" in p


def test_bull_opening_round_makes_case_outright():
    llm = _llm()
    create_bull_researcher(llm)(_state())
    p = _prompt(llm)
    assert "You open the debate" in p
    assert "point by point" not in p


def test_aggressive_advocates_upside():
    llm = _llm()
    create_aggressive_debator(llm)(_state())
    p = _prompt(llm)
    assert "Aggressive Risk Analyst" in p
    assert "not advocacy" not in p
    assert "Probability weight" in p  # full scenario table on first round


def test_aggressive_does_not_repeat_table_in_later_rounds():
    llm = _llm()
    create_aggressive_debator(llm)(_state(aggressive_history="Aggressive Analyst: table..."))
    p = _prompt(llm)
    assert "Do NOT repeat it" in p
    assert "Probability weight" not in p
