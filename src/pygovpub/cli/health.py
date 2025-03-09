"""
Command-line interface for PyGovPub SDK health checks.

This module provides a CLI for running health checks on PyGovPub SDK
installations, verifying API connections, and validating configurations.
"""

import json as json_lib
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pygovpub.diagnostics.health import run_health_check


# Create Typer app
app = typer.Typer(
    help="Check the health of PyGovPub SDK installation and connections.",
    rich_markup_mode="rich"
)

console = Console()


class OutputFormat(str, Enum):
    """Output format options."""
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"


def display_json_report(report: Dict[str, Any]) -> None:
    """Display the report in JSON format."""
    console.print_json(json_lib.dumps(report))


def display_markdown_report(report: Dict[str, Any]) -> None:
    """Display the report in Markdown format."""
    md_lines = []
    
    # Header
    md_lines.append(f"# PyGovPub Health Report")
    md_lines.append(f"\nTime: {report['timestamp']}")
    md_lines.append(f"Status: **{report['status'].upper()}**")
    md_lines.append(f"Version: {report['version']}")
    
    # APIs
    md_lines.append(f"\n## APIs")
    for api in report["apis"]:
        status_marker = "✅" if api["status"] == "connected" else "❌"
        md_lines.append(f"\n### {api['name']} {status_marker}")
        
        if api["status"] == "connected":
            md_lines.append(f"- Status: Connected")
            md_lines.append(f"- Latency: {api['latency_ms']}ms")
        elif api["status"] == "rate_limited":
            md_lines.append(f"- Status: Rate Limited")
            md_lines.append(f"- Message: {api.get('message', 'No details')}")
            if "retry_after" in api:
                md_lines.append(f"- Retry After: {api['retry_after']} seconds")
        else:
            md_lines.append(f"- Status: Error")
            md_lines.append(f"- Message: {api.get('message', 'No details')}")
    
    # Configuration
    md_lines.append(f"\n## Configuration")
    config = report["configuration"]
    status_marker = "✅" if config["valid"] else "❌"
    md_lines.append(f"\nStatus: {status_marker}")
    md_lines.append(f"Environment: {config['environment']}")
    
    if not config["valid"]:
        md_lines.append("\n### Issues")
        for issue in config["issues"]:
            md_lines.append(f"- {issue}")
            
    # System Information
    md_lines.append(f"\n## System Information")
    system = report["system"]
    md_lines.append(f"\n### Python Environment")
    md_lines.append(f"- Version: {system['python_version']}")
    md_lines.append(f"- OS: {system['os']['system']} {system['os']['release']} ({system['os']['machine']})")
    
    if "memory" in system:
        memory = system["memory"]
        md_lines.append(f"\n### Memory")
        md_lines.append(f"- Total: {memory['total_gb']} GB")
        md_lines.append(f"- Available: {memory['available_gb']} GB")
        md_lines.append(f"- Used: {memory['percent_used']}%")
    
    md_lines.append(f"\n### Packages")
    for pkg, version in system["packages"].items():
        md_lines.append(f"- {pkg}: {version}")
    
    # Performance
    md_lines.append(f"\n## Performance")
    perf = report["performance"]
    md_lines.append(f"- Memory Usage: {perf['memory_usage_mb']} MB")
    md_lines.append(f"- CPU Usage: {perf['cpu_percent']}%")
    
    if perf["response_times_ms"]:
        md_lines.append(f"\n### Response Times")
        for api, time_ms in perf["response_times_ms"].items():
            md_lines.append(f"- {api}: {time_ms}ms")
    
    md_content = "\n".join(md_lines)
    console.print(Markdown(md_content))


