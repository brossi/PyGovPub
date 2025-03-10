"""
Unit tests for the GovInfo.gov CLI module.
"""
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, mock_open, call

import pytest
from typer.testing import CliRunner

from pygovpub.cli.govinfo import (
    app,
    get_collections, 
    get_collection, 
    get_package, 
    search_packages, 
    download_package,
    collection_list,
    collection_get,
    package_get,
    package_search,
    package_download
)
from pygovpub.cli.output import OutputFormat


# Create a CLI runner for testing Typer apps
runner = CliRunner()


class TestGovInfoAPIFunctions:
    """Tests for the GovInfo.gov API client functions."""
    
    def test_get_collections(self):
        """Test getting collections."""
        collections = get_collections()
        
        assert isinstance(collections, dict)
        assert "collections" in collections
        assert isinstance(collections["collections"], list)
        assert len(collections["collections"]) > 0
        
        # Verify format parameter is accepted
        collections_with_format = get_collections(format="json")
        assert isinstance(collections_with_format, dict)
    
    def test_get_collection(self):
        """Test getting a specific collection."""
        collection = get_collection("BILLS")
        
        assert isinstance(collection, dict)
        assert collection["collectionCode"] == "BILLS"
        assert "collectionName" in collection
        assert "lastModified" in collection
        assert "packageCount" in collection
        assert "granules" in collection
        
        # Verify format parameter is accepted
        collection_with_format = get_collection("BILLS", format="json")
        assert isinstance(collection_with_format, dict)
    
    def test_get_package(self):
        """Test getting package information."""
        package = get_package("BILLS-117hr1234ih")
        
        assert isinstance(package, dict)
        assert package["packageId"] == "BILLS-117hr1234ih"
        assert "lastModified" in package
        assert "packageLink" in package
        assert "dateIssued" in package
        assert "title" in package
        assert "download" in package
        assert "pdfLink" in package["download"]
        
        # Verify format parameter is accepted
        package_with_format = get_package("BILLS-117hr1234ih", format="json")
        assert isinstance(package_with_format, dict)
    
    def test_search_packages(self):
        """Test searching packages."""
        search_results = search_packages("test")
        
        assert isinstance(search_results, dict)
        assert "packages" in search_results
        assert isinstance(search_results["packages"], list)
        assert len(search_results["packages"]) > 0
        assert "pagination" in search_results
        
        # Test with all parameters
        search_results_full = search_packages(
            "test", 
            collection="BILLS", 
            start_date="2023-01-01", 
            end_date="2023-12-31", 
            limit=20, 
            offset=5, 
            format="json"
        )
        assert isinstance(search_results_full, dict)
    
    def test_download_package(self):
        """Test downloading a package."""
        # Mock the open function to avoid actually writing a file
        with patch("builtins.open", mock_open()) as mock_file:
            output_path = download_package("BILLS-117hr1234ih")
            
            # Verify the file path has the correct extension
            assert output_path == "BILLS-117hr1234ih.pdf"
            
            # Verify open was called with the correct path and mode
            mock_file.assert_called_once_with("BILLS-117hr1234ih.pdf", "w")
            
            # Get the mock file handle
            handle = mock_file()
            
            # Verify write was called with the expected content
            handle.write.assert_called_once_with("Simulated PDF content for BILLS-117hr1234ih")
    
    def test_download_package_with_custom_format(self):
        """Test downloading a package with a custom format."""
        # Mock the open function to avoid actually writing a file
        with patch("builtins.open", mock_open()) as mock_file:
            output_path = download_package("BILLS-117hr1234ih", format="xml")
            
            # Verify the file path has the correct extension
            assert output_path == "BILLS-117hr1234ih.xml"
            
            # Verify open was called with the correct path and mode
            mock_file.assert_called_once_with("BILLS-117hr1234ih.xml", "w")
            
            # Get the mock file handle
            handle = mock_file()
            
            # Verify write was called with the expected content
            handle.write.assert_called_once_with("Simulated XML content for BILLS-117hr1234ih")
    
    def test_download_package_with_custom_output(self):
        """Test downloading a package with a custom output path."""
        # Mock the open function to avoid actually writing a file
        with patch("builtins.open", mock_open()) as mock_file:
            output_path = download_package("BILLS-117hr1234ih", output="custom_file.pdf")
            
            # Verify the output path is the custom path
            assert output_path == "custom_file.pdf"
            
            # Verify open was called with the correct path and mode
            mock_file.assert_called_once_with("custom_file.pdf", "w")


