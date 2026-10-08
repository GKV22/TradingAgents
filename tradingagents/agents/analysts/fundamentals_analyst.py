from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_instrument_context_from_state,
    get_language_instruction,
)


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]

        system_message = (
            "You are a fundamentals researcher. Analyze the company's financial statements, valuation, and guidance. Provide specific, evidence-based insights to help traders make informed decisions."
            + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements."
            + """

DOMAIN RESTRICTION — strictly enforced:
- Do NOT make any claims about current stock price, recent price direction, how price compares to moving averages (50-day, 200-day), or whether the stock is "trading above/below" any technical level. Those are the market analyst's domain. If your data tools return a current price, do not use it to characterize trend or momentum.
- Do NOT describe the stock's recent price action as bullish, bearish, consolidating, rebounding, or any other directional characterisation.

FINANCIAL ACCURACY RULES:
- For every financial figure, state: (a) whether GAAP or adjusted/non-GAAP, (b) the time period (TTM, FY ending date, or forward estimate period), and (c) the data source (tool name).
- For forward EPS or consensus estimates: use only the figure returned by the data tool. If the tool does not return a consensus forward EPS, state "consensus forward EPS not available from fetched data" — do not estimate or infer it.
- For valuation multiples (PE, PEG, EV/EBITDA): state the exact EPS or EBITDA figure used in the denominator and its period. A PEG ratio is only meaningful if the earnings-growth rate used is explicitly cited and sourced.
- For margin figures: derive them from the revenue and gross-profit/operating-income figures in the same period — do not state a margin percentage without showing the calculation or confirming it matches the fetched numbers.
- For guidance: quote management guidance exactly as reported ("raised", "reiterated", "cut" — with the specific figures). Do not paraphrase in a way that changes the characterisation.

Make sure to append a Markdown table at the end of the report listing every key metric with its value, period, and GAAP/adjusted label."""
            + get_language_instruction(),
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}."
                    " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges. {instrument_context}\n"
                    "{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
