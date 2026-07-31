"""
Clinical Trial Protocol Workflow — Sequential (Research → Draft)

Orchestration pattern:
  Step 1: Trials Research Agent searches ClinicalTrials.gov + PubMed for
          similar trials, protocol patterns, and published results.
  Step 2: Protocol Draft Agent uses research output to generate an
          FDA/NIH-compliant trial protocol following the 6-step waypoint
          structure from the clinical-trial-protocol skill.

Uses Microsoft Agent Framework's SequentialBuilder so research output
flows directly into the drafting agent's context.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_framework import Agent

from ..agents import PROTOCOL_DRAFT_AGENT_INSTRUCTIONS, create_trials_research_agent
from ..config import AgentConfig
from ..llm_client import create_chat_client
from ..tools import MCPToolKit

logger = logging.getLogger(__name__)


# Protocol Draft Agent reuses instructions from agents.py
PROTOCOL_DRAFT_INSTRUCTIONS = PROTOCOL_DRAFT_AGENT_INSTRUCTIONS


async def run_clinical_trials_workflow(
    intervention: dict[str, Any],
    config: AgentConfig | None = None,
    *,
    output_dir: str | None = None,
    local: bool = False,
    research_only: bool = False,
) -> dict[str, Any]:
    """
    Execute the clinical trial protocol generation workflow.

    Args:
        intervention: Dict with keys like 'condition', 'intervention_type',
                      'intervention_name', 'phase', etc.
        config: Optional AgentConfig override.
        output_dir: Directory for waypoint files.
        local: Use localhost MCP endpoints.
        research_only: If True, stop after research phase (Steps 0-1 equivalent).

    Returns:
        Structured protocol or research output dict.
    """
    if config is None:
        config = AgentConfig.load(local=local)

    output_path = Path(output_dir or "waypoints")
    output_path.mkdir(parents=True, exist_ok=True)

    client = create_chat_client(config, local=local)

    toolkit = MCPToolKit.from_endpoints(config.endpoints, subscription_key=config.apim_subscription_key)
    intervention_json = json.dumps(intervention, indent=2)

    logger.info("=== Clinical Trial Protocol Workflow Started ===")

    async with toolkit:
        # ------------------------------------------------------------------
        # Step 1: Research Phase
        # ------------------------------------------------------------------
        logger.info("Step 1: Trials research")

        research_agent = create_trials_research_agent(
            client=client,
            tools=toolkit.trials_research_tools(),
        )

        research_prompt = (
            f"Research existing clinical trials and published literature for the following intervention.\n"
            f"Find similar trials, identify common protocol patterns, and gather published results.\n\n"
            f"Intervention Details:\n```json\n{intervention_json}\n```"
        )

        async with research_agent:
            research_result = await research_agent.run(research_prompt)

        research_text = str(research_result)
        logger.info("Step 1 complete: research gathered")

        # Write research waypoint
        research_waypoint = {
            "workflow": "clinical_trial_protocol",
            "step": "research",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "intervention": intervention,
            "research_output": research_text,
        }
        _write_waypoint(output_path / "01_clinical_research_summary.json", research_waypoint)

        if research_only:
            logger.info("Research-only mode — stopping after Step 1")
            return research_waypoint

        # ------------------------------------------------------------------
        # Step 2: Protocol Draft Phase
        # ------------------------------------------------------------------
        logger.info("Step 2: Protocol draft generation")

        draft_agent = Agent(
            client=client,
            name="ProtocolDraftAgent",
            instructions=PROTOCOL_DRAFT_INSTRUCTIONS,
        )

        draft_prompt = (
            f"Generate a draft clinical trial protocol based on the following research.\n\n"
            f"## Intervention\n```json\n{intervention_json}\n```\n\n"
            f"## Research Findings\n{research_text}\n\n"
            f"Generate all 8 protocol sections with citations to the research findings."
        )

        draft_result = await draft_agent.run(draft_prompt)
        draft_text = str(draft_result)
        logger.info("Step 2 complete: protocol draft generated")

        # Write protocol waypoint
        protocol_waypoint = {
            "workflow": "clinical_trial_protocol",
            "step": "protocol_draft",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "intervention": intervention,
            "research_output": research_text,
            "protocol_draft": draft_text,
            "status": "DRAFT",
        }
        _write_waypoint(output_path / "protocol_draft.json", protocol_waypoint)

        logger.info("=== Clinical Trial Protocol Workflow Complete ===")
        return protocol_waypoint


def _write_waypoint(path: Path, data: dict) -> None:
    """Write a waypoint JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info("Waypoint written: %s", path)
