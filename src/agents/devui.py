"""
Healthcare Agent Orchestration — Developer UI

Gradio-based interface for testing and visualizing multi-agent workflows.
Provides real-time agent activity logs, structured result display,
and architecture diagrams for each workflow.

Usage:
    python -m agents --devui
    python -m agents --devui --local
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import textwrap
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import gradio as gr

# ---------------------------------------------------------------------------
# Demo data — same as main.py, kept here for the UI's Load Demo buttons
# ---------------------------------------------------------------------------

DEMO_DATA: dict[str, dict[str, Any]] = {
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
        "clinical_summary": (
            "Patient presents with progressive dyspnea and "
            "interstitial lung disease. CT chest requested to evaluate disease "
            "progression and guide treatment planning."
        ),
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


# ---------------------------------------------------------------------------
# Architecture diagrams (Mermaid rendered as Markdown)
# ---------------------------------------------------------------------------

WORKFLOW_DIAGRAMS: dict[str, str] = {
    "prior-auth": textwrap.dedent("""\
        ## Prior Authorization — Hybrid Sequential / Concurrent / Synthesis

        ```mermaid
        %%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#4a9eff', 'primaryTextColor': '#fff', 'lineColor': '#6b7280', 'secondaryColor': '#10b981', 'tertiaryColor': '#f59e0b'}}}%%
        graph TD
            A[📋 PA Request] --> B[🔍 Compliance Agent]
            B -->|Gate: PASS| C{Fan-out}
            B -->|Gate: FAIL| G[🟡 PEND — Compliance Issues]
            C --> D[🏥 Clinical Reviewer Agent]
            C --> E[📑 Coverage Agent]
            D --> F{Synthesis}
            E --> F
            F --> H[⚖️ Synthesis Agent]
            H --> I[✅ APPROVE / 🟡 PEND]

            style B fill:#4a9eff,color:#fff,stroke:#3b82f6
            style D fill:#10b981,color:#fff,stroke:#059669
            style E fill:#f59e0b,color:#fff,stroke:#d97706
            style H fill:#8b5cf6,color:#fff,stroke:#7c3aed
        ```

        | Phase | Agent | MCP Servers | Pattern |
        |-------|-------|-------------|---------|
        | 1 — Gate | Compliance | NPI, ICD-10 | Sequential |
        | 2 — Review | Clinical Reviewer | FHIR, PubMed, Trials | Concurrent |
        | 2 — Review | Coverage | CMS, ICD-10 | Concurrent |
        | 3 — Decision | Synthesis | *(none — aggregation only)* | Sequential |
    """),
    "clinical-trial": textwrap.dedent("""\
        ## Clinical Trial Protocol — Sequential Research → Draft

        ```mermaid
        %%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#4a9eff', 'primaryTextColor': '#fff', 'lineColor': '#6b7280'}}}%%
        graph TD
            A[🧬 Intervention] --> B[🔬 Trials Research Agent]
            B --> C[📝 Protocol Draft Agent]
            C --> D[📄 Draft Protocol]

            style B fill:#4a9eff,color:#fff,stroke:#3b82f6
            style C fill:#10b981,color:#fff,stroke:#059669
        ```

        | Step | Agent | MCP Servers | Output |
        |------|-------|-------------|--------|
        | 1 — Research | Trials Research | Clinical Trials, PubMed | Related trials + patterns |
        | 2 — Draft | Protocol Draft | *(none — LLM only)* | FDA/NIH-compliant protocol |
    """),
    "patient-summary": textwrap.dedent("""\
        ## Patient Data — Single Agent Retrieval

        ```mermaid
        %%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#4a9eff', 'primaryTextColor': '#fff', 'lineColor': '#6b7280'}}}%%
        graph TD
            A[🔎 Patient Query] --> B[🏥 Patient Data Agent]
            B --> C[📊 Patient Summary]

            style B fill:#4a9eff,color:#fff,stroke:#3b82f6
        ```

        | Step | Agent | MCP Servers | Output |
        |------|-------|-------------|--------|
        | 1 | Patient Data | FHIR, NPI | Conditions, meds, vitals, encounters |
    """),
    "literature-search": textwrap.dedent("""\
        ## Literature Search — Concurrent Evidence + Trials

        ```mermaid
        %%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#4a9eff', 'primaryTextColor': '#fff', 'lineColor': '#6b7280', 'secondaryColor': '#10b981'}}}%%
        graph TD
            A[📚 Clinical Query] --> B{Fan-out}
            B --> C[📖 Literature Agent]
            B --> D[🔬 Trials Correlation Agent]
            C --> E{Merge}
            D --> E
            E --> F[📋 Evidence Report]

            style C fill:#4a9eff,color:#fff,stroke:#3b82f6
            style D fill:#10b981,color:#fff,stroke:#059669
        ```

        | Phase | Agent | MCP Servers | Output |
        |-------|-------|-------------|--------|
        | Fan-out | Literature Search | PubMed | Key articles + synthesis |
        | Fan-out | Trials Correlation | Clinical Trials | Matching active trials |
    """),
}

# Input schema hints for each workflow
INPUT_SCHEMAS: dict[str, str] = {
    "prior-auth": textwrap.dedent("""\
        {
          "member": {"id": "", "name": "", "dob": "", "plan": ""},
          "provider": {"npi": "", "name": "", "specialty": ""},
          "service": {
            "cpt_code": "",
            "description": "",
            "icd10_codes": [],
            "place_of_service": ""
          },
          "clinical_summary": ""
        }"""),
    "clinical-trial": textwrap.dedent("""\
        {
          "condition": "",
          "intervention_type": "Drug",
          "intervention_name": "",
          "phase": "Phase 3",
          "target_population": ""
        }"""),
    "patient-summary": textwrap.dedent("""\
        {
          "patient_id": "",
          "name": ""
        }"""),
    "literature-search": textwrap.dedent("""\
        {
          "condition": "",
          "intervention": "",
          "focus": "therapy",
          "keywords": ""
        }"""),
}


# ---------------------------------------------------------------------------
# Log capture — intercepts agent logging for real-time display
# ---------------------------------------------------------------------------


class QueueHandler(logging.Handler):
    """Logging handler that pushes formatted records into a queue."""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.log_queue.put(msg)
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# Settings helpers — load / save / validate Azure OpenAI settings
# ---------------------------------------------------------------------------

_ENV_FILE = Path(__file__).parent / ".env"


def _load_settings() -> dict[str, str]:
    """Load current settings from environment (which may come from .env)."""
    return {
        "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        "deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
        "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
    }


def _save_settings(endpoint: str, deployment: str, api_version: str) -> str:
    """Save settings to .env and update os.environ. Returns status message."""
    endpoint = endpoint.strip()
    deployment = deployment.strip() or "gpt-4o"
    api_version = api_version.strip() or "2025-01-01-preview"

    if not endpoint:
        return "⚠️ Endpoint is required"
    if not endpoint.startswith("https://"):
        return "⚠️ Endpoint must start with https://"

    # Update os.environ so AgentConfig.load() picks them up
    os.environ["AZURE_OPENAI_ENDPOINT"] = endpoint
    os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"] = deployment
    os.environ["AZURE_OPENAI_API_VERSION"] = api_version

    # Persist to .env file
    lines = []
    if _ENV_FILE.exists():
        lines = _ENV_FILE.read_text().splitlines()

    env_vars = {
        "AZURE_OPENAI_ENDPOINT": endpoint,
        "AZURE_OPENAI_DEPLOYMENT_NAME": deployment,
        "AZURE_OPENAI_API_VERSION": api_version,
    }

    # Update existing lines or append
    updated_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in env_vars:
            new_lines.append(f"{key}={env_vars[key]}")
            updated_keys.add(key)
        else:
            new_lines.append(line)
    for key, val in env_vars.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")

    _ENV_FILE.write_text("\n".join(new_lines) + "\n")
    return f"✅ Settings saved to .env — endpoint: {endpoint}"


def _validate_settings() -> str:
    """Check if Azure OpenAI settings are configured."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    if not endpoint or endpoint == "https://your-resource.openai.azure.com":
        return (
            "⚠️ **Azure OpenAI not configured.** "
            "Open **Settings** (gear icon) and enter your Azure OpenAI endpoint before running workflows."
        )
    return f"✅ Azure OpenAI: `{endpoint}`"


