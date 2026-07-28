"""Unit tests for agent-output parsing helpers.

These tests are fully deterministic: they exercise pure functions over
literal strings. No LLM, no MCP server, no Azure credential is required.
"""

import pytest

from agents.workflows.parsing import extract_json_from_text, iter_json_objects, split_concurrent_outputs


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


class TestIterJsonObjects:
    """Direct coverage for the scanner that split_concurrent_outputs depends on.

    Task 2 only exercised this indirectly via extract_json_from_text, which
    stops at the first object. The multi-object behaviour below is the actual
    contract split_concurrent_outputs relies on.
    """

    def test_yields_every_top_level_object_in_order(self):
        assert list(iter_json_objects('{"a": 1}{"b": 2}{"c": 3}')) == [{"a": 1}, {"b": 2}, {"c": 3}]

    def test_yields_objects_separated_by_prose(self):
        text = 'Agent A said:\n{"a": 1}\n\nAgent B said:\n{"b": 2}'
        assert list(iter_json_objects(text)) == [{"a": 1}, {"b": 2}]

    def test_does_not_yield_nested_objects_separately(self):
        assert list(iter_json_objects('{"outer": {"inner": 1}}')) == [{"outer": {"inner": 1}}]

    def test_skips_balanced_but_invalid_json(self):
        text = '{not valid json}{"valid": true}'
        assert list(iter_json_objects(text)) == [{"valid": True}]

    def test_ignores_braces_and_quotes_inside_strings(self):
        text = '{"a": "brace } and \\" quote"}{"b": 2}'
        assert list(iter_json_objects(text)) == [{"a": 'brace } and " quote'}, {"b": 2}]

    def test_tolerates_stray_closing_brace_before_any_object(self):
        assert list(iter_json_objects('}}{"a": 1}')) == [{"a": 1}]

    def test_yields_nothing_for_unterminated_object(self):
        assert list(iter_json_objects('{"a": 1')) == []

    def test_yields_nothing_for_non_string_input(self):
        assert list(iter_json_objects(None)) == []
        assert list(iter_json_objects(42)) == []

    def test_skips_top_level_arrays(self):
        """Only dicts are yielded; a top-level array is not an agent payload."""
        assert list(iter_json_objects('[1, 2, 3]{"a": 1}')) == [{"a": 1}]


class TestSplitConcurrentOutputs:
    def test_splits_two_plain_concatenated_objects(self):
        from tests.unit.fixtures import concurrent_outputs as fx

        clinical, coverage = split_concurrent_outputs(
            fx.CONCATENATED_PLAIN,
            first_marker="clinical_summary",
            second_marker="applicable_policies",
        )
        assert clinical is not None
        assert clinical["clinical_summary"]["primary_diagnosis"] == "Crohn's disease"
        assert coverage is not None
        assert coverage["applicable_policies"][0]["policy_id"] == "Cigna-Adalimumab-Products-PA-Policy"

    def test_splits_fenced_outputs(self):
        from tests.unit.fixtures import concurrent_outputs as fx

        clinical, coverage = split_concurrent_outputs(
            fx.CONCATENATED_FENCED,
            first_marker="clinical_summary",
            second_marker="applicable_policies",
        )
        assert clinical is not None and "clinical_summary" in clinical
        assert coverage is not None and "applicable_policies" in coverage

    def test_returns_same_object_twice_when_merged(self):
        from tests.unit.fixtures import concurrent_outputs as fx

        clinical, coverage = split_concurrent_outputs(
            fx.MERGED_SINGLE_OBJECT,
            first_marker="clinical_summary",
            second_marker="applicable_policies",
        )
        assert clinical is coverage
        assert clinical is not None
        assert clinical["applicable_policies"][0]["policy_id"] == "P-1"

    def test_returns_none_for_missing_second_agent(self):
        from tests.unit.fixtures import concurrent_outputs as fx

        clinical, coverage = split_concurrent_outputs(
            fx.CLINICAL_ONLY,
            first_marker="clinical_summary",
            second_marker="applicable_policies",
        )
        assert clinical is not None and "clinical_summary" in clinical
        assert coverage is None

    def test_order_independent(self):
        """Agents finish concurrently; coverage output may arrive first."""
        from tests.unit.fixtures import concurrent_outputs as fx

        reversed_text = fx.COVERAGE_JSON + "\n" + fx.CLINICAL_JSON
        clinical, coverage = split_concurrent_outputs(
            reversed_text,
            first_marker="clinical_summary",
            second_marker="applicable_policies",
        )
        assert clinical is not None and "clinical_summary" in clinical
        assert coverage is not None and "applicable_policies" in coverage

    def test_returns_none_none_for_prose(self):
        clinical, coverage = split_concurrent_outputs(
            "Both agents failed to produce output.",
            first_marker="clinical_summary",
            second_marker="applicable_policies",
        )
        assert clinical is None
        assert coverage is None
