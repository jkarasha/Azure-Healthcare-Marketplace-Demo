"""
Literature Search & Evidence Review Workflow — Concurrent

Orchestration pattern:
  Fan-out: Literature Agent (PubMed) + Trials Correlation Agent (ClinicalTrials.gov)
           run in parallel on the same clinical query.
  Fan-in:  Custom aggregator merges evidence + trial matches into a unified report.

Uses Microsoft Agent Framework's ConcurrentBuilder.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_framework.azure import AzureOpenAIResponsesClient
from agent_framework_orchestrations import ConcurrentBuilder
from azure.identity import AzureCliCredential, DefaultAzureCredential

from ..agents import (
    create_literature_search_agent,
    create_trials_correlation_agent,
)
from ..config import AgentConfig
from ..tools import CLINICAL_TRIALS_TOOLS_ALL, MCPToolKit, create_clinical_research_tool

logger = logging.getLogger(__name__)


async def run_literature_search_workflow(
    query: dict[str, Any],
    config: AgentConfig | None = None,
    *,
    output_dir: str | None = None,
    local: bool = False,
) -> dict[str, Any]:
    """
    Search medical literature and correlate with active clinical trials.

    Args:
        query: Dict with search parameters, e.g.:
               {"condition": "non-small cell lung cancer",
                "intervention": "pembrolizumab",
                "focus": "therapy"}
        config: Optional AgentConfig override.
        output_dir: Directory for output files.
        local: Use localhost MCP endpoints.

    Returns:
        Structured evidence report dict.
    """
    if config is None:
        config = AgentConfig.load(local=local)

    output_path = Path(output_dir or "outputs")
    output_path.mkdir(parents=True, exist_ok=True)

    credential = DefaultAzureCredential() if not local else AzureCliCredential()
    client = AzureOpenAIResponsesClient(
        credential=credential,
        endpoint=config.openai.endpoint,
        deployment_name=config.openai.deployment_name,
        api_version=config.openai.api_version,
    )

    toolkit = MCPToolKit.from_endpoints(config.endpoints, subscription_key=config.apim_subscription_key)
    query_json = json.dumps(query, indent=2)

    logger.info("=== Literature Search Workflow Started ===")

    async with toolkit:
        literature_agent = create_literature_search_agent(
            client=client,
            tools=toolkit.literature_tools(),
        )

        trials_agent = create_trials_correlation_agent(
            client=client,
            tools=[create_clinical_research_tool(
                config.endpoints.clinical_research,
                name="Clinical Research (Correlation)",
                allowed_tools=CLINICAL_TRIALS_TOOLS_ALL,
            )],
        )

        combined_prompt = (
            f"Search for medical evidence related to the following clinical query. "
            f"Perform YOUR specific role as described in your instructions.\n\n"
            f"Clinical Query:\n```json\n{query_json}\n```"
        )

        # Run both agents concurrently
        concurrent_workflow = ConcurrentBuilder(
            participants=[literature_agent, trials_agent],
        ).build()

        async with literature_agent, trials_agent:
            concurrent_results = await concurrent_workflow.run(combined_prompt)

        results_text = str(concurrent_results)
        logger.info("Concurrent search complete: %d chars", len(results_text))

        # Build evidence report
        output = {
            "workflow": "literature_search",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "evidence_report": results_text,
        }

        output_file = output_path / "evidence_report.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2, default=str)
        logger.info("Output written: %s", output_file)

        logger.info("=== Literature Search Workflow Complete ===")
        return output
