"""
Tests for API contract testing in the mock server.

This module tests the API contract validation utilities for the mock server.
"""

import json
import os
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call

from fastapi import HTTPException, Request
from pydantic import BaseModel

from pygovpub.mock.api_contract import (
    ContractMonitor,
    ContractViolation,
    get_monitor,
    validate_request,
    validate_response,
    get_report,
    clear_violations
)


class TestContractViolation:
    """Tests for the ContractViolation model."""
    
    def test_contract_violation_model(self):
        """Test the ContractViolation model."""
        # Create a violation instance
        violation = ContractViolation(
            timestamp="2023-05-15T10:30:00Z",
            api_source="congress",
            endpoint="bills",
            violation_type="request",
            errors=["Missing required parameter"],
            data={"test": "data"}
        )
        
        # Check fields
        assert violation.timestamp == "2023-05-15T10:30:00Z"
        assert violation.api_source == "congress"
        assert violation.endpoint == "bills"
        assert violation.violation_type == "request"
        assert violation.errors == ["Missing required parameter"]
        assert violation.data == {"test": "data"}
        
        # Test serialization
        json_data = violation.model_dump_json()
        assert "timestamp" in json_data
        assert "api_source" in json_data
        assert "errors" in json_data
        assert "data" in json_data


class TestContractMonitor:
    """Tests for the ContractMonitor class."""
    
    def test_init(self):
        """Test initializing the contract monitor."""
        # Test with default violations directory
        with patch('os.makedirs') as mock_makedirs:
            monitor = ContractMonitor()
            assert "contract_violations" in str(monitor.violations_dir)
            mock_makedirs.assert_called_once()
            
        # Test with custom violations directory
        with patch('os.makedirs') as mock_makedirs:
            custom_dir = "/tmp/violations"
            monitor = ContractMonitor(violations_dir=custom_dir)
            assert str(monitor.violations_dir) == custom_dir
            # Convert Path to string for comparison
            mock_makedirs.assert_called_once_with(Path(custom_dir), exist_ok=True)
    
    @pytest.mark.asyncio
    async def test_validate_request_contract_get(self):
        """Test validating GET request contracts."""
        monitor = ContractMonitor()
        
        # Mock request with query parameters
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.query_params = {"param1": "value1", "param2": "value2"}
        mock_request.path_params = {"id": "123"}
        
        # Mock the validator
        with patch('pygovpub.mock.api_contract.validate_request') as mock_validate:
            mock_validate.return_value = (True, [])
            
            # Test successful validation
            is_valid, errors = await monitor.validate_request_contract("congress", "bills", mock_request)
            
            # Check validation was called correctly
            mock_validate.assert_called_once()
            call_args = mock_validate.call_args[0]
            assert call_args[0] == "congress"
            assert call_args[1] == "bills"
            assert call_args[2] == {"param1": "value1", "param2": "value2", "id": "123"}
            
            # Check result
            assert is_valid is True
            assert errors == []
            
    @pytest.mark.asyncio
    async def test_validate_request_contract_post(self):
        """Test validating POST request contracts."""
        monitor = ContractMonitor()
        
        # Mock request with JSON body
        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.query_params = {}
        mock_request.path_params = {"id": "123"}
        mock_request.json = AsyncMock(return_value={"data": "test"})
        
        # Mock the validator
        with patch('pygovpub.mock.api_contract.validate_request') as mock_validate:
            mock_validate.return_value = (False, ["Error"])
            
            # Mock config for non-strict validation
            with patch('pygovpub.mock.api_contract.config') as mock_config:
                mock_config.mock.strict_contract_validation = False
                
                # Mock record_violation
                with patch.object(monitor, 'record_violation') as mock_record:
                    # Test failed validation without strict mode
                    is_valid, errors = await monitor.validate_request_contract("congress", "bills", mock_request)
                    
                    # Check validation was called correctly
                    mock_validate.assert_called_once()
                    call_args = mock_validate.call_args[0]
                    assert call_args[0] == "congress"
                    assert call_args[1] == "bills"
                    assert call_args[2] == {"data": "test", "id": "123"}
                    
                    # Check violation was recorded
                    mock_record.assert_called_once()
                    violation = mock_record.call_args[0][0]
                    assert violation.api_source == "congress"
                    assert violation.endpoint == "bills"
                    assert violation.violation_type == "request"
                    assert violation.errors == ["Error"]
                    assert violation.data == {"data": "test", "id": "123"}
                    
                    # Check result
                    assert is_valid is False
                    assert errors == ["Error"]
    
    @pytest.mark.asyncio
    async def test_validate_request_contract_strict(self):
        """Test validating request contracts with strict validation."""
        monitor = ContractMonitor()
        
        # Mock request
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.query_params = {}
        mock_request.path_params = {}
        
        # Mock the validator to return a failure
        with patch('pygovpub.mock.api_contract.validate_request') as mock_validate:
            mock_validate.return_value = (False, ["Missing required parameter"])
            
            # Mock config for strict validation
            with patch('pygovpub.mock.api_contract.config') as mock_config:
                mock_config.mock.strict_contract_validation = True
                
                # Mock record_violation
                with patch.object(monitor, 'record_violation'):
                    # Test failed validation with strict mode
                    with pytest.raises(HTTPException) as excinfo:
                        await monitor.validate_request_contract("congress", "bills", mock_request)
                    
                    # Check exception details
                    assert excinfo.value.status_code == 400
                    assert "API contract violation" in excinfo.value.detail["message"]
                    assert excinfo.value.detail["errors"] == ["Missing required parameter"]
    
    def test_validate_response_contract(self):
        """Test validating response contracts."""
        monitor = ContractMonitor()
        
        # Test data
        response_data = {"test": "data"}
        
        # Mock the validator
        with patch('pygovpub.mock.api_contract.validate_response') as mock_validate:
            mock_validate.return_value = (True, [])
            
            # Test successful validation
            is_valid, errors = monitor.validate_response_contract("congress", "bills", response_data)
            
            # Check validation was called correctly
            mock_validate.assert_called_once_with("congress", "bills", response_data)
            
            # Check result
            assert is_valid is True
            assert errors == []
    
    def test_validate_response_contract_failure(self):
        """Test validating response contracts with failures."""
        monitor = ContractMonitor()
        
        # Test data
        response_data = {"test": "data"}
        
        # Mock the validator to return a failure
        with patch('pygovpub.mock.api_contract.validate_response') as mock_validate:
            mock_validate.return_value = (False, ["Invalid response format"])
            
            # Mock config for non-strict validation
            with patch('pygovpub.mock.api_contract.config') as mock_config:
                mock_config.mock.strict_contract_validation = False
                
                # Mock record_violation
                with patch.object(monitor, 'record_violation') as mock_record:
                    # Test failed validation without strict mode
                    is_valid, errors = monitor.validate_response_contract("congress", "bills", response_data)
                    
                    # Check validation was called correctly
                    mock_validate.assert_called_once_with("congress", "bills", response_data)
                    
                    # Check violation was recorded
                    mock_record.assert_called_once()
                    violation = mock_record.call_args[0][0]
                    assert violation.api_source == "congress"
                    assert violation.endpoint == "bills"
                    assert violation.violation_type == "response"
                    assert violation.errors == ["Invalid response format"]
                    assert violation.data == response_data
                    
                    # Check result
                    assert is_valid is False
                    assert errors == ["Invalid response format"]
    
    def test_validate_response_contract_strict(self):
        """Test validating response contracts with strict validation."""
        monitor = ContractMonitor()
        
        # Test data
        response_data = {"test": "data"}
        
        # Mock the validator to return a failure
        with patch('pygovpub.mock.api_contract.validate_response') as mock_validate:
            mock_validate.return_value = (False, ["Invalid response format"])
            
            # Mock config for strict validation
            with patch('pygovpub.mock.api_contract.config') as mock_config:
                mock_config.mock.strict_contract_validation = True
                
                # Mock record_violation
                with patch.object(monitor, 'record_violation'):
                    # Test failed validation with strict mode
                    with pytest.raises(HTTPException) as excinfo:
                        monitor.validate_response_contract("congress", "bills", response_data)
                    
                    # Check exception details
                    assert excinfo.value.status_code == 500
                    assert "API contract violation" in excinfo.value.detail["message"]
                    assert excinfo.value.detail["errors"] == ["Invalid response format"]
    
    def test_record_violation(self, tmp_path):
        """Test recording a contract violation."""
        # Create a monitor with test violations directory
        monitor = ContractMonitor(violations_dir=str(tmp_path))
        
        # Create a violation
        violation = ContractViolation(
            timestamp=datetime.now().isoformat(),
            api_source="congress",
            endpoint="bills",
            violation_type="request",
            errors=["Missing required parameter"],
            data={"test": "data"}
        )
        
        # Record the violation
        with patch('pygovpub.mock.api_contract.logger') as mock_logger:
            file_path = monitor.record_violation(violation)
            
            # Check file was created
            assert os.path.exists(file_path)
            
            # Check file content
            with open(file_path, "r") as f:
                content = json.load(f)
                assert content["api_source"] == "congress"
                assert content["endpoint"] == "bills"
                assert content["errors"] == ["Missing required parameter"]
            
            # Check in-memory tracking
            assert len(monitor.violations) == 1
            assert monitor.violations[0] == violation
            
            # Check logging
            mock_logger.warning.assert_called_once()
            assert "API contract violation" in mock_logger.warning.call_args[0][0]
    
    def test_get_violations(self):
        """Test getting filtered violations."""
        monitor = ContractMonitor()
        
        # Create test violations
        violations = [
            ContractViolation(
                timestamp=datetime.now().isoformat(),
                api_source="congress",
                endpoint="bills",
                violation_type="request",
                errors=["Error 1"],
                data={}
            ),
            ContractViolation(
                timestamp=datetime.now().isoformat(),
                api_source="congress",
                endpoint="members",
                violation_type="response",
                errors=["Error 2"],
                data={}
            ),
            ContractViolation(
                timestamp=datetime.now().isoformat(),
                api_source="govinfo",
                endpoint="packages",
                violation_type="request",
                errors=["Error 3"],
                data={}
            )
        ]
        
        # Add to monitor
        for v in violations:
            monitor.violations.append(v)
            
        # Test unfiltered
        result = monitor.get_violations()
        assert len(result) == 3
        
        # Test filter by API source
        result = monitor.get_violations(api_source="congress")
        assert len(result) == 2
        assert all(v.api_source == "congress" for v in result)
        
        # Test filter by endpoint
        result = monitor.get_violations(endpoint="bills")
        assert len(result) == 1
        assert result[0].endpoint == "bills"
        
        # Test filter by violation type
        result = monitor.get_violations(violation_type="request")
        assert len(result) == 2
        assert all(v.violation_type == "request" for v in result)
        
        # Test combined filters
        result = monitor.get_violations(api_source="congress", violation_type="response")
        assert len(result) == 1
        assert result[0].api_source == "congress"
        assert result[0].violation_type == "response"
    
    def test_clear_violations(self):
        """Test clearing violations."""
        monitor = ContractMonitor()
        
        # Add test violations
        monitor.violations = [
            ContractViolation(
                timestamp=datetime.now().isoformat(),
                api_source="congress",
                endpoint="bills",
                violation_type="request",
                errors=["Error"],
                data={}
            ),
            ContractViolation(
                timestamp=datetime.now().isoformat(),
                api_source="govinfo",
                endpoint="packages",
                violation_type="response",
                errors=["Error"],
                data={}
            )
        ]
        
        # Clear violations
        count = monitor.clear_violations()
        
        # Check result
        assert count == 2
        assert len(monitor.violations) == 0
    
    def test_generate_report(self):
        """Test generating a contract violations report."""
        monitor = ContractMonitor()
        
        # Create test violations with different errors
        monitor.violations = [
            ContractViolation(
                timestamp="2023-05-01T10:00:00Z",
                api_source="congress",
                endpoint="bills",
                violation_type="request",
                errors=["Missing parameter 1", "Invalid format"],
                data={}
            ),
            ContractViolation(
                timestamp="2023-05-02T11:00:00Z",
                api_source="congress",
                endpoint="members",
                violation_type="response",
                errors=["Missing field", "Invalid format"],
                data={}
            ),
            ContractViolation(
                timestamp="2023-05-03T12:00:00Z",
                api_source="govinfo",
                endpoint="packages",
                violation_type="request",
                errors=["Missing parameter 2"],
                data={}
            )
        ]
        
        # Generate report
        report = monitor.generate_report()
        
        # Check report structure
        assert report["total_violations"] == 3
        assert report["unique_api_sources"] == 2
        assert report["unique_endpoints"] == 3
        assert report["request_violations"] == 2
        assert report["response_violations"] == 1
        
        # Check API breakdown
        assert len(report["by_api"]) == 2
        assert "congress" in report["by_api"]
        assert "govinfo" in report["by_api"]
        assert report["by_api"]["congress"]["total"] == 2
        assert report["by_api"]["congress"]["request"] == 1
        assert report["by_api"]["congress"]["response"] == 1
        assert len(report["by_api"]["congress"]["endpoints"]) == 2
        
        # Check error counts
        assert len(report["most_common_errors"]) > 0
        # "Invalid format" should appear twice
        format_errors = [e for e in report["most_common_errors"] if e["error"] == "Invalid format"]
        assert len(format_errors) == 1
        assert format_errors[0]["count"] == 2
        
        # Check timestamps
        assert report["first_violation"] == "2023-05-01T10:00:00Z"
        assert report["last_violation"] == "2023-05-03T12:00:00Z"


