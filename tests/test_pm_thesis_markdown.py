"""Portfolio Manager thesis: model-written HTML/one-line markdown is made readable."""

from markdown_it import MarkdownIt

from tradingagents.agents.schemas import (
    PortfolioDecision,
    PortfolioRating,
    render_pm_decision,
    tidy_markdown,
)

# Shape of a real ONTO run: HTML tables, headings and lists all on one line.
ONE_LINE = (
    "## 1. Verified Facts <table><tr><th>Metric</th><th>Value</th></tr>"
    "<tr><td>Current Price</td><td>$201.57</td></tr>"
    "<tr><td>Net Debt</td><td>-$410.4M <b>(Net Cash)</b></td></tr></table> "
    "## 2. Disputed Assumptions 1. Gross Margin Step-up: unproven. "
    "2. Organic vs Acquired Growth: unknown. "
    "## 3. Scenario Model <table><tr><th>Scenario</th><th>Price</th></tr>"
    "<tr><td>Bear</td><td>$164.00</td></tr></table> Probability-weighted Expected Value: $228.00 "
    "## 4. Decision Rating: Hold."
)


def test_html_tables_become_pipe_tables():
    out = tidy_markdown(ONE_LINE)
    assert "<t" not in out
    assert "| Metric | Value |\n|---|---|\n| Current Price | $201.57 |" in out
    assert "| Net Debt | -$410.4M (Net Cash) |" in out


def test_headings_and_list_items_get_their_own_lines():
    out = tidy_markdown(ONE_LINE)
    assert "\n## 2. Disputed Assumptions\n\n1. Gross Margin Step-up: unproven.\n2. Organic" in out
    assert "\n## 4. Decision\n\nRating: Hold." in out
    html = MarkdownIt("commonmark", {"html": False}).enable("table").render(out)
    assert html.count("<table>") == 2 and html.count("<h2>") == 4
    assert "&lt;t" not in html


def test_well_formed_markdown_is_unchanged():
    text = "## 1. Verified Facts\n\n| A | B |\n|---|---|\n| 1. X. 2. Y | 2 |\n\n## 2. Disputed Assumptions\n\n1. One."
    assert tidy_markdown(text) == text


def test_rendered_thesis_starts_on_its_own_line():
    md = render_pm_decision(PortfolioDecision(
        rating=PortfolioRating.HOLD, executive_summary="s", investment_thesis=ONE_LINE))
    assert "**Investment Thesis**:\n\n## 1. Verified Facts\n\n| Metric | Value |" in md
