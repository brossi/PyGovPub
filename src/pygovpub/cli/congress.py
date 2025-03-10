"""
CLI commands for the Congress.gov API.

This module provides commands for interacting with the Congress.gov API,
including bills, members, and committees.
"""

import sys
from enum import Enum
from typing import Dict, List, Optional, Any

import typer
from rich.console import Console

from pygovpub.cli.output import (
    OutputFormat,
    get_output_format,
    output_json,
    output_text,
    output_xml,
    output_to_file
)

# Create Typer app
app = typer.Typer(
    help="Access Congress.gov API data",
    rich_markup_mode="rich"
)

# Create console for output
console = Console()


# API client functions (to be implemented when real API client is available)
def get_bill(bill_id: str, congress: Optional[int] = None, format: Optional[str] = None) -> Dict[str, Any]:
    """Get bill information from Congress.gov API."""
    # This is a stub function that would be replaced with actual API call
    return {
        "congress": congress or 117,
        "billType": bill_id[:2],
        "billNumber": bill_id[2:],
        "title": f"Example Bill {bill_id}",
        "introducedDate": "2023-01-01",
        "latestAction": {"text": "Introduced", "date": "2023-01-01"}
    }


def search_bills(
    query: str,
    congress: Optional[int] = None,
    limit: int = 10,
    offset: int = 0,
    format: Optional[str] = None
) -> Dict[str, Any]:
    """Search bills in Congress.gov API."""
    # This is a stub function that would be replaced with actual API call
    return {
        "bills": [
            {"billType": "hr", "billNumber": "1234", "title": f"Example Bill 1 matching '{query}'"},
            {"billType": "hr", "billNumber": "5678", "title": f"Example Bill 2 matching '{query}'"}
        ],
        "pagination": {"count": 2, "next": None}
    }


def get_member(member_id: str, format: Optional[str] = None) -> Dict[str, Any]:
    """Get member information from Congress.gov API."""
    # This is a stub function that would be replaced with actual API call
    return {
        "bioguideId": member_id,
        "firstName": "Test",
        "lastName": "Member",
        "party": "D",
        "state": "CA"
    }


def get_committee(committee_id: str, format: Optional[str] = None) -> Dict[str, Any]:
    """Get committee information from Congress.gov API."""
    # This is a stub function that would be replaced with actual API call
    return {
        "committeeId": committee_id,
        "name": f"Example Committee {committee_id}",
        "chamber": "House",
        "subcommittees": []
    }


# Bill subcommands
bill_app = typer.Typer()
app.add_typer(bill_app, name="bill", help="Access bill information")


@bill_app.command("get")
def bill_get(
    bill_id: str = typer.Argument(..., help="Bill ID (e.g., hr1234)"),
    congress: Optional[int] = typer.Option(None, "--congress", "-c", help="Congress number"),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (json, xml, text)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file")
):
    """Get information about a specific bill."""
    # Get bill data
    bill_data = get_bill(bill_id, congress, format)
    
    # Handle output
    if output:
        # Determine format and write to file
        output_format = get_output_format(format, output)
        output_to_file(bill_data, output, output_format)
    else:
        # Output to console
        output_format = get_output_format(format)
        if output_format == OutputFormat.JSON:
            output_json(bill_data)
        elif output_format == OutputFormat.XML:
            output_xml(bill_data)
        else:
            output_text(bill_data)


@bill_app.command("search")
def bill_search(
    query: str = typer.Argument(..., help="Search query"),
    congress: Optional[int] = typer.Option(None, "--congress", "-c", help="Congress number"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results"),
    offset: int = typer.Option(0, "--offset", help="Result offset for pagination"),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (json, xml, text)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file")
):
    """Search for bills that match a query."""
    # Search bills
    results = search_bills(query, congress, limit, offset, format)
    
    # Handle output
    if output:
        # Determine format and write to file
        output_format = get_output_format(format, output)
        output_to_file(results, output, output_format)
    else:
        # Output to console
        output_format = get_output_format(format)
        if output_format == OutputFormat.JSON:
            output_json(results)
        elif output_format == OutputFormat.XML:
            output_xml(results)
        else:
            output_text(results)


# Member subcommands
member_app = typer.Typer()
app.add_typer(member_app, name="member", help="Access member information")


@member_app.command("get")
def member_get(
    member_id: str = typer.Argument(..., help="Member ID (e.g., A000123)"),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (json, xml, text)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file")
):
    """Get information about a specific member."""
    # Get member data
    member_data = get_member(member_id, format)
    
    # Handle output
    if output:
        # Determine format and write to file
        output_format = get_output_format(format, output)
        output_to_file(member_data, output, output_format)
    else:
        # Output to console
        output_format = get_output_format(format)
        if output_format == OutputFormat.JSON:
            output_json(member_data)
        elif output_format == OutputFormat.XML:
            output_xml(member_data)
        else:
            output_text(member_data)


# Committee subcommands
committee_app = typer.Typer()
app.add_typer(committee_app, name="committee", help="Access committee information")


@committee_app.command("get")
def committee_get(
    committee_id: str = typer.Argument(..., help="Committee ID"),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (json, xml, text)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file")
):
    """Get information about a specific committee."""
    # Get committee data
    committee_data = get_committee(committee_id, format)
    
    # Handle output
    if output:
        # Determine format and write to file
        output_format = get_output_format(format, output)
        output_to_file(committee_data, output, output_format)
    else:
        # Output to console
        output_format = get_output_format(format)
        if output_format == OutputFormat.JSON:
            output_json(committee_data)
        elif output_format == OutputFormat.XML:
            output_xml(committee_data)
        else:
            output_text(committee_data)