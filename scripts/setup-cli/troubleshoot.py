"""Troubleshooting wizard — diagnoses common issues and suggests Copilot-powered fixes."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .checks import _run, scan_environment
from .styles import COPILOT_TIPS, MCP_SERVERS, THEME
from .testing import health_check

console = Console(theme=THEME)


def _check_port_user(port: int) -> str | None:
    """Return the process using a port, or None."""
    ok, out = _run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"])
    if ok and out.strip():
        pid = out.strip().split("\n")[0]
        # Get process name
        ok2, name = _run(["ps", "-p", pid, "-o", "comm="])
        return f"PID {pid} ({name.strip()})" if ok2 else f"PID {pid}"
    return None


def _check_venv_health(server_dir: Path, max_minor: int) -> list[str]:
    """Check venv integrity for an MCP server."""
    issues = []
    venv = server_dir / ".venv"
    if not venv.is_dir():
        issues.append("No .venv directory — run setup first")
        return issues

    python = venv / "bin" / "python"
    if not python.is_file():
        issues.append(".venv/bin/python missing — venv is corrupted")
        return issues

    # Check Python version compatibility
    ok, ver = _run([str(python), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"])
    if ok:
        try:
            major, minor = [int(x) for x in ver.strip().split(".")]
            if major != 3 or minor < 9 or minor > max_minor:
                issues.append(f"Python {ver.strip()} in venv — Azure Functions needs 3.9-3.{max_minor}")
        except ValueError:
            pass

    # Check key packages
    for pkg in ["azure.functions", "httpx", "pydantic"]:
        ok, _ = _run([str(python), "-c", f"import {pkg}"])
        if not ok:
            issues.append(f"Package '{pkg}' not importable in venv")

    # Check .python_packages
    pkg_dir = server_dir / ".python_packages" / "lib" / "site-packages"
    if not pkg_dir.is_dir():
        issues.append(".python_packages not created — Azure Functions worker may fail")

    return issues


def _check_azurite_running() -> bool:
    """Check if Azurite is running on standard ports."""
    for port in [10000, 10001, 10002]:
        ok, _ = _run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"])
        if ok:
            return True
    return False


def _check_local_settings(server_dir: Path) -> list[str]:
    """Check local.settings.json exists and has needed keys."""
    issues = []
    settings_file = server_dir / "local.settings.json"
    if not settings_file.is_file():
        issues.append("No local.settings.json found")
        return issues

    import json

    try:
        with open(settings_file) as f:
            data = json.load(f)
        values = data.get("Values", {})
        if not values.get("AzureWebJobsStorage"):
            issues.append("AzureWebJobsStorage not set in local.settings.json")
    except (json.JSONDecodeError, OSError) as e:
        issues.append(f"Error reading local.settings.json: {e}")

    return issues


# ---------------------------------------------------------------------------
# Main diagnostic
# ---------------------------------------------------------------------------


def run_diagnostics(project_root: Path) -> None:
    """Full troubleshooting diagnostic."""
    console.print()
    console.print(Panel("[header]🔍 Troubleshooting Diagnostic[/header]", expand=False))
    console.print()

    # 1. Environment
    console.print("[step]1. Checking environment prerequisites…[/step]")
    report = scan_environment()
    max_minor = report.python_max_minor

    env_table = Table(show_lines=False, show_header=False, padding=(0, 2))
    env_table.add_column("Check")
    env_table.add_column("Result")

    checks = [
        (f"Python 3.9-3.{max_minor}", report.python and report.python.found),
        ("Node.js", report.node and report.node.found),
        ("Azure Functions Core Tools", report.func_tools and report.func_tools.found),
        ("Azurite", report.azurite and report.azurite.found),
        ("Docker", report.docker and report.docker.found),
        ("Git", report.git and report.git.found),
    ]
    for name, ok in checks:
        mark = "[success]✓[/success]" if ok else "[error]✗[/error]"
        env_table.add_row(f"  {name}", mark)

    console.print(env_table)

    # 2. Azurite
    console.print()
    console.print("[step]2. Checking Azurite storage emulator…[/step]")
    if _check_azurite_running():
        console.print("  [success]✓[/success] Azurite is running")
    else:
        console.print("  [warning]⚠  Azurite not detected on ports 10000-10002[/warning]")
        console.print("  [info]Start it with:[/info] azurite --silent --location /tmp/azurite &")
        console.print(COPILOT_TIPS["azurite_not_found"])

    # 3. Port conflicts
    console.print()
    console.print("[step]3. Checking for port conflicts…[/step]")
    port_issues = False
    for name, info in MCP_SERVERS.items():
        port = info["port"]
        user = _check_port_user(port)
        if user and not health_check(name, port):
            console.print(f"  [warning]⚠  Port {port} ({name}) in use by {user} but NOT an MCP server[/warning]")
            console.print(f"     {COPILOT_TIPS['port_busy'].format(port=port)}")
            port_issues = True
    if not port_issues:
        console.print("  [success]✓[/success] No port conflicts detected")

    # 4. Per-server venv health
    console.print()
    console.print("[step]4. Checking MCP server venvs…[/step]")
    server_table = Table(show_lines=True)
    server_table.add_column("Server", style="server")
    server_table.add_column("Venv", justify="center")
    server_table.add_column("Packages", justify="center")
    server_table.add_column("local.settings", justify="center")
    server_table.add_column("Issues")

    for name in MCP_SERVERS:
        sdir = project_root / "src" / "mcp-servers" / name
        if not sdir.is_dir():
            server_table.add_row(name, "[error]✗[/error]", "—", "—", "Directory missing")
            continue

        venv_issues = _check_venv_health(sdir, max_minor)
        settings_issues = _check_local_settings(sdir)
        all_issues = venv_issues + settings_issues

        venv_ok = not any("venv" in i.lower() or "corrupted" in i.lower() for i in venv_issues)
        pkg_ok = not any("importable" in i or ".python_packages" in i for i in venv_issues)
        settings_ok = len(settings_issues) == 0

        v = "[success]✓[/success]" if venv_ok else "[error]✗[/error]"
        p = "[success]✓[/success]" if pkg_ok else "[error]✗[/error]"
        s = "[success]✓[/success]" if settings_ok else "[warning]⚠[/warning]"
        issue_text = "; ".join(all_issues[:2]) if all_issues else "[muted]—[/muted]"

        server_table.add_row(name, v, p, s, issue_text)

    console.print(server_table)

    # 5. Running servers health check
    console.print()
    console.print("[step]5. Health-checking running servers…[/step]")
    any_running = False
    for name, info in MCP_SERVERS.items():
        port = info["port"]
        if health_check(name, port):
            console.print(f"  [success]✓[/success] {name} (:{port}) is healthy")
            any_running = True
        else:
            user = _check_port_user(port)
            if user:
                console.print(f"  [error]✗[/error] {name} (:{port}) — process running but not healthy")
            # Don't report stopped servers as errors — they may intentionally be off
    if not any_running:
        console.print("  [muted]No servers currently running. Start with: make local-start[/muted]")

    # 6. Summary + tips
    console.print()
    console.print(
        Panel(
            "[bold]Need more help?[/bold]\n\n"
            "• Run [bold]make local-start[/bold] to start all servers\n"
            "• Run [bold]make local-logs[/bold] to view server logs\n"
            "• Open VS Code Copilot Chat and ask:\n"
            '  [italic]"@healthcare Help me debug my local MCP setup"[/italic]\n\n'
            "• Check docs: [info]docs/LOCAL-TESTING.md[/info] and [info]docs/DEVELOPER-GUIDE.md[/info]",
            title="[header]💡 Quick References[/header]",
            expand=False,
        )
    )
