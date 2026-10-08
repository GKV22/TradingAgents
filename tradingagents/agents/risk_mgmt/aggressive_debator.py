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

        prompt = f"""You are the Risk Analyst responsible for stress-testing the bull case and evaluating whether the risk/reward is favourable at current levels. Your goal is rigorous analysis — not advocacy. Use only data from the provided reports.

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
1. **Scenario table (required):** Present a concise bear/base/bull scenario table with:
   - Assumed EPS or EBITDA for each scenario (cite the basis — management guide, consensus, or your stated assumption)
   - Applied valuation multiple for each scenario and why
   - Implied price range
   - Probability weight you assign to each scenario (must sum to 100%)

2. **Entry and invalidation:** Specify entry conditions (price level AND volume confirmation required), the technical invalidation level derived from ATR or the support zone in the market report (not an arbitrary tight stop), and fundamental invalidation criteria (e.g., "Q2 margins below X%", "FY27 EBITDA guidance cut").

3. **Engage the conservative/neutral arguments:** Where their caution is supported by the data, concede it. Where it rests on an assumption you disagree with, state the alternative assumption and its basis.

HARD RULES — violations make the output unusable:
- Do NOT fabricate portfolio holdings, entry prices, mandate constraints, fund context, or any position the system does not have a verified source for.
- Do NOT present scenarios as facts. Use "if consensus EPS is achieved..." not "earnings will recover."
- Do NOT treat a low PEG or forward P/E as proof of undervaluation unless the forward EPS denominator is explicitly cited and credible.
- Social media sentiment and isolated options flow are colour only — do not use them as primary evidence for a directional call.

Be concise. A scenario table and clear invalidation levels are more useful than rhetorical length.""" + get_language_instruction()

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
