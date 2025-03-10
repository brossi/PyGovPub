"""
Command-line interface for managing PyGovPub configuration.

This module provides commands for:
- Viewing current configuration
- Updating configuration settings
- Managing feature flags
- Managing API credentials
- Switching environment profiles
"""

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pygovpub.config import (
    ConfigFormat,
    ConfigManager,
    ConfigValidationError,
    Environment,
    FeatureFlag,
    get_config_manager,
)


# Create console for output
console = Console()


def get_config_command(args: argparse.Namespace) -> None:
    """Get configuration value."""
    manager = get_config_manager()
    
    if args.key.startswith("feature."):
        # Get feature flag
        flag_name = args.key.split(".", 1)[1]
        try:
            flag = FeatureFlag(flag_name)
            value = manager.get_feature_flag(flag)
            console.print(f"[green]{flag_name}[/green] = [blue]{value}[/blue]")
        except ValueError:
            console.print(f"[red]Unknown feature flag: {flag_name}[/red]")
            console.print(f"Available flags: {', '.join(f.value for f in FeatureFlag)}")
    
    elif args.key.startswith("api."):
        # Get API key
        api_name = args.key.split(".", 1)[1]
        
        # Don't show the actual key for security
        value = manager.get_api_key(api_name)
        if value:
            masked_value = "********" + value[-4:] if len(value) > 4 else "********"
            console.print(f"[green]API key for {api_name}[/green] = [blue]{masked_value}[/blue]")
        else:
            console.print(f"[yellow]No API key set for {api_name}[/yellow]")
    
    elif args.key.startswith("url."):
        # Get API base URL
        api_name = args.key.split(".", 1)[1]
        value = manager.get_api_base_url(api_name)
        if value:
            console.print(f"[green]API base URL for {api_name}[/green] = [blue]{value}[/blue]")
        else:
            console.print(f"[yellow]No API base URL set for {api_name}[/yellow]")
    
    elif args.key.startswith("option."):
        # Get option
        option_name = args.key.split(".", 1)[1]
        value = manager.get_option(option_name)
        if value is not None:
            console.print(f"[green]{option_name}[/green] = [blue]{value}[/blue]")
        else:
            console.print(f"[yellow]Option not set: {option_name}[/yellow]")
    
    elif args.key == "environment":
        # Get environment
        console.print(f"[green]Environment[/green] = [blue]{manager.environment.value}[/blue]")
    
    else:
        console.print(f"[red]Unknown configuration key: {args.key}[/red]")
        console.print("Keys should be in format: 'feature.<name>', 'api.<name>', 'url.<name>', 'option.<name>', or 'environment'")


def set_config_command(args: argparse.Namespace) -> None:
    """Set configuration value."""
    manager = get_config_manager()
    
    if args.key.startswith("feature."):
        # Set feature flag
        flag_name = args.key.split(".", 1)[1]
        try:
            flag = FeatureFlag(flag_name)
            value = args.value.lower() in ("true", "yes", "1", "on")
            manager.set_feature_flag(flag, value)
            console.print(f"[green]Feature flag {flag_name}[/green] set to [blue]{value}[/blue]")
        except ValueError:
            console.print(f"[red]Unknown feature flag: {flag_name}[/red]")
            console.print(f"Available flags: {', '.join(f.value for f in FeatureFlag)}")
    
    elif args.key.startswith("api."):
        # Set API key
        api_name = args.key.split(".", 1)[1]
        manager.set_api_key(api_name, args.value)
        console.print(f"[green]API key for {api_name}[/green] updated")
    
    elif args.key.startswith("url."):
        # Set API base URL
        api_name = args.key.split(".", 1)[1]
        manager.set_api_base_url(api_name, args.value)
        console.print(f"[green]API base URL for {api_name}[/green] set to [blue]{args.value}[/blue]")
    
    elif args.key.startswith("option."):
        # Set option
        option_name = args.key.split(".", 1)[1]
        
        # Try to convert value to appropriate type
        value: Any = args.value
        if value.lower() in ("true", "yes", "1", "on"):
            value = True
        elif value.lower() in ("false", "no", "0", "off"):
            value = False
        else:
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
        
        manager.set_option(option_name, value)
        console.print(f"[green]{option_name}[/green] set to [blue]{value}[/blue]")
    
    elif args.key == "environment":
        # Set environment
        try:
            env = Environment.from_string(args.value)
            manager.environment = env
            console.print(f"[green]Environment[/green] set to [blue]{env.value}[/blue]")
            
            # Ask if they want to switch profile too
            should_switch = input("Do you want to switch to this environment profile? [y/N] ")
            if should_switch.lower() in ("y", "yes"):
                manager.switch_profile(env)
                console.print(f"[green]Switched to {env.value} profile[/green]")
        except ValueError:
            console.print(f"[red]Unknown environment: {args.value}[/red]")
            console.print(f"Available environments: {', '.join(e.value for e in Environment)}")
    
    else:
        console.print(f"[red]Unknown configuration key: {args.key}[/red]")
        console.print("Keys should be in format: 'feature.<name>', 'api.<name>', 'url.<name>', 'option.<name>', or 'environment'")
        return
    
    # Save configuration
    if args.save:
        manager.save_to_file()
        console.print("[green]Configuration saved[/green]")


