"""Pure helpers for Azure OpenAI client options.

This module must not import anything outside the standard library. It is
imported by the offline unit-test suite, whose venv contains neither
agent_framework nor python-dotenv.
"""

from __future__ import annotations

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
