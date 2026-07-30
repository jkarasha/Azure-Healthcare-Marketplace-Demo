"""The prior-auth assessment contract, in one executable place.

The workflow writes assessments and the eval harness scores them; before
this module they each carried their own copy of the expected shape. This is
the single source of truth for both. Pure and dependency-free so it can be
imported by tests without the agent framework.

Mirrors .github/skills/prior-auth-azure/SKILL.md.
"""

from __future__ import annotations

from typing import Any

BEAD_IDS = [
    "bd-pa-001-intake",
    "bd-pa-002-clinical",
    "bd-pa-003-recommend",
    "bd-pa-004-decision",
    "bd-pa-005-notify",
]

VALID_BEAD_STATUSES = {"not-started", "in-progress", "completed", "blocked"}
VALID_DECISIONS = {"APPROVE", "PEND", "DENY"}

REQUIRED_TOP_LEVEL_KEYS = {
    "request_id",
    "workflow_id",
    "status",
    "beads",
    "request",
    "clinical",
    "policy",
    "recommendation",
}
REQUIRED_REQUEST_KEYS = {"member", "service", "provider"}
REQUIRED_RECOMMENDATION_KEYS = {"decision", "confidence", "confidence_score", "rationale"}
REQUIRED_POLICY_KEYS = {"policy_id", "policy_title", "medical_necessity_check"}
REQUIRED_CLINICAL_KEYS = {"chief_complaint", "key_findings"}


def _missing(container: Any, required: set[str], label: str) -> list[str]:
    if not isinstance(container, dict):
        return [f"{label}: expected an object, got {type(container).__name__}"]
    return [f"{label}: missing required key '{k}'" for k in sorted(required) if k not in container]


def validate_assessment(assessment: Any) -> list[str]:
    """Return a list of human-readable contract violations. Empty means valid.

    Never raises and never mutates ``assessment``.
    """
    if not isinstance(assessment, dict):
        return [f"assessment: expected an object, got {type(assessment).__name__}"]

    errors: list[str] = []
    errors += _missing(assessment, REQUIRED_TOP_LEVEL_KEYS, "assessment")
    errors += _missing(assessment.get("request"), REQUIRED_REQUEST_KEYS, "request")
    errors += _missing(assessment.get("clinical"), REQUIRED_CLINICAL_KEYS, "clinical")
    errors += _missing(assessment.get("policy"), REQUIRED_POLICY_KEYS, "policy")
    errors += _missing(assessment.get("recommendation"), REQUIRED_RECOMMENDATION_KEYS, "recommendation")

    rec = assessment.get("recommendation")
    if isinstance(rec, dict) and "decision" in rec:
        decision = str(rec.get("decision", "")).upper()
        if decision not in VALID_DECISIONS:
            errors.append(f"recommendation.decision: '{decision}' is not one of {sorted(VALID_DECISIONS)}")

    beads = assessment.get("beads")
    if not isinstance(beads, list):
        errors.append("beads: expected a list")
    else:
        by_id = {b.get("id"): b for b in beads if isinstance(b, dict)}
        for bead_id in BEAD_IDS:
            bead = by_id.get(bead_id)
            if bead is None:
                errors.append(f"beads: missing bead '{bead_id}'")
                continue
            status = bead.get("status")
            if status not in VALID_BEAD_STATUSES:
                errors.append(
                    f"beads.{bead_id}.status: '{status}' is not one of {sorted(VALID_BEAD_STATUSES)}"
                )

    return errors
