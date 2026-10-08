"""Report Critic: independent quality review of the full analysis stack.

Runs after the Portfolio Manager. Reads all analyst reports, the full
research and risk debates, and the final trading decision. Produces a
structured quality audit covering:

  - Internal contradictions across agent reports
  - Echo chamber detection (same inputs recycled as corroboration)
  - Technical label accuracy (RSI, SMA relationships, ATR-stop sizing)
  - Unverified causal assertions
  - Valuation methodology red flags
  - Overall reliability rating with TRADEABLE / CAUTION / DO-NOT-TRADE verdict

Does NOT change the recommendation. Output is appended to the report so
the human reader knows exactly what to verify before acting.
"""

from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import NO_EXTERNAL_TOOLS


def create_report_critic(llm):
    def critic_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state)

        market_report = state.get("market_report", "")
        sentiment_report = state.get("sentiment_report", "")
        news_report = state.get("news_report", "")
        fundamentals_report = state.get("fundamentals_report", "")
        investment_debate = state.get("investment_debate_state", {}).get("history", "")
        risk_debate = state.get("risk_debate_state", {}).get("history", "")
        final_decision = state.get("final_trade_decision", "")

        prompt = f"""You are an independent senior analyst auditing the quality and reliability of an investment analysis produced by a multi-agent system. Your role is quality control — not to make a new recommendation.

{instrument_context}

You have access to the complete analysis pipeline output:

=== MARKET ANALYST REPORT ===
{market_report}

=== SENTIMENT ANALYST REPORT ===
{sentiment_report}

=== NEWS ANALYST REPORT ===
{news_report}

=== FUNDAMENTALS ANALYST REPORT ===
{fundamentals_report}

=== RESEARCH DEBATE (Bull vs Bear) ===
{investment_debate}

=== RISK DEBATE (Aggressive / Conservative / Neutral) ===
{risk_debate}

=== FINAL PORTFOLIO MANAGER DECISION ===
{final_decision}

---

Produce a structured quality review with these exact sections. Be specific — quote the problematic text, name the source agent, and state what is wrong and why it matters.

## 1. Internal Contradictions
Every case where one agent states a fact that directly contradicts another agent. Format:
- **Claim A** (source agent): exact quote
- **Claim B** (source agent): exact quote
- Resolution: which is correct based on data, or "cannot resolve without external source"
- Severity: CRITICAL (affects investment conclusion) / MODERATE / MINOR

## 2. Echo Chamber Check
Cases where the bull case, aggressive analyst, or trading plan cite the same fact or assumption and present agreement between agents as independent corroboration. True corroboration requires independent data sources. For each recycled claim: name the claim, list which agents repeated it verbatim or near-verbatim, and state whether any provided genuinely new evidence or just restated the same input.

## 3. Technical Label Accuracy
Check every technical claim:
- **RSI:** Is the label correct? RSI below 30 = oversold; above 70 = overbought; 30–70 = neither. Flag any mislabelling.
- **Moving averages:** Do "death cross / golden cross / price above / price below" assertions match the actual SMA values cited in the market report?
- **Stop vs ATR:** Is the proposed stop loss further than 1× ATR from the stated entry price? Flag any stop tighter than 0.5× ATR as a noise stop that does not represent thesis invalidation.
- **Bollinger Bands:** Do band relationship claims match the cited band values?

## 4. Unverified Causal Assertions
Every strong causal claim (e.g., "supply issue is transient," "the decline priced in all downside," "contract with X provides Y revenue") that is not directly supported by a named, verifiable source in the report. For each:
- State the claim and which agent made it
- State what primary source (earnings release, contract filing, call transcript, press release) would be needed to verify it
- State whether the analysis provides that source or merely references secondary commentary

## 5. Valuation Red Flags
- Is the forward EPS denominator in any P/E or PEG calculation clearly sourced, labelled GAAP/adjusted, and period-specified?
- Is any leverage ratio (net debt / EBITDA) derived by annualizing a single quarter's EBITDA for a business with seasonal or hedged cash flows? Flag as aggressive methodology.
- Are price targets derived from a stated methodology with explicit assumptions, or asserted without derivation?
- Does the PEG ratio's growth denominator come from consensus estimates, management guidance, or model assumptions — and is it stated?

## 6. Overall Reliability Assessment

| Dimension | Score (1–5) | Key Issues |
|---|---|---|
| Factual consistency | | |
| Evidence quality | | |
| Analytical independence | | |
| Risk discipline | | |
| **Overall** | | |

**Verdict:** TRADEABLE (no critical issues found) / CAUTION (moderate issues — verify before acting) / DO-NOT-TRADE (critical contradictions or data quality failures that undermine the conclusion)

**Top 3 things to verify before trading:**
1.
2.
3.

---

After the narrative above, append a machine-readable YAML block delimited by triple backticks. Use this exact schema — do not add extra keys:

```yaml
run_summary:
  overall_verdict: needs_revision  # clean | minor_issues | needs_revision | do_not_trade
  confidence_in_report: 2          # 1 (very low) – 5 (high)
  confidence_in_recommendation: 2  # 1–5
errors:
  - category: arithmetic_inconsistency  # arithmetic_inconsistency | technical_misclassification | unsupported_causality | echo_chamber | valuation_error | missing_source
    severity: critical                   # critical | major | moderate | minor
    agent: research_manager              # the agent responsible
    claim: "short exact quote from the report"
    issue: "what is analytically wrong"
    correction: "the rule or methodology that should have been applied"
    reusable_rule: true                  # true = rule applies beyond this ticker; false = specific to this run
    policy_scope: []                     # [] for universal rules; list sector/context tags otherwise e.g. [utilities, independent_power_producers]
decision:
  original_action: BUY                  # Rating from Portfolio Manager
  required_before_upgrade:
    - "primary source needed for X"
    - "reconcile Y before acting"
```

List every error found. Only set `reusable_rule: true` if the correction is a general analytical principle applicable to future analyses. Set `policy_scope: []` for universal rules; populate it for sector- or instrument-specific rules.

{NO_EXTERNAL_TOOLS}{get_language_instruction()}"""

        response = llm.invoke(prompt)
        review = response.content if hasattr(response, "content") else str(response)

        return {"analyst_review": review}

    return critic_node
