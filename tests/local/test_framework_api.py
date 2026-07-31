"""Guard against agent_framework API drift.

NOT part of the CI gate. Requires the full framework stack, so run it with
the agents venv:

    make test-local

An unpinned agent-framework floor once drifted to 1.8.0, which removed
AzureOpenAIResponsesClient and broke every workflow with no failing test.
These assertions are signature-only: no network, no credentials, no LLM calls.
"""

import inspect

import pytest

pytest.importorskip("agent_framework", reason="requires the agents venv")


def _params(func) -> set[str]:
    return set(inspect.signature(func).parameters)


class TestChatClientSurface:
    def test_openai_chat_client_accepts_azure_parameters(self):
        from agent_framework.openai import OpenAIChatClient

        params = _params(OpenAIChatClient.__init__)
        for name in ("azure_endpoint", "model", "credential", "api_version"):
            assert name in params, f"OpenAIChatClient lost '{name}'"


class TestAgentSurface:
    def test_agent_accepts_client(self):
        from agent_framework import Agent

        assert "client" in _params(Agent.__init__)

    def test_core_symbols_exist(self):
        import agent_framework

        for name in ("Agent", "MCPStreamableHTTPTool", "SupportsChatGetResponse"):
            assert hasattr(agent_framework, name), f"agent_framework lost '{name}'"


class TestOrchestrationsSurface:
    def test_concurrent_builder_accepts_participants(self):
        from agent_framework_orchestrations import ConcurrentBuilder

        assert "participants" in _params(ConcurrentBuilder.__init__)

    def test_concurrent_builder_has_build(self):
        from agent_framework_orchestrations import ConcurrentBuilder

        assert callable(ConcurrentBuilder.build)


class TestFactoryImports:
    def test_llm_client_imports(self):
        from agents.llm_client import create_chat_client

        params = _params(create_chat_client)
        assert {"config", "local", "credential"} <= params
