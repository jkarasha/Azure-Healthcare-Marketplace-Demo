"""Unit tests for the shared assessment schema contract."""

import copy

import pytest

from agents.workflows.assessment_schema import (
    BEAD_IDS,
    VALID_DECISIONS,
    validate_assessment,
)


def _valid_assessment() -> dict:
    return {
        "request_id": "PA-2026-0001",
        "workflow_id": "wf-abc123",
        "status": "completed",
        "beads": [
            {"id": "bd-pa-001-intake", "status": "completed"},
            {"id": "bd-pa-002-clinical", "status": "completed"},
            {"id": "bd-pa-003-recommend", "status": "completed"},
            {"id": "bd-pa-004-decision", "status": "not-started"},
            {"id": "bd-pa-005-notify", "status": "not-started"},
        ],
        "request": {
            "member": {"patient_id": "MRN 123456"},
            "service": {"name_of_medication_or_procedure": "Adalimumab"},
            "provider": {"npi": "1234567890"},
        },
        "clinical": {
            "chief_complaint": "Crohn's disease",
            "key_findings": ["Hgb 9.0"],
        },
        "policy": {
            "policy_id": "P-1",
            "policy_title": "Adalimumab PA Policy",
            "medical_necessity_check": {"is_covered": True, "policy_basis": "Section 2.A"},
        },
        "recommendation": {
            "decision": "PEND",
            "confidence": {"overall": 53.8},
            "confidence_score": 53.8,
            "rationale": "PA form incomplete.",
        },
    }


class TestValidateAssessment:
    def test_valid_assessment_has_no_errors(self):
        assert validate_assessment(_valid_assessment()) == []

    def test_reports_missing_top_level_keys(self):
        a = _valid_assessment()
        del a["request_id"]
        del a["status"]
        errors = validate_assessment(a)
        assert any("request_id" in e for e in errors)
        assert any("status" in e for e in errors)

    def test_reports_missing_recommendation_keys(self):
        a = _valid_assessment()
        del a["recommendation"]["confidence_score"]
        errors = validate_assessment(a)
        assert any("confidence_score" in e for e in errors)

    @pytest.mark.parametrize("decision", ["APPROVE", "PEND", "DENY"])
    def test_accepts_all_valid_decisions(self, decision):
        a = _valid_assessment()
        a["recommendation"]["decision"] = decision
        assert validate_assessment(a) == []

    def test_rejects_unknown_decision(self):
        a = _valid_assessment()
        a["recommendation"]["decision"] = "MAYBE"
        errors = validate_assessment(a)
        assert any("MAYBE" in e for e in errors)

    def test_rejects_missing_bead(self):
        a = _valid_assessment()
        a["beads"] = a["beads"][:-1]
        errors = validate_assessment(a)
        assert any("bd-pa-005-notify" in e for e in errors)

    def test_rejects_invalid_bead_status(self):
        a = _valid_assessment()
        a["beads"][0]["status"] = "finished"
        errors = validate_assessment(a)
        assert any("finished" in e for e in errors)

    def test_rejects_non_dict_input(self):
        assert validate_assessment("not a dict") != []

    def test_does_not_mutate_input(self):
        a = _valid_assessment()
        before = copy.deepcopy(a)
        validate_assessment(a)
        assert a == before

    def test_bead_ids_are_ordered(self):
        assert BEAD_IDS == [
            "bd-pa-001-intake",
            "bd-pa-002-clinical",
            "bd-pa-003-recommend",
            "bd-pa-004-decision",
            "bd-pa-005-notify",
        ]

    def test_valid_decisions_contract(self):
        assert {"APPROVE", "PEND", "DENY"} == VALID_DECISIONS
