#!/usr/bin/env python3
"""
Healthcare MCP — Interactive Setup CLI

An interactive guide for setting up, validating, and troubleshooting the
Azure Healthcare Marketplace locally.

Usage:
    python -m setup-cli                 # Interactive menu
    python -m setup-cli check           # Environment check only
    python -m setup-cli setup           # Setup all MCP server venvs
    python -m setup-cli status          # Show server status
    python -m setup-cli test            # Run smoke tests
    python -m setup-cli doctor          # Full troubleshooting diagnostic
    python -m setup-cli guided          # Guided first-time setup
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from .checks import EnvironmentReport, is_ready, print_report, scan_environment
from .deploy import cmd_deploy_walkthrough, cmd_post_deploy_guide
from .servers import (
    check_server_status,
    setup_agents_venv,
    setup_all_servers,
)
from .styles import COPILOT_TIPS, LOGO, MCP_SERVERS, THEME
from .testing import run_eval_contracts, run_eval_latency, run_smoke_tests
from .troubleshoot import run_diagnostics

console = Console(theme=THEME)


# ---------------------------------------------------------------------------
# Menu helpers
# ---------------------------------------------------------------------------


def _clear() -> None:
    console.print("\n" * 2)


def _show_logo() -> None:
    console.print(LOGO)


def _pause(msg: str = "Press Enter to continue…") -> None:
    Prompt.ask(f"[muted]{msg}[/muted]", default="")


MENU_ITEMS = [
    ("1", "Check Environment", "Verify prerequisites (Python, func, Azurite, etc.)"),
    ("2", "Setup MCP Servers", "Create venvs and install dependencies for all servers"),
    ("3", "Setup Agent Workflows", "Create venv for the agents orchestration layer"),
    ("4", "Server Status", "See which MCP servers are running"),
    ("5", "Run Smoke Tests", "Health + discovery + tools/list against running servers"),
    ("6", "Run Evaluations", "Contract and latency evals"),
    ("7", "Troubleshoot", "Full diagnostic — find and fix common issues"),
    ("8", "Guided Setup", "Step-by-step first-time setup walkthrough (local)"),
    ("9", "Deploy to Azure", "azd provision → container deploy → post-deploy validation"),
    ("10", "Post-Deploy: Copilot Demo", "Test PA review with Copilot + sample files"),
    ("11", "VS Code / Copilot Tips", "Integration tips for GitHub Copilot + MCP"),
    ("q", "Quit", ""),
]


def _show_menu() -> str:
    console.print()
    console.print(Panel("[header]Healthcare MCP — Setup & Diagnostics[/header]", expand=False))
    console.print()
    for key, label, desc in MENU_ITEMS:
        if key == "q":
            console.print("  [muted]q)[/muted] [muted]Quit[/muted]")
        else:
            console.print(f"  [highlight]{key})[/highlight] [step]{label}[/step]  [muted]{desc}[/muted]")
    console.print()
    return Prompt.ask("[bold]Choose an option[/bold]", choices=[m[0] for m in MENU_ITEMS], default="1")


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------


def cmd_check() -> EnvironmentReport:
    console.print()
    console.print("[header]🔎 Environment Check[/header]")
    report = scan_environment()
    print_report(report)
    if is_ready(report):
        console.print("[success]✓ Minimum requirements met for local MCP testing.[/success]")
    else:
        console.print("[error]✗ Missing requirements — resolve issues above before continuing.[/error]")
    return report


def cmd_setup_servers(report: EnvironmentReport | None = None) -> None:
    if report is None:
        report = scan_environment()

    if not report.project_root:
        console.print("[error]Cannot find project root. Run from the repo directory.[/error]")
        return

    python_cmd = report.python.path if (report.python and report.python.found) else "python3"

    # Let user pick servers or all
    console.print()
    console.print("[header]🔧 MCP Server Setup[/header]")
    console.print()
    console.print("Available servers:")
    for i, (name, info) in enumerate(MCP_SERVERS.items(), 1):
        console.print(f"  {i}. [server]{name}[/server] — {info['desc']}")
    console.print("  a. [highlight]All servers[/highlight]")
    console.print()

    choice = Prompt.ask("Setup which servers?", default="a")

    if choice.lower() == "a":
        targets = None  # all
    else:
        names = list(MCP_SERVERS.keys())
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            targets = [names[i] for i in indices if 0 <= i < len(names)]
        except (ValueError, IndexError):
            console.print("[error]Invalid selection. Running all servers.[/error]")
            targets = None

    force = Confirm.ask("Force-recreate venvs?", default=False)

    results = setup_all_servers(report.project_root, python_cmd, force=force, servers=targets)

    console.print()
    ok_count = sum(1 for v in results.values() if v)
    total = len(results)
    if ok_count == total:
        console.print(f"[success]✓ All {total} servers set up successfully![/success]")
    else:
        console.print(f"[warning]⚠  {ok_count}/{total} servers set up. Check errors above.[/warning]")


def cmd_setup_agents(report: EnvironmentReport | None = None) -> None:
    if report is None:
        report = scan_environment()
    if not report.project_root:
        console.print("[error]Cannot find project root.[/error]")
        return

    console.print()
    console.print("[header]🤖 Agent Workflow Setup[/header]")
    python_cmd = report.python.path if (report.python and report.python.found) else "python3"
    setup_agents_venv(report.project_root, python_cmd)


def cmd_status(report: EnvironmentReport | None = None) -> None:
    root = report.project_root if report else None
    check_server_status(root)


def cmd_test() -> None:
    console.print()
    mode = Prompt.ask("Test mode", choices=["local", "docker"], default="local")
    run_smoke_tests(docker=(mode == "docker"))


def cmd_evals(report: EnvironmentReport | None = None) -> None:
    if report is None:
        report = scan_environment()
    if not report.project_root:
        console.print("[error]Cannot find project root.[/error]")
        return

    console.print()
    console.print("[header]📊 Evaluations[/header]")
    console.print()
    console.print("  1. Contract evaluations (tools/list schema compliance)")
    console.print("  2. Latency evaluations (response time per tool)")
    console.print("  3. Both")
    console.print()
    choice = Prompt.ask("Run which evals?", choices=["1", "2", "3"], default="3")

    if choice in ("1", "3"):
        run_eval_contracts(report.project_root)
    if choice in ("2", "3"):
        run_eval_latency(report.project_root)


def cmd_troubleshoot(report: EnvironmentReport | None = None) -> None:
    if report is None:
        report = scan_environment()
    if not report.project_root:
        console.print("[error]Cannot find project root.[/error]")
        return
    run_diagnostics(report.project_root)


def cmd_deploy(report: EnvironmentReport | None = None) -> None:
    cmd_deploy_walkthrough(report)


def cmd_post_deploy(report: EnvironmentReport | None = None) -> None:
    cmd_post_deploy_guide(report)


def cmd_copilot_tips() -> None:
    console.print()
    console.print(
        Panel(
            "[header]VS Code / GitHub Copilot Integration[/header]\n\n"
            "[bold]1. Native MCP in Copilot Chat[/bold]\n"
            "   Copilot natively reads [info].vscode/mcp.json[/info] for MCP tool access.\n"
            "   Start local servers, then Copilot can call tools directly.\n\n"
            "[bold]2. Skills (auto-loaded)[/bold]\n"
            "   Skills in [info].github/skills/[/info] are automatically injected into Copilot context.\n"
            "   Use: [italic]@healthcare /pa Review this PA request[/italic]\n\n"
            "[bold]3. Helpful Copilot Prompts[/bold]\n"
            '   • "Help me set up local MCP servers for healthcare development"\n'
            '   • "What MCP tools are available in this workspace?"\n'
            '   • "Debug why my fhir-operations server returns 500"\n'
            '   • "Write a smoke test for the NPI lookup MCP tool"\n'
            '   • "Explain this prior authorization workflow step by step"\n\n'
            "[bold]4. Configure MCP for Copilot[/bold]\n"
            "   After running [bold]make local-start[/bold], create [info].vscode/mcp.json[/info]:\n"
            "   [muted](The guided setup does this automatically)[/muted]\n\n"
            "   {\n"
            '     "servers": {\n'
            '       "npi-lookup": { "type": "http", "url": "http://localhost:7071/mcp" }\n'
            "     }\n"
            "   }\n\n"
            "[bold]5. Agent Framework DevUI[/bold]\n"
            "   Run Gradio UI for interactive workflow testing:\n"
            "   [info]cd src && source agents/.venv/bin/activate && python -m agents --devui --local[/info]",
            expand=True,
        )
    )


# ---------------------------------------------------------------------------
# Guided setup
# ---------------------------------------------------------------------------


def cmd_guided_setup() -> None:
    """Step-by-step walkthrough for first-time users."""
    _clear()
    console.print(
        Panel(
            "[header]🚀 Guided First-Time Setup[/header]\n\n"
            "This wizard will walk you through:\n"
            "  1. Verify prerequisites\n"
            "  2. Set up MCP server environments\n"
            "  3. Start servers locally\n"
            "  4. Run smoke tests to validate\n"
            "  5. Configure VS Code MCP integration\n"
            "  6. (Optional) Set up agent workflows",
            expand=False,
        )
    )
    console.print()
    if not Confirm.ask("Ready to start?", default=True):
        return

    # Step 1 — Prerequisites
    console.print()
    console.print("[step]━━━ Step 1/6: Prerequisites ━━━[/step]")
    report = scan_environment()
    print_report(report)

    if not is_ready(report):
        console.print()
        console.print("[error]Please install missing prerequisites before continuing.[/error]")
        console.print()
        console.print("[info]Quick install commands (macOS):[/info]")
        if report.func_tools and not report.func_tools.found:
            console.print("  brew install azure-functions-core-tools@4")
        if report.azurite and not report.azurite.found:
            console.print("  npm install -g azurite")
        if report.node and not report.node.found:
            console.print("  brew install node")
        console.print()
        console.print(COPILOT_TIPS["general"])
        if not Confirm.ask("Continue anyway?", default=False):
            return

    # Step 2 — Setup server venvs
    console.print()
    console.print("[step]━━━ Step 2/6: MCP Server Environments ━━━[/step]")
    if Confirm.ask("Set up all MCP server venvs now?", default=True):
        python_cmd = report.python.path if (report.python and report.python.found) else "python3"
        results = setup_all_servers(report.project_root, python_cmd)
        ok = sum(1 for v in results.values() if v)
        console.print(
            f"\n  [{'success' if ok == len(results) else 'warning'}]{ok}/{len(results)} servers set up[/{'success' if ok == len(results) else 'warning'}]"
        )
    else:
        console.print("  [muted]Skipped[/muted]")

    # Step 3 — Start servers
    console.print()
    console.print("[step]━━━ Step 3/6: Start Servers ━━━[/step]")
    console.print("  You have two options:")
    console.print("    [highlight]a)[/highlight] [bold]make local-start[/bold] — native (requires Azurite)")
    console.print("    [highlight]b)[/highlight] [bold]make docker-up[/bold]   — Docker Compose (self-contained)")
    console.print()
    start_choice = Prompt.ask("Start servers now?", choices=["a", "b", "skip"], default="skip")

    import subprocess

    if start_choice == "a":
        console.print("[step]Starting servers via make local-start…[/step]")
        subprocess.run(["make", "local-start"], cwd=str(report.project_root))
    elif start_choice == "b":
        console.print("[step]Starting servers via make docker-up…[/step]")
        subprocess.run(["make", "docker-up"], cwd=str(report.project_root))

    if start_choice != "skip":
        console.print("[muted]Waiting 8s for servers to initialise…[/muted]")
        import time

        time.sleep(8)

    # Step 4 — Smoke tests
    console.print()
    console.print("[step]━━━ Step 4/6: Validate ━━━[/step]")
    if start_choice != "skip":
        docker = start_choice == "b"
        run_smoke_tests(docker=docker)
    else:
        console.print("  [muted]Skipped (servers not started in this session)[/muted]")

    # Step 5 — VS Code MCP config
    console.print()
    console.print("[step]━━━ Step 5/6: VS Code MCP Configuration ━━━[/step]")
    mcp_json = report.project_root / ".vscode" / "mcp.json"
    if mcp_json.is_file():
        console.print("  [success]✓[/success] .vscode/mcp.json already exists")
    else:
        if Confirm.ask("Generate .vscode/mcp.json for local MCP servers?", default=True):
            _generate_mcp_json(report.project_root, docker=(start_choice == "b"))
            console.print("  [success]✓[/success] Created .vscode/mcp.json")
        else:
            console.print("  [muted]Skipped[/muted]")

    # Step 6 — Agents
    console.print()
    console.print("[step]━━━ Step 6/6: Agent Workflows (Optional) ━━━[/step]")
    if Confirm.ask("Set up the agents orchestration venv?", default=False):
        python_cmd = report.python.path if (report.python and report.python.found) else "python3"
        setup_agents_venv(report.project_root, python_cmd)

        env_file = report.project_root / "src" / "agents" / ".env"
        example = report.project_root / "src" / "agents" / ".env.example"
        if not env_file.is_file() and example.is_file():
            console.print("  [info]Copying .env.example → .env (edit with your Azure OpenAI values)[/info]")
            import shutil

            shutil.copy2(str(example), str(env_file))
    else:
        console.print("  [muted]Skipped — come back when you're ready[/muted]")

    # Done!
    console.print()
    console.print(
        Panel(
            "[success]🎉 Local Setup Complete![/success]\n\n"
            "[bold]What's next:[/bold]\n"
            "  • [bold]make local-start[/bold]           Start all MCP servers\n"
            "  • [bold]make eval-contracts[/bold]        Validate MCP contracts\n"
            "  • Open Copilot Chat and try: [italic]@healthcare /pa[/italic]\n\n"
            "[bold]Ready for Azure?[/bold]\n"
            "  • [bold]make setup[/bold] → option [highlight]9[/highlight] (Deploy to Azure)\n"
            "  • After deploy → option [highlight]10[/highlight] (Post-Deploy: Copilot Demo)\n"
            "    Upload sample PA files and let Copilot + MCP validate them end-to-end!\n\n"
            "For full docs: [info]docs/DEVELOPER-GUIDE.md[/info] · [info]docs/LOCAL-TESTING.md[/info]",
            title="[header]All Done[/header]",
            expand=False,
        )
    )


def _generate_mcp_json(project_root: Path, *, docker: bool = False) -> None:
    """Generate a .vscode/mcp.json for local development."""
    import json

    key_suffix = "?code=docker-default-key" if docker else ""
    servers = {}
    for name, info in MCP_SERVERS.items():
        servers[name] = {
            "type": "http",
            "url": f"http://localhost:{info['port']}/mcp{key_suffix}",
        }

    config = {"servers": servers}

    vscode_dir = project_root / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    mcp_file = vscode_dir / "mcp.json"
    with open(mcp_file, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry — interactive menu or direct sub-command."""
    args = sys.argv[1:]

    # Direct sub-command mode
    if args:
        cmd = args[0].lower()
        if cmd == "check":
            _show_logo()
            cmd_check()
        elif cmd == "setup":
            _show_logo()
            cmd_setup_servers()
        elif cmd == "agents":
            _show_logo()
            cmd_setup_agents()
        elif cmd == "status":
            _show_logo()
            cmd_status()
        elif cmd == "test":
            _show_logo()
            cmd_test()
        elif cmd == "evals":
            _show_logo()
            cmd_evals()
        elif cmd == "doctor":
            _show_logo()
            cmd_troubleshoot()
        elif cmd == "guided":
            _show_logo()
            cmd_guided_setup()
        elif cmd == "deploy":
            _show_logo()
            cmd_deploy()
        elif cmd in ("post-deploy", "postdeploy", "demo"):
            _show_logo()
            cmd_post_deploy()
        elif cmd == "tips":
            _show_logo()
            cmd_copilot_tips()
        else:
            console.print(f"[error]Unknown command: {cmd}[/error]")
            console.print(
                "[info]Available: check, setup, agents, status, test, evals, doctor, guided, deploy, post-deploy, tips[/info]"
            )
            sys.exit(1)
        return

    # Interactive menu mode
    _show_logo()
    report: EnvironmentReport | None = None

    while True:
        try:
            choice = _show_menu()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[muted]Bye![/muted]")
            break

        if choice == "q":
            console.print("[muted]Bye! 👋[/muted]")
            break
        elif choice == "1":
            report = cmd_check()
        elif choice == "2":
            cmd_setup_servers(report)
        elif choice == "3":
            cmd_setup_agents(report)
        elif choice == "4":
            cmd_status(report)
        elif choice == "5":
            cmd_test()
        elif choice == "6":
            cmd_evals(report)
        elif choice == "7":
            cmd_troubleshoot(report)
        elif choice == "8":
            cmd_guided_setup()
        elif choice == "9":
            cmd_deploy(report)
        elif choice == "10":
            cmd_post_deploy(report)
        elif choice == "11":
            cmd_copilot_tips()

        console.print()
        _pause()
