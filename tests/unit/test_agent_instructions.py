"""Agent instructions must not contradict the authoritative skill rubric.

The rubric (.github/skills/prior-auth-azure/references/rubric.md) permits an
AI DENY recommendation when a mandatory criterion is NOT_MET at >= 90%
confidence, with the human confirming in Subskill 2. These tests keep the
prompt text and the rubric from drifting apart again.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_PY = REPO_ROOT / "src" / "agents" / "agents.py"
RUBRIC = REPO_ROOT / ".github" / "skills" / "prior-auth-azure" / "references" / "rubric.md"
SKILL_REFS_DIR = REPO_ROOT / ".github" / "skills" / "prior-auth-azure" / "references"

# Every file that is sent (verbatim or by reference) to an LLM during a
# prior-auth workflow.  Coverage is by construction: if a surface is added
# here it is automatically guarded; if a new surface is created it must be
# added here.
_LLM_FACING_SURFACES: list[Path] = [
    AGENTS_PY,
    REPO_ROOT / "src" / "agents" / "workflows" / "prior_auth.py",
    REPO_ROOT / ".github" / "skills" / "prior-auth-azure" / "SKILL.md",
    *sorted(SKILL_REFS_DIR.glob("*.md")),
]

# Phrases that constitute a DENY prohibition — any one of these appearing in an
# LLM-facing surface contradicts rubric.md and must fail the suite.
# Matched case-insensitively.
# IMPORTANT: these must NOT match legitimate prose such as
#   "Final denial authority is always human", "Denial decisions (human-only)",
#   or role-scoping notes like "never make approval/denial recommendations"
#   (the Synthesis Agent's role note for Clinical and Coverage agents).
# M7 note: "may only recommend" is anchored to include "approve" to avoid
#   false-positives on correct future prose like
#   "may only recommend DENY when all three conditions hold".
_DENY_PROHIBITION_PHRASES = [
    "never recommends deny",
    "never recommend deny",
    "ai never recommends deny",
    "never denies",
    "may only recommend approve",       # plain-text form
    "may only recommend **approve**",   # markdown-bold form
    "never make denial recommendations",
    "deny is not an option",
]


def _read_surface(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _agents_text() -> str:
    return _read_surface(AGENTS_PY)


def _rubric_text() -> str:
    return _read_surface(RUBRIC)


class TestRubricContract:
    """The authoritative rubric must document AI DENY capability."""

    def test_rubric_permits_ai_deny(self):
        """rubric.md must explicitly state the AI can recommend DENY."""
        assert "The AI **can** recommend DENY" in _rubric_text(), (
            "rubric.md no longer states 'The AI **can** recommend DENY'; "
            "the authoritative contract has drifted"
        )

    def test_rubric_describes_not_met_vs_insufficient(self):
        """rubric.md must define the NOT_MET / INSUFFICIENT distinction."""
        text = _rubric_text()
        assert "NOT_MET" in text, "rubric.md must define NOT_MET status"
        assert "INSUFFICIENT" in text, "rubric.md must define INSUFFICIENT status"


class TestAgentInstructionsAlignWithRubric:
    """agents.py synthesis-agent prompt must not prohibit DENY."""

    def test_agent_instructions_do_not_forbid_deny(self):
        """None of the known stale DENY-prohibition phrases must appear in agents.py."""
        text_lower = _agents_text().lower()
        found = [phrase for phrase in _DENY_PROHIBITION_PHRASES if phrase in text_lower]
        assert not found, (
            f"agents.py contradicts the rubric — remove or replace these phrases: {found}"
        )

    def test_agent_instructions_describe_the_deny_condition(self):
        """agents.py must explain the NOT_MET vs INSUFFICIENT distinction."""
        text = _agents_text()
        assert "NOT_MET" in text, (
            "agents.py must explain the NOT_MET status (DENY candidate)"
        )
        assert "INSUFFICIENT" in text, (
            "agents.py must explain the INSUFFICIENT status (PEND candidate)"
        )

    def test_agent_output_format_includes_deny(self):
        """The output-format description must list DENY as a valid recommendation value."""
        text = _agents_text()
        assert "APPROVE, PEND, or DENY" in text, (
            "agents.py output-format block must list DENY as a valid recommendation value"
        )


class TestSkillReferenceFilesAlignWithRubric:
    """No LLM-facing surface may contain a DENY-prohibition phrase that
    contradicts rubric.md.  Coverage is by construction via _LLM_FACING_SURFACES:
    every LLM-facing file in the prior-auth workflow must appear in that list."""

    def test_no_deny_prohibition_in_any_llm_surface(self):
        """Scan every LLM-facing surface for DENY-prohibition phrases.

        Fails immediately with the offending file path and phrase on the first
        hit, so a future regression is instantly actionable.
        """
        assert _LLM_FACING_SURFACES, "_LLM_FACING_SURFACES is empty — check path constants"

        for surface in _LLM_FACING_SURFACES:
            text_lower = _read_surface(surface).lower()
            for phrase in _DENY_PROHIBITION_PHRASES:
                if phrase in text_lower:
                    raise AssertionError(
                        f"DENY-prohibition phrase found in LLM-facing surface.\n"
                        f"  File   : {surface.relative_to(REPO_ROOT)}\n"
                        f"  Phrase : '{phrase}'\n"
                        f"This contradicts rubric.md — update the file to reflect the "
                        f"correct policy (DENY is permitted for NOT_MET at >=90% confidence)."
                    )
