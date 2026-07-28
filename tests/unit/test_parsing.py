"""Unit tests for agent-output parsing helpers.

These tests are fully deterministic: they exercise pure functions over
literal strings. No LLM, no MCP server, no Azure credential is required.
"""

import pytest

from agents.workflows.parsing import extract_json_from_text


class TestExtractJsonFromText:
    def test_parses_bare_json_object(self):
        assert extract_json_from_text('{"a": 1}') == {"a": 1}

    def test_parses_json_inside_fenced_block(self):
        text = 'Here is my analysis:\n```json\n{"a": 1}\n```\nDone.'
        assert extract_json_from_text(text) == {"a": 1}

    def test_parses_json_inside_unlabelled_fence(self):
        text = '```\n{"a": 1}\n```'
        assert extract_json_from_text(text) == {"a": 1}

    def test_parses_json_embedded_in_prose(self):
        text = 'The result is {"decision": "PEND"} per policy.'
        assert extract_json_from_text(text) == {"decision": "PEND"}

    def test_handles_nested_objects(self):
        text = 'Result: {"outer": {"inner": {"deep": true}}} end'
        assert extract_json_from_text(text) == {"outer": {"inner": {"deep": True}}}

    def test_ignores_braces_inside_string_literals(self):
        text = '{"note": "a } brace in a string", "ok": true}'
        assert extract_json_from_text(text) == {"note": "a } brace in a string", "ok": True}

    def test_returns_none_for_prose_without_json(self):
        assert extract_json_from_text("No structured output was produced.") is None

    def test_returns_none_for_unbalanced_braces(self):
        assert extract_json_from_text('{"a": 1') is None

    def test_returns_none_for_empty_string(self):
        assert extract_json_from_text("") is None

    @pytest.mark.parametrize("bad", [None, 123, [], {}])
    def test_returns_none_for_non_string_input(self, bad):
        assert extract_json_from_text(bad) is None

    def test_returns_first_object_when_several_present(self):
        text = '{"first": 1}\n{"second": 2}'
        assert extract_json_from_text(text) == {"first": 1}
