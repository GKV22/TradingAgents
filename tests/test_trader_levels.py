"""TraderProposal drops entry/stop levels that cannot be executed as stated."""

import pytest

from tradingagents.agents.schemas import TraderProposal, render_trader_proposal


def _p(action, entry, stop):
    return TraderProposal(action=action, reasoning="r", entry_price=entry, stop_loss=stop)


@pytest.mark.parametrize("action,entry,stop", [
    ("Buy", 250.0, 230.0),
    ("Hold", 227.0, 215.0),
    ("Sell", 250.0, 262.0),
    ("Buy", 250.0, None),
    ("Buy", None, 230.0),
])
def test_consistent_levels_kept(action, entry, stop):
    p = _p(action, entry, stop)
    assert (p.entry_price, p.stop_loss) == (entry, stop)
    assert "Level Check" not in render_trader_proposal(p)


@pytest.mark.parametrize("action,entry,stop", [
    ("Hold", 227.0, 227.77),   # the ZS 2026-10-23 run
    ("Buy", 250.0, 250.0),
    ("Sell", 250.0, 240.0),
    ("Buy", -1.0, None),
    ("Buy", 250.0, 0.0),
])
def test_inconsistent_levels_dropped_and_flagged(action, entry, stop):
    p = _p(action, entry, stop)
    assert p.entry_price is None and p.stop_loss is None
    out = render_trader_proposal(p)
    assert "Level Check" in out
    assert out.rstrip().endswith(f"**{action.upper()}**")


def test_private_warning_not_in_llm_schema():
    assert "level_warning" not in str(TraderProposal.model_json_schema())
