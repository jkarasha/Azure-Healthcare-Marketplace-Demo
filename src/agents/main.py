"""
CLI runner for Healthcare Agent Orchestration.

Usage:
    python -m agents --workflow prior-auth --input pa_request.json
    python -m agents --workflow clinical-trial --input intervention.json
    python -m agents --workflow patient-summary --input query.json
    python -m agents --workflow literature-search --input query.json
    python -m agents --workflow prior-auth --input pa_request.json --local
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .workflows.clinical_trials import run_clinical_trials_workflow
from .workflows.literature_search import run_literature_search_workflow
from .workflows.patient_data import run_patient_data_workflow
from .workflows.prior_auth import run_prior_auth_workflow

REPO_ROOT = Path(__file__).resolve().parents[2]

WORKFLOWS = {
    "prior-auth": run_prior_auth_workflow,
    "clinical-trial": run_clinical_trials_workflow,
    "patient-summary": run_patient_data_workflow,
    "literature-search": run_literature_search_workflow,
}

# Sample data paths (relative to project root)
SAMPLE_DATA = {
    "prior-auth": "data/sample_cases/prior_auth_baseline/pa_request.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agents",
        description="Healthcare Agent Orchestration — Multi-agent workflows powered by Microsoft Agent Framework",
    )
    parser.add_argument(
        "--workflow",
        "-w",
        required=False,
        choices=list(WORKFLOWS.keys()),
        help="Workflow to execute (required unless --devui is used)",
    )
    parser.add_argument(
        "--input",
        "-i",
        help="Path to input JSON file (or use --demo for sample data)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use built-in sample data for the selected workflow",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=None,
        help="Output directory for waypoints/results (default: waypoints/ or outputs/)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use localhost MCP endpoints (for local development)",
    )
    parser.add_argument(
        "--research-only",
        action="store_true",
        help="For clinical-trial workflow: stop after research phase",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )
    parser.add_argument(
        "--devui",
        action="store_true",
        help="Launch the Gradio developer UI instead of running a single workflow",
    )
    parser.add_argument(
        "--framework-devui",
        action="store_true",
        help="Launch the Agent Framework DevUI (React app with debug panel, traces, entity discovery)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for the dev UI server (default: 7860 for Gradio, 8080 for framework DevUI)",
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="Create a public Gradio share link (--devui only)",
    )
    parser.add_argument(
        "--instrumentation",
        action="store_true",
        help="Enable OpenTelemetry tracing (--framework-devui only)",
    )
    return parser.parse_args()


def load_input(args: argparse.Namespace) -> dict:
    """Load input data from file or demo samples."""
    if args.demo:
        sample_paths = SAMPLE_DATA.get(args.workflow, [])
        if isinstance(sample_paths, str):
            sample_paths = [sample_paths]

        for sample_path in sample_paths:
            candidate = Path(sample_path)
            if not candidate.exists():
                candidate = REPO_ROOT / sample_path
            if candidate.exists():
                with open(candidate) as f:
                    return json.load(f)
        # Provide minimal demo data for workflows without sample files
        return _get_demo_data(args.workflow)

    if not args.input:
        print("Error: --input or --demo required", file=sys.stderr)
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path) as f:
        return json.load(f)


def _get_demo_data(workflow: str) -> dict:
    """Return minimal demo data for each workflow."""
    demo_data = {
        "prior-auth": {
            "member": {
                "id": "MEM-12345",
                "name": "Jane Smith",
                "dob": "1965-03-15",
                "plan": "Medicare Advantage PPO",
            },
            "provider": {
                "npi": "1234567890",
                "name": "Dr. Robert Johnson",
                "specialty": "Pulmonology",
            },
            "service": {
                "cpt_code": "71260",
                "description": "CT Chest with contrast",
                "icd10_codes": ["J84.10", "R91.8"],
                "place_of_service": "Outpatient Hospital",
            },
            "clinical_summary": "Patient presents with progressive dyspnea and "
            "interstitial lung disease. CT chest requested to evaluate disease "
            "progression and guide treatment planning.",
        },
        "clinical-trial": {
            "condition": "Non-small cell lung cancer",
            "intervention_type": "Drug",
            "intervention_name": "Pembrolizumab + chemotherapy",
            "phase": "Phase 3",
            "target_population": "Adults with advanced NSCLC, PD-L1 TPS ≥50%",
        },
        "patient-summary": {
            "patient_id": "example",
            "name": "Smith",
        },
        "literature-search": {
            "condition": "Type 2 diabetes mellitus",
            "intervention": "GLP-1 receptor agonists",
            "focus": "therapy",
            "keywords": "cardiovascular outcomes",
        },
    }
    return demo_data.get(workflow, {})


async def main_async(args: argparse.Namespace) -> None:
    """Async entry point."""
    input_data = load_input(args)
    workflow_fn = WORKFLOWS[args.workflow]

    print(f"\n{'=' * 60}")
    print(f"  Healthcare Agent Workflow: {args.workflow}")
    print(f"  Mode: {'local' if args.local else 'APIM passthrough'}")
    print(f"{'=' * 60}\n")

    kwargs = {
        "config": None,
        "output_dir": args.output_dir,
        "local": args.local,
    }

    # Add workflow-specific kwargs
    if args.workflow == "clinical-trial":
        kwargs["research_only"] = args.research_only

    result = await workflow_fn(input_data, **kwargs)

    # Print summary
    print(f"\n{'=' * 60}")
    print("  Workflow Complete")
    print(f"{'=' * 60}")

    if isinstance(result, dict):
        # Print key fields depending on workflow
        if "recommendation" in result:
            rec = result.get("recommendation", "")
            if isinstance(rec, str) and len(rec) > 500:
                print(f"\nRecommendation (first 500 chars):\n{rec[:500]}...")
            else:
                print(f"\nRecommendation:\n{rec}")

        if "status" in result:
            print(f"\nStatus: {result['status']}")

        if args.output_dir:
            print(f"\nOutputs written to: {args.output_dir}/")
        else:
            print("\nOutputs written to: waypoints/ or outputs/")


def main() -> None:
    """Synchronous CLI entry point."""
    args = parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.devui:
        from .devui import launch

        port = args.port or 7860
        launch(local=args.local, share=args.share, port=port)
        return

    if args.framework_devui:
        from .framework_devui import launch as fw_launch

        port = args.port or 8080
        fw_launch(
            local=args.local,
            port=port,
            auto_open=True,
            instrumentation=args.instrumentation,
        )
        return

    if not args.workflow:
        print("Error: --workflow is required (unless using --devui or --framework-devui)", file=sys.stderr)
        sys.exit(1)

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
