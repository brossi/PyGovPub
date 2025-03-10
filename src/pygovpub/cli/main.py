"""
Main CLI entry point for PyGovPub.

This module provides the main CLI command and subcommands.
"""

import importlib.metadata
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pygovpub.cli.config import (
    check_required_config,
    get_config_value,
    list_config,
    set_config_value
)

# Version
try:
    __version__ = importlib.metadata.version("pygovpub")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.0"  # Default version if not installed

# Create Typer app
app = typer.Typer(
    help="PyGovPub CLI: Access U.S. Federal Government data through Congress.gov and GovInfo.gov APIs.",
    rich_markup_mode="rich"
)

# Create console for output
console = Console()


@app.callback()
def callback():
    """PyGovPub CLI: Access U.S. Federal Government data."""
    pass


@app.command()
def version():
    """Show the version of PyGovPub."""
    text = Text()
    text.append("PyGovPub ", style="bold cyan")
    text.append(f"version ", style="dim")
    text.append(f"{__version__}", style="bold")
    console.print(text)


@app.command()
def status():
    """Show the status of PyGovPub services and configuration."""
    # Check configuration
    missing_config = check_required_config()
    
    # Check API connectivity
    from pygovpub.diagnostics.health import check_api_connectivity
    
    # Create status panel
    panel = Panel.fit(
        Text("Checking PyGovPub status..."),
        title="PyGovPub Status",
        border_style="cyan"
    )
    console.print(panel)
    
    # Display configuration status
    if missing_config:
        console.print("[bold yellow]Configuration Warning:[/bold yellow]")
        console.print("The following configuration values are missing:")
        for key in missing_config:
            console.print(f"  - [cyan]{key}[/cyan]")
        console.print()
        console.print("You can set these values using:")
        for key in missing_config:
            console.print(f"  [dim]pygovpub config set {key} <value>[/dim]")
        console.print()
    else:
        console.print("[bold green]Configuration:[/bold green] Valid")
    
    # Display API status (if keys are configured)
    if not any(key.startswith("api_keys") for key in missing_config):
        console.print("[bold]API Status:[/bold]")
        with console.status("[cyan]Checking API connectivity...[/cyan]"):
            apis = check_api_connectivity()
        
        # Create table for API status
        table = Table(show_header=True)
        table.add_column("API", style="cyan")
        table.add_column("Status")
        table.add_column("Details")
        
        for api in apis:
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
                
            table.add_row(api_name, status_str, details)
        
        console.print(table)


# Config subcommands
config_app = typer.Typer()
app.add_typer(config_app, name="config", help="Manage PyGovPub configuration")


@config_app.command("list")
def config_list():
    """List all configuration values."""
    list_config()


@config_app.command("get")
def config_get(key: str):
    """Get a configuration value."""
    value = get_config_value(key)
    if value is None:
        console.print(f"[yellow]Config key '{key}' not found[/yellow]")
    else:
        # Mask API keys for security
        if key.startswith("api_keys.") and value:
            display_value = "********" + value[-4:] if len(value) > 4 else "********"
        else:
            display_value = value
        
        console.print(f"{key} = {display_value}")


@config_app.command("set")
def config_set(key: str, value: str):
    """Set a configuration value."""
    try:
        set_config_value(key, value)
        console.print(f"[green]Config value '{key}' set successfully[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


# Import other commands
from pygovpub.cli.health import app as health_app
app.add_typer(health_app, name="health", help="Check the health of PyGovPub SDK")

from pygovpub.cli.congress import app as congress_app
app.add_typer(congress_app, name="congress", help="Access Congress.gov API data")

from pygovpub.cli.govinfo import app as govinfo_app
app.add_typer(govinfo_app, name="govinfo", help="Access GovInfo.gov API data")

from pygovpub.cli.schema_monitor import create_parser as schema_parser
@app.command("schema")
def schema(args: Optional[List[str]] = typer.Argument(None)):
    """Manage API schemas."""
    # Pass through to schema_monitor command
    parser = schema_parser()
    parsed_args = parser.parse_args(args or [])
    
    if hasattr(parsed_args, "func"):
        parsed_args.func(parsed_args)
    else:
        parser.print_help()

# Mock server command
@app.command("mock")
def mock(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to run on"),
    log_level: str = typer.Option("info", "--log-level", help="Log level"),
    latency: Optional[int] = typer.Option(None, "--latency", help="Simulated latency in ms"),
    rate_limits: bool = typer.Option(False, "--rate-limits", help="Simulate rate limits"),
    record: bool = typer.Option(False, "--record", help="Record real API responses"),
    fixtures: Optional[str] = typer.Option(None, "--fixtures", help="Path to fixtures directory")
):
    """Run the mock server for testing."""
    # Import mock_server dynamically to avoid circular imports
    from pygovpub.cli.mock_server import start_mock_server_cli
    
    # Set up command-line arguments
    sys.argv = ["pygovpub-mock"]
    if host != "127.0.0.1":
        sys.argv.extend(["--host", host])
    if port != 8000:
        sys.argv.extend(["--port", str(port)])
    if log_level != "info":
        sys.argv.extend(["--log-level", log_level])
    if latency is not None:
        sys.argv.extend(["--latency", str(latency)])
    if rate_limits:
        sys.argv.append("--rate-limits")
    if record:
        sys.argv.append("--record")
    if fixtures is not None:
        sys.argv.extend(["--fixtures", fixtures])
    
    # Run the mock server
    start_mock_server_cli()


# Entry point function
def main():
    """Main CLI entry point."""
    app()