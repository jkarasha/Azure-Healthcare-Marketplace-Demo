"""Tests for the Azure OpenAI api_version resolution rule.

This module must stay importable in the offline CI venv, which has no
agent_framework and no python-dotenv. Import only from agents.llm_options.
"""

import pytest

from agents.llm_options import (
    DEFAULT_CLI_PROCESS_TIMEOUT,
    cli_process_timeout,
    resolve_api_version,
)


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


class TestCliProcessTimeout:
    """azure-identity's 10s default is too short for a cold Azure CLI."""

    @pytest.mark.parametrize("raw", ["", "   ", "abc", "0", "-5", "1.5"])
    def test_falls_back_to_default(self, monkeypatch, raw):
        monkeypatch.setenv("AZURE_CLI_PROCESS_TIMEOUT", raw)
        assert cli_process_timeout() == DEFAULT_CLI_PROCESS_TIMEOUT

    def test_defaults_when_unset(self, monkeypatch):
        monkeypatch.delenv("AZURE_CLI_PROCESS_TIMEOUT", raising=False)
        assert cli_process_timeout() == DEFAULT_CLI_PROCESS_TIMEOUT

    @pytest.mark.parametrize(("raw", "expected"), [("30", 30), ("  90  ", 90), ("1", 1)])
    def test_honours_valid_override(self, monkeypatch, raw, expected):
        monkeypatch.setenv("AZURE_CLI_PROCESS_TIMEOUT", raw)
        assert cli_process_timeout() == expected

    def test_default_exceeds_azure_identity_default(self):
        assert DEFAULT_CLI_PROCESS_TIMEOUT > 10
