"""Research Manager: turns the bull/bear debate into a structured investment plan for the trader."""

from __future__ import annotations

from tradingagents.agents.schemas import ResearchPlan, render_research_plan
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    NO_EXTERNAL_TOOLS,
    bind_structured,
    invoke_structured_or_freetext,
)


def create_research_manager(llm):
    structured_llm = bind_structured(llm, ResearchPlan, "Research Manager")

    def research_manager_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state)
        history = state["investment_debate_state"].get("history", "")

        investment_debate_state = state["investment_debate_state"]

        prompt = f"""As the Research Manager and debate facilitator, your role is to critically evaluate this round of debate and deliver a clear, actionable investment plan for the trader.

{instrument_context}

---

**Step 1 — Consistency audit (required before rating):**
Before forming a view, check for internal contradictions in the analyst reports referenced by the debate:
- Do technical indicator labels match the underlying values? (e.g., if 50-SMA > 200-SMA, "death cross" is wrong — flag it)
- Are all cited financial figures consistent? (e.g., does implied forward EPS reconcile with reported GAAP EPS and share count?)
- Are margin percentages consistent with the revenue and gross-profit figures quoted?
- Are any "facts" actually forward projections presented as certainties?
List any contradictions or unverified claims you identify. These reduce the reliability of the debate and should lower your conviction level accordingly.

**Step 2 — Signal vs. noise filter:**
Downweight or discard arguments that rest on: social-media sentiment counts alone, prediction-market probabilities for macro events, isolated options activity, or analyst projections not grounded in the fetched data. Note which arguments you are discounting and why.

**Step 3 — Rating:**

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction in the bull thesis; recommend taking or growing the position
- **Overweight**: Constructive view; recommend gradually increasing exposure
- **Hold**: Balanced view; recommend maintaining the current position; also use when data quality is too low for a directional call
- **Underweight**: Cautious view; recommend trimming exposure
- **Sell**: Strong conviction in the bear thesis; recommend exiting or avoiding the position

Commit to a clear stance whenever the debate's strongest *verified* arguments warrant one. If material contradictions in the source data remain unresolved, default to Hold and state why.

---

**Debate History:**
{history}

{NO_EXTERNAL_TOOLS}""" + get_language_instruction()

        investment_plan = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_research_plan,
            "Research Manager",
        )

        new_investment_debate_state = {
            "judge_decision": investment_plan,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": investment_plan,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": investment_plan,
        }

    return research_manager_node
