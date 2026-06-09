"""Environment detection and prerequisite checks."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .styles import COPILOT_TIPS, THEME

console = Console(theme=THEME)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    found: bool
    version: str = ""
    path: str = ""
    note: str = ""


@dataclass
class EnvironmentReport:
    python: CheckResult | None = None
    node: CheckResult | None = None
    func_tools: CheckResult | None = None
    azurite: CheckResult | None = None
    docker: CheckResult | None = None
    az_cli: CheckResult | None = None
    azd_cli: CheckResult | None = None
    git: CheckResult | None = None
    project_root: Path | None = None
    python_max_minor: int = 11
    issues: list[str] = field(default_factory=list)
    copilot_tips: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _run(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    """Run a command and return (success, stdout)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, ""


def detect_func_supported_python_max_minor(default: int = 11) -> int:
    """Infer max supported Python minor from installed Azure Functions workers."""
    func_path = shutil.which("func")
    if not func_path:
        return default

    try:
        func_real = Path(func_path).resolve()
    except OSError:
        return default

    worker_root = func_real.parent.parent / "workers" / "python"
    if not worker_root.is_dir():
        return default

    supported: list[int] = []
    for child in worker_root.iterdir():
        if not child.is_dir() or not child.name.startswith("3."):
            continue
        try:
            minor = int(child.name.split(".", 1)[1])
            if minor >= 9:
                supported.append(minor)
        except ValueError:
            continue

    return max([default, *supported]) if supported else default


def check_python(max_minor: int = 11) -> CheckResult:
    """Check for a compatible Python installation (3.9..max_minor)."""
    candidates = [
        "python3.13",
        "python3.12",
        "python3.11",
        "python3.10",
        "python3.9",
        "python3",
        sys.executable,
    ]
    for py in candidates:
        ok, ver = _run([py, "--version"])
        if ok and ver:
            parts = ver.split()
            version_str = parts[-1] if parts else ver
            try:
                major, minor = [int(x) for x in version_str.split(".")[:2]]
                if major == 3 and 9 <= minor <= max_minor:
                    path = shutil.which(py) or py
                    return CheckResult("Python", True, version_str, path)
            except ValueError:
                continue
    return CheckResult(f"Python 3.9-3.{max_minor}", False, note="Required for Azure Functions runtime")


def check_node() -> CheckResult:
    ok, ver = _run(["node", "--version"])
    if ok:
        return CheckResult("Node.js", True, ver, shutil.which("node") or "")
    return CheckResult("Node.js", False, note="Needed for Azurite and TS server")


def check_func_tools() -> CheckResult:
    ok, ver = _run(["func", "--version"])
    if ok:
        return CheckResult("Azure Functions Core Tools", True, ver, shutil.which("func") or "")
    return CheckResult("Azure Functions Core Tools", False)


def check_azurite() -> CheckResult:
    path = shutil.which("azurite")
    if path:
        return CheckResult("Azurite", True, path=path)
    # Check if available via npm global
    ok, _ = _run(["npm", "list", "-g", "azurite", "--depth=0"], timeout=5)
    if ok:
        return CheckResult("Azurite", True, note="installed globally via npm")
    return CheckResult("Azurite", False)


def check_docker() -> CheckResult:
    ok, ver = _run(["docker", "--version"])
    if ok:
        return CheckResult("Docker", True, ver.split(",")[0] if "," in ver else ver, shutil.which("docker") or "")
    return CheckResult("Docker", False, note="Optional — needed for containerised testing")


def check_az_cli() -> CheckResult:
    ok, ver = _run(["az", "--version"], timeout=8)
    if ok:
        first_line = ver.split("\n")[0] if ver else ""
        return CheckResult("Azure CLI", True, first_line, shutil.which("az") or "")
    return CheckResult("Azure CLI", False, note="Optional — needed for cloud deploy/test")


def check_azd_cli() -> CheckResult:
    ok, ver = _run(["azd", "version"])
    if ok:
        return CheckResult("Azure Developer CLI", True, ver, shutil.which("azd") or "")
    return CheckResult("Azure Developer CLI", False, note="Optional — needed for azd up")


def check_git() -> CheckResult:
    ok, ver = _run(["git", "--version"])
    if ok:
        return CheckResult("Git", True, ver, shutil.which("git") or "")
    return CheckResult("Git", False)


def find_project_root() -> Path | None:
    """Walk up from CWD looking for Makefile + src/mcp-servers/."""
    current = Path.cwd()
    for _ in range(10):
        if (current / "Makefile").is_file() and (current / "src" / "mcp-servers").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


# ---------------------------------------------------------------------------
# Full scan
# ---------------------------------------------------------------------------


def scan_environment() -> EnvironmentReport:
    """Run all prerequisite checks and return a report."""
    report = EnvironmentReport()
    report.project_root = find_project_root()
    report.python_max_minor = detect_func_supported_python_max_minor()

    report.python = check_python(report.python_max_minor)
    report.node = check_node()
    report.func_tools = check_func_tools()
    report.azurite = check_azurite()
    report.docker = check_docker()
    report.az_cli = check_az_cli()
    report.azd_cli = check_azd_cli()
    report.git = check_git()

    # Derive issues and tips
    if not report.python.found:
        report.issues.append(f"No compatible Python (3.9-3.{report.python_max_minor}) found.")
        report.copilot_tips.append(COPILOT_TIPS["venv_fail"])
    if not report.func_tools.found:
        report.issues.append("Azure Functions Core Tools not installed.")
        report.copilot_tips.append(COPILOT_TIPS["func_not_found"])
    if not report.azurite.found:
        report.issues.append("Azurite not installed (needed for local Function host).")
        report.copilot_tips.append(COPILOT_TIPS["azurite_not_found"])
    if not report.project_root:
        report.issues.append("Could not find project root (Makefile + src/mcp-servers).")
    return report


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


def print_report(report: EnvironmentReport) -> None:
    """Pretty-print the environment report."""
    table = Table(title="Environment Check", show_lines=True)
    table.add_column("Component", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Details")

    checks = [
        report.python,
        report.node,
        report.func_tools,
        report.azurite,
        report.docker,
        report.az_cli,
        report.azd_cli,
        report.git,
    ]

    for c in checks:
        if c is None:
            continue
        status = "[success]✓[/success]" if c.found else "[error]✗[/error]"
        details = c.version or c.path or c.note or ""
        table.add_row(c.name, status, details)

    # Project root
    if report.project_root:
        table.add_row("Project Root", "[success]✓[/success]", str(report.project_root))
    else:
        table.add_row("Project Root", "[error]✗[/error]", "Not found — run from repo directory")

    console.print()
    console.print(table)

    if report.issues:
        console.print()
        console.print("[warning]⚠  Issues found:[/warning]")
        for issue in report.issues:
            console.print(f"  [warning]•[/warning] {issue}")

    if report.copilot_tips:
        console.print()
        for tip in report.copilot_tips:
            console.print(tip)
            console.print()


def is_ready(report: EnvironmentReport) -> bool:
    """Return True if minimum requirements are met for local MCP testing."""
    return bool(
        report.python and report.python.found and report.func_tools and report.func_tools.found and report.project_root
    )
