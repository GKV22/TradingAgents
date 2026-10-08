"""Portfolio Manager: synthesises the risk-analyst debate into the final decision.

Uses LangChain's ``with_structured_output`` so the LLM produces a typed
``PortfolioDecision`` directly, in a single call.  The result is rendered
back to markdown for storage in ``final_trade_decision`` so memory log,
CLI display, and saved reports continue to consume the same shape they do
today.  When a provider does not expose structured output, the agent falls
back gracefully to free-text generation.
"""

from __future__ import annotations

from tradingagents.agents.schemas import PortfolioDecision, render_pm_decision
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    NO_EXTERNAL_TOOLS,
    bind_structured,
    invoke_structured_or_freetext,
)


def create_portfolio_manager(llm):
    structured_llm = bind_structured(llm, PortfolioDecision, "Portfolio Manager")

    def portfolio_manager_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state)

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        research_plan = state["investment_plan"]
        trader_plan = state["trader_investment_plan"]

        past_context = state.get("past_context", "")
        lessons_line = (
            f"- Lessons from prior decisions and outcomes:\n{past_context}\n"
            if past_context
            else ""
        )

        prompt = f"""As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision.

{instrument_context}

---

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction to enter or add to position
- **Overweight**: Favorable outlook, gradually increase exposure
- **Hold**: Maintain current position, no action needed; also use if core data quality issues prevent a reliable directional call
- **Underweight**: Reduce exposure, take partial profits
- **Sell**: Exit position or avoid entry

**Context:**
- Research Manager's investment plan: **{research_plan}**
- Trader's transaction proposal: **{trader_plan}**
{lessons_line}
**Risk Analysts Debate History:**
{history}

---

**The `investment_thesis` field must contain all five sections in order:**

**Section 1 — Verified Facts:** Table of every key figure used in the analysis (current price, 50-day SMA, 200-day SMA, 52W high/low, trailing EPS with GAAP/adjusted label and period, forward EPS with source, forward P/E, PEG with growth rate cited, revenue TTM, gross/operating margins, FCF, net debt, guidance exact wording). Label GAAP vs adjusted and period for each.

**Section 2 — Disputed Assumptions:** Every claim in the debate that is an assumption not yet supported by fetched data. For each: the assumption, why it is uncertain, what evidence would confirm or deny it. Use conditional framing ("if consensus EPS is achieved...") not rhetorical certainty ("earnings will recover").

**Section 3 — Scenario Model:** Bear/Base/Bull table — EPS or EBITDA assumption (state basis), applied multiple (and why), implied price, probability weight. Weights sum to 100%. Include probability-weighted expected value.

**Section 4 — Decision:** Rating, entry trigger (price AND volume conditions), position sizing based on distance to invalidation level, technical invalidation (ATR-derived or named zone — a stop tighter than 0.5× ATR is a noise stop, flag it), fundamental invalidation (specific metrics and thresholds).

**Section 5 — Data Quality Report:** List contradictions (SMA labels vs values, margin figures that don't reconcile, guidance characterisation mismatches), assumptions presented as facts, missing data. Rate overall reliability. If core numbers don't reconcile, add **DO-NOT-TRADE** flag with explanation.

**Hard rules — violations make the output unusable:**
- Do NOT fabricate portfolio holdings, entry prices, fund mandates, or any position context not from the debate.
- Do NOT present scenarios as certainties.
- If the forward EPS in any valuation multiple is not sourced from fetched data, flag it in Section 5 and mark the resulting multiple as unverified.

{NO_EXTERNAL_TOOLS}{get_language_instruction()}"""

        final_trade_decision = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_pm_decision,
            "Portfolio Manager",
        )

        new_risk_debate_state = {
            "judge_decision": final_trade_decision,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": final_trade_decision,
        }

    return portfolio_manager_node
