from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
)


def create_bull_researcher(llm):
    def bull_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        instrument_context = get_instrument_context_from_state(state)
        asset_type = state.get("asset_type", "stock")
        target_label = "stock" if asset_type == "stock" else "asset"
        fundamentals_label = (
            "Company fundamentals report"
            if asset_type == "stock"
            else "Asset fundamentals report (may be unavailable for crypto)"
        )

        prompt = f"""You are a Bull Analyst making the investment case for the {target_label}. Build an evidence-based argument using only the data provided — do not introduce facts, figures, or comparisons not present in the source reports.

Key points to focus on:
- Growth Potential: Highlight market opportunities and revenue trends backed by figures in the reports.
- Competitive Advantages: Cite specific factors from the data — do not assert advantages without evidence.
- Positive Indicators: Reference specific financial metrics, trends, and news items from the provided reports.
- Bear Counterpoints: Address the bear's specific claims with data from the reports; if a bear claim cannot be refuted with provided data, concede it rather than speculate.
- Confidence Calibration: Label forward projections explicitly as scenarios or estimates, not certainties. Avoid superlatives ("generational", "definitive", "certain") unless directly supported by a cited source. Never assert timing of recoveries or future FCF figures unless the data explicitly supports them.

Resources available:
{instrument_context}
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
{fundamentals_label}: {fundamentals_report}
Conversation history of the debate: {history}
Last bear argument: {current_response}
Use this information to deliver a compelling bull argument, refute the bear's concerns, and engage in a dynamic debate that demonstrates the strengths of the bull position.
""" + get_language_instruction()

        response = llm.invoke(prompt)

        argument = f"Bull Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
