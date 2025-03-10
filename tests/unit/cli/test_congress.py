"""
Unit tests for the Congress.gov CLI module.
"""
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, mock_open, call

import pytest
from typer.testing import CliRunner

from pygovpub.cli.congress import (
    app,
    get_bill,
    search_bills,
    get_member,
    get_committee,
    bill_get,
    bill_search,
    member_get,
    committee_get
)
from pygovpub.cli.output import OutputFormat


# Create a CLI runner for testing Typer apps
runner = CliRunner()


class TestCongressAPIFunctions:
    """Tests for the Congress.gov API client functions."""
    
    def test_get_bill(self):
        """Test getting a bill."""
        bill = get_bill("hr1234")
        
        assert isinstance(bill, dict)
        assert bill["billType"] == "hr"
        assert bill["billNumber"] == "1234"
        assert "title" in bill
        assert "introducedDate" in bill
        assert "latestAction" in bill
        
        # Test with congress parameter
        bill_with_congress = get_bill("hr1234", congress=118)
        assert bill_with_congress["congress"] == 118
        
        # Test with format parameter
        bill_with_format = get_bill("hr1234", format="json")
        assert isinstance(bill_with_format, dict)
    
    def test_search_bills(self):
        """Test searching bills."""
        results = search_bills("test")
        
        assert isinstance(results, dict)
        assert "bills" in results
        assert isinstance(results["bills"], list)
        assert len(results["bills"]) > 0
        assert "pagination" in results
        
        # Test with all parameters
        results_full = search_bills(
            "test", 
            congress=118, 
            limit=20, 
            offset=5, 
            format="json"
        )
        assert isinstance(results_full, dict)
    
    def test_get_member(self):
        """Test getting a member."""
        member = get_member("A000123")
        
        assert isinstance(member, dict)
        assert member["bioguideId"] == "A000123"
        assert "firstName" in member
        assert "lastName" in member
        assert "party" in member
        assert "state" in member
        
        # Test with format parameter
        member_with_format = get_member("A000123", format="json")
        assert isinstance(member_with_format, dict)
    
    def test_get_committee(self):
        """Test getting a committee."""
        committee = get_committee("HSAG")
        
        assert isinstance(committee, dict)
        assert committee["committeeId"] == "HSAG"
        assert "name" in committee
        assert "chamber" in committee
        assert "subcommittees" in committee
        
        # Test with format parameter
        committee_with_format = get_committee("HSAG", format="json")
        assert isinstance(committee_with_format, dict)


