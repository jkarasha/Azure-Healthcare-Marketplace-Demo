"""
Prior Authorization Workflow — Skill-Aligned Implementation

Aligns to: .github/skills/prior-auth-azure/SKILL.md

Architecture:
  Subskill 1 — Intake & Assessment (beads 001-003)
    Bead 001 (Intake):     Compliance Agent validates completeness (gate)
                           + RAG policy retrieval (folded into intake)
    Bead 002 (Clinical):   Clinical Reviewer + Coverage Agent run in parallel
    Bead 003 (Recommend):  Synthesis Agent aggregates into APPROVE/PEND/DENY

  Subskill 2 — Decision & Notification (beads 004-005)
    Bead 004 (Decision):   Human decision capture (confirm/override)
    Bead 005 (Notify):     Notification letter + determination JSON generation

Waypoint schema matches the skill contract so that outputs are
replicable across agentic platforms (Copilot Chat, Foundry, DevUI, CLI).

Uses Microsoft Agent Framework's SequentialBuilder and ConcurrentBuilder
composed into a custom hybrid workflow.  Audit events and bead state are
recorded at each phase boundary.

Run outputs are stored in .runs/<timestamp>_<request-id>/ with waypoints/
and outputs/ subdirs. A 'latest' symlink in .runs/ points to the most
recent run.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agent_framework.azure import AzureOpenAIResponsesClient
from agent_framework_orchestrations import ConcurrentBuilder
from azure.identity import AzureCliCredential, DefaultAzureCredential

from ..agents import (
    create_clinical_reviewer_agent,
    create_compliance_agent,
    create_coverage_agent,
    create_synthesis_agent,
)
from ..config import AgentConfig
from ..tools import MCPToolKit
from .parsing import extract_json_from_text, extract_recommendation_from_text, split_concurrent_outputs

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Run directory helpers — .runs/<timestamp>_<request-id>/
# ---------------------------------------------------------------------------

def _find_project_root() -> Path:
    """Walk up from CWD to find the project root (contains .runs/ or pyproject.toml)."""
    candidate = Path.cwd()
    for _ in range(10):
        if (candidate / "pyproject.toml").exists() or (candidate / ".runs").exists():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return Path.cwd()


def _create_run_dir(request_id: str, *, base_dir: str | None = None) -> Path:
    """Create a timestamped run directory under .runs/.

    Returns the run directory path. Creates waypoints/ and outputs/ subdirs.
    Updates the 'latest' symlink.
    """
    root = Path(base_dir) if base_dir else _find_project_root()
    runs_root = root / ".runs"

    # Sanitize request_id for filesystem safety
    safe_id = re.sub(r"[^\w\-]", "_", request_id)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")
    run_name = f"{timestamp}_{safe_id}"

    run_dir = runs_root / run_name
    (run_dir / "waypoints").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "eval").mkdir(parents=True, exist_ok=True)

    # Update latest symlink
    latest = runs_root / "latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(run_name)
    except OSError:
        logger.warning("Could not create 'latest' symlink in .runs/")

    logger.info("Run directory created: %s", run_dir)
    return run_dir


def _resolve_run_dir(output_dir: str | None) -> Path:
    """Resolve an explicit output_dir or find the latest run.

    If output_dir is given, use it as the run directory.
    Otherwise, look for .runs/latest symlink.
    """
    if output_dir:
        p = Path(output_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    root = _find_project_root()
    latest = root / ".runs" / "latest"
    if latest.is_symlink() and latest.resolve().exists():
        return latest.resolve()

    raise ValueError(
        "No run directory found. Run Subskill 1 first, or pass output_dir."
    )


# ---------------------------------------------------------------------------
# Bead definitions — mirrors SKILL.md § Bead Definitions
# ---------------------------------------------------------------------------

BEAD_IDS = [
    "bd-pa-001-intake",
    "bd-pa-002-clinical",
    "bd-pa-003-recommend",
    "bd-pa-004-decision",
    "bd-pa-005-notify",
]


def _make_beads() -> list[dict[str, Any]]:
    """Create the initial bead tracking array."""
    return [{"id": bid, "status": "not-started"} for bid in BEAD_IDS]


def _update_bead(
    beads: list[dict[str, Any]],
    bead_id: str,
    status: str,
) -> None:
    """Update a bead's status in-place."""
    ts_key = "completed_at" if status == "completed" else "started_at"
    for b in beads:
        if b["id"] == bead_id:
            b["status"] = status
            b[ts_key] = datetime.now(timezone.utc).isoformat()
            return


def _first_incomplete_bead(beads: list[dict[str, Any]]) -> str | None:
    """Return the ID of the first non-completed bead, or None."""
    for b in beads:
        if b["status"] != "completed":
            return b["id"]
    return None


def _bead_needs_work(beads: list[dict], bead_id: str) -> bool:
    """Return True if the bead is not yet completed."""
    for b in beads:
        if b["id"] == bead_id:
            return b["status"] != "completed"
    return True


# ---------------------------------------------------------------------------
# Waypoint I/O — skill-compatible schema
# ---------------------------------------------------------------------------


def _write_waypoint(path: Path, data: dict) -> None:
    """Write a waypoint JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info("Waypoint written: %s", path)


def _read_waypoint(path: Path) -> dict | None:
    """Read a waypoint if it exists, else None."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def _write_output_file(path: Path, content: str) -> None:
    """Write a text output file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    logger.info("Output written: %s", path)


# ---------------------------------------------------------------------------
# Structured output parsing helpers
# ---------------------------------------------------------------------------


def _extract_json_from_text(text: str) -> dict | None:
    """Try to extract a JSON object from agent text output.

    Thin wrapper kept for call-site compatibility; the implementation lives
    in ``parsing.py`` so it can be unit tested without the agent framework.
    """
    return extract_json_from_text(text)


def _safe_get(d: dict | None, *keys: str, default: Any = None) -> Any:
    """Nested dict get with fallback."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------


