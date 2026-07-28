"""Pure helpers for turning free-form agent text into structured data.

This module is deliberately dependency-free: no agent framework, no Azure
SDK, no logging side effects, no file I/O. That makes the riskiest seam in
the workflow — the boundary where LLM text becomes workflow state — fully
testable offline.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def iter_json_objects(text: str) -> Iterator[dict[str, Any]]:
    """Yield every top-level JSON object found in ``text``, in order.

    Scans for balanced ``{...}`` spans while tracking string literals and
    backslash escapes, so braces inside JSON strings never affect nesting
    depth. Spans that are balanced but not valid JSON are skipped.
    """
    if not isinstance(text, str):
        return

    depth = 0
    start = -1
    in_string = False
    escaped = False

    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = text[start : i + 1]
                start = -1
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    yield parsed


def extract_json_from_text(text: str) -> dict[str, Any] | None:
    """Return the first JSON object in ``text``, or ``None``.

    Tries, in order: the whole string as JSON, the contents of a fenced code
    block, then the first balanced brace span anywhere in the text.
    """
    if not isinstance(text, str) or not text:
        return None

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    for match in _FENCE_RE.finditer(text):
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    for obj in iter_json_objects(text):
        return obj

    return None
