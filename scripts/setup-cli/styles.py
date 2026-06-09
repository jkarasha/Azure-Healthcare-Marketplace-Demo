"""Shared styling constants and helpers for the setup CLI."""

from rich.theme import Theme

THEME = Theme(
    {
        "header": "bold cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "info": "dim cyan",
        "muted": "dim white",
        "highlight": "bold magenta",
        "step": "bold white",
        "server": "bold blue",
    }
)

LOGO = r"""
[bold cyan]
  ╦ ╦┌─┐┌─┐┬  ┌┬┐┬ ┬┌─┐┌─┐┬─┐┌─┐  ╔╦╗╔═╗╔═╗
  ╠═╣├┤ ├─┤│   │ ├─┤│  ├─┤├┬┘├┤   ║║║║  ╠═╝
  ╩ ╩└─┘┴ ┴┴─┘ ┴ ┴ ┴└─┘┴ ┴┴└─└─┘  ╩ ╩╚═╝╩
[/bold cyan]
[dim]Azure Healthcare Marketplace — Interactive Setup[/dim]
"""

MCP_SERVERS = {
    "mcp-reference-data": {"port": 7071, "desc": "NPI + ICD-10 + CMS Coverage (consolidated)"},
    "mcp-clinical-research": {"port": 7072, "desc": "FHIR + PubMed + ClinicalTrials (consolidated)"},
    "cosmos-rag": {"port": 7073, "desc": "Cosmos DB RAG & audit"},
    "document-reader": {"port": 7078, "desc": "Local document/PDF reader"},
}

COPILOT_TIPS = {
    "venv_fail": (
        "[bold]💡 Copilot Tip:[/bold] Ask GitHub Copilot:\n"
        '  [italic]"My Python venv creation is failing — how do I fix it on macOS?"[/italic]'
    ),
    "func_not_found": (
        "[bold]💡 Copilot Tip:[/bold] Ask GitHub Copilot:\n"
        '  [italic]"How do I install Azure Functions Core Tools v4?"[/italic]'
    ),
    "azurite_not_found": (
        "[bold]💡 Copilot Tip:[/bold] Ask GitHub Copilot:\n"
        '  [italic]"How do I install and run Azurite for local Azure Storage emulation?"[/italic]'
    ),
    "docker_not_found": (
        "[bold]💡 Copilot Tip:[/bold] Ask GitHub Copilot:\n"
        '  [italic]"How do I install Docker Desktop on macOS?"[/italic]'
    ),
    "server_unhealthy": (
        "[bold]💡 Copilot Tip:[/bold] Ask GitHub Copilot:\n"
        '  [italic]"My MCP server on port {port} isn\'t responding — how do I debug Azure Functions locally?"[/italic]'
    ),
    "pip_fail": (
        "[bold]💡 Copilot Tip:[/bold] Ask GitHub Copilot:\n"
        '  [italic]"pip install is failing with dependency conflicts — how do I resolve this?"[/italic]'
    ),
    "port_busy": (
        "[bold]💡 Copilot Tip:[/bold] Ask GitHub Copilot:\n"
        '  [italic]"Port {port} is already in use — how do I find and kill the process?"[/italic]'
    ),
    "general": (
        "[bold]💡 Copilot Tip:[/bold] Open VS Code Copilot Chat and ask:\n"
        '  [italic]"@healthcare Help me troubleshoot my local MCP server setup"[/italic]'
    ),
}
