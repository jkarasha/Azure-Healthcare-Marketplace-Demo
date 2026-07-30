"""Factory for the Azure-backed chat client used by every workflow.

agent_framework 1.8 removed AzureOpenAIResponsesClient. The replacement is the
unified OpenAIChatClient, which accepts Azure parameters directly:

    endpoint        -> azure_endpoint
    deployment_name -> model

This module is the single seam where the framework's client is constructed, so
a future upstream change is a one-file fix rather than an 11-site hunt.
"""

from __future__ import annotations

from typing import Any

from agent_framework.openai import OpenAIChatClient
from azure.identity import AzureCliCredential, DefaultAzureCredential

from .config import AgentConfig
from .llm_options import resolve_api_version


def create_chat_client(
    config: AgentConfig,
    *,
    local: bool,
    credential: Any | None = None,
) -> OpenAIChatClient:
    """Build the chat client for a workflow run.

    Args:
        config: Loaded agent configuration.
        local: When True, prefer AzureCliCredential (developer machine).
        credential: Explicit credential. When provided, ``local`` is not used
            for credential selection. This exists so framework_devui.py can
            keep its DefaultAzureCredential -> AzureCliCredential retry, which
            is a fallback-on-failure and is NOT equivalent to choosing a
            credential up front.

    Returns:
        A configured OpenAIChatClient.
    """
    if credential is None:
        credential = AzureCliCredential() if local else DefaultAzureCredential()

    kwargs: dict[str, Any] = {
        "credential": credential,
        "azure_endpoint": config.openai.endpoint,
        "model": config.openai.deployment_name,
    }

    api_version = resolve_api_version(config.openai.api_version)
    if api_version is not None:
        kwargs["api_version"] = api_version

    return OpenAIChatClient(**kwargs)
