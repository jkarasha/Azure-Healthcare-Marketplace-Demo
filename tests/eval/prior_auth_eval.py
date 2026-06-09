"""
Prior Authorization Workflow Evaluation — Core Logic

Evaluates how faithfully the agentic prior-auth workflow adheres to its
defined flow (SKILL.md) by validating:

  1. Schema compliance — assessment JSON matches the skill contract
  2. Bead sequencing — all 5 beads execute in order, none skipped
  3. Decision accuracy — AI recommendations match human MD ground truth
  4. Confidence calibration — high-confidence cases should be accurate

No pytest dependency — can be imported from scripts or tests.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# Bead contract definitions (from SKILL.md)
# ============================================================================

BEAD_IDS = [
    "bd-pa-001-intake",
    "bd-pa-002-clinical",
    "bd-pa-003-recommend",
    "bd-pa-004-decision",
    "bd-pa-005-notify",
]

BEAD_VALID_STATUSES = {"not-started", "in-progress", "completed"}

# Tools expected to be called per bead/agent role
EXPECTED_TOOL_USAGE = {
    "bd-pa-001-intake": {
        "agent": "ComplianceAgent",
        "required_tools": {"validate_npi", "lookup_npi", "validate_icd10"},
        "optional_tools": {"lookup_icd10", "hybrid_search"},
    },
    "bd-pa-002-clinical": {
        "agent": "ClinicalReviewer + CoverageAgent",
        "required_tools": set(),
        "optional_tools": {
            "search_pubmed",
            "get_article",
            "get_article_abstract",
            "search_patients",
            "get_patient",
            "get_patient_conditions",
            "search_coverage",
            "get_coverage_by_cpt",
            "get_coverage_by_icd10",
            "check_medical_necessity",
            "hybrid_search",
        },
    },
    "bd-pa-003-recommend": {
        "agent": "SynthesisAgent",
        "required_tools": set(),
        "optional_tools": set(),
    },
}

# ============================================================================
# Assessment schema contract
# ============================================================================

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
VALID_DECISIONS = {"APPROVE", "PEND", "DENY"}

REQUIRED_POLICY_KEYS = {"policy_id", "policy_title", "medical_necessity_check"}
REQUIRED_CLINICAL_KEYS = {"chief_complaint", "key_findings"}


# ============================================================================
# Data classes
# ============================================================================


@dataclass
class BeadEvalResult:
    """Evaluation result for a single bead."""

    bead_id: str
    present: bool = False
    status_valid: bool = False
    status: str = ""
    ordered: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class SchemaEvalResult:
    """Schema validation result for an assessment."""

    valid: bool = True
    missing_top_level: list[str] = field(default_factory=list)
    missing_request: list[str] = field(default_factory=list)
    missing_recommendation: list[str] = field(default_factory=list)
    missing_policy: list[str] = field(default_factory=list)
    missing_clinical: list[str] = field(default_factory=list)
    decision_valid: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class DecisionEvalResult:
    """Decision accuracy comparison against ground truth."""

    case_id: str
    ground_truth_decision: str
    ai_decision: str
    match: bool = False
    confidence_score: float = 0.0
    criteria_percentage: float = 0.0


@dataclass
class CaseEvalReport:
    """Complete evaluation report for a single PA case."""

    case_id: str
    assessment_path: str
    bead_results: list[BeadEvalResult] = field(default_factory=list)
    schema_result: SchemaEvalResult = field(default_factory=SchemaEvalResult)
    decision_result: DecisionEvalResult | None = None
    score: float = 0.0


# ============================================================================
# Evaluation functions
# ============================================================================


def evaluate_beads(assessment: dict) -> list[BeadEvalResult]:
    """Validate bead sequencing and status in an assessment."""
    beads = assessment.get("beads", [])
    bead_map = {b["id"]: b for b in beads if isinstance(b, dict) and "id" in b}

    results = []
    prev_completed = True

    for expected_id in BEAD_IDS:
        result = BeadEvalResult(bead_id=expected_id)

        if expected_id in bead_map:
            result.present = True
            bead = bead_map[expected_id]
            result.status = bead.get("status", "")
            result.status_valid = result.status in BEAD_VALID_STATUSES

            if result.status == "completed" and not prev_completed:
                result.ordered = False
                result.errors.append("Completed out of order (prev bead not completed)")
            else:
                result.ordered = True

            prev_completed = result.status == "completed"
        else:
            result.errors.append("Bead missing from assessment")
            prev_completed = False

        results.append(result)

    return results


def evaluate_schema(assessment: dict) -> SchemaEvalResult:
    """Validate the assessment matches the skill contract schema."""
    result = SchemaEvalResult()

    result.missing_top_level = [k for k in REQUIRED_TOP_LEVEL_KEYS if k not in assessment]
    if result.missing_top_level:
        result.valid = False

    request = assessment.get("request", {})
    result.missing_request = [k for k in REQUIRED_REQUEST_KEYS if k not in request]
    if result.missing_request:
        result.valid = False

    rec = assessment.get("recommendation", {})
    result.missing_recommendation = [k for k in REQUIRED_RECOMMENDATION_KEYS if k not in rec]
    if result.missing_recommendation:
        result.valid = False

    decision = rec.get("decision", "").upper()
    result.decision_valid = decision in VALID_DECISIONS
    if not result.decision_valid:
        result.errors.append(f"Invalid decision: '{decision}' (expected {VALID_DECISIONS})")
        result.valid = False

    policy = assessment.get("policy", {})
    result.missing_policy = [k for k in REQUIRED_POLICY_KEYS if k not in policy]

    clinical = assessment.get("clinical", {})
    result.missing_clinical = [k for k in REQUIRED_CLINICAL_KEYS if k not in clinical]

    return result


def evaluate_decision(
    case_id: str,
    assessment: dict,
    ground_truth: dict,
) -> DecisionEvalResult:
    """Compare AI decision against human MD ground truth."""
    gt_entry = ground_truth.get(case_id, {})
    gt_decision = gt_entry.get("decision", "unknown")

    rec = assessment.get("recommendation", {})
    ai_decision = rec.get("decision", "UNKNOWN").upper()
    confidence_score = rec.get("confidence_score", 0)
    if isinstance(confidence_score, dict):
        confidence_score = confidence_score.get("overall", 0)
    criteria_pct = rec.get("criteria_percentage", 0)

    gt_normalized = gt_decision.lower()
    ai_normalized = ai_decision.lower()

    if gt_normalized == "approved":
        match = ai_normalized == "approve"
    elif gt_normalized == "rejected":
        match = ai_normalized in ("pend", "deny")
    else:
        match = False

    return DecisionEvalResult(
        case_id=case_id,
        ground_truth_decision=gt_decision,
        ai_decision=ai_decision,
        match=match,
        confidence_score=confidence_score if isinstance(confidence_score, (int, float)) else 0,
        criteria_percentage=criteria_pct if isinstance(criteria_pct, (int, float)) else 0,
    )


def compute_fidelity_score(
    bead_results: list[BeadEvalResult],
    schema_result: SchemaEvalResult,
    decision_result: DecisionEvalResult | None = None,
) -> float:
    """
    Compute composite fidelity score (0-100).

    Weighting:
      - Bead compliance:   30%
      - Schema compliance: 30%
      - Decision accuracy: 40%
    """
    total_beads = len(BEAD_IDS)
    present = sum(1 for b in bead_results if b.present)
    ordered = sum(1 for b in bead_results if b.ordered)
    valid_status = sum(1 for b in bead_results if b.status_valid)
    bead_score = (present + ordered + valid_status) / (total_beads * 3) * 30

    schema_penalties = (
        len(schema_result.missing_top_level) * 3
        + len(schema_result.missing_request) * 2
        + len(schema_result.missing_recommendation) * 3
        + len(schema_result.missing_policy)
        + len(schema_result.missing_clinical)
    )
    schema_score = max(0, 30 - schema_penalties)

    if decision_result:
        if decision_result.match and decision_result.confidence_score >= 60:
            decision_score = 40
        elif decision_result.match:
            decision_score = 30
        else:
            decision_score = 0
    else:
        decision_score = 0

    return round(bead_score + schema_score + decision_score, 1)


def evaluate_case(
    case_id: str,
    assessment: dict,
    ground_truth: dict | None = None,
    assessment_path: str = "",
) -> CaseEvalReport:
    """Run all evaluations for a single PA case."""
    bead_results = evaluate_beads(assessment)
    schema_result = evaluate_schema(assessment)

    decision_result = None
    if ground_truth and case_id in ground_truth:
        decision_result = evaluate_decision(case_id, assessment, ground_truth)

    score = compute_fidelity_score(bead_results, schema_result, decision_result)

    return CaseEvalReport(
        case_id=case_id,
        assessment_path=assessment_path,
        bead_results=bead_results,
        schema_result=schema_result,
        decision_result=decision_result,
        score=score,
    )


# ============================================================================
# Batch evaluation
# ============================================================================


def evaluate_all_cases(
    cases_dir: Path,
    ground_truth_path: Path | None = None,
) -> list[CaseEvalReport]:
    """Evaluate all PA cases found in the data/cases directory."""
    ground_truth = {}
    if ground_truth_path and ground_truth_path.exists():
        with open(ground_truth_path) as f:
            ground_truth = json.load(f)

    reports: list[CaseEvalReport] = []

    for case_dir in sorted(cases_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        for variant_dir in sorted(case_dir.iterdir()):
            if not variant_dir.is_dir():
                continue

            assessment_path = variant_dir / "waypoints" / "assessment.json"
            if not assessment_path.exists():
                continue

            case_id = f"{case_dir.name}_{variant_dir.name}"
            with open(assessment_path) as f:
                assessment = json.load(f)

            report = evaluate_case(
                case_id=case_id,
                assessment=assessment,
                ground_truth=ground_truth,
                assessment_path=str(assessment_path),
            )
            reports.append(report)

    return reports


def format_report(reports: list[CaseEvalReport]) -> str:
    """Format evaluation reports into a human-readable summary."""
    lines = [
        "=" * 72,
        "PRIOR AUTH WORKFLOW FIDELITY EVALUATION",
        "=" * 72,
        "",
    ]

    total_score = 0
    matched = 0
    total_with_gt = 0

    for r in reports:
        total_score += r.score
        if r.decision_result:
            total_with_gt += 1
            if r.decision_result.match:
                matched += 1

        beads_ok = sum(1 for b in r.bead_results if b.present and b.ordered)
        schema_ok = "pass" if r.schema_result.valid else "FAIL"

        decision_str = "N/A"
        gt_str = ""
        if r.decision_result:
            icon = "MATCH" if r.decision_result.match else "MISS"
            decision_str = (
                f"{icon} AI={r.decision_result.ai_decision} "
                f"GT={r.decision_result.ground_truth_decision}"
            )
            gt_str = f" (conf={r.decision_result.confidence_score}%)"

        lines.append(
            f"  {r.case_id:12s}  "
            f"Score={r.score:5.1f}  "
            f"Beads={beads_ok}/5  "
            f"Schema={schema_ok:4s}  "
            f"Decision={decision_str}{gt_str}"
        )

        if r.schema_result.missing_top_level:
            lines.append(f"    [warn] Missing top-level: {r.schema_result.missing_top_level}")
        if r.schema_result.missing_recommendation:
            lines.append(f"    [warn] Missing recommendation: {r.schema_result.missing_recommendation}")

        for b in r.bead_results:
            if b.errors:
                lines.append(f"    [warn] {b.bead_id}: {', '.join(b.errors)}")

    lines.append("")
    lines.append("-" * 72)

    n = len(reports)
    avg = total_score / n if n else 0
    accuracy = (matched / total_with_gt * 100) if total_with_gt else 0

    lines.append(f"  Cases evaluated:     {n}")
    lines.append(f"  Average fidelity:    {avg:.1f} / 100")
    lines.append(f"  Decision accuracy:   {matched}/{total_with_gt} ({accuracy:.0f}%)")
    lines.append("")
    lines.append("=" * 72)

    return "\n".join(lines)