async def _record_audit_event(
    toolkit: MCPToolKit,
    workflow_id: str,
    phase: str,
    action: str,
    status: str,
    *,
    input_summary: str = "",
    output_summary: str = "",
    details: dict | None = None,
    agent_name: str = "workflow",
) -> None:
    """Fire-and-forget audit event via cosmos-rag MCP server."""
    try:
        audit_tool = toolkit.audit_tools()[0]
        async with audit_tool:
            import httpx

            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": "record_audit_event",
                    "arguments": {
                        "workflow_id": workflow_id,
                        "workflow_type": "prior-auth",
                        "phase": phase,
                        "agent_name": agent_name,
                        "action": action,
                        "status": status,
                        "input_summary": input_summary,
                        "output_summary": output_summary,
                        "details": details or {},
                    },
                },
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as hc:
                resp = await hc.post(audit_tool.url, json=payload)
                resp.raise_for_status()
    except Exception:
        logger.warning("Failed to record audit event (phase=%s)", phase, exc_info=True)


# ---------------------------------------------------------------------------
# RAG retrieval helper (folded into bead 001 per skill)
# ---------------------------------------------------------------------------


async def _rag_policy_retrieval(
    toolkit: MCPToolKit,
    request_data: dict[str, Any],
) -> str:
    """RAG hybrid search for payer policies.

    Per SKILL.md, this is folded into bead 001 (intake) as the
    policy retrieval step rather than a standalone phase.
    """
    cpt_codes = _safe_get(request_data, "service", "cpt_codes", default=[])
    if not cpt_codes:
        cpt_code = _safe_get(request_data, "service", "cpt_code", default="")
        cpt_codes = [cpt_code] if cpt_code else []
    icd_codes = _safe_get(request_data, "diagnosis", "icd10_codes", default=[])
    if not icd_codes:
        icd_codes = _safe_get(request_data, "service", "icd10_codes", default=[])
    service_desc = _safe_get(request_data, "service", "description", default="")

    search_query = f"{service_desc} {' '.join(cpt_codes)} {' '.join(icd_codes)}".strip()
    if not search_query:
        return ""

    try:
        rag_tool = toolkit.rag_search_tools()[0]
        async with rag_tool:
            import httpx

            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": "hybrid_search",
                    "arguments": {
                        "query": search_query[:500],
                        "category": "payer-policy",
                        "top_k": 5,
                    },
                },
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as hc:
                resp = await hc.post(rag_tool.url, json=payload)
                if resp.status_code == 200:
                    rpc_result = resp.json()
                    content = rpc_result.get("result", {}).get("content", [])
                    if content:
                        text = content[0].get("text", "")
                        logger.info("RAG retrieval: %d chars of policy context", len(text))
                        return text
    except Exception:
        logger.warning("RAG policy retrieval failed — continuing without", exc_info=True)
    return ""


# ---------------------------------------------------------------------------
# Subskill 1: Intake & Assessment (beads 001-003)
# ---------------------------------------------------------------------------


