"""
Patient Data Retrieval & Summary Workflow — Single Agent

Simple single-agent workflow that uses FHIR + NPI MCP tools to
retrieve comprehensive patient information and produce a summary.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..agents import create_patient_summary_agent
from ..config import AgentConfig
from ..llm_client import create_chat_client
from ..tools import MCPToolKit

logger = logging.getLogger(__name__)


async def run_patient_data_workflow(
    query: dict[str, Any],
    config: AgentConfig | None = None,
    *,
    output_dir: str | None = None,
    local: bool = False,
) -> dict[str, Any]:
    """
    Retrieve and summarize patient data from FHIR.

    Args:
        query: Dict with patient identifiers, e.g.:
               {"patient_id": "123"} or {"name": "Smith", "birthdate": "1960-01-01"}
        config: Optional AgentConfig override.
        output_dir: Directory for output files.
        local: Use localhost MCP endpoints.

    Returns:
        Structured patient summary dict.
    """
    if config is None:
        config = AgentConfig.load(local=local)

    output_path = Path(output_dir or "outputs")
    output_path.mkdir(parents=True, exist_ok=True)

    client = create_chat_client(config, local=local)

    toolkit = MCPToolKit.from_endpoints(config.endpoints, subscription_key=config.apim_subscription_key)
    query_json = json.dumps(query, indent=2)

    logger.info("=== Patient Data Workflow Started ===")

    async with toolkit:
        patient_agent = create_patient_summary_agent(
            client=client,
            tools=toolkit.patient_tools(),
        )

        prompt = (
            f"Retrieve comprehensive patient data and produce a summary.\n\n"
            f"Patient Query:\n```json\n{query_json}\n```\n\n"
            f"Use the FHIR tools to search for the patient, then retrieve their "
            f"conditions, medications, observations, and recent encounters. "
            f"If provider NPIs are available, look up their details."
        )

        async with patient_agent:
            result = await patient_agent.run(prompt)

        result_text = str(result)
        logger.info("Patient data retrieved")

        output = {
            "workflow": "patient_data",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "patient_summary": result_text,
        }

        output_file = output_path / "patient_summary.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2, default=str)
        logger.info("Output written: %s", output_file)

        logger.info("=== Patient Data Workflow Complete ===")
        return output
