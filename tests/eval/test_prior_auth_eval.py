"""
Prior Authorization Workflow Evaluation — pytest Test Suite

Runs the eval framework against existing waypoints in data/cases/.

Run via:
  pytest tests/eval/test_prior_auth_eval.py -v
  python scripts/eval_prior_auth.py  (aggregate report)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.eval.prior_auth_eval import (
    BEAD_IDS,
    BEAD_VALID_STATUSES,
    REQUIRED_REQUEST_KEYS,
    REQUIRED_TOP_LEVEL_KEYS,
    VALID_DECISIONS,
    CaseEvalReport,
    evaluate_all_cases,
    evaluate_beads,
    format_report,
)

# ============================================================================
# pytest tests — run offline against existing waypoints
# ============================================================================

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
CASES_DIR = WORKSPACE_ROOT / "data" / "cases"
GROUND_TRUTH_PATH = CASES_DIR / "ground_truth.json"


class TestPriorAuthSchemaContract:
    """Validates assessment JSON structure for existing waypoints."""

    @pytest.fixture(scope="class")
    def ground_truth(self) -> dict:
        if GROUND_TRUTH_PATH.exists():
            with open(GROUND_TRUTH_PATH) as f:
                return json.load(f)
        return {}

    @pytest.fixture(scope="class")
    def sample_assessment(self) -> dict | None:
        """Load first available assessment.json for schema testing."""
        for case_dir in sorted(CASES_DIR.iterdir()):
            if not case_dir.is_dir():
                continue
            for variant_dir in sorted(case_dir.iterdir()):
                if not variant_dir.is_dir():
                    continue
                path = variant_dir / "waypoints" / "assessment.json"
                if path.exists():
                    with open(path) as f:
                        return json.load(f)
        pytest.skip("No assessment.json found in data/cases/")

    def test_top_level_keys(self, sample_assessment):
        """Assessment has all required top-level keys."""
        missing = REQUIRED_TOP_LEVEL_KEYS - set(sample_assessment.keys())
        assert not missing, f"Missing top-level keys: {missing}"

    def test_beads_array_complete(self, sample_assessment):
        """All 5 beads are present."""
        beads = sample_assessment.get("beads", [])
        bead_ids = {b["id"] for b in beads if isinstance(b, dict)}
        expected = set(BEAD_IDS)
        missing = expected - bead_ids
        assert not missing, f"Missing beads: {missing}"

    def test_bead_statuses_valid(self, sample_assessment):
        """Every bead has a valid status."""
        for bead in sample_assessment.get("beads", []):
            assert bead.get("status") in BEAD_VALID_STATUSES, (
                f"Bead {bead.get('id')} has invalid status: {bead.get('status')}"
            )

    def test_recommendation_has_decision(self, sample_assessment):
        """Recommendation includes a decision."""
        rec = sample_assessment.get("recommendation", {})
        decision = rec.get("decision", "")
        assert decision, "Recommendation missing decision"

    def test_recommendation_decision_is_valid(self, sample_assessment):
        """Decision is one of APPROVE, PEND, DENY."""
        rec = sample_assessment.get("recommendation", {})
        decision = rec.get("decision", "").upper()
        assert decision in VALID_DECISIONS, f"Invalid decision: {decision}"

    def test_request_has_member_service_provider(self, sample_assessment):
        """Request block has member, service, provider."""
        request = sample_assessment.get("request", {})
        for key in REQUIRED_REQUEST_KEYS:
            assert key in request, f"Request missing '{key}'"

    def test_criteria_evaluation_is_list(self, sample_assessment):
        """criteria_evaluation is a list (can be empty)."""
        ce = sample_assessment.get("criteria_evaluation")
        assert isinstance(ce, list), "criteria_evaluation should be a list"

    def test_criteria_items_have_status(self, sample_assessment):
        """Each criterion has a status field."""
        for i, c in enumerate(sample_assessment.get("criteria_evaluation", [])):
            assert "status" in c, f"Criterion {i} missing status"
            assert "criterion" in c, f"Criterion {i} missing criterion name"


class TestPriorAuthBeadSequencing:
    """Validates bead ordering for all available assessments."""

    @pytest.fixture(scope="class")
    def all_assessments(self) -> list[tuple[str, dict]]:
        results = []
        for case_dir in sorted(CASES_DIR.iterdir()):
            if not case_dir.is_dir():
                continue
            for variant_dir in sorted(case_dir.iterdir()):
                if not variant_dir.is_dir():
                    continue
                path = variant_dir / "waypoints" / "assessment.json"
                if path.exists():
                    with open(path) as f:
                        results.append((f"{case_dir.name}_{variant_dir.name}", json.load(f)))
        if not results:
            pytest.skip("No assessment files found")
        return results

    def test_beads_in_correct_order(self, all_assessments):
        """For each case, completed beads should be in sequential order."""
        for case_id, assessment in all_assessments:
            results = evaluate_beads(assessment)
            for r in results:
                if r.errors:
                    pytest.fail(f"Case {case_id}: bead {r.bead_id} — {r.errors}")

    def test_no_skipped_beads(self, all_assessments):
        """No completed bead should follow a not-started bead."""
        for case_id, assessment in all_assessments:
            beads = assessment.get("beads", [])
            seen_not_started = False
            for b in beads:
                if b.get("status") == "not-started":
                    seen_not_started = True
                elif b.get("status") == "completed" and seen_not_started:
                    pytest.fail(
                        f"Case {case_id}: bead {b['id']} completed after "
                        f"a not-started bead"
                    )


class TestPriorAuthDecisionAccuracy:
    """Compares AI decisions against human MD ground truth."""

    @pytest.fixture(scope="class")
    def eval_reports(self) -> list[CaseEvalReport]:
        if not GROUND_TRUTH_PATH.exists():
            pytest.skip("No ground_truth.json found")
        reports = evaluate_all_cases(CASES_DIR, GROUND_TRUTH_PATH)
        if not reports:
            pytest.skip("No assessment files found to evaluate")
        return reports

    def test_overall_accuracy_above_threshold(self, eval_reports):
        """Decision accuracy should be >= 50% (baseline threshold)."""
        with_gt = [r for r in eval_reports if r.decision_result]
        if not with_gt:
            pytest.skip("No cases with ground truth match")
        matched = sum(1 for r in with_gt if r.decision_result.match)
        accuracy = matched / len(with_gt) * 100
        assert accuracy >= 50, f"Decision accuracy {accuracy:.0f}% below 50% threshold"

    def test_rejection_recall(self, eval_reports):
        """System should correctly flag rejected cases (PEND or DENY)."""
        rejected = [
            r
            for r in eval_reports
            if r.decision_result and r.decision_result.ground_truth_decision == "rejected"
        ]
        if not rejected:
            pytest.skip("No rejected cases in ground truth")
        flagged = sum(1 for r in rejected if r.decision_result.match)
        recall = flagged / len(rejected) * 100
        # Rejection recall is critical — should be high
        assert recall >= 50, (
            f"Rejection recall {recall:.0f}% below 50% threshold. "
            f"System missed {len(rejected) - flagged}/{len(rejected)} rejections."
        )

    def test_average_fidelity_score(self, eval_reports):
        """Average fidelity score should be >= 40 (lenient baseline)."""
        avg = sum(r.score for r in eval_reports) / len(eval_reports)
        assert avg >= 40, f"Average fidelity {avg:.1f} below 40-point threshold"

    def test_print_report(self, eval_reports):
        """Print full evaluation report (always passes, informational)."""
        report = format_report(eval_reports)
        print("\n" + report)
