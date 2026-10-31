"""Tool-using analysts only accept a complete reply as their final report."""

from langchain_core.messages import AIMessage

from tradingagents.agents.utils.agent_utils import invoke_tool_analyst

FULL = "A complete fundamentals report. " * 30


class _Chain:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), 0

    def invoke(self, messages):
        self.calls += 1
        return self.replies.pop(0)


def _msg(content="", tool_calls=None, invalid=None, finish=None):
    m = AIMessage(content=content, tool_calls=tool_calls or [],
                  invalid_tool_calls=invalid or [])
    if finish:
        m.response_metadata = {"finish_reason": finish}
    return m


def test_tool_call_returns_no_report():
    call = {"name": "get_cashflow", "args": {}, "id": "1"}
    result, report = invoke_tool_analyst(_Chain(_msg("Fetching", tool_calls=[call])), [])
    assert result.tool_calls and report == ""


def test_complete_reply_accepted_first_time():
    chain = _Chain(_msg(FULL, finish="stop"))
    _, report = invoke_tool_analyst(chain, [])
    assert report == FULL and chain.calls == 1


def test_truncated_preamble_is_retried_then_accepted():
    # The ZS 2026-10-30 failure: a one-line preamble taken as the report.
    stub = _msg("Now the annual statements to reconcile FY26 full-year figures (SBC, FCF, acqui")
    chain = _Chain(stub, _msg(FULL))
    _, report = invoke_tool_analyst(chain, [])
    assert report == FULL and chain.calls == 2


def test_still_incomplete_after_retry_is_flagged():
    chain = _Chain(_msg(FULL[:900], finish="length"), _msg(FULL[:900], finish="length"))
    _, report = invoke_tool_analyst(chain, [])
    assert report.startswith("**[INCOMPLETE REPORT: the model's output was cut off")
    assert "do not cite it as evidence" in report


def test_malformed_tool_call_is_not_a_report():
    bad = {"name": "get_cashflow", "args": '{"ticker": "ZS"', "id": "1", "error": "bad json"}
    chain = _Chain(_msg(FULL, invalid=[bad]), _msg(FULL, invalid=[bad]))
    _, report = invoke_tool_analyst(chain, [])
    assert "malformed tool call" in report