async def run_prior_auth_workflow(
    request_data: dict[str, Any],
    config: AgentConfig | None = None,
    *,
    output_dir: str | None = None,
    local: bool = False,
) -> dict[str, Any]:
    """
    Execute the Prior Authorization multi-agent workflow (Subskill 1).

    Produces skill-compatible waypoint files with bead tracking.
    Supports resume from the first incomplete bead if waypoints exist.

    Args:
        request_data: PA request (member, service, provider, clinical docs).
        config: Optional AgentConfig override; loads from env if None.
        output_dir: Directory for run files. Defaults to .runs/<timestamp>_<id>/.
        local: If True, use localhost MCP endpoints.

    Returns:
        Skill-compatible assessment dict (also written to waypoints/assessment.json).
    """
    if config is None:
        config = AgentConfig.load(local=local)

    # ── Resolve run directory ──────────────────────────────────────
    # If output_dir is explicit, use it (backwards compat). Otherwise
    # create a new timestamped run dir under .runs/.
    if output_dir:
        run_dir = Path(output_dir)
        waypoint_dir = run_dir / "waypoints" if (run_dir / "waypoints").exists() else run_dir
        output_path = run_dir / "outputs" if (run_dir / "outputs").exists() else run_dir
        waypoint_dir.mkdir(parents=True, exist_ok=True)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        # Will be created after we have a request_id — see below
        run_dir = None
        waypoint_dir = None
        output_path = None

    # ── Resume detection (SKILL.md § Resume via Beads) ─────────────
    beads = _make_beads()
    workflow_id = str(uuid.uuid4())
    request_id = f"PA-{datetime.now(timezone.utc).strftime('%Y%m%d')}-" f"{uuid.uuid4().hex[:5].upper()}"

    # Try to resume from existing waypoint if run_dir was provided
    existing = None
    if waypoint_dir:
        assessment_path = waypoint_dir / "assessment.json"
        existing = _read_waypoint(assessment_path)

    if existing and "beads" in existing:
        beads = existing["beads"]
        workflow_id = existing.get("workflow_id", workflow_id)
        request_id = existing.get("request_id", request_id)
        resume_bead = _first_incomplete_bead(beads)
        if resume_bead:
            logger.info("Resuming from bead %s (prior session found)", resume_bead)
        else:
            logger.info("All beads completed — returning existing assessment")
            return existing

    # ── Create run directory if not yet resolved ───────────────────
    if run_dir is None:
        run_dir = _create_run_dir(request_id)
        waypoint_dir = run_dir / "waypoints"
        output_path = run_dir / "outputs"

    assessment_path = waypoint_dir / "assessment.json"

    # ── Build LLM client ───────────────────────────────────────────
    credential = DefaultAzureCredential() if not local else AzureCliCredential()
    client = AzureOpenAIResponsesClient(
        credential=credential,
        endpoint=config.openai.endpoint,
        deployment_name=config.openai.deployment_name,
        api_version=config.openai.api_version,
    )

    # ── Build MCP tools ────────────────────────────────────────────
    toolkit = MCPToolKit.from_endpoints(
        config.endpoints,
        subscription_key=config.apim_subscription_key,
    )

    request_json = json.dumps(request_data, indent=2)

    # ── Normalize request into skill contract schema ───────────────
    member = _safe_get(request_data, "member", default={})
    provider = _safe_get(request_data, "provider", default={})
    service = _safe_get(request_data, "service", default={})

    cpt_codes = service.get("cpt_codes", [])
    if not cpt_codes and service.get("cpt_code"):
        cpt_codes = [service["cpt_code"]]

    icd10_codes = service.get("icd10_codes", [])
    if not icd10_codes:
        diag = _safe_get(request_data, "diagnosis", default={})
        icd10_codes = diag.get("icd10_codes", [])

    request_block = {
        "member": {
            "name": member.get("name", ""),
            "id": member.get("id", ""),
            "dob": member.get("dob", ""),
            "state": member.get("state", member.get("plan", "")),
        },
        "service": {
            "type": service.get("type", ""),
            "description": service.get("description", ""),
            "cpt_codes": cpt_codes,
            "icd10_codes": icd10_codes,
            "place_of_service": service.get("place_of_service", ""),
        },
        "provider": {
            "npi": provider.get("npi", ""),
            "name": provider.get("name", ""),
            "specialty": provider.get("specialty", ""),
            "verified": False,
        },
    }

    # ── Initialize assessment skeleton (skill contract) ────────────
    assessment: dict[str, Any] = (
        existing
        if existing and "beads" in existing
        else {
            "request_id": request_id,
            "workflow_id": workflow_id,
            "created": datetime.now(timezone.utc).isoformat(),
            "status": "in_progress",
            "version": "2.0",
            "beads": beads,
            "request": request_block,
            "fhir_patient_context": {
                "patient_found": False,
                "fhir_patient_id": None,
                "active_conditions": [],
                "active_medications": [],
                "recent_observations": [],
                "cross_reference_notes": "",
            },
            "clinical": {
                "chief_complaint": "",
                "key_findings": [],
                "prior_treatments": [],
                "extraction_confidence": 0,
            },
            "policy": {
                "policy_id": "",
                "policy_title": "",
                "policy_type": "",
                "contractor": "",
                "covered_indications": [],
                "medical_necessity_check": {
                    "cpt_code": cpt_codes[0] if cpt_codes else "",
                    "icd10_codes": icd10_codes,
                    "is_covered": None,
                    "policy_basis": "",
                },
                "rag_context": "",
            },
            "literature_support": {
                "searched": False,
                "query_used": "",
                "articles_found": 0,
                "key_citations": [],
                "evidence_summary": "",
            },
            "criteria_evaluation": [],
            "recommendation": {
                "decision": "",
                "confidence": "",
                "confidence_score": 0,
                "rationale": "",
                "criteria_met": "",
                "criteria_percentage": 0,
                "prerequisite_checks": {
                    "provider_verified": False,
                    "codes_valid": False,
                    "policy_found": False,
                    "criteria_threshold_met": False,
                    "confidence_threshold_met": False,
                },
                "gaps": [],
            },
        }
    )

    logger.info("=== Prior Authorization Workflow Started (id=%s) ===", workflow_id)

    async with toolkit:
        # ==============================================================
        # BEAD 001: Intake — Compliance gate + RAG policy retrieval
        # ==============================================================
        if _bead_needs_work(beads, "bd-pa-001-intake"):
            _update_bead(beads, "bd-pa-001-intake", "in-progress")
            _write_waypoint(assessment_path, assessment)
            logger.info("Bead 001: Intake — compliance gate + policy retrieval")

            # --- RAG policy retrieval (folded into intake per skill) ---
            rag_context = await _rag_policy_retrieval(toolkit, request_data)
            assessment["policy"]["rag_context"] = rag_context[:2000] if rag_context else ""

            await _record_audit_event(
                toolkit,
                workflow_id,
                "bead-001-intake",
                "rag_retrieval",
                "success" if rag_context else "skipped",
                output_summary=f"Retrieved {len(rag_context)} chars of policy context",
            )

            # --- Compliance Agent (NPI + ICD-10 validation) ---
            logger.info("Bead 001: Running Compliance Agent...")
            compliance_agent = create_compliance_agent(
                client=client,
                tools=toolkit.compliance_tools(),
            )

            compliance_prompt = (
                "Validate the following prior authorization request for compliance.\n"
                "Check provider NPI, validate all ICD-10 codes, and identify any "
                "missing fields.\n"
                "If provider NPI is 1234567890, this is demo mode — mark as verified.\n\n"
                f"PA Request:\n```json\n{request_json}\n```"
            )

            async with compliance_agent:
                compliance_result = await compliance_agent.run(compliance_prompt)

            compliance_text = str(compliance_result)
            compliance_parsed = _extract_json_from_text(compliance_text)

            # --- Populate assessment from compliance output ---
            if compliance_parsed:
                pv = _safe_get(compliance_parsed, "provider_verification", default={})
                assessment["request"]["provider"]["verified"] = pv.get("verified", False)
                assessment["request"]["provider"]["name"] = pv.get("name", provider.get("name", ""))
                assessment["request"]["provider"]["specialty"] = pv.get("specialty", provider.get("specialty", ""))

                cv = _safe_get(compliance_parsed, "code_validation", default={})
                checks = assessment["recommendation"]["prerequisite_checks"]
                checks["codes_valid"] = cv.get("all_codes_valid", False)
                checks["provider_verified"] = pv.get("verified", False)

            can_proceed = _check_compliance_gate(compliance_text)
            logger.info("Bead 001: Compliance result — can_proceed=%s", can_proceed)

            await _record_audit_event(
                toolkit,
                workflow_id,
                "bead-001-intake",
                "compliance_check",
                "success" if can_proceed else "failure",
                agent_name="ComplianceAgent",
                input_summary=f"PA request with {len(icd10_codes)} ICD-10 codes",
                output_summary=f"can_proceed={can_proceed}",
            )

            if not can_proceed:
                logger.info("Compliance gate FAILED — generating PEND assessment")
                assessment["recommendation"]["decision"] = "PEND"
                assessment["recommendation"]["rationale"] = (
                    "Compliance gate failed. Review compliance results and resubmit."
                )
                assessment["recommendation"]["gaps"] = [
                    {
                        "what": "Compliance check failed",
                        "critical": True,
                        "request": "Review and resubmit",
                    }
                ]
                assessment["status"] = "gated_at_compliance"
                _update_bead(beads, "bd-pa-001-intake", "completed")
                _write_waypoint(assessment_path, assessment)
                return assessment

            # --- Context Checkpoint 1: persist intake results ---
            _update_bead(beads, "bd-pa-001-intake", "completed")
            assessment["_raw_compliance"] = compliance_text[:3000]
            _write_waypoint(assessment_path, assessment)
            logger.info("Bead 001: COMPLETED — context checkpoint 1 written")

        # ==============================================================
        # BEAD 002: Clinical — Concurrent clinical review + coverage
        # ==============================================================
        if _bead_needs_work(beads, "bd-pa-002-clinical"):
            _update_bead(beads, "bd-pa-002-clinical", "in-progress")
            _write_waypoint(assessment_path, assessment)
            logger.info("Bead 002: Clinical review + coverage (concurrent)")

            compliance_text = assessment.get("_raw_compliance", "")

            clinical_agent = create_clinical_reviewer_agent(
                client=client,
                tools=toolkit.clinical_reviewer_tools(),
            )
            coverage_agent = create_coverage_agent(
                client=client,
                tools=toolkit.coverage_tools(),
            )

            rag_section = ""
            rag_ctx = assessment.get("policy", {}).get("rag_context", "")
            if rag_ctx:
                rag_section = "\n\n## Indexed Payer Policy Context (from RAG)\n" + rag_ctx

            combined_prompt = (
                "You are part of a prior authorization review team. Below is the "
                "PA request and compliance results. Perform YOUR specific role as "
                "described in your instructions.\n\n"
                f"PA Request:\n```json\n{request_json}\n```\n\n"
                f"Compliance Results:\n{compliance_text}"
                f"{rag_section}"
            )

            concurrent_workflow = ConcurrentBuilder(
                participants=[clinical_agent, coverage_agent],
            ).build()

            async with clinical_agent, coverage_agent:
                concurrent_results = await concurrent_workflow.run(combined_prompt)

            concurrent_text = str(concurrent_results)
            logger.info("Bead 002: Concurrent phase produced %d chars", len(concurrent_text))

            # --- Parse both agents' outputs from the concatenated result ---
            # ConcurrentBuilder returns one string containing both agents'
            # JSON in nondeterministic order; identify each by a schema-unique
            # key rather than by offset.
            clinical_parsed, coverage_parsed = split_concurrent_outputs(
                concurrent_text,
                first_marker="clinical_summary",
                second_marker="applicable_policies",
            )
            if clinical_parsed is None:
                logger.warning("Bead 002: no parseable ClinicalReviewer output")
            if coverage_parsed is None:
                logger.warning("Bead 002: no parseable CoverageAgent output")
            if clinical_parsed:
                cs = _safe_get(clinical_parsed, "clinical_summary", default={})
                assessment["clinical"]["chief_complaint"] = cs.get(
                    "primary_diagnosis",
                    _safe_get(request_data, "clinical_summary", default=""),
                )
                assessment["clinical"]["key_findings"] = cs.get("clinical_indicators", [])
                assessment["clinical"]["prior_treatments"] = (
                    [cs["treatment_history"]] if cs.get("treatment_history") else []
                )
                assessment["clinical"]["extraction_confidence"] = clinical_parsed.get("clinical_confidence", 70)

                # Evidence mapping → criteria_evaluation
                em = clinical_parsed.get("evidence_mapping", [])
                assessment["criteria_evaluation"] = [
                    {
                        "criterion": item.get("criterion", ""),
                        "status": item.get("status", "INSUFFICIENT"),
                        "evidence": item.get("evidence", ""),
                        "notes": "",
                        "confidence": item.get("confidence", 50),
                    }
                    for item in em
                ]

                # Literature support
                lit = clinical_parsed.get("literature_support", [])
                if lit:
                    assessment["literature_support"]["searched"] = True
                    assessment["literature_support"]["articles_found"] = len(lit)
                    assessment["literature_support"]["key_citations"] = lit[:5]

                # FHIR patient context
                fhir_ctx = clinical_parsed.get("patient_data", {})
                if fhir_ctx:
                    assessment["fhir_patient_context"]["patient_found"] = True
                    assessment["fhir_patient_context"]["active_conditions"] = fhir_ctx.get("conditions", [])

            if coverage_parsed and "applicable_policies" in coverage_parsed:
                policies = coverage_parsed.get("applicable_policies", [])
                if policies:
                    p = policies[0]
                    assessment["policy"]["policy_id"] = p.get("policy_id", "")
                    assessment["policy"]["policy_title"] = p.get("title", "")
                    assessment["policy"]["policy_type"] = p.get("type", "LCD")
                    assessment["policy"]["covered_indications"] = p.get("coverage_criteria", [])
                    checks = assessment["recommendation"]["prerequisite_checks"]
                    checks["policy_found"] = True

                mn = _safe_get(coverage_parsed, "medical_necessity", default={})
                if mn:
                    mnc = assessment["policy"]["medical_necessity_check"]
                    mnc["is_covered"] = mn.get("is_medically_necessary")
                    mnc["policy_basis"] = mn.get("rationale", "")

            await _record_audit_event(
                toolkit,
                workflow_id,
                "bead-002-clinical",
                "concurrent_review",
                "success",
                agent_name="ClinicalReviewer+CoverageAgent",
                output_summary=(
                    f"Produced {len(concurrent_text)} chars; "
                    f"criteria_count={len(assessment['criteria_evaluation'])}"
                ),
            )

            # --- Context Checkpoint 2 ---
            _update_bead(beads, "bd-pa-002-clinical", "completed")
            assessment["_raw_concurrent"] = concurrent_text[:5000]
            _write_waypoint(assessment_path, assessment)
            logger.info("Bead 002: COMPLETED — context checkpoint 2 written")

        # ==============================================================
        # BEAD 003: Recommend — Synthesis agent → recommendation
        # ==============================================================
        if _bead_needs_work(beads, "bd-pa-003-recommend"):
            _update_bead(beads, "bd-pa-003-recommend", "in-progress")
            _write_waypoint(assessment_path, assessment)
            logger.info("Bead 003: Synthesis — generating recommendation")

            compliance_text = assessment.get("_raw_compliance", "")
            concurrent_text = assessment.get("_raw_concurrent", "")

            synthesis_agent = create_synthesis_agent(client=client)

            synthesis_prompt = (
                "Aggregate the following agent outputs into a final prior "
                "authorization assessment.\n"
                "Apply the decision rubric strictly.\n\n"
                f"## Original PA Request\n```json\n{request_json}\n```\n\n"
                f"## Compliance Agent Output\n{compliance_text}\n\n"
                f"## Clinical Review + Coverage Agent Outputs\n{concurrent_text}\n\n"
                "Produce your final structured assessment JSON with:\n"
                '  "recommendation": "APPROVE", "PEND", or "DENY"\n'
                '  "confidence_score": 0-100\n'
                '  "confidence_breakdown": {provider, codes, policy, clinical, '
                "doc_quality}\n"
                '  "criteria_summary": [{criterion, status, evidence}]\n'
                '  "approval_rationale": "if APPROVE: why criteria are met"\n'
                '  "pend_reasons": [...] "if PEND: specific information gaps"\n'
                '  "denial_rationale": "if DENY: mandatory criterion violated and clinical basis"\n'
                '  "required_actions": [...] "if PEND: what must be provided; omit for DENY"\n'
                '  "summary": "2-3 sentence executive summary"'
            )

            synthesis_result = await synthesis_agent.run(synthesis_prompt)
            synthesis_text = str(synthesis_result)
            synthesis_parsed = _extract_json_from_text(synthesis_text)

            # --- Populate recommendation block ---
            if synthesis_parsed:
                rec = synthesis_parsed.get("recommendation", "PEND")
                if isinstance(rec, dict):
                    rec = rec.get("decision", "PEND")

                confidence_score = synthesis_parsed.get("confidence_score", 0)
                if confidence_score >= 80:
                    confidence_level = "HIGH"
                elif confidence_score >= 60:
                    confidence_level = "MEDIUM"
                else:
                    confidence_level = "LOW"

                criteria_summary = synthesis_parsed.get("criteria_summary", [])
                met_count = sum(1 for c in criteria_summary if c.get("status", "").upper() == "MET")
                total = max(
                    len(criteria_summary),
                    len(assessment["criteria_evaluation"]),
                    1,
                )

                assessment["recommendation"] = {
                    "decision": rec.upper() if isinstance(rec, str) else "PEND",
                    "confidence": confidence_level,
                    "confidence_score": confidence_score,
                    "rationale": synthesis_parsed.get(
                        "summary",
                        synthesis_parsed.get(
                            "approval_rationale",
                            synthesis_parsed.get("denial_rationale", synthesis_text[:500]),
                        ),
                    ),
                    "criteria_met": f"{met_count}/{total}",
                    "criteria_percentage": round(met_count / total * 100),
                    "prerequisite_checks": assessment["recommendation"]["prerequisite_checks"],
                    "gaps": [
                        {"what": r, "critical": True, "request": r}
                        for r in synthesis_parsed.get(
                            "pend_reasons",
                            synthesis_parsed.get("required_actions", []),
                        )
                    ],
                }

                if criteria_summary and len(criteria_summary) >= len(assessment["criteria_evaluation"]):
                    assessment["criteria_evaluation"] = [
                        {
                            "criterion": c.get("criterion", ""),
                            "status": c.get("status", "INSUFFICIENT"),
                            "evidence": c.get("evidence", ""),
                            "notes": "",
                            "confidence": c.get("confidence", 50),
                        }
                        for c in criteria_summary
                    ]

                cb = synthesis_parsed.get("confidence_breakdown", {})
                if cb:
                    checks = assessment["recommendation"]["prerequisite_checks"]
                    checks["provider_verified"] = cb.get("provider", 0) >= 60
                    checks["codes_valid"] = cb.get("codes", 0) >= 60
                    checks["policy_found"] = cb.get("policy", 0) >= 60
                    checks["criteria_threshold_met"] = assessment["recommendation"]["criteria_percentage"] >= 80
                    checks["confidence_threshold_met"] = confidence_score >= 60
            else:
                rec = extract_recommendation_from_text(synthesis_text)
                assessment["recommendation"]["decision"] = rec
                assessment["recommendation"]["rationale"] = synthesis_text[:500]

            logger.info(
                "Bead 003: Recommendation=%s, Confidence=%s",
                assessment["recommendation"]["decision"],
                assessment["recommendation"]["confidence_score"],
            )

            await _record_audit_event(
                toolkit,
                workflow_id,
                "bead-003-recommend",
                "recommendation_rendered",
                "success",
                agent_name="SynthesisAgent",
                output_summary=(
                    f"decision={assessment['recommendation']['decision']}, "
                    f"confidence={assessment['recommendation']['confidence_score']}"
                ),
            )

            # --- Generate audit justification document ---
            audit_doc = _generate_audit_justification(assessment)
            _write_output_file(output_path / "audit_justification.md", audit_doc)

            # --- Context Checkpoint 3: finalize assessment ---
            assessment["status"] = "assessment_complete"
            assessment.pop("_raw_compliance", None)
            assessment.pop("_raw_concurrent", None)

            _update_bead(beads, "bd-pa-003-recommend", "completed")
            _write_waypoint(assessment_path, assessment)
            logger.info("Bead 003: COMPLETED — assessment_complete")

    logger.info("=== Subskill 1 Complete — Assessment ready for human review ===")
    logger.info("Run directory: %s", run_dir)
    return assessment


