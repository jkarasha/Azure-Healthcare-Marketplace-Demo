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


def _agents_text() -> str:
    return AGENTS_PY.read_text()


def _rubric_text() -> str:
    return RUBRIC.read_text()


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
        text = _agents_text()
        forbidden = [
            "AI Never Recommends DENY",
            "You may ONLY recommend **APPROVE** or **PEND**",
            "never DENY",
            "Never make denial recommendations",
        ]
        found = [phrase for phrase in forbidden if phrase in text]
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