def list_config_command(args: argparse.Namespace) -> None:
    """List configuration values."""
    manager = get_config_manager()
    
    if args.section == "all" or args.section == "features":
        # List feature flags
        table = Table(title="Feature Flags")
        table.add_column("Name", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Description", style="dim")
        
        for flag in FeatureFlag:
            value = manager.get_feature_flag(flag)
            description = ""
            if flag == FeatureFlag.CACHE_ENABLED:
                description = "Enable caching of API responses"
            elif flag == FeatureFlag.ADVANCED_ROUTING:
                description = "Enable advanced request routing"
            elif flag == FeatureFlag.DEBUG_MODE:
                description = "Enable debug mode for detailed logging"
            
            table.add_row(
                flag.value,
                str(value),
                description
            )
        
        console.print(table)
    
    if args.section == "all" or args.section == "api":
        # List API keys and URLs
        table = Table(title="API Configuration")
        table.add_column("API", style="cyan")
        table.add_column("Key", style="green")
        table.add_column("Base URL", style="blue")
        
        for api in ("congress", "govinfo"):
            key = manager.get_api_key(api)
            url = manager.get_api_base_url(api)
            
            # Mask API key for security
            masked_key = "********" + key[-4:] if key and len(key) > 4 else "********" if key else "(not set)"
            
            table.add_row(
                api,
                masked_key,
                url or "(not set)"
            )
        
        console.print(table)
    
    if args.section == "all" or args.section == "options":
        # List options
        table = Table(title="Options")
        table.add_column("Name", style="cyan")
        table.add_column("Value", style="green")
        
        for option, value in manager._options.items():
            table.add_row(
                option,
                str(value)
            )
        
        console.print(table)
    
    if args.section == "all" or args.section == "environment":
        # Show environment
        env_panel = Panel(
            f"Current environment: [bold]{manager.environment.value}[/bold]",
            title="Environment"
        )
        console.print(env_panel)


def validate_config_command(args: argparse.Namespace) -> None:
    """Validate configuration."""
    manager = get_config_manager()
    
    try:
        manager.validate()
        console.print("[green]Configuration is valid[/green]")
    except ConfigValidationError as e:
        console.print(f"[red]Configuration validation failed:[/red]\n{str(e)}")

        if args.fix:
            console.print("\n[yellow]Attempting to fix issues...[/yellow]")
            
            # Simple fixes based on the error message
            if "API key missing for:" in str(e):
                console.print("[yellow]Fix: Please set API keys manually using the 'config set' command[/yellow]")
                console.print("Example: pygovpub-config set api.congress YOUR_API_KEY --save")
                console.print("Example: pygovpub-config set api.govinfo YOUR_API_KEY --save")
            
            if "API base URL missing for:" in str(e):
                for api in ("congress", "govinfo"):
                    if manager.get_api_base_url(api) == "":
                        if api == "congress":
                            manager.set_api_base_url(api, "https://api.congress.gov/v3")
                            console.print(f"[green]Fixed: Set Congress.gov API URL to default[/green]")
                        elif api == "govinfo":
                            manager.set_api_base_url(api, "https://api.govinfo.gov")
                            console.print(f"[green]Fixed: Set GovInfo.gov API URL to default[/green]")
            
            if "Required option missing:" in str(e):
                if "default_format" not in manager._options:
                    manager.set_option("default_format", "text")
                    console.print("[green]Fixed: Set default_format to 'text'[/green]")
                
                if "cache_ttl" not in manager._options:
                    manager.set_option("cache_ttl", 3600)
                    console.print("[green]Fixed: Set cache_ttl to 3600 seconds[/green]")
            
            # Save fixed configuration if requested
            if args.save:
                manager.save_to_file()
                console.print("[green]Fixed configuration saved[/green]")


def switch_profile_command(args: argparse.Namespace) -> None:
    """Switch environment profile."""
    manager = get_config_manager()
    
    try:
        env = Environment.from_string(args.profile)
        manager.switch_profile(env)
        console.print(f"[green]Switched to {env.value} profile[/green]")
        
        # Show current feature flags
        table = Table(title=f"{env.value.capitalize()} Profile Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        # Add environment
        table.add_row("Environment", env.value)
        
        # Add feature flags
        for flag in FeatureFlag:
            value = manager.get_feature_flag(flag)
            table.add_row(f"Feature: {flag.value}", str(value))
        
        # Add key options
        for option in ("default_format", "cache_ttl", "log_level"):
            value = manager.get_option(option)
            if value is not None:
                table.add_row(f"Option: {option}", str(value))
        
        console.print(table)
        
        # Save if requested
        if args.save:
            manager.save_to_file()
            console.print("[green]Configuration saved[/green]")
    
    except ValueError:
        console.print(f"[red]Unknown profile: {args.profile}[/red]")
        console.print(f"Available profiles: {', '.join(e.value for e in Environment)}")


def export_config_command(args: argparse.Namespace) -> None:
    """Export configuration to a file."""
    manager = get_config_manager()
    
    if not args.format:
        # Try to determine format from file extension
        try:
            extension = Path(args.file).suffix
            format_type = ConfigFormat.from_extension(extension)
        except (ValueError, AttributeError):
            format_type = ConfigFormat.JSON
    else:
        try:
            format_type = ConfigFormat(args.format.lower())
        except ValueError:
            console.print(f"[red]Unknown format: {args.format}[/red]")
            console.print(f"Available formats: {', '.join(f.value for f in ConfigFormat)}")
            return
    
    try:
        # Save configuration to specified file
        manager.save_to_file(args.file)
        console.print(f"[green]Configuration exported to {args.file}[/green]")
    except Exception as e:
        console.print(f"[red]Failed to export configuration: {e}[/red]")


def import_config_command(args: argparse.Namespace) -> None:
    """Import configuration from a file."""
    manager = get_config_manager()
    
    try:
        # Load configuration from specified file
        manager.load_from_file(args.file)
        console.print(f"[green]Configuration imported from {args.file}[/green]")
        
        # Save if requested
        if args.save:
            manager.save_to_file()
            console.print("[green]Imported configuration saved[/green]")
        
        # Validate if requested
        if args.validate:
            try:
                manager.validate()
                console.print("[green]Imported configuration is valid[/green]")
            except ConfigValidationError as e:
                console.print(f"[yellow]Warning: Imported configuration has validation issues:[/yellow]\n{str(e)}")
    
    except Exception as e:
        console.print(f"[red]Failed to import configuration: {e}[/red]")


def init_config_command(args: argparse.Namespace) -> None:
    """Initialize configuration with defaults."""
    manager = get_config_manager()
    
    # Check if configuration exists
    config_path = manager.get_config_file_path()
    if config_path.exists() and not args.force:
        console.print(f"[yellow]Configuration file already exists at {config_path}[/yellow]")
        should_continue = input("Do you want to overwrite it? [y/N] ")
        if should_continue.lower() not in ("y", "yes"):
            console.print("[yellow]Initialization cancelled[/yellow]")
            return
    
    # Set environment based on args
    if args.environment:
        try:
            env = Environment.from_string(args.environment)
            manager.environment = env
            manager.switch_profile(env)
            console.print(f"[green]Set environment to {env.value}[/green]")
        except ValueError:
            console.print(f"[red]Unknown environment: {args.environment}[/red]")
            console.print(f"Available environments: {', '.join(e.value for e in Environment)}")
            return
    
    # Set API keys if provided
    if args.congress_key:
        manager.set_api_key("congress", args.congress_key)
        console.print("[green]Set Congress.gov API key[/green]")
    
    if args.govinfo_key:
        manager.set_api_key("govinfo", args.govinfo_key)
        console.print("[green]Set GovInfo.gov API key[/green]")
    
    # Save configuration
    manager.save_to_file()
    console.print(f"[green]Configuration initialized and saved to {config_path}[/green]")


def main() -> None:
    """Run the configuration CLI."""
    parser = argparse.ArgumentParser(description="PyGovPub Configuration Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Get command
    get_parser = subparsers.add_parser("get", help="Get configuration value")
    get_parser.add_argument("key", help="Configuration key (e.g., 'feature.cache_enabled', 'api.congress', 'environment')")
    
    # Set command
    set_parser = subparsers.add_parser("set", help="Set configuration value")
    set_parser.add_argument("key", help="Configuration key (e.g., 'feature.cache_enabled', 'api.congress', 'environment')")
    set_parser.add_argument("value", help="Value to set")
    set_parser.add_argument("--save", action="store_true", help="Save configuration to file")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List configuration values")
    list_parser.add_argument("section", nargs="?", default="all", choices=["all", "features", "api", "options", "environment"], help="Section to list")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration")
    validate_parser.add_argument("--fix", action="store_true", help="Try to fix validation issues")
    validate_parser.add_argument("--save", action="store_true", help="Save fixed configuration to file")
    
    # Switch profile command
    switch_parser = subparsers.add_parser("switch", help="Switch environment profile")
    switch_parser.add_argument("profile", help="Profile to switch to (development, test, production)")
    switch_parser.add_argument("--save", action="store_true", help="Save configuration to file")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export configuration to a file")
    export_parser.add_argument("file", help="File to export to")
    export_parser.add_argument("--format", choices=["json", "yaml", "env"], help="Format to export as (defaults to file extension)")
    
    # Import command
    import_parser = subparsers.add_parser("import", help="Import configuration from a file")
    import_parser.add_argument("file", help="File to import from")
    import_parser.add_argument("--save", action="store_true", help="Save imported configuration to default file")
    import_parser.add_argument("--validate", action="store_true", help="Validate imported configuration")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize configuration with defaults")
    init_parser.add_argument("--environment", choices=["development", "test", "production"], help="Environment to initialize")
    init_parser.add_argument("--congress-key", help="Congress.gov API key")
    init_parser.add_argument("--govinfo-key", help="GovInfo.gov API key")
    init_parser.add_argument("--force", action="store_true", help="Force initialization even if configuration exists")
    
    args = parser.parse_args()
    
    if args.command == "get":
        get_config_command(args)
    elif args.command == "set":
        set_config_command(args)
    elif args.command == "list":
        list_config_command(args)
    elif args.command == "validate":
        validate_config_command(args)
    elif args.command == "switch":
        switch_profile_command(args)
    elif args.command == "export":
        export_config_command(args)
    elif args.command == "import":
        import_config_command(args)
    elif args.command == "init":
        init_config_command(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()