# ---------------------------------------------------------------------------
# Workflow execution wrapper (generator for streaming logs)
# ---------------------------------------------------------------------------


async def _run_workflow_async(
    workflow_name: str,
    input_data: dict[str, Any],
    local: bool,
    log_queue: queue.Queue,
) -> dict[str, Any]:
    """Run the appropriate workflow, capturing logs to the queue."""
    from .workflows.clinical_trials import run_clinical_trials_workflow
    from .workflows.literature_search import run_literature_search_workflow
    from .workflows.patient_data import run_patient_data_workflow
    from .workflows.prior_auth import run_prior_auth_workflow

    workflows = {
        "prior-auth": run_prior_auth_workflow,
        "clinical-trial": run_clinical_trials_workflow,
        "patient-summary": run_patient_data_workflow,
        "literature-search": run_literature_search_workflow,
    }

    workflow_fn = workflows[workflow_name]
    kwargs: dict[str, Any] = {"local": local}
    if workflow_name == "clinical-trial":
        kwargs["research_only"] = False

    return await workflow_fn(input_data, config=None, **kwargs)


def run_workflow_streaming(
    workflow_name: str,
    input_json: str,
    local: bool,
) -> Generator[tuple[str, str, str], None, None]:
    """
    Generator that yields (log_text, result_json, status) tuples.

    Used by Gradio to stream updates to the UI as the workflow executes.
    """
    # Validate input
    try:
        input_data = json.loads(input_json)
    except json.JSONDecodeError as e:
        yield ("", f'{{"error": "Invalid JSON: {e}"}}', "❌ Invalid JSON input")
        return

    # Validate Azure OpenAI settings before attempting to run
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    if not endpoint or not endpoint.startswith("https://"):
        yield (
            "❌ Azure OpenAI endpoint is not configured.\n\n"
            "Open the ⚙️ Settings accordion at the top of the page and enter your\n"
            "Azure OpenAI endpoint, then click 'Save Settings' before running.\n\n"
            "Example: https://my-resource.openai.azure.com",
            json.dumps(
                {
                    "error": "Azure OpenAI endpoint not configured",
                    "fix": "Open Settings and enter your AZURE_OPENAI_ENDPOINT",
                },
                indent=2,
            ),
            "⚠️ Configure Azure OpenAI in Settings first",
        )
        return

    # Set up log capture
    log_queue: queue.Queue = queue.Queue()
    handler = QueueHandler(log_queue)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"))

    # Attach handler to relevant loggers
    loggers = [
        logging.getLogger("agents"),
        logging.getLogger("agent_framework"),
    ]
    for lgr in loggers:
        lgr.addHandler(handler)
        lgr.setLevel(logging.DEBUG)

    log_lines: list[str] = []
    status = "🔄 Running..."

    # Yield initial state
    yield ("Initializing workflow...\n", "{}", status)

    # Start the async workflow in a thread
    result_container: dict[str, Any] = {}
    error_container: dict[str, Any] = {}

    def _run():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_run_workflow_async(workflow_name, input_data, local, log_queue))
            result_container["data"] = result
        except BaseException as e:
            error_container["error"] = str(e)
            import traceback

            error_container["traceback"] = traceback.format_exc()
        finally:
            log_queue.put(None)  # Sentinel

    import threading

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # Poll the log queue and yield updates
    while True:
        try:
            msg = log_queue.get(timeout=0.5)
            if msg is None:
                # Sentinel received — workflow finished
                break
            log_lines.append(msg)
            log_text = "\n".join(log_lines)
            yield (log_text, "{}", status)
        except queue.Empty:
            # No new logs — check if thread died without putting sentinel
            if not thread.is_alive():
                # Give it one more chance to drain
                time.sleep(0.1)
                break

    # Wait for thread to fully complete so containers are populated
    thread.join(timeout=5.0)

    # Drain remaining messages
    while not log_queue.empty():
        msg = log_queue.get_nowait()
        if msg is not None:
            log_lines.append(msg)

    # Clean up handlers
    for lgr in loggers:
        lgr.removeHandler(handler)

    # Build final output
    log_text = "\n".join(log_lines)

    if error_container:
        error_msg = error_container.get("error", "Unknown error")
        tb = error_container.get("traceback", "")
        log_lines.append(f"\n❌ ERROR: {error_msg}")
        if tb:
            log_lines.append(f"\n{tb}")
        log_text = "\n".join(log_lines)
        result_json = json.dumps({"error": error_msg}, indent=2)
        status = f"❌ Failed: {error_msg[:100]}"
        yield (log_text, result_json, status)
    elif result_container:
        result = result_container["data"]
        result_json = json.dumps(result, indent=2, default=str)
        rec = ""
        if isinstance(result, dict):
            if "recommendation" in result:
                rec = f" — {result.get('recommendation', '')[:50]}"
            elif "status" in result:
                rec = f" — {result.get('status', '')}"
        status = f"✅ Complete{rec}"
        yield (log_text, result_json, status)
    else:
        log_lines.append(
            "\n⚠️ Workflow returned no result or error. Check Azure OpenAI credentials and MCP server connectivity."
        )
        log_text = "\n".join(log_lines)
        yield (log_text, '{"error": "No result returned — check credentials and connectivity"}', "⚠️ No result")


