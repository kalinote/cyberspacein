"""Tests for tool hint formatting (nanobot.utils.tool_hints)."""

from app.service.nanobot.utils.tool_hints import format_tool_hints
from app.service.nanobot.providers.base import ToolCallRequest


def _tc(name: str, args) -> ToolCallRequest:
    return ToolCallRequest(id="c1", name=name, arguments=args)


def _hint(calls):
    """Shortcut for format_tool_hints."""
    return format_tool_hints(calls)


class TestToolHintKnownTools:
    """Test registered tool types produce correct formatted output."""

    def test_web_search(self):
        result = _hint([_tc("web_search", {"query": "Claude 4 vs GPT-4"})])
        assert result == 'search "Claude 4 vs GPT-4"'

    def test_web_fetch(self):
        result = _hint([_tc("web_fetch", {"url": "https://example.com/page"})])
        assert result == "fetch https://example.com/page"


class TestToolHintMCP:
    """Test MCP tools are abbreviated to server::tool format."""

    def test_mcp_standard_format(self):
        result = _hint([_tc("mcp_4_5v_mcp__analyze_image", {"imageSource": "https://img.jpg", "prompt": "describe"})])
        assert "4_5v" in result
        assert "analyze_image" in result

    def test_mcp_simple_name(self):
        result = _hint([_tc("mcp_github__create_issue", {"title": "Bug fix"})])
        assert "github" in result
        assert "create_issue" in result


class TestToolHintFallback:
    """Test unknown tools fall back to original behavior."""

    def test_unknown_tool_with_string_arg(self):
        result = _hint([_tc("custom_tool", {"data": "hello world"})])
        assert result == 'custom_tool("hello world")'

    def test_unknown_tool_with_long_arg_truncates(self):
        long_val = "a" * 60
        result = _hint([_tc("custom_tool", {"data": long_val})])
        assert len(result) < 80
        assert "\u2026" in result

    def test_unknown_tool_no_string_arg(self):
        result = _hint([_tc("custom_tool", {"count": 42})])
        assert result == "custom_tool"

    def test_empty_tool_calls(self):
        result = _hint([])
        assert result == ""


class TestToolHintFolding:
    """Test consecutive same-tool calls are folded."""

    def test_single_call_no_fold(self):
        calls = [_tc("web_search", {"query": "a"})]
        result = _hint(calls)
        assert "\u00d7" not in result

    def test_two_consecutive_different_args_not_folded(self):
        calls = [
            _tc("web_search", {"query": "a"}),
            _tc("web_search", {"query": "b"}),
        ]
        result = _hint(calls)
        assert "\u00d7" not in result

    def test_two_consecutive_same_args_folded(self):
        calls = [
            _tc("web_search", {"query": "same"}),
            _tc("web_search", {"query": "same"}),
        ]
        result = _hint(calls)
        assert "\u00d7 2" in result

    def test_three_consecutive_different_args_not_folded(self):
        calls = [
            _tc("web_fetch", {"url": "https://a.example"}),
            _tc("web_fetch", {"url": "https://b.example"}),
            _tc("web_fetch", {"url": "https://c.example"}),
        ]
        result = _hint(calls)
        assert "\u00d7" not in result

    def test_different_tools_not_folded(self):
        calls = [
            _tc("web_search", {"query": "x"}),
            _tc("web_fetch", {"url": "https://example.com"}),
        ]
        result = _hint(calls)
        assert "\u00d7" not in result

    def test_interleaved_same_tools_not_folded(self):
        calls = [
            _tc("web_search", {"query": "a"}),
            _tc("web_fetch", {"url": "https://example.com/a"}),
            _tc("web_search", {"query": "b"}),
        ]
        result = _hint(calls)
        assert "\u00d7" not in result


class TestToolHintMultipleCalls:
    """Test multiple different tool calls are comma-separated."""

    def test_two_different_tools(self):
        calls = [
            _tc("web_search", {"query": "TODO"}),
            _tc("web_fetch", {"url": "https://example.com/main.py"}),
        ]
        result = _hint(calls)
        assert 'search "TODO"' in result
        assert "fetch https://example.com/main.py" in result
        assert ", " in result


class TestToolHintEdgeCases:
    """Test edge cases and defensive handling (G1, G2)."""

    def test_known_tool_empty_list_args(self):
        """C1/G1: Empty list arguments should not crash."""
        result = _hint([_tc("web_fetch", [])])
        assert result == "web_fetch"

    def test_known_tool_none_args(self):
        """G2: None arguments should not crash."""
        result = _hint([_tc("web_fetch", None)])
        assert result == "web_fetch"

    def test_fallback_empty_list_args(self):
        """C1: Empty list args in fallback should not crash."""
        result = _hint([_tc("custom_tool", [])])
        assert result == "custom_tool"

    def test_fallback_none_args(self):
        """G2: None args in fallback should not crash."""
        result = _hint([_tc("custom_tool", None)])
        assert result == "custom_tool"

class TestToolHintMixedFolding:
    """G4: Mixed folding groups with interleaved same-tool segments."""

    def test_read_read_grep_grep_read(self):
        """All different args — each hint listed separately."""
        calls = [
            _tc("web_fetch", {"url": "https://a.example"}),
            _tc("web_fetch", {"url": "https://b.example"}),
            _tc("web_search", {"query": "x"}),
            _tc("web_search", {"query": "y"}),
            _tc("web_fetch", {"url": "https://c.example"}),
        ]
        result = _hint(calls)
        assert "\u00d7" not in result
        parts = result.split(", ")
        assert len(parts) == 5