def display_text_report(report: Dict[str, Any], verbose: bool = False) -> None:
    """Display the report in rich text format."""
    # Status panel with appropriate color
    status = report["status"].upper()
    status_color = {
        "healthy": "green",
        "degraded": "yellow",
        "unhealthy": "red",
        "critical": "bright_red"
    }.get(report["status"], "white")
    
    status_text = Text(f"Status: {status}", style=status_color)
    version_text = Text(f"Version: {report['version']}")
    timestamp_text = Text(f"Time: {report['timestamp']}")
    
    status_panel = Panel.fit(
        Text.assemble(status_text, "\n", version_text, "\n", timestamp_text),
        title="PyGovPub Health Report",
        border_style=status_color
    )
    console.print(status_panel)
    
    # API Status Table
    api_table = Table(title="API Status", show_header=True, header_style="bold")
    api_table.add_column("API", style="cyan")
    api_table.add_column("Status")
    api_table.add_column("Details")
    
    for api in report["apis"]:
        api_name = api["name"]
        
        if api["status"] == "connected":
            status_str = Text("Connected", style="green")
            details = Text(f"Latency: {api['latency_ms']}ms")
        elif api["status"] == "rate_limited":
            status_str = Text("Rate Limited", style="yellow")
            retry = f", Retry after: {api['retry_after']}s" if "retry_after" in api else ""
            details = Text(f"{api.get('message', 'No details')}{retry}")
        else:
            status_str = Text("Error", style="red")
            details = Text(api.get('message', 'No details'))
            
        api_table.add_row(api_name, status_str, details)
    
    console.print(api_table)
    
    # Configuration Panel
    config = report["configuration"]
    config_valid = config["valid"]
    config_color = "green" if config_valid else "red"
    
    config_content = [
        Text(f"Environment: {config['environment']}"),
        Text(f"Status: {'Valid' if config_valid else 'Invalid'}", style=config_color)
    ]
    
    if not config_valid and config["issues"]:
        config_content.append(Text("\nIssues:", style="bold"))
        for issue in config["issues"]:
            config_content.append(Text(f"  - {issue}", style="red"))
    
    config_panel = Panel(
        Text.assemble(*[Text("\n") if i > 0 else Text("") + item for i, item in enumerate(config_content)]),
        title="Configuration",
        border_style=config_color
    )
    console.print(config_panel)
    
    # System Information
    system = report["system"]
    sys_text = [
        Text(f"Python: {system['python_version']}"),
        Text(f"OS: {system['os']['system']} {system['os']['release']} ({system['os']['machine']})")
    ]
    
    # Only show package details in verbose mode or if there are issues
    if verbose or not config_valid:
        sys_text.append(Text("\nKey Packages:", style="bold"))
        for pkg in ["pygovpub", "requests", "aiohttp", "fastapi"]:
            if pkg in system["packages"]:
                sys_text.append(Text(f"  {pkg}: {system['packages'][pkg]}"))
    
    system_panel = Panel(
        Text.assemble(*[Text("\n") if i > 0 else Text("") + item for i, item in enumerate(sys_text)]),
        title="System Information"
    )
    console.print(system_panel)
    
    # Performance Panel (only in verbose mode)
    if verbose:
        perf = report["performance"]
        perf_text = [
            Text(f"Memory Usage: {perf['memory_usage_mb']} MB"),
            Text(f"CPU Usage: {perf['cpu_percent']}%")
        ]
        
        if perf["response_times_ms"]:
            perf_text.append(Text("\nResponse Times:", style="bold"))
            for api, time_ms in perf["response_times_ms"].items():
                perf_text.append(Text(f"  {api}: {time_ms}ms"))
                
        perf_panel = Panel(
            Text.assemble(*[Text("\n") if i > 0 else Text("") + item for i, item in enumerate(perf_text)]),
            title="Performance Metrics"
        )
        console.print(perf_panel)


@app.command()
def check(
    format: OutputFormat = typer.Option(
        OutputFormat.TEXT,
        "--format",
        "-f",
        help="Output format [text|json|markdown]"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="File to write output to"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed information"
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Show only critical information"
    ),
    json: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format (shorthand for --format json)"
    )
) -> None:
    """
    Run a comprehensive health check on the PyGovPub SDK.
    
    This command checks API connectivity, configuration validity,
    and system environment to ensure the SDK is properly set up.
    
    Exit codes:
    0 - Healthy
    1 - Unhealthy or critical issues detected
    2 - Error running health check
    """
    try:
        # Handle --json shorthand
        if json:
            format = OutputFormat.JSON
            
        # Run the health check
        with console.status("[bold cyan]Running health check...", spinner="dots") as status:
            report = run_health_check()
            status.update("[bold green]Health check complete!")
        
        # If output file is specified, redirect output
        if output:
            # Create a file console
            file_console = Console(file=open(output, "w", encoding="utf-8"), width=100)
            
            # Save the original console
            original_console = console
            # Replace with file console temporarily
            globals()["console"] = file_console
            
            # Display based on format
            if format == OutputFormat.JSON:
                file_console.print_json(json_lib.dumps(report))
            elif format == OutputFormat.MARKDOWN:
                display_markdown_report(report)
            else:
                display_text_report(report, verbose)
                
            # Close the file
            file_console.file.close()
            
            # Restore the original console
            globals()["console"] = original_console
            console.print(f"Report saved to [cyan]{output}[/cyan]")
        else:
            # Display to console based on format
            if format == OutputFormat.JSON:
                display_json_report(report)
            elif format == OutputFormat.MARKDOWN:
                display_markdown_report(report)
            else:
                display_text_report(report, verbose)
            
        # Exit with appropriate code based on status
        if report["status"] in ["unhealthy", "critical"]:
            sys.exit(1)
            
    except Exception as e:
        console.print(f"[bold red]Error running health check:[/bold red] {str(e)}")
        sys.exit(2)


def main() -> None:
    """Main entry point for the health CLI."""
    app()


if __name__ == "__main__":
    main()