# ---------------------------------------------------------------------------
# Gradio UI builder
# ---------------------------------------------------------------------------


def _make_workflow_tab(
    workflow_key: str,
    label: str,
) -> tuple:
    """Build a single workflow tab and return its components."""

    with gr.Column(elem_classes=["workflow-tab-content"]):
        # Status bar
        status_box = gr.Textbox(
            label="Status",
            value="Ready",
            interactive=False,
            max_lines=1,
            elem_classes=["status-box"],
        )

        with gr.Row(equal_height=True, elem_classes=["workflow-main-row"]):
            # Left column: input + controls
            with gr.Column(scale=1, elem_classes=["panel", "input-panel"]):
                gr.Markdown("### Input", elem_classes=["panel-title"])
                input_box = gr.Code(
                    label="Request JSON",
                    language="json",
                    value=INPUT_SCHEMAS[workflow_key],
                    lines=14,
                    elem_classes=["request-json-box"],
                )
                with gr.Row(elem_classes=["action-row"]):
                    demo_btn = gr.Button(
                        "📋 Load Demo",
                        variant="secondary",
                        size="sm",
                        elem_classes=["demo-btn"],
                    )
                    run_btn = gr.Button(
                        "▶ Run Workflow",
                        variant="primary",
                        size="sm",
                        elem_classes=["run-btn"],
                    )

            # Right column: architecture diagram
            with gr.Column(scale=1, elem_classes=["panel", "diagram-panel"]):
                gr.Markdown(WORKFLOW_DIAGRAMS[workflow_key], elem_classes=["diagram-content"])

        # Agent activity log
        log_box = gr.Code(
            label="Agent Activity Log",
            language=None,
            lines=12,
            interactive=False,
            elem_classes=["log-box"],
        )

        # Result display
        result_box = gr.Code(
            label="Structured Result",
            language="json",
            lines=18,
            interactive=False,
            elem_classes=["result-box"],
        )

    return input_box, demo_btn, run_btn, log_box, result_box, status_box