class TestGovInfoCLICommands:
    """Tests for the GovInfo.gov CLI commands."""
    
    def test_collection_list_command(self):
        """Test the collection list command."""
        mock_collections = {
            "collections": [
                {"collectionCode": "BILLS", "collectionName": "Congressional Bills"},
                {"collectionCode": "FR", "collectionName": "Federal Register"}
            ]
        }
        
        # Test with default format (text)
        with patch("pygovpub.cli.govinfo.get_collections", return_value=mock_collections) as mock_get:
            with patch("pygovpub.cli.govinfo.output_text") as mock_output:
                result = runner.invoke(app, ["collection", "list"])
                assert result.exit_code == 0
                
                # Verify that get_collections was called
                mock_get.assert_called_once_with(None)
                
                # Verify that output_text was called with collections
                mock_output.assert_called_once_with(mock_collections)
    
    def test_collection_list_command_with_json_format(self):
        """Test the collection list command with JSON format."""
        mock_collections = {
            "collections": [
                {"collectionCode": "BILLS", "collectionName": "Congressional Bills"},
                {"collectionCode": "FR", "collectionName": "Federal Register"}
            ]
        }
        
        with patch("pygovpub.cli.govinfo.get_collections", return_value=mock_collections) as mock_get:
            with patch("pygovpub.cli.govinfo.output_json") as mock_output:
                result = runner.invoke(app, ["collection", "list", "--format", "json"])
                assert result.exit_code == 0
                
                # Verify that get_collections was called
                mock_get.assert_called_once_with("json")
                
                # Verify that output_json was called with collections
                mock_output.assert_called_once_with(mock_collections)
    
    def test_collection_list_command_with_file_output(self):
        """Test the collection list command with file output."""
        mock_collections = {
            "collections": [
                {"collectionCode": "BILLS", "collectionName": "Congressional Bills"},
                {"collectionCode": "FR", "collectionName": "Federal Register"}
            ]
        }
        
        with patch("pygovpub.cli.govinfo.get_collections", return_value=mock_collections) as mock_get:
            with patch("pygovpub.cli.govinfo.output_to_file") as mock_output:
                result = runner.invoke(app, ["collection", "list", "--output", "collections.json"])
                assert result.exit_code == 0
                
                # Verify that get_collections was called
                mock_get.assert_called_once_with(None)
                
                # Verify that output_to_file was called with correct parameters
                mock_output.assert_called_once()
                args, kwargs = mock_output.call_args
                assert args[0] == mock_collections
                assert args[1] == "collections.json"
                assert args[2] == OutputFormat.JSON
    
    def test_collection_get_command(self):
        """Test the collection get command."""
        mock_collection = {
            "collectionCode": "BILLS",
            "collectionName": "Example Collection BILLS",
            "lastModified": "2023-01-01T12:00:00Z",
            "packageCount": 1000,
            "granules": ["title", "section"]
        }
        
        # Test with default format (text)
        with patch("pygovpub.cli.govinfo.get_collection", return_value=mock_collection) as mock_get:
            with patch("pygovpub.cli.govinfo.output_text") as mock_output:
                result = runner.invoke(app, ["collection", "get", "BILLS"])
                assert result.exit_code == 0
                
                # Verify that get_collection was called with correct parameters
                mock_get.assert_called_once_with("BILLS", None)
                
                # Verify that output_text was called with collection
                mock_output.assert_called_once_with(mock_collection)
    
    def test_package_get_command(self):
        """Test the package get command."""
        mock_package = {
            "packageId": "BILLS-117hr1234ih",
            "lastModified": "2023-01-01T12:00:00Z",
            "packageLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih",
            "dateIssued": "2023-01-01",
            "title": "Example Package BILLS-117hr1234ih",
            "download": {
                "pdfLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/pdf",
                "mods": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/mods",
                "xml": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/xml"
            }
        }
        
        # Test with default format (text)
        with patch("pygovpub.cli.govinfo.get_package", return_value=mock_package) as mock_get:
            with patch("pygovpub.cli.govinfo.output_text") as mock_output:
                result = runner.invoke(app, ["package", "get", "BILLS-117hr1234ih"])
                assert result.exit_code == 0
                
                # Verify that get_package was called with correct parameters
                mock_get.assert_called_once_with("BILLS-117hr1234ih", None)
                
                # Verify that output_text was called with package
                mock_output.assert_called_once_with(mock_package)
    
    def test_package_get_command_with_xml_format(self):
        """Test the package get command with XML format."""
        mock_package = {
            "packageId": "BILLS-117hr1234ih",
            "lastModified": "2023-01-01T12:00:00Z"
        }
        
        with patch("pygovpub.cli.govinfo.get_package", return_value=mock_package) as mock_get:
            with patch("pygovpub.cli.govinfo.output_xml") as mock_output:
                result = runner.invoke(app, ["package", "get", "BILLS-117hr1234ih", "--format", "xml"])
                assert result.exit_code == 0
                
                # Verify that get_package was called with correct parameters
                mock_get.assert_called_once_with("BILLS-117hr1234ih", "xml")
                
                # Verify that output_xml was called with package
                mock_output.assert_called_once_with(mock_package)
    
    def test_package_search_command(self):
        """Test the package search command."""
        mock_results = {
            "packages": [
                {"packageId": "BILLS-117hr1234ih", "title": "Example Package 1 matching 'budget'"},
                {"packageId": "BILLS-117hr5678ih", "title": "Example Package 2 matching 'budget'"}
            ],
            "pagination": {"count": 2, "next": None}
        }
        
        # Test with basic search
        with patch("pygovpub.cli.govinfo.search_packages", return_value=mock_results) as mock_search:
            with patch("pygovpub.cli.govinfo.output_text") as mock_output:
                result = runner.invoke(app, ["package", "search", "budget"])
                assert result.exit_code == 0
                
                # Verify that search_packages was called with correct parameters
                mock_search.assert_called_once_with("budget", None, None, None, 10, 0, None)
                
                # Verify that output_text was called with results
                mock_output.assert_called_once_with(mock_results)
    
    def test_package_search_command_with_all_options(self):
        """Test the package search command with all options."""
        mock_results = {
            "packages": [
                {"packageId": "BILLS-117hr1234ih", "title": "Example Package 1 matching 'budget'"}
            ],
            "pagination": {"count": 1, "next": None}
        }
        
        # Test with all options
        with patch("pygovpub.cli.govinfo.search_packages", return_value=mock_results) as mock_search:
            with patch("pygovpub.cli.govinfo.output_json") as mock_output:
                result = runner.invoke(app, [
                    "package", "search", "budget",
                    "--collection", "BILLS",
                    "--start-date", "2023-01-01",
                    "--end-date", "2023-12-31",
                    "--limit", "20",
                    "--offset", "5",
                    "--format", "json"
                ])
                assert result.exit_code == 0
                
                # Verify that search_packages was called with correct parameters
                mock_search.assert_called_once_with(
                    "budget", "BILLS", "2023-01-01", "2023-12-31", 20, 5, "json"
                )
                
                # Verify that output_json was called with results
                mock_output.assert_called_once_with(mock_results)
    
    def test_package_search_command_with_file_output(self):
        """Test the package search command with file output."""
        mock_results = {
            "packages": [
                {"packageId": "BILLS-117hr1234ih", "title": "Example Package 1 matching 'budget'"}
            ],
            "pagination": {"count": 1, "next": None}
        }
        
        with patch("pygovpub.cli.govinfo.search_packages", return_value=mock_results) as mock_search:
            with patch("pygovpub.cli.govinfo.output_to_file") as mock_output:
                result = runner.invoke(app, [
                    "package", "search", "budget",
                    "--output", "search_results.json"
                ])
                assert result.exit_code == 0
                
                # Verify that search_packages was called
                mock_search.assert_called_once()
                
                # Verify that output_to_file was called with correct parameters
                mock_output.assert_called_once()
                args, kwargs = mock_output.call_args
                assert args[0] == mock_results
                assert args[1] == "search_results.json"
                assert args[2] == OutputFormat.JSON
    
    def test_package_download_command(self):
        """Test the package download command."""
        # Test downloading a package with default format
        with patch("pygovpub.cli.govinfo.download_package", return_value="BILLS-117hr1234ih.pdf") as mock_download:
            with patch("pygovpub.cli.govinfo.console.print") as mock_print:
                result = runner.invoke(app, ["package", "download", "BILLS-117hr1234ih"])
                assert result.exit_code == 0
                
                # Verify that download_package was called with correct parameters
                mock_download.assert_called_once_with("BILLS-117hr1234ih", "pdf", None)
                
                # Verify that console.print was called with success message
                mock_print.assert_called_once()
                assert "Downloaded to:" in mock_print.call_args[0][0]
                assert "BILLS-117hr1234ih.pdf" in mock_print.call_args[0][0]
    
    def test_package_download_command_with_custom_format_and_output(self):
        """Test the package download command with custom format and output path."""
        # Test downloading a package with custom format and output
        with patch("pygovpub.cli.govinfo.download_package", return_value="custom_file.xml") as mock_download:
            with patch("pygovpub.cli.govinfo.console.print") as mock_print:
                result = runner.invoke(app, [
                    "package", "download", "BILLS-117hr1234ih",
                    "--format", "xml",
                    "--output", "custom_file.xml"
                ])
                assert result.exit_code == 0
                
                # Verify that download_package was called with correct parameters
                mock_download.assert_called_once_with("BILLS-117hr1234ih", "xml", "custom_file.xml")
                
                # Verify that console.print was called with success message
                mock_print.assert_called_once()
                assert "Downloaded to:" in mock_print.call_args[0][0]
                assert "custom_file.xml" in mock_print.call_args[0][0]