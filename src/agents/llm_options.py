"""Pure helpers for Azure OpenAI client options.

This module must not import anything outside the standard library. It is
imported by the offline unit-test suite, whose venv contains neither
agent_framework nor python-dotenv.
"""

from __future__ import annotations

import os

# Values that are not real API versions. Azure's newer "v1" surface is
# selected by omitting api_version entirely, which is also the only setting
# that works against both *.openai.azure.com and *.cognitiveservices.azure.com.
_OMIT_SENTINELS = frozenset({"preview", "v1", "none"})


def resolve_api_version(raw: str | None) -> str | None:
    """Return the api_version to send, or None to request no specific version.

    Args:
        raw: The configured value, typically ``AZURE_OPENAI_API_VERSION``.

    Returns:
        The trimmed version string, or ``None`` when no particular version
        should be requested. Passing ``None`` to the client is equivalent to
        omitting the argument; see ``llm_client.create_chat_client``.
    """
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    if value.lower() in _OMIT_SENTINELS:
        return None
    return value


# azure-identity defaults to a 10s timeout when shelling out to `az`, which is
# not always enough: a cold Azure CLI has been measured at ~15s on a developer
# machine. It surfaces as a confusing CredentialUnavailableError("Failed to
# invoke the Azure CLI") rather than as a timeout, and it is intermittent,
# because a warm CLI answers well inside 10s.
DEFAULT_CLI_PROCESS_TIMEOUT = 60


def cli_process_timeout() -> int:
    """Seconds to allow the Azure CLI when acquiring a token.

    Override with AZURE_CLI_PROCESS_TIMEOUT. Values that are unset, blank,
    non-numeric, or non-positive fall back to the default.
    """
    raw = os.getenv("AZURE_CLI_PROCESS_TIMEOUT", "").strip()
    if not raw:
        return DEFAULT_CLI_PROCESS_TIMEOUT
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_CLI_PROCESS_TIMEOUT
    return value if value > 0 else DEFAULT_CLI_PROCESS_TIMEOUT