def build_app(local: bool = False) -> gr.Blocks:
    """Construct the Gradio Blocks application."""

    with gr.Blocks(
        title="Healthcare Agent Orchestration — Dev UI",
    ) as app:
        # Header
        gr.Markdown(
            textwrap.dedent("""\
                # 🏥 Healthcare Agent Orchestration
                Streamlined developer UI for testing healthcare workflows powered by **Microsoft Agent Framework** and **6 MCP servers**.
            """),
            elem_classes=["app-hero"],
        )

        with gr.Row(elem_classes=["meta-row"]):
            gr.Markdown(
                f"**Mode:** {'🖥️ Local (localhost)' if local else '☁️ APIM Passthrough'}",
                elem_classes=["mode-badge"],
            )

        # Settings panel
        settings = _load_settings()
        settings_status = _validate_settings()

        with gr.Accordion(
            "⚙️ Settings — Azure OpenAI",
            open=not bool(settings["endpoint"]),
            elem_classes=["settings-panel"],
        ):
            settings_msg = gr.Markdown(settings_status, elem_classes=["settings-message"])
            with gr.Row(elem_classes=["settings-row"]):
                endpoint_box = gr.Textbox(
                    label="Azure OpenAI Endpoint",
                    value=settings["endpoint"],
                    placeholder="https://my-resource.openai.azure.com",
                    scale=3,
                    elem_classes=["settings-field"],
                )
                deployment_box = gr.Textbox(
                    label="Deployment Name",
                    value=settings["deployment"],
                    placeholder="gpt-4o",
                    scale=1,
                    elem_classes=["settings-field"],
                )
                api_version_box = gr.Textbox(
                    label="API Version",
                    value=settings["api_version"],
                    placeholder="2025-01-01-preview",
                    scale=1,
                    elem_classes=["settings-field"],
                )
                save_btn = gr.Button(
                    "💾 Save Settings",
                    variant="primary",
                    size="sm",
                    scale=0,
                    elem_classes=["save-btn"],
                )

            save_btn.click(
                fn=_save_settings,
                inputs=[endpoint_box, deployment_box, api_version_box],
                outputs=[settings_msg],
            )

        # Tabs for each workflow
        tabs_data: dict[str, tuple] = {}

        with gr.Tabs(elem_classes=["workflow-tabs"]):
            with gr.Tab("Prior Auth"):
                tabs_data["prior-auth"] = _make_workflow_tab("prior-auth", "Prior Authorization")

            with gr.Tab("Clinical Trials"):
                tabs_data["clinical-trial"] = _make_workflow_tab("clinical-trial", "Clinical Trial Protocol")

            with gr.Tab("Patient Data"):
                tabs_data["patient-summary"] = _make_workflow_tab("patient-summary", "Patient Data Summary")

            with gr.Tab("Literature Search"):
                tabs_data["literature-search"] = _make_workflow_tab("literature-search", "Literature & Evidence")

        # Wire up events for each tab
        for wf_key, (input_box, demo_btn, run_btn, log_box, result_box, status_box) in tabs_data.items():
            # Load demo data
            def _load_demo(wf=wf_key):
                return json.dumps(DEMO_DATA[wf], indent=2)

            demo_btn.click(
                fn=_load_demo,
                outputs=[input_box],
            )

            # Run workflow (streaming)
            def _run_streaming(input_json: str, wf=wf_key, is_local=local):
                yield from run_workflow_streaming(wf, input_json, is_local)

            run_btn.click(
                fn=_run_streaming,
                inputs=[input_box],
                outputs=[log_box, result_box, status_box],
            )

        # Footer
        gr.Markdown(
            textwrap.dedent("""\
                ---
                **MCP Servers**: NPI Lookup · ICD-10 Validation · CMS Coverage · FHIR Operations · PubMed · Clinical Trials
                *Agent Framework*: `agent-framework[azure]` · *Orchestration*: Sequential · Concurrent · Hybrid
            """),
            elem_classes=["app-footer"],
        )

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def launch(local: bool = False, share: bool = False, port: int = 7860) -> None:
    """Build and launch the dev UI."""
    app = build_app(local=local)
    app.queue()  # Enable queuing for streaming
    app.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=share,
        theme=gr.themes.Soft(),
        css=textwrap.dedent("""\
            :root {
                --app-bg-top: #f7fafc;
                --app-bg-bottom: #e6eef8;
                --panel-bg: #ffffffcc;
                --panel-border: #d7dfec;
                --panel-shadow: 0 8px 28px rgba(20, 31, 53, 0.08);
                --muted-text: #445168;
            }

            body {
                background:
                    radial-gradient(1300px 420px at 0% -10%, #dce8f8 0%, transparent 60%),
                    radial-gradient(1200px 360px at 100% -10%, #e8f0fb 0%, transparent 60%),
                    linear-gradient(180deg, var(--app-bg-top), var(--app-bg-bottom));
            }

            footer { display: none !important; }

            /* Centering and page width */
            .gradio-container {
                max-width: 1280px !important;
                margin: 0 auto !important;
                padding: 24px clamp(12px, 2vw, 26px) 28px !important;
            }

            .app-hero {
                border: 1px solid var(--panel-border);
                background: linear-gradient(135deg, #ffffffea, #f4f8ffea);
                border-radius: 16px;
                padding: 14px 18px;
                box-shadow: var(--panel-shadow);
            }
            .app-hero h1 {
                margin-bottom: 0.2rem !important;
                letter-spacing: 0.01em;
            }
            .app-hero p {
                color: var(--muted-text);
                margin-top: 0.25rem !important;
            }

            .meta-row { margin-top: 8px; margin-bottom: 8px; }
            .mode-badge {
                display: inline-flex;
                width: fit-content;
                border-radius: 999px;
                padding: 6px 12px;
                background: #ffffffd9;
                border: 1px solid #d6e0f0;
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.06);
            }

            .settings-panel,
            .workflow-tab-content,
            .app-footer {
                border: 1px solid var(--panel-border);
                border-radius: 16px;
                background: var(--panel-bg);
                backdrop-filter: blur(4px);
                box-shadow: var(--panel-shadow);
            }
            .settings-panel { margin-top: 8px; }
            .settings-panel .label-wrap span { font-weight: 600; }
            .settings-message p { margin: 0; }
            .settings-row { align-items: end; gap: 10px; }
            .save-btn button {
                border-radius: 10px !important;
                font-weight: 600 !important;
            }

            .workflow-tabs {
                margin-top: 12px;
            }
            .workflow-tabs .tab-nav button {
                border-radius: 10px !important;
                font-weight: 600 !important;
            }
            .workflow-tabs .tab-nav button.selected {
                box-shadow: inset 0 0 0 1px #8eb2ea;
                background: linear-gradient(180deg, #ecf4ff, #dceaff) !important;
            }

            .workflow-tab-content {
                margin-top: 10px;
                padding: 14px !important;
            }
            .workflow-main-row { gap: 12px; }
            .panel {
                border: 1px solid var(--panel-border);
                border-radius: 14px;
                padding: 10px;
                background: #ffffffd9;
            }
            .panel-title h3 { margin-bottom: 0.4rem !important; }

            .status-box textarea,
            .log-box textarea,
            .result-box textarea,
            .request-json-box textarea {
                border-radius: 10px !important;
                border: 1px solid #ccd8ea !important;
            }
            .status-box textarea {
                font-weight: 600 !important;
                color: #1f3557 !important;
                background: #f5f9ff !important;
            }

            .action-row { margin-top: 8px; gap: 8px; }
            .demo-btn button,
            .run-btn button {
                border-radius: 10px !important;
                font-weight: 600 !important;
            }

            .diagram-content h2 { margin-top: 0 !important; }
            .diagram-content table { font-size: 0.94rem; }

            .app-footer {
                margin-top: 12px;
                text-align: center;
                padding: 10px 14px;
                color: var(--muted-text);
            }
            .app-footer hr {
                margin-top: 0 !important;
                margin-bottom: 10px !important;
            }

            @media (max-width: 900px) {
                .gradio-container {
                    padding: 12px !important;
                }
                .workflow-tab-content {
                    padding: 10px !important;
                }
                .mode-badge {
                    width: 100%;
                }
            }

            /* Dark mode surface + contrast tuning */
            .dark body {
                background:
                    radial-gradient(1300px 420px at 0% -10%, #1c2636 0%, transparent 60%),
                    radial-gradient(1200px 360px at 100% -10%, #1b2a40 0%, transparent 60%),
                    linear-gradient(180deg, #0e1625, #111c2e) !important;
            }

            .dark .app-hero,
            .dark .settings-panel,
            .dark .workflow-tab-content,
            .dark .panel,
            .dark .app-footer,
            .dark .mode-badge {
                background: linear-gradient(180deg, #101a2aee, #0f1828ee) !important;
                border-color: #2c3b52 !important;
                box-shadow: 0 10px 26px rgba(1, 5, 12, 0.45) !important;
            }
            .dark .app-hero p,
            .dark .app-footer,
            .dark .mode-badge {
                color: #c7d2e3 !important;
            }
            .dark .app-footer hr {
                border-color: #2c3b52 !important;
            }

            .dark .workflow-tabs .tab-nav button {
                background: #111a2a !important;
                border-color: #2e3e57 !important;
                color: #d8e3f2 !important;
            }
            .dark .workflow-tabs .tab-nav button.selected {
                box-shadow: inset 0 0 0 1px #4f7fce !important;
                background: linear-gradient(180deg, #162742, #14233b) !important;
            }

            .dark .status-box textarea,
            .dark .log-box textarea,
            .dark .result-box textarea,
            .dark .request-json-box textarea,
            .dark .settings-field textarea,
            .dark .settings-field input {
                background: #0c1524 !important;
                color: #e5edf8 !important;
                border-color: #334864 !important;
            }
            .dark .status-box textarea {
                color: #dce8f8 !important;
                background: #102038 !important;
            }

            /* Dark-mode readability for Markdown + Mermaid */
            .dark .prose, .dark .prose * {
                color: var(--body-text-color) !important;
            }
            .dark .prose code {
                color: #e0e0e0 !important;
                background: #374151 !important;
            }
            .dark .mermaid .nodeLabel,
            .dark .mermaid .edgeLabel,
            .dark .mermaid .label,
            .dark .mermaid text {
                fill: #f0f0f0 !important;
                color: #f0f0f0 !important;
            }
            .dark .mermaid .edgePath .path {
                stroke: #9ca3af !important;
            }
            .dark .mermaid marker path {
                fill: #9ca3af !important;
            }
        """),
    )


if __name__ == "__main__":
    launch(local=True)
