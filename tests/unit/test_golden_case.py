"""The committed reference assessment must satisfy the schema contract.

data/cases/001/a is the repo's only golden prior-auth output. If it drifts
from the contract, every downstream eval number is meaningless.
"""

import json
from pathlib import Path

from agents.workflows.assessment_schema import validate_assessment

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN = REPO_ROOT / "data" / "cases" / "001" / "a" / "waypoints" / "assessment.json"


def test_golden_assessment_file_exists():
    assert GOLDEN.exists(), f"missing golden assessment: {GOLDEN}"


def test_golden_assessment_is_valid_json():
    json.loads(GOLDEN.read_text())


def test_golden_assessment_satisfies_schema():
    assessment = json.loads(GOLDEN.read_text())
    errors = validate_assessment(assessment)
    assert errors == [], "golden assessment violates the contract:\n  " + "\n  ".join(errors)


def test_golden_assessment_matches_ground_truth_shape():
    """Ground truth for 001_a is 'rejected'; a PEND or DENY is consistent."""
    assessment = json.loads(GOLDEN.read_text())
    ground_truth = json.loads((REPO_ROOT / "data" / "cases" / "ground_truth.json").read_text())
    assert ground_truth["001_a"]["decision"] == "rejected"
    assert assessment["recommendation"]["decision"] in ("PEND", "DENY")
