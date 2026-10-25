"""build_initial_state wiring and web-entry ticker validation."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from tradingagents.graph.propagation import Propagator
from tradingagents.graph.trading_graph import TradingAgentsGraph


def _fake_graph():
    g = MagicMock()
    g.propagator = Propagator()
    g.memory_log.get_past_context.return_value = "PAST CONTEXT"
    return g


def test_build_initial_state_carries_identity_memory_and_scoped_policies():
    identity = {"company_name": "Zscaler, Inc.", "sector": "Technology",
                "industry": "Software - Infrastructure"}
    with patch("tradingagents.graph.trading_graph.resolve_instrument_identity",
               return_value=identity), \
         patch("tradingagents.graph.trading_graph.load_approved_policies",
               return_value="POLICIES") as load:
        state = TradingAgentsGraph.build_initial_state(_fake_graph(), "ZS", "2026-10-23")

    assert "Zscaler, Inc." in state["instrument_context"]
    assert state["past_context"] == "PAST CONTEXT"
    assert state["research_policies"] == "POLICIES"
    tags = load.call_args.kwargs["applies_to"]
    assert "software" in tags and "banks" not in tags


def test_build_initial_state_unresolved_identity_passes_no_tags():
    with patch("tradingagents.graph.trading_graph.resolve_instrument_identity",
               return_value={}), \
         patch("tradingagents.graph.trading_graph.load_approved_policies",
               return_value="") as load:
        TradingAgentsGraph.build_initial_state(_fake_graph(), "ZZZZ", "2026-10-23")
    assert load.call_args.kwargs["applies_to"] == []


def test_web_analyze_rejects_path_like_ticker():
    from web.server import app

    resp = TestClient(app).post(
        "/api/analyze", json={"ticker": "../../etc", "date": "2026-10-23"}
    )
    assert resp.status_code == 422