class TestCongressCLICommands:
    """Tests for the Congress.gov CLI commands."""
    
    def test_bill_get_command(self):
        """Test the bill get command."""
        mock_bill = {
            "congress": 117,
            "billType": "hr",
            "billNumber": "1234",
            "title": "Example Bill hr1234",
            "introducedDate": "2023-01-01",
            "latestAction": {"text": "Introduced", "date": "2023-01-01"}
        }
        
        # Test with default format (text)
        with patch("pygovpub.cli.congress.get_bill", return_value=mock_bill) as mock_get:
            with patch("pygovpub.cli.congress.output_text") as mock_output:
                result = runner.invoke(app, ["bill", "get", "hr1234"])
                assert result.exit_code == 0
                
                # Verify that get_bill was called with correct parameters
                mock_get.assert_called_once_with("hr1234", None, None)
                
                # Verify that output_text was called with bill
                mock_output.assert_called_once_with(mock_bill)
    
    def test_bill_get_command_with_congress(self):
        """Test the bill get command with congress parameter."""
        mock_bill = {
            "congress": 118,
            "billType": "hr",
            "billNumber": "1234",
            "title": "Example Bill hr1234",
            "introducedDate": "2023-01-01"
        }
        
        with patch("pygovpub.cli.congress.get_bill", return_value=mock_bill) as mock_get:
            with patch("pygovpub.cli.congress.output_text") as mock_output:
                result = runner.invoke(app, ["bill", "get", "hr1234", "--congress", "118"])
                assert result.exit_code == 0
                
                # Verify that get_bill was called with correct parameters
                mock_get.assert_called_once_with("hr1234", 118, None)
                
                # Verify that output_text was called with bill
                mock_output.assert_called_once_with(mock_bill)
    
    def test_bill_get_command_with_json_format(self):
        """Test the bill get command with JSON format."""
        mock_bill = {
            "congress": 117,
            "billType": "hr",
            "billNumber": "1234",
            "title": "Example Bill hr1234"
        }
        
        with patch("pygovpub.cli.congress.get_bill", return_value=mock_bill) as mock_get:
            with patch("pygovpub.cli.congress.output_json") as mock_output:
                result = runner.invoke(app, ["bill", "get", "hr1234", "--format", "json"])
                assert result.exit_code == 0
                
                # Verify that get_bill was called with correct parameters
                mock_get.assert_called_once_with("hr1234", None, "json")
                
                # Verify that output_json was called with bill
                mock_output.assert_called_once_with(mock_bill)
    
    def test_bill_get_command_with_file_output(self):
        """Test the bill get command with file output."""
        mock_bill = {
            "congress": 117,
            "billType": "hr",
            "billNumber": "1234",
            "title": "Example Bill hr1234"
        }
        
        with patch("pygovpub.cli.congress.get_bill", return_value=mock_bill) as mock_get:
            with patch("pygovpub.cli.congress.output_to_file") as mock_output:
                result = runner.invoke(app, ["bill", "get", "hr1234", "--output", "bill.json"])
                assert result.exit_code == 0
                
                # Verify that get_bill was called
                mock_get.assert_called_once()
                
                # Verify that output_to_file was called with correct parameters
                mock_output.assert_called_once()
                args, kwargs = mock_output.call_args
                assert args[0] == mock_bill
                assert args[1] == "bill.json"
                assert args[2] == OutputFormat.JSON
    
    def test_bill_search_command(self):
        """Test the bill search command."""
        mock_results = {
            "bills": [
                {"billType": "hr", "billNumber": "1234", "title": "Example Bill 1 matching 'health'"},
                {"billType": "hr", "billNumber": "5678", "title": "Example Bill 2 matching 'health'"}
            ],
            "pagination": {"count": 2, "next": None}
        }
        
        # Test with basic search
        with patch("pygovpub.cli.congress.search_bills", return_value=mock_results) as mock_search:
            with patch("pygovpub.cli.congress.output_text") as mock_output:
                result = runner.invoke(app, ["bill", "search", "health"])
                assert result.exit_code == 0
                
                # Verify that search_bills was called with correct parameters
                mock_search.assert_called_once_with("health", None, 10, 0, None)
                
                # Verify that output_text was called with results
                mock_output.assert_called_once_with(mock_results)
    
    def test_bill_search_command_with_all_options(self):
        """Test the bill search command with all options."""
        mock_results = {
            "bills": [
                {"billType": "hr", "billNumber": "1234", "title": "Example Bill 1 matching 'health'"}
            ],
            "pagination": {"count": 1, "next": None}
        }
        
        # Test with all options
        with patch("pygovpub.cli.congress.search_bills", return_value=mock_results) as mock_search:
            with patch("pygovpub.cli.congress.output_json") as mock_output:
                result = runner.invoke(app, [
                    "bill", "search", "health",
                    "--congress", "118",
                    "--limit", "20",
                    "--offset", "5",
                    "--format", "json"
                ])
                assert result.exit_code == 0
                
                # Verify that search_bills was called with correct parameters
                mock_search.assert_called_once_with("health", 118, 20, 5, "json")
                
                # Verify that output_json was called with results
                mock_output.assert_called_once_with(mock_results)
    
    def test_bill_search_command_with_file_output(self):
        """Test the bill search command with file output."""
        mock_results = {
            "bills": [
                {"billType": "hr", "billNumber": "1234", "title": "Example Bill 1 matching 'health'"}
            ],
            "pagination": {"count": 1, "next": None}
        }
        
        with patch("pygovpub.cli.congress.search_bills", return_value=mock_results) as mock_search:
            with patch("pygovpub.cli.congress.output_to_file") as mock_output:
                result = runner.invoke(app, [
                    "bill", "search", "health",
                    "--output", "search_results.json"
                ])
                assert result.exit_code == 0
                
                # Verify that search_bills was called
                mock_search.assert_called_once()
                
                # Verify that output_to_file was called with correct parameters
                mock_output.assert_called_once()
                args, kwargs = mock_output.call_args
                assert args[0] == mock_results
                assert args[1] == "search_results.json"
                assert args[2] == OutputFormat.JSON
    
    def test_member_get_command(self):
        """Test the member get command."""
        mock_member = {
            "bioguideId": "A000123",
            "firstName": "Test",
            "lastName": "Member",
            "party": "D",
            "state": "CA"
        }
        
        # Test with default format (text)
        with patch("pygovpub.cli.congress.get_member", return_value=mock_member) as mock_get:
            with patch("pygovpub.cli.congress.output_text") as mock_output:
                result = runner.invoke(app, ["member", "get", "A000123"])
                assert result.exit_code == 0
                
                # Verify that get_member was called with correct parameters
                mock_get.assert_called_once_with("A000123", None)
                
                # Verify that output_text was called with member
                mock_output.assert_called_once_with(mock_member)
    
    def test_member_get_command_with_xml_format(self):
        """Test the member get command with XML format."""
        mock_member = {
            "bioguideId": "A000123",
            "firstName": "Test",
            "lastName": "Member"
        }
        
        with patch("pygovpub.cli.congress.get_member", return_value=mock_member) as mock_get:
            with patch("pygovpub.cli.congress.output_xml") as mock_output:
                result = runner.invoke(app, ["member", "get", "A000123", "--format", "xml"])
                assert result.exit_code == 0
                
                # Verify that get_member was called with correct parameters
                mock_get.assert_called_once_with("A000123", "xml")
                
                # Verify that output_xml was called with member
                mock_output.assert_called_once_with(mock_member)
    
    def test_committee_get_command(self):
        """Test the committee get command."""
        mock_committee = {
            "committeeId": "HSAG",
            "name": "Example Committee HSAG",
            "chamber": "House",
            "subcommittees": []
        }
        
        # Test with default format (text)
        with patch("pygovpub.cli.congress.get_committee", return_value=mock_committee) as mock_get:
            with patch("pygovpub.cli.congress.output_text") as mock_output:
                result = runner.invoke(app, ["committee", "get", "HSAG"])
                assert result.exit_code == 0
                
                # Verify that get_committee was called with correct parameters
                mock_get.assert_called_once_with("HSAG", None)
                
                # Verify that output_text was called with committee
                mock_output.assert_called_once_with(mock_committee)
    
    def test_committee_get_command_with_json_format_and_file_output(self):
        """Test the committee get command with JSON format and file output."""
        mock_committee = {
            "committeeId": "HSAG",
            "name": "Example Committee HSAG",
            "chamber": "House",
            "subcommittees": []
        }
        
        with patch("pygovpub.cli.congress.get_committee", return_value=mock_committee) as mock_get:
            with patch("pygovpub.cli.congress.output_to_file") as mock_output:
                result = runner.invoke(app, [
                    "committee", "get", "HSAG",
                    "--format", "json",
                    "--output", "committee.json"
                ])
                assert result.exit_code == 0
                
                # Verify that get_committee was called with correct parameters
                mock_get.assert_called_once_with("HSAG", "json")
                
                # Verify that output_to_file was called with correct parameters
                mock_output.assert_called_once()
                args, kwargs = mock_output.call_args
                assert args[0] == mock_committee
                assert args[1] == "committee.json"
                assert args[2] == OutputFormat.JSON