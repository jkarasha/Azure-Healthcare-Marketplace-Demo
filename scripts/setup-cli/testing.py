"""Local testing helpers — health checks, smoke tests, endpoint validation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .styles import COPILOT_TIPS, MCP_SERVERS, THEME

console = Console(theme=THEME)


# ---------------------------------------------------------------------------
# Health / smoke checks
# ---------------------------------------------------------------------------


def _curl_json(url: str, method: str = "GET", data: dict | None = None, timeout: int = 5) -> tuple[bool, dict | str]:
    """Lightweight HTTP request via curl. Returns (ok, parsed_json_or_text)."""
    cmd = ["curl", "-sf", "--max-time", str(timeout)]
    if method == "POST":
        cmd += ["-X", "POST", "-H", "Content-Type: application/json"]
        if data:
            cmd += ["-d", json.dumps(data)]
    cmd.append(url)

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
        if r.returncode != 0:
            return False, r.stderr.strip()
        try:
            return True, json.loads(r.stdout)
        except json.JSONDecodeError:
            return True, r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "timeout or curl not found"


def health_check(server_name: str, port: int, *, key: str = "") -> bool:
    """Hit /health endpoint and return True if healthy."""
    url = f"http://localhost:{port}/health"
    if key:
        url += f"?code={key}"
    ok, _ = _curl_json(url)
    return ok


def mcp_discovery(server_name: str, port: int, *, key: str = "") -> tuple[bool, dict | str]:
    """Hit /.well-known/mcp and return parsed response."""
    url = f"http://localhost:{port}/.well-known/mcp"
    if key:
        url += f"?code={key}"
    return _curl_json(url)


def mcp_tools_list(server_name: str, port: int, *, key: str = "") -> tuple[bool, dict | str]:
    """Call tools/list via MCP JSON-RPC."""
    url = f"http://localhost:{port}/mcp"
    if key:
        url += f"?code={key}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    return _curl_json(url, method="POST", data=payload)


# ---------------------------------------------------------------------------
# Full smoke test
# ---------------------------------------------------------------------------


def smoke_test_server(server_name: str, port: int, *, key: str = "") -> dict:
    """Run health + discovery + tools/list against one server."""
    results = {}

    # Health
    results["health"] = health_check(server_name, port, key=key)

    # Discovery
    ok, data = mcp_discovery(server_name, port, key=key)
    results["discovery"] = ok
    results["discovery_data"] = data if ok else None

    # Tools list
    ok, data = mcp_tools_list(server_name, port, key=key)
    results["tools_list"] = ok
    if ok and isinstance(data, dict):
        tools = data.get("result", {}).get("tools", [])
        results["tools"] = [t.get("name", "?") for t in tools]
    else:
        results["tools"] = []

    return results


def run_smoke_tests(*, docker: bool = False) -> None:
    """Run smoke tests against all MCP servers and display results."""
    key = "docker-default-key" if docker else ""
    mode = "Docker" if docker else "Local"

    console.print()
    console.print(f"[header]Running smoke tests ({mode} mode)…[/header]")
    console.print()

    table = Table(title=f"MCP Smoke Tests — {mode}", show_lines=True)
    table.add_column("Server", style="server")
    table.add_column("Port", justify="center")
    table.add_column("Health", justify="center")
    table.add_column("Discovery", justify="center")
    table.add_column("Tools", justify="center")
    table.add_column("Tool Names")

    all_ok = True
    for name, info in MCP_SERVERS.items():
        port = info["port"]
        r = smoke_test_server(name, port, key=key)

        h = "[success]✓[/success]" if r["health"] else "[error]✗[/error]"
        d = "[success]✓[/success]" if r["discovery"] else "[error]✗[/error]"
        t = "[success]✓[/success]" if r["tools_list"] else "[error]✗[/error]"
        tools = ", ".join(r["tools"]) if r["tools"] else "[muted]—[/muted]"

        table.add_row(name, str(port), h, d, t, tools)

        if not all(r[k] for k in ("health", "discovery", "tools_list")):
            all_ok = False

    console.print(table)

    if all_ok:
        console.print()
        console.print("[success]All servers passed smoke tests! 🎉[/success]")
    else:
        console.print()
        console.print("[warning]Some servers failed. Check logs and ensure servers are running.[/warning]")
        console.print(COPILOT_TIPS["general"])


# ---------------------------------------------------------------------------
# Eval shortcuts
# ---------------------------------------------------------------------------


def run_eval_contracts(project_root: Path) -> bool:
    """Run the contract eval script."""
    script = project_root / "scripts" / "eval_contracts.py"
    if not script.is_file():
        console.print("[error]eval_contracts.py not found[/error]")
        return False
    console.print("[step]Running contract evaluations…[/step]")
    result = subprocess.run(
        ["python3", str(script)],
        cwd=str(project_root),
    )
    return result.returncode == 0


def _detect_function_code() -> str:
    """Detect whether the running MCP servers require a Functions access key.

    Local `func start` servers run anonymously (no key); Docker containers
    enforce FUNCTION auth with the ``docker-default-key``. Probe the
    reference-data server's health endpoint to pick the right mode.
    """
    base = "http://localhost:7071/health"
    ok, _ = _curl_json(base)
    if ok:
        return ""
    ok, _ = _curl_json(f"{base}?code=docker-default-key")
    if ok:
        return "docker-default-key"
    return ""


def run_eval_latency(project_root: Path) -> bool:
    """Run the latency eval script."""
    script = project_root / "scripts" / "eval_latency.py"
    config = project_root / "scripts" / "evals" / "mcp-latency.local.json"
    if not script.is_file():
        console.print("[error]eval_latency.py not found[/error]")
        return False
    console.print("[step]Running latency evaluations…[/step]")
    cmd = ["python3", str(script), "--config", str(config)]
    code = _detect_function_code()
    if code:
        cmd += ["--code", code]
    result = subprocess.run(
        cmd,
        cwd=str(project_root),
    )
    return result.returncode == 0
