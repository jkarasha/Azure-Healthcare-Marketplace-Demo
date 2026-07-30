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


def _iter_all_objects(text: str) -> list[dict[str, Any]]:
    """Collect every JSON object in ``text``.

    Fenced blocks are scanned first because fencing isolates each payload
    from surrounding prose, which can otherwise derail the raw scanner (an
    unmatched quote in the prose opens a phantom string literal). The raw
    text is then scanned as well, so that an agent which omitted its fence
    is not silently dropped when its partner used one. Objects already
    recovered from a fence are not added twice.
    """
    if not isinstance(text, str):
        return []

    objects: list[dict[str, Any]] = []
    for block in _FENCE_RE.findall(text):
        for obj in iter_json_objects(block):
            if obj not in objects:
                objects.append(obj)

    for obj in iter_json_objects(text):
        if obj not in objects:
            objects.append(obj)

    return objects


def split_concurrent_outputs(
    text: str,
    first_marker: str,
    second_marker: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Split one concatenated concurrent-agent result into two objects.

    ``ConcurrentBuilder`` returns both participants' outputs as a single
    string with no delimiter, and the agents may finish in either order.
    Rather than guessing at offsets, this parses *every* JSON object in the
    text and identifies each participant by a key unique to its schema.

    Returns ``(first, second)``. Either may be ``None`` when that agent
    produced no parseable output. When one object contains both markers
    (an agent merged the payloads), the same object is returned for both.
    """
    objects = _iter_all_objects(text)

    first: dict[str, Any] | None = None
    second: dict[str, Any] | None = None

    for obj in objects:
        has_first = first_marker in obj
        has_second = second_marker in obj
        if has_first and has_second:
            return obj, obj
        if has_first and first is None:
            first = obj
        elif has_second and second is None:
            second = obj

    return first, second


# ---------------------------------------------------------------------------
# Recommendation extraction — last-resort fallback for prose agent output
# ---------------------------------------------------------------------------

_RECOMMENDATION_LABEL_RE = re.compile(
    r'"recommendation"\s*:\s*"(APPROVE|PEND|DENY)"',
    re.IGNORECASE,
)

# "Recommendation: PEND." / "Decision: APPROVE" / "recommendation: deny"
_DIRECTIVE_LABEL_RE = re.compile(
    r"\b(?:recommendation|decision)\s*[:\s]+\s*(APPROVE|PEND|DENY)\b",
    re.IGNORECASE,
)

# Negators that immediately precede "approve" — e.g. "cannot approve", "will not approve"
# Covers single-word and two-word negators (word-boundary anchored).
_NEGATED_APPROVE_RE = re.compile(
    r"\b(?:not|cannot|can\s+not|unable\s+to|do\s+not|don't|won't|will\s+not|no|never"
    r"|rather\s+than|instead\s+of)\s+approv\w*",
    re.IGNORECASE,
)

# Explicit directive verb + "deny": "I recommend DENY", "must DENY", "should DENY"
# Word-boundary on both sides so "denied"/"denial" do not match.
_DIRECTIVE_DENY_RE = re.compile(
    r"\b(?:recommend|recommends|recommending|must|should|will)\s+deny\b",
    re.IGNORECASE,
)

_PEND_WORD_RE = re.compile(r"\bpend\b", re.IGNORECASE)
_APPROVE_WORD_RE = re.compile(r"\bapprove\b", re.IGNORECASE)


def extract_recommendation_from_text(text: str) -> str:
    """Infer a recommendation value (APPROVE | PEND | DENY) from free-form text.

    Used only when JSON extraction has already failed so the synthesis-agent
    response is being treated as plain prose.

    **Precedence ladder** (first match wins):

    1. ``"recommendation": "VALUE"`` JSON/labelled field — the most reliable
       signal in a partially-malformed response.
    2. A directive label phrase such as ``Recommendation: PEND`` or
       ``Decision: APPROVE`` — catches prose summaries that mirror JSON schema.
    3. Any bare ``\\bpend\\b`` → **PEND** — if the agent wrote PEND anywhere,
       that explicit safe outcome wins over an incidental APPROVE or DENY
       keyword. This also neutralises prompt-option-list echoes such as
       ``"APPROVE", "PEND", or "DENY" … I choose PEND``.
    4. A negated-APPROVE phrase (``cannot approve``, ``unable to approve``,
       ``will not approve``, etc.) → **PEND** — auto-approving a request the
       agent explicitly declined to approve is the worst failure mode here.
    5. An explicit directive DENY verb (``recommend DENY``, ``must DENY``,
       ``should DENY``, ``will DENY``):
       - If a competing ``\\bapprove\\b`` is also present → **PEND** (ambiguity
         is never resolved in DENY's favour; the human reviewer handles it).
       - Otherwise → **DENY**.
    6. A bare ``\\bapprove\\b`` with no negator → **APPROVE**.
    7. Default → **PEND** (the safe fallback; prompts human information-gathering
       rather than granting or blocking coverage).

    **Why PEND is the safe default, not DENY:**
    A false DENY is a worse clinical and regulatory error than a false PEND.
    PEND already degrades gracefully — it prompts the human to gather more
    information. A false DENY blocks potentially necessary care and exposes
    the payer to regulatory risk. DENY should only be emitted when the signal
    is unambiguous.

    **On ``denial``/``denied``:** ``\\bdeny\\b`` is word-boundary anchored, so
    ``denied`` and ``denial`` never match the DENY branch. This is deliberate:
    those forms appear naturally in procedural prose (``'the appeal was denied'``)
    and are not directive recommendation signals.
    """
    if not isinstance(text, str):
        return "PEND"

    # Step 1: explicit JSON/labelled field
    m = _RECOMMENDATION_LABEL_RE.search(text)
    if m:
        return m.group(1).upper()

    # Step 2: directive label phrase ("Recommendation: PEND", "Decision: APPROVE")
    m = _DIRECTIVE_LABEL_RE.search(text)
    if m:
        return m.group(1).upper()

    # Step 3: any bare PEND keyword — safe outcome wins
    if _PEND_WORD_RE.search(text):
        return "PEND"

    # Step 4: negated APPROVE → PEND
    if _NEGATED_APPROVE_RE.search(text):
        return "PEND"

    # Step 5: directive DENY verb — only when unambiguous
    if _DIRECTIVE_DENY_RE.search(text):
        if _APPROVE_WORD_RE.search(text):
            return "PEND"  # competing signals → ambiguity → PEND
        return "DENY"

    # Step 6: plain APPROVE keyword
    if _APPROVE_WORD_RE.search(text):
        return "APPROVE"

    return "PEND"
