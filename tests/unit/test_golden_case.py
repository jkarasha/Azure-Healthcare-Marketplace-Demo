"""The committed reference assessment must satisfy the schema contract.

data/cases/001/a is the repo's only golden prior-auth output. If it drifts
from the contract, every downstream eval number is meaningless.
"""

import json
from pathlib import Path

from agents.workflows.assessment_schema import validate_assessment
from tests.eval.prior_auth_eval import evaluate_decision

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN = REPO_ROOT / "data" / "cases" / "001" / "a" / "waypoints" / "assessment.json"
GROUND_TRUTH_PATH = REPO_ROOT / "data" / "cases" / "ground_truth.json"


def _golden_assessment() -> dict:
    return json.loads(GOLDEN.read_text())


def _ground_truth() -> dict:
    return json.loads(GROUND_TRUTH_PATH.read_text())


class TestGoldenCase:
    def test_golden_assessment_file_exists(self):
        assert GOLDEN.exists(), f"missing golden assessment: {GOLDEN}"

    def test_golden_assessment_is_valid_json(self):
        _golden_assessment()

    def test_golden_assessment_satisfies_schema(self):
        assessment = _golden_assessment()
        errors = validate_assessment(assessment)
        assert errors == [], "golden assessment violates the contract:\n  " + "\n  ".join(errors)

    def test_golden_confidence_score_agrees_with_breakdown(self):
        rec = _golden_assessment()["recommendation"]
        assert isinstance(rec["confidence"], str) and rec["confidence"] in {"HIGH", "MEDIUM", "LOW"}, (
            f"recommendation.confidence must be a HIGH/MEDIUM/LOW string, got {rec['confidence']!r}"
        )
        assert rec["confidence_score"] == rec["confidence_scores"]["overall"], (
            "flat confidence_score must equal the per-dimension overall"
        )

    def test_ground_truth_001a_decision_is_rejected(self):
        """The human-MD ground truth for case 001_a must be 'rejected'."""
        ground_truth = _ground_truth()
        assert ground_truth["001_a"]["decision"] == "rejected", (
            "ground_truth.json: expected 001_a decision='rejected', "
            f"got {ground_truth['001_a'].get('decision')!r}"
        )

    def test_golden_decision_matches_ground_truth(self):
        """Golden PEND/DENY must agree with ground-truth 'rejected' via evaluate_decision."""
        result = evaluate_decision("001_a", _golden_assessment(), _ground_truth())
        assert result.match, (
            f"golden decision {result.ai_decision!r} does not match "
            f"ground truth {result.ground_truth_decision!r} for case 001_a"
        )
