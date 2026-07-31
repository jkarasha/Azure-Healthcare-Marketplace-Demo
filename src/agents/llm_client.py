"""Factory for the Azure-backed chat client used by every workflow.

agent_framework 1.8 removed AzureOpenAIResponsesClient. The replacement is the
unified OpenAIChatClient, which accepts Azure parameters directly:

    endpoint        -> azure_endpoint
    deployment_name -> model

This module is the single seam where the framework's client is constructed, so
a future upstream change is a one-file fix rather than an 11-site hunt.
"""

from __future__ import annotations

from agent_framework.openai import OpenAIChatClient
from azure.core.credentials import TokenCredential
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity import AzureCliCredential, DefaultAzureCredential

from .config import AgentConfig
from .llm_options import cli_process_timeout, resolve_api_version


def create_chat_client(
    config: AgentConfig,
    *,
    local: bool,
    credential: TokenCredential | AsyncTokenCredential | None = None,
) -> OpenAIChatClient:
    """Build the chat client for a workflow run.

    Args:
        config: Loaded agent configuration.
        local: When True, prefer AzureCliCredential (developer machine).
        credential: Explicit credential. When provided, ``local`` is not used
            for credential selection. This exists so framework_devui.py can
            keep its DefaultAzureCredential -> AzureCliCredential retry, which
            is a fallback-on-failure and is NOT equivalent to choosing a
            credential up front. A credential created here is never closed;
            that is acceptable because the CLI is a short-lived process.

    Returns:
        A configured OpenAIChatClient.
    """
    if credential is None:
        timeout = cli_process_timeout()
        credential = (
            AzureCliCredential(process_timeout=timeout)
            if local
            else DefaultAzureCredential(process_timeout=timeout)
        )

    # resolve_api_version returns None for unset/empty values and for the
    # sentinels preview/v1/none. Passing None is identical to omitting the
    # argument: the framework substitutes its own default, which is "preview"
    # in 1.8.0 (_shared.py `api_version=api_version or default_azure_api_version`,
    # _chat_client.py DEFAULT_AZURE_OPENAI_RESPONSES_API_VERSION). A real dated
    # version is passed through unchanged and takes effect.
    return OpenAIChatClient(
        credential=credential,
        azure_endpoint=config.openai.endpoint,
        model=config.openai.deployment_name,
        api_version=resolve_api_version(config.openai.api_version),
    )
