"""Tests for the Azure OpenAI api_version resolution rule.

This module must stay importable in the offline CI venv, which has no
agent_framework and no python-dotenv. Import only from agents.llm_options.
"""

import pytest

from agents.llm_options import resolve_api_version


class TestResolveApiVersionOmits:
    """Values that mean 'do not send api_version at all'."""

    @pytest.mark.parametrize(
        "raw",
        [
            None,
            "",
            "   ",
            "\t",
            "preview",
            "PREVIEW",
            "Preview",
            "v1",
            "V1",
            "none",
            "NONE",
            "  preview  ",
        ],
    )
    def test_returns_none(self, raw):
        assert resolve_api_version(raw) is None


class TestResolveApiVersionPassesThrough:
    """Real dated versions stay under operator control."""

    @pytest.mark.parametrize(
        "raw",
        [
            "2024-10-21",
            "2025-01-01-preview",
            "2025-04-01-preview",
        ],
    )
    def test_returns_value_unchanged(self, raw):
        assert resolve_api_version(raw) == raw

    def test_strips_surrounding_whitespace(self):
        assert resolve_api_version("  2024-10-21  ") == "2024-10-21"
