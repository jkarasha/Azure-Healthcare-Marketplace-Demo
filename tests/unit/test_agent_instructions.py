"""Agent instructions must not contradict the authoritative skill rubric.

The rubric (.github/skills/prior-auth-azure/references/rubric.md) permits an
AI DENY recommendation when a mandatory criterion is NOT_MET at >= 90%
confidence, with the human confirming in Subskill 2. These tests keep the
prompt text and the rubric from drifting apart again.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_PY = REPO_ROOT / "src" / "agents" / "agents.py"
PRIOR_AUTH_PY = REPO_ROOT / "src" / "agents" / "workflows" / "prior_auth.py"
RUBRIC = REPO_ROOT / ".github" / "skills" / "prior-auth-azure" / "references" / "rubric.md"
SKILL_MD = REPO_ROOT / ".github" / "skills" / "prior-auth-azure" / "SKILL.md"
SKILL_REFS_DIR = REPO_ROOT / ".github" / "skills" / "prior-auth-azure" / "references"
PA_REPORT_DIR = REPO_ROOT / ".github" / "skills" / "pa-report-formatter"

# Every file that is sent (verbatim or by reference) to an LLM during a
# prior-auth workflow.  Coverage is by construction: if a surface is added
# here it is automatically guarded; if a new surface is created it must be
# added here.
_LLM_FACING_SURFACES: list[Path] = [
    AGENTS_PY,
    PRIOR_AUTH_PY,
    SKILL_MD,
    *sorted(SKILL_REFS_DIR.rglob("*.md")),
    *sorted(PA_REPORT_DIR.rglob("*.md")),
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


class TestRuntimePromptDecisionSpace:
    """The synthesis-agent runtime prompt in prior_auth.py must expose the
    three-way decision space (APPROVE / PEND / DENY).  These are *positive*
    assertions — a trivial typo or revert that collapses the option list to
    two values must fail the suite immediately (I2-a).

    Also guards SKILL.md and 04-determination.md, which feed the same
    decision loop from the skill side.
    """

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    def test_prior_auth_py_synthesis_prompt_includes_deny(self):
        """prior_auth.py must tell the synthesis agent that DENY is a valid output."""
        text = self._read(PRIOR_AUTH_PY)
        assert '"APPROVE", "PEND", or "DENY"' in text, (
            'prior_auth.py synthesis prompt must contain \'\"APPROVE\", \"PEND\", or \"DENY\"\'; '
            "reverting line 777 to a two-value option list silently removes DENY as an output."
        )

    def test_prior_auth_py_synthesis_prompt_includes_denial_rationale(self):
        """prior_auth.py must request denial_rationale so DENY decisions surface clinical basis."""
        text = self._read(PRIOR_AUTH_PY)
        assert "denial_rationale" in text, (
            "prior_auth.py must include 'denial_rationale' in the synthesis prompt; "
            "without it DENY decisions lose their clinical justification."
        )

    def test_skill_md_includes_deny_decision_space(self):
        """SKILL.md must document that DENY is a valid AI recommendation."""
        text = self._read(SKILL_MD)
        assert "APPROVE, PEND, or DENY" in text, (
            "SKILL.md must document the three-way decision space (APPROVE/PEND/DENY); "
            "a two-value reference contradicts the rubric."
        )

    def test_04_determination_md_includes_deny_in_purpose(self):
        """04-determination.md Purpose line must list DENY alongside APPROVE/PEND."""
        path = SKILL_REFS_DIR / "prompts" / "04-determination.md"
        text = self._read(path)
        # The Purpose line drives what the prompt module tells agents it produces.
        assert "DENY" in text.splitlines()[3], (
            "04-determination.md line 4 (Purpose) must include DENY; "
            "omitting it contradicts the same file's decision logic at lines 116/129/163."
        )
