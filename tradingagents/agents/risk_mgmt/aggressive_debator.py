from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
)


def create_aggressive_debator(llm):
    def aggressive_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        instrument_context = get_instrument_context_from_state(state)

        trader_decision = state["trader_investment_plan"]

        first_round = not aggressive_history.strip()
        scenario_task = (
            """1. **Scenario table (required):** Present a concise bear/base/bull scenario table with:
   - Assumed EPS, EBITDA or revenue for each scenario (cite the basis — management guide, consensus, or your stated assumption)
   - Applied valuation multiple for each scenario and why
   - Implied price range, showing the arithmetic (multiple × figure ± net cash, ÷ diluted shares)
   - Probability weight you assign to each scenario (must sum to 100%)"""
            if first_round
            else """1. **Scenario table:** You already presented it (see your previous arguments). Do NOT repeat it. Only state which inputs you are changing in response to the other analysts, and the new result."""
        )

        prompt = f"""You are the Aggressive Risk Analyst. Your seat exists so the panel does not default to inaction: champion the highest-reward course the data can support — adding, buying a pullback, or sizing up — and argue it hard. The conservative and neutral analysts will make the cautious case; do not make it for them. Stay inside the evidence: use only data from the provided reports.

Trader's decision under review:
{trader_decision}

Source reports:
{instrument_context}
Market Research Report: {market_research_report}
News Report: {news_report}
Fundamentals Report: {fundamentals_report}

Debate history: {history}
Conservative analyst's last argument: {current_conservative_response}
Neutral analyst's last argument: {current_neutral_response}

YOUR TASK:
{scenario_task}

2. **The upside case:** State the most aggressive action you would defend (e.g. add X% on a pullback to a named level, or buy now), the specific evidence that justifies it, and what the cautious seats lose by waiting (opportunity cost, upcoming catalysts).

3. **Entry and invalidation:** Specify entry conditions (price level AND volume confirmation required), the technical invalidation level derived from ATR or the support zone in the market report (not an arbitrary tight stop), and fundamental invalidation criteria (e.g., "Q2 margins below X%", "FY27 EBITDA guidance cut").

4. **Rebut the conservative/neutral arguments point by point:** Concede only what the data forces you to concede. Where their caution rests on an assumption, name the assumption and argue the alternative. A missing data point is a risk to size for, not by itself a reason to do nothing.

HARD RULES — violations make the output unusable:
- Do NOT fabricate portfolio holdings, entry prices, mandate constraints, fund context, or any position the system does not have a verified source for.
- Do NOT present scenarios as facts. Use "if consensus EPS is achieved..." not "earnings will recover."
- Do NOT treat a low PEG or forward P/E as proof of undervaluation unless the forward EPS denominator is explicitly cited and credible.
- Social media sentiment and isolated options flow are colour only — do not use them as primary evidence for a directional call.

- Do NOT repeat your previous arguments verbatim; each round must add something new.

Be concise. Clear numbers and invalidation levels are more useful than rhetorical length.""" + get_language_instruction()

        response = llm.invoke(prompt)

        argument = f"Aggressive Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": aggressive_history + "\n" + argument,
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Aggressive",
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get(
                "current_conservative_response", ""
            ),
            "current_neutral_response": risk_debate_state.get("current_neutral_response", ""),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