# ---------------------------------------------------------------------------
# Subskill 2: Decision & Notification (beads 004-005)
# ---------------------------------------------------------------------------


async def run_prior_auth_decision(
    decision_input: dict[str, Any],
    *,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """
    Execute Subskill 2 — Decision & Notification.

    Reads the assessment waypoint, applies the human decision, generates
    authorization (if approved), and creates notification letters +
    determination JSON.

    Args:
        decision_input: Human decision capture::

            {
                "outcome": "APPROVED" | "DENIED" | "PENDING",
                "override_applied": bool,
                "justification": str,  # required if override or deny
                "overriding_authority": str,
                "limitations": [str],
            }

        output_dir: Directory for run files. Defaults to latest .runs/ dir.

    Returns:
        Decision dict (also written to waypoints/decision.json).
    """
    run_dir = _resolve_run_dir(output_dir)
    waypoint_dir = run_dir / "waypoints" if (run_dir / "waypoints").exists() else run_dir
    output_path = run_dir / "outputs" if (run_dir / "outputs").exists() else run_dir

    assessment_path = waypoint_dir / "assessment.json"
    decision_path = waypoint_dir / "decision.json"

    # --- Load assessment ---
    assessment = _read_waypoint(assessment_path)
    if not assessment or assessment.get("status") != "assessment_complete":
        raise ValueError("Assessment not found or incomplete. Complete Subskill 1 first.")

    beads = assessment.get("beads", _make_beads())
    request_id = assessment.get("request_id", "")

    outcome = decision_input.get("outcome", "PENDING").upper()
    override_applied = decision_input.get("override_applied", False)
    original_rec = assessment.get("recommendation", {}).get("decision", "PEND")

    # ==================================================================
    # BEAD 004: Decision capture
    # ==================================================================
    _update_bead(beads, "bd-pa-004-decision", "in-progress")

    auth_number = None
    valid_from = None
    valid_through = None

    if outcome == "APPROVED":
        auth_number = f"PA-{datetime.now(timezone.utc).strftime('%Y%m%d')}-" f"{uuid.uuid4().hex[:5].upper()}"
        valid_from = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        valid_through = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")

    decision: dict[str, Any] = {
        "request_id": request_id,
        "decision_date": datetime.now(timezone.utc).isoformat(),
        "beads": beads,
        "decision": {
            "outcome": outcome,
            "auth_number": auth_number,
            "valid_from": valid_from,
            "valid_through": valid_through,
            "limitations": decision_input.get("limitations", []),
            "override_applied": override_applied,
        },
        "rationale": {
            "summary": decision_input.get(
                "justification",
                assessment["recommendation"]["rationale"],
            ),
            "supporting_facts": [],
            "policy_basis": assessment.get("policy", {}).get("policy_title", ""),
        },
        "audit": {
            "reviewed_by": decision_input.get("overriding_authority", "AI-Assisted Review"),
            "review_date": datetime.now(timezone.utc).isoformat(),
            "turnaround_hours": None,
            "confidence": assessment.get("recommendation", {}).get("confidence", ""),
            "auto_approved": not override_applied and outcome == "APPROVED",
        },
        "override_details": (
            {
                "original_recommendation": original_rec,
                "final_decision": outcome,
                "override_reason": decision_input.get("justification", ""),
                "overriding_authority": decision_input.get("overriding_authority", ""),
            }
            if override_applied
            else None
        ),
    }

    _update_bead(beads, "bd-pa-004-decision", "completed")
    _write_waypoint(decision_path, decision)
    logger.info("Bead 004: COMPLETED — decision captured: %s", outcome)

    # ==================================================================
    # BEAD 005: Notification letters + determination JSON
    # ==================================================================
    _update_bead(beads, "bd-pa-005-notify", "in-progress")

    # --- Determination JSON (prompt module 05 schema) ---
    determination = _generate_determination_json(assessment, decision)
    _write_output_file(
        output_path / "determination.json",
        json.dumps(determination, indent=2, default=str),
    )

    # --- Notification letter ---
    member = assessment.get("request", {}).get("member", {})
    service_block = assessment.get("request", {}).get("service", {})
    provider_block = assessment.get("request", {}).get("provider", {})
    rec_block = assessment.get("recommendation", {})

    if outcome == "APPROVED":
        letter = _generate_approval_letter(
            member,
            service_block,
            provider_block,
            decision["decision"],
            request_id,
        )
        _write_output_file(output_path / "approval_letter.md", letter)
    elif outcome == "PENDING":
        letter = _generate_pend_letter(
            member,
            service_block,
            rec_block.get("gaps", []),
            request_id,
        )
        _write_output_file(output_path / "pend_letter.md", letter)
    elif outcome == "DENIED":
        letter = _generate_denial_letter(
            member,
            service_block,
            assessment.get("policy", {}),
            decision_input.get("justification", ""),
            request_id,
        )
        _write_output_file(output_path / "denial_letter.md", letter)

    _update_bead(beads, "bd-pa-005-notify", "completed")
    decision["beads"] = beads
    _write_waypoint(decision_path, decision)
    logger.info("Bead 005: COMPLETED — notification artifacts generated")

    return decision


# ---------------------------------------------------------------------------
# Output generators (skill contract templates)
# ---------------------------------------------------------------------------


def _generate_audit_justification(assessment: dict) -> str:
    """Generate outputs/audit_justification.md per prompt module 04."""
    member = assessment.get("request", {}).get("member", {})
    service = assessment.get("request", {}).get("service", {})
    provider = assessment.get("request", {}).get("provider", {})
    policy = assessment.get("policy", {})
    rec = assessment.get("recommendation", {})
    criteria = assessment.get("criteria_evaluation", [])
    clinical = assessment.get("clinical", {})

    criteria_rows = ""
    for c in criteria:
        icon = {"MET": "✅", "NOT_MET": "❌", "INSUFFICIENT": "⚠️"}.get(c.get("status", ""), "❓")
        evidence_text = str(c.get("evidence", "N/A"))[:100]
        criteria_rows += (
            f"| {icon} {c.get('status', 'N/A')} "
            f"| {c.get('criterion', 'N/A')} "
            f"| {evidence_text} "
            f"| {c.get('confidence', 'N/A')}% |\n"
        )

    gaps_section = ""
    if rec.get("gaps"):
        gaps_section = "### Gaps Identified\n\n"
        for g in rec["gaps"]:
            gaps_section += (
                f"- **{g.get('what', 'N/A')}** — "
                f"{g.get('request', 'N/A')} "
                f"(Critical: {g.get('critical', False)})\n"
            )

    return (
        "⚠️ AI-ASSISTED DRAFT - REVIEW REQUIRED\n"
        "Coverage policies reflect Medicare LCDs/NCDs only. If this review is for a\n"
        "commercial or Medicare Advantage plan, payer-specific policies were not applied.\n"
        "All decisions require human clinical review before finalization.\n"
        "\n---\n\n"
        "# Prior Authorization Audit Justification\n\n"
        "## 1. Executive Summary\n\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        f"| Request ID | {assessment.get('request_id', 'N/A')} |\n"
        f"| Review Date | {assessment.get('created', 'N/A')} |\n"
        f"| Member | {member.get('name', 'N/A')} ({member.get('id', 'N/A')}) |\n"
        f"| DOB | {member.get('dob', 'N/A')} |\n"
        f"| Service | {service.get('description', 'N/A')} |\n"
        f"| CPT Code(s) | {', '.join(service.get('cpt_codes', []))} |\n"
        f"| Provider | {provider.get('name', 'N/A')} (NPI: {provider.get('npi', 'N/A')}) |\n"
        f"| Specialty | {provider.get('specialty', 'N/A')} |\n"
        f"| Provider Verified | {'✅ Yes' if provider.get('verified') else '❌ No'} |\n"
        f"| **Recommendation** | **{rec.get('decision', 'N/A')}** |\n"
        f"| Confidence | {rec.get('confidence_score', 'N/A')}% ({rec.get('confidence', 'N/A')}) |\n"
        "\n"
        "## 2. Clinical Synopsis\n\n"
        f"- **Chief Complaint:** {clinical.get('chief_complaint', 'N/A')}\n"
        f"- **Key Findings:** {', '.join(str(f) for f in clinical.get('key_findings', [])) or 'N/A'}\n"
        f"- **Prior Treatments:** {', '.join(clinical.get('prior_treatments', [])) or 'N/A'}\n"
        f"- **ICD-10 Codes:** {', '.join(service.get('icd10_codes', []))}\n"
        f"- **Extraction Confidence:** {clinical.get('extraction_confidence', 'N/A')}%\n"
        "\n"
        "## 3. Policy Analysis\n\n"
        f"- **Applicable Policy:** {policy.get('policy_id', 'N/A')} — {policy.get('policy_title', 'N/A')}\n"
        f"- **Policy Type:** {policy.get('policy_type', 'N/A')}\n"
        f"- **Contractor:** {policy.get('contractor', 'N/A')}\n"
        f"- **Medical Necessity:** "
        f"{'Covered' if policy.get('medical_necessity_check', {}).get('is_covered') else 'Not Covered / Unknown'}\n"
        f"- **Policy Basis:** {policy.get('medical_necessity_check', {}).get('policy_basis', 'N/A')}\n"
        "\n"
        "### Criteria Evaluation\n\n"
        "| Status | Criterion | Evidence | Confidence |\n"
        "|--------|-----------|----------|------------|\n"
        f"{criteria_rows or '| N/A | No criteria evaluated | N/A | N/A |'}\n"
        f"\n**Criteria Met:** {rec.get('criteria_met', 'N/A')} "
        f"({rec.get('criteria_percentage', 0)}%)\n"
        "\n"
        "## 4. Recommendation Details\n\n"
        f"- **Decision:** {rec.get('decision', 'N/A')}\n"
        f"- **Rationale:** {rec.get('rationale', 'N/A')}\n"
        f"\n{gaps_section}"
    )


def _generate_determination_json(
    assessment: dict,
    decision: dict,
) -> dict:
    """Generate outputs/determination.json per prompt module 05 schema."""
    outcome = decision.get("decision", {}).get("outcome", "PENDING")
    determination_map = {
        "APPROVED": "Approved",
        "DENIED": "Rejected",
        "PENDING": "Needs More Information",
    }
    status_map = {
        "MET": "Fully Met",
        "NOT_MET": "Not Met",
        "INSUFFICIENT": "Partially Met",
    }

    criteria_assessment = []
    for c in assessment.get("criteria_evaluation", []):
        criteria_assessment.append(
            {
                "CriterionName": c.get("criterion", ""),
                "Assessment": status_map.get(c.get("status", ""), "Partially Met"),
                "Evidence": c.get("evidence", ""),
                "PolicyReference": assessment.get("policy", {}).get("policy_id", ""),
                "Notes": c.get("notes", ""),
            }
        )

    missing_info = []
    if outcome in ("PENDING", "DENIED"):
        for g in assessment.get("recommendation", {}).get("gaps", []):
            missing_info.append(
                {
                    "InformationNeeded": g.get("what", ""),
                    "Reason": g.get("request", ""),
                }
            )

    return {
        "Determination": determination_map.get(outcome, "Needs More Information"),
        "Rationale": decision.get("rationale", {}).get("summary", ""),
        "DetailedAnalysis": {
            "PolicyCriteriaAssessment": criteria_assessment,
            "MissingInformation": missing_info,
        },
    }


def _generate_approval_letter(
    member: dict,
    service: dict,
    provider: dict,
    decision_block: dict,
    request_id: str,
) -> str:
    """Generate outputs/approval_letter.md."""
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    limitations = decision_block.get("limitations", [])
    limitations_text = "\n".join(f"- {lim}" for lim in limitations) if limitations else "- None"
    return (
        "# Prior Authorization Approval\n\n"
        f"**Date:** {today}\n"
        f"**Authorization Number:** {decision_block.get('auth_number', 'N/A')}\n\n"
        "---\n\n"
        "**Member Information:**\n"
        f"- Name: {member.get('name', 'N/A')}\n"
        f"- Member ID: {member.get('id', 'N/A')}\n"
        f"- Date of Birth: {member.get('dob', 'N/A')}\n\n"
        "**Approved Service:**\n"
        f"- Description: {service.get('description', 'N/A')}\n"
        f"- CPT Code(s): {', '.join(service.get('cpt_codes', []))}\n"
        f"- Provider: {provider.get('name', 'N/A')} "
        f"(NPI: {provider.get('npi', 'N/A')})\n\n"
        "**Authorization Period:**\n"
        f"- Valid From: {decision_block.get('valid_from', 'N/A')}\n"
        f"- Valid Through: {decision_block.get('valid_through', 'N/A')}\n\n"
        f"**Limitations/Conditions:**\n{limitations_text}\n\n"
        "---\n\n"
        "This authorization confirms that the requested service meets medical\n"
        "necessity criteria based on the clinical information provided.\n\n"
        "If you have questions, please contact the utilization management "
        "department.\n"
    )


def _generate_pend_letter(
    member: dict,
    service: dict,
    gaps: list,
    request_id: str,
) -> str:
    """Generate outputs/pend_letter.md."""
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    gaps_text = ""
    for i, g in enumerate(gaps, 1):
        gaps_text += (
            f"\n{i}. **{g.get('what', 'Additional information needed')}**\n"
            f"   - What's needed: "
            f"{g.get('request', 'Please provide additional documentation')}\n"
            f"   - Why it's needed: Required per applicable coverage policy "
            f"criteria\n"
        )
    return (
        "# Prior Authorization - Additional Information Required\n\n"
        f"**Date:** {today}\n"
        f"**Reference Number:** {request_id}\n\n"
        "---\n\n"
        "**Member Information:**\n"
        f"- Name: {member.get('name', 'N/A')}\n"
        f"- Member ID: {member.get('id', 'N/A')}\n\n"
        "**Requested Service:**\n"
        f"- Description: {service.get('description', 'N/A')}\n"
        f"- CPT Code(s): {', '.join(service.get('cpt_codes', []))}\n\n"
        "---\n\n"
        "## Information Needed\n\n"
        "To complete our review of this prior authorization request, we need\n"
        "the following additional information:\n"
        f"{gaps_text or '1. Additional clinical documentation supporting medical necessity'}\n\n"
        "## How to Submit\n\n"
        "Please submit the requested information within 14 calendar days to\n"
        "the utilization management department.\n\n"
        "## Questions?\n\n"
        "If you have questions about this request, please contact the\n"
        "utilization management department.\n"
    )


def _generate_denial_letter(
    member: dict,
    service: dict,
    policy: dict,
    justification: str,
    request_id: str,
) -> str:
    """Generate outputs/denial_letter.md."""
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    return (
        "# Prior Authorization Denial\n\n"
        f"**Date:** {today}\n"
        f"**Reference Number:** {request_id}\n\n"
        "---\n\n"
        "**Member Information:**\n"
        f"- Name: {member.get('name', 'N/A')}\n"
        f"- Member ID: {member.get('id', 'N/A')}\n\n"
        "**Denied Service:**\n"
        f"- Description: {service.get('description', 'N/A')}\n"
        f"- CPT Code(s): {', '.join(service.get('cpt_codes', []))}\n\n"
        "---\n\n"
        "## Denial Reason\n\n"
        f"{justification or 'The requested service does not meet the applicable coverage criteria.'}\n\n"
        "## Policy Basis\n\n"
        "This decision is based on:\n"
        f"- Policy: {policy.get('policy_id', 'N/A')} — "
        f"{policy.get('policy_title', 'N/A')}\n"
        "- Criteria not met: See detailed analysis in determination.json\n\n"
        "## Appeal Rights\n\n"
        "You have the right to appeal this decision. To appeal:\n"
        "1. Submit a written request within 60 days of this notice\n"
        "2. Include any additional clinical documentation supporting medical "
        "necessity\n"
        "3. Send to the utilization management department\n\n"
        "## Questions?\n\n"
        "If you have questions about this decision, please contact the\n"
        "utilization management department.\n"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_compliance_gate(compliance_text: str) -> bool:
    """Parse compliance output to determine if we can proceed."""
    lower = compliance_text.lower()
    if '"can_proceed_to_clinical_review": true' in lower:
        return True
    if '"compliance_status": "pass"' in lower:
        return True
    if '"can_proceed_to_clinical_review": false' in lower:
        return False
    if '"compliance_status": "fail"' in lower:
        return False
    logger.warning("Could not parse compliance gate — defaulting to proceed")
    return True
