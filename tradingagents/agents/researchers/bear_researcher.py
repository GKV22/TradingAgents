from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
)


def create_bear_researcher(llm):
    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        instrument_context = get_instrument_context_from_state(state)
        if current_response.strip():
            engagement = (
                "Answer the last bull argument point by point — quote the specific claim, then "
                "concede or rebut it with data. Do not restate arguments you already made in earlier "
                "rounds (listed below); every round must add new evidence or a new rebuttal. If you "
                "have nothing new to add, say so in one sentence and summarise where the debate stands."
            )
        else:
            engagement = (
                "You open the debate: there is no bull argument yet. Make your case outright "
                "and pre-empt the strongest bull objections visible in the reports. Do not "
                "mention or ask for a missing bull argument."
            )
        asset_type = state.get("asset_type", "stock")
        target_label = "stock" if asset_type == "stock" else "asset"
        fundamentals_label = (
            "Company fundamentals report"
            if asset_type == "stock"
            else "Asset fundamentals report (may be unavailable for crypto)"
        )

        prompt = f"""You are a Bear Analyst making the case against investing in the {target_label}. Build a rigorous, evidence-based argument using only the data provided — do not introduce facts, figures, or comparisons not present in the source reports.

Key points to focus on:

- Risks and Challenges: Cite specific figures or events from the reports — market saturation, financial instability, execution risk. Do not assert risk without a data basis.
- Competitive Weaknesses: Reference specific data points, not general assertions.
- Negative Indicators: Use figures directly from the financial data, market report, or news. When data is absent or ambiguous, say so rather than inferring negatives.
- Bull Counterpoints: Challenge the bull's specific claims using the provided data; if a bull claim is supported by the data, concede it and focus your argument elsewhere.
- Engagement: {engagement}
- Confidence Calibration: Label downside scenarios explicitly as scenarios or risks, not certainties. Avoid catastrophising — overstatement is as unreliable as overoptimism. If a risk cannot be quantified from the provided data, flag it as unquantifiable rather than speculating on magnitude.

Resources available:

{instrument_context}
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
{fundamentals_label}: {fundamentals_report}
Conversation history of the debate: {history}
Your own previous arguments (do not repeat them): {bear_history}
Last bull argument: {current_response or '(none yet — you open the debate)'}
Use this information to deliver a compelling bear argument, refute the bull's claims, and engage in a dynamic debate that demonstrates the risks and weaknesses of investing in the {target_label}.
""" + get_language_instruction()

        response = llm.invoke(prompt)

        argument = f"Bear Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