class TestHelperFunctions:
    """Tests for the helper functions."""
    
    def test_get_monitor(self):
        """Test getting the singleton monitor instance."""
        # Reset the singleton
        from pygovpub.mock import api_contract
        api_contract._monitor = None
        
        # Get the monitor
        monitor1 = get_monitor()
        assert monitor1 is not None
        assert isinstance(monitor1, ContractMonitor)
        
        # Get it again and verify it's the same instance
        monitor2 = get_monitor()
        assert monitor2 is monitor1
    
    @pytest.mark.asyncio
    async def test_validate_request_helper(self):
        """Test the validate_request helper function."""
        # Mock the monitor
        mock_monitor = MagicMock()
        mock_monitor.validate_request_contract = AsyncMock(return_value=(True, []))
        
        # Mock get_monitor
        with patch('pygovpub.mock.api_contract.get_monitor', return_value=mock_monitor):
            # Test the helper
            mock_request = MagicMock()
            is_valid, errors = await validate_request("congress", "bills", mock_request)
            
            # Check monitor was called
            mock_monitor.validate_request_contract.assert_called_once_with("congress", "bills", mock_request)
            assert is_valid is True
            assert errors == []
    
    def test_validate_response_helper(self):
        """Test the validate_response helper function."""
        # Mock the monitor
        mock_monitor = MagicMock()
        mock_monitor.validate_response_contract.return_value = (False, ["Error"])
        
        # Mock get_monitor
        with patch('pygovpub.mock.api_contract.get_monitor', return_value=mock_monitor):
            # Test the helper
            response_data = {"test": "data"}
            is_valid, errors = validate_response("congress", "bills", response_data)
            
            # Check monitor was called
            mock_monitor.validate_response_contract.assert_called_once_with("congress", "bills", response_data)
            assert is_valid is False
            assert errors == ["Error"]
    
    def test_get_report_helper(self):
        """Test the get_report helper function."""
        # Mock the monitor
        mock_monitor = MagicMock()
        mock_monitor.generate_report.return_value = {"total": 5}
        
        # Mock get_monitor
        with patch('pygovpub.mock.api_contract.get_monitor', return_value=mock_monitor):
            # Test the helper
            report = get_report()
            
            # Check monitor was called
            mock_monitor.generate_report.assert_called_once()
            assert report == {"total": 5}
    
    def test_clear_violations_helper(self):
        """Test the clear_violations helper function."""
        # Mock the monitor
        mock_monitor = MagicMock()
        mock_monitor.clear_violations.return_value = 10
        
        # Mock get_monitor
        with patch('pygovpub.mock.api_contract.get_monitor', return_value=mock_monitor):
            # Test the helper
            count = clear_violations()
            
            # Check monitor was called
            mock_monitor.clear_violations.assert_called_once()
            assert count == 10