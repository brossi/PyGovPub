# Real Data Fetch Test Proposal

## 1. Test Objectives
- Validate user stories through live API calls to Congress.gov and GovInfo
- Verify endpoint functionality against original user story requirements
- Establish performance baselines for legislative data endpoints
- Ensure comprehensive coverage of all implemented user stories
- Compare PyGovPub's normalized API responses with direct source API responses
- Verify data integrity and completeness across the transformation pipeline

## 2. User Story Coverage Matrix

| Domain | User Story | Description | Test Coverage |
|--------|------------|-------------|---------------|
| **Authentication** | AUTH-001 | API Authentication Management | Authentication, Rate Limiting |
| **Core** | CORE-001 | Unified Data Response Format | Data Transformation, Schema Validation |
| **Core** | CORE-002 | Comprehensive Error Handling | Error Scenarios, Recovery Strategies |
| **DevOps** | DX-001 | SDK Health Check and Validation | Health Verification, Environment Testing |
| **DevOps** | DX-002 | Command Line Interface | CLI Functionality, Output Formats |
| **DevOps** | DX-004 | Development Logging and Debugging | Logging Verification, Debug Mode Testing |
| **Legislative** | LM-BT-001 | Bill Status Information Retrieval | Bill Retrieval, Status Tracking |

## 3. Jupyter Notebook Structure
```python
# Cell 1: Configuration and Imports
import requests
import pandas as pd
import json
import os
import matplotlib.pyplot as plt
import deepdiff
import jsonschema
from dotenv import load_dotenv
from datetime import datetime
from pygovpub import PyGovPub  # Import our SDK

# Load environment variables
load_dotenv()

# Direct API endpoints
API_ENDPOINTS = {
    'BILL_STATUS': 'https://api.congress.gov/v3/bill',
    'MEMBERS': 'https://api.congress.gov/v3/member',
    'COMMITTEES': 'https://api.congress.gov/v3/committee',
    'GOVINFO_COLLECTIONS': 'https://api.govinfo.gov/collections',
    'GOVINFO_PACKAGES': 'https://api.govinfo.gov/packages'
}

# PyGovPub normalized endpoints (to be compared with direct API calls)
PYGOVPUB_ENDPOINTS = {
    'BILL_STATUS': '/api/v1/legislative/bill',
    'MEMBERS': '/api/v1/legislative/member',
    'COMMITTEES': '/api/v1/legislative/committee',
    'GOVINFO_COLLECTIONS': '/api/v1/documents/collections',
    'GOVINFO_PACKAGES': '/api/v1/documents/packages'
}

# Cell 2: Test Harness
class APITestRunner:
    def __init__(self, congress_api_key=None, govinfo_api_key=None, pygovpub_base_url="http://localhost:8000"):
        # Direct API sessions
        self.congress_session = requests.Session()
        self.govinfo_session = requests.Session()
        
        # PyGovPub SDK client
        self.pygovpub_client = PyGovPub(
            api_key=congress_api_key or os.getenv('CONGRESS_API_KEY'),
            govinfo_api_key=govinfo_api_key or os.getenv('GOVINFO_API_KEY'),
            base_url=pygovpub_base_url
        )
        
        # PyGovPub API session (for direct comparison with raw APIs)
        self.pygovpub_session = requests.Session()
        self.pygovpub_base_url = pygovpub_base_url
        
        # Congress.gov uses header-based authentication
        if congress_api_key:
            self.congress_session.headers.update({'X-Api-Key': congress_api_key})
        else:
            self.congress_session.headers.update({'X-Api-Key': os.getenv('CONGRESS_API_KEY')})
            
        # GovInfo uses query parameter authentication
        self.govinfo_api_key = govinfo_api_key or os.getenv('GOVINFO_API_KEY')
        
        # Track rate limits
        self.rate_limits = {
            'congress': {'remaining': 5000, 'reset': None},
            'govinfo': {'remaining': 1000, 'reset': None}
        }
        
    def update_rate_limits(self, response, api_type):
        """Update rate limit tracking based on response headers"""
        if api_type == 'congress':
            if 'X-RateLimit-Remaining' in response.headers:
                self.rate_limits['congress']['remaining'] = int(response.headers['X-RateLimit-Remaining'])
            if 'X-RateLimit-Reset' in response.headers:
                self.rate_limits['congress']['reset'] = response.headers['X-RateLimit-Reset']
        # Similar implementation for GovInfo
        
    def compare_responses(self, direct_response, pygovpub_response, mapping_rules=None):
        """Compare direct API response with PyGovPub normalized response
        
        Args:
            direct_response: JSON response from direct API call
            pygovpub_response: JSON response from PyGovPub API
            mapping_rules: Optional dictionary mapping direct API fields to PyGovPub fields
        
        Returns:
            dict: Comparison results including differences and match percentage
        """
        # Apply mapping rules if provided
        if mapping_rules:
            mapped_direct = self._apply_mapping(direct_response, mapping_rules)
        else:
            mapped_direct = direct_response
            
        # Calculate differences using DeepDiff
        differences = deepdiff.DeepDiff(mapped_direct, pygovpub_response, ignore_order=True)
        
        # Calculate match percentage
        total_fields = self._count_fields(mapped_direct)
        different_fields = len(differences.get('values_changed', {})) + \
                          len(differences.get('dictionary_item_removed', {})) + \
                          len(differences.get('dictionary_item_added', {}))
        
        match_percentage = 100 - (different_fields / total_fields * 100) if total_fields > 0 else 0
        
        return {
            'differences': differences,
            'match_percentage': match_percentage,
            'total_fields': total_fields,
            'different_fields': different_fields
        }
    
    def _count_fields(self, obj, count=0):
        """Recursively count fields in a nested object"""
        if isinstance(obj, dict):
            count += len(obj)
            for value in obj.values():
                count = self._count_fields(value, count)
        elif isinstance(obj, list):
            for item in obj:
                count = self._count_fields(item, count)
        return count
        
    def _apply_mapping(self, data, mapping_rules):
        """Apply field mapping rules to transform direct API response"""
        result = {}
        for src_key, dest_key in mapping_rules.items():
            if isinstance(src_key, str) and '.' in src_key:
                # Handle nested keys with dot notation
                parts = src_key.split('.')
                value = data
                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        value = None
                        break
                if value is not None:
                    result[dest_key] = value
            elif src_key in data:
                result[dest_key] = data[src_key]
        return result

# Cell 3: User Story Test Mapping
TEST_MATRIX = {
    # Authentication & Security
    'AUTH-001': [
        ('test_congress_key_header_formatting', 'unit-test-manifest.md#L141'),
        ('test_govinfo_key_query_param', 'unit-test-manifest.md#L143'),
        ('test_key_validation', 'unit-test-manifest.md#L145'),
        ('test_rate_limit_tracking', 'unit-test-manifest.md#L181')
    ],
    
    # Core SDK Features
    'CORE-001': [
        ('test_unified_response_format', 'unit-test-manifest.md#L36'),
        ('test_data_transformation', 'unit-test-manifest.md#L50')
    ],
    'CORE-002': [
        ('test_error_classification', 'unit-test-manifest.md#L345'),
        ('test_error_recovery_guidance', 'unit-test-manifest.md#L350')
    ],
    
    # Developer Experience
    'DX-001': [
        ('test_health_check_command', 'unit-test-manifest.md#L400'),
        ('test_api_connectivity', 'unit-test-manifest.md#L405')
    ],
    'DX-002': [
        ('test_cli_commands', 'unit-test-manifest.md#L450'),
        ('test_output_formats', 'unit-test-manifest.md#L455')
    ],
    'DX-004': [
        ('test_logging_system', 'unit-test-manifest.md#L500'),
        ('test_debug_mode', 'unit-test-manifest.md#L505')
    ],
    
    # Legislative Monitoring
    'LM-BT-001': [
        ('test_bill_retrieval', 'unit-test-manifest.md#L141'),
        ('test_bill_status_information', 'unit-test-manifest.md#L600'),
        ('test_response_completeness', 'unit-test-manifest.md#L696')
    ]
}

# Cell 4: Visualization Setup
%matplotlib inline
plt.style.use('ggplot')

# Cell 5: Traceability Matrix
def generate_coverage_report():
    """Auto-generated test coverage map linking user stories
    to implemented test cases"""
    return pd.DataFrame.from_dict({
        'User Story': ['AUTH-001', 'CORE-001', 'CORE-002', 'DX-001', 'DX-002', 'DX-004', 'LM-BT-001'],
        'Validation Tests': [
            'test_key_validation', 'test_unified_response_format', 'test_error_classification',
            'test_health_check_command', 'test_cli_commands', 'test_logging_system', 'test_bill_retrieval'
        ],
        'Security Tests': [
            'test_key_rotation', 'test_data_sanitization', 'test_error_handling',
            'test_environment_validation', 'test_output_sanitization', 'test_sensitive_data_handling', 'test_data_authenticity'
        ],
        'Performance Tests': [
            'test_rate_limit_compliance', 'test_response_time', 'test_error_recovery_time',
            'test_health_check_performance', 'test_cli_response_time', 'test_logging_overhead', 'test_bill_retrieval_performance'
        ]
    })

# Cell 6: Test Execution Categories
TEST_CATEGORIES = {
    'Critical Path': [
        ('test_congress_api_authentication', 'unit-test-manifest.md#L141'),
        ('test_govinfo_api_authentication', 'unit-test-manifest.md#L143'),
        ('test_bill_retrieval_basic', 'unit-test-manifest.md#L600'),
        ('test_unified_response_format_basic', 'unit-test-manifest.md#L36')
    ],
    'Edge Cases': [
        ('test_invalid_key_handling', 'unit-test-manifest.md#L180'),
        ('test_rate_limit_handling', 'integration-test-manifest.md#L779'),
        ('test_malformed_request_handling', 'unit-test-manifest.md#L350'),
        ('test_network_failure_recovery', 'integration-test-manifest.md#L800')
    ],
    'Performance': [
        ('test_response_time_baseline', 'performance/metrics.md#L50'),
        ('test_concurrent_request_handling', 'performance/metrics.md#L75'),
        ('test_memory_usage', 'performance/metrics.md#L100')
    ],
    'Security': [
        ('test_key_rotation_handling', 'unit-test-manifest.md#L160'),
        ('test_data_sanitization', 'unit-test-manifest.md#L350'),
        ('test_sensitive_data_handling', 'unit-test-manifest.md#L400')
    ]
}

# Cell 7: Sample Test Implementation
def test_bill_retrieval(runner, congress=117, bill_type='hr', bill_number=1):
    """Test bill retrieval functionality (LM-BT-001)"""
    # Direct API call
    direct_url = f"{API_ENDPOINTS['BILL_STATUS']}/{congress}/{bill_type}/{bill_number}"
    direct_response = runner.congress_session.get(direct_url)
    runner.update_rate_limits(direct_response, 'congress')
    
    # Validate direct response
    assert direct_response.status_code == 200, f"Failed to retrieve bill from direct API: {direct_response.status_code}"
    direct_data = direct_response.json()
    
    # Validate required fields in direct response (LM-BT-001 criteria)
    direct_required_fields = ['congress', 'type', 'number', 'title', 'updateDate', 'actions']
    for field in direct_required_fields:
        assert field in direct_data['bill'], f"Missing required field in direct API: {field}"
    
    # PyGovPub API call
    pygovpub_url = f"{runner.pygovpub_base_url}{PYGOVPUB_ENDPOINTS['BILL_STATUS']}/{congress}/{bill_type}/{bill_number}"
    pygovpub_response = runner.pygovpub_session.get(pygovpub_url)
    
    # Validate PyGovPub response
    assert pygovpub_response.status_code == 200, f"Failed to retrieve bill from PyGovPub API: {pygovpub_response.status_code}"
    pygovpub_data = pygovpub_response.json()
    
    # Validate required fields in PyGovPub response
    pygovpub_required_fields = ['congress', 'type', 'number', 'title', 'updated_date', 'actions']
    for field in pygovpub_required_fields:
        assert field in pygovpub_data['bill'], f"Missing required field in PyGovPub API: {field}"
    
    # Define mapping rules between direct API and PyGovPub API
    mapping_rules = {
        'bill.congress': 'bill.congress',
        'bill.type': 'bill.type',
        'bill.number': 'bill.number',
        'bill.title': 'bill.title',
        'bill.updateDate': 'bill.updated_date',
        'bill.actions': 'bill.actions'
        # Add more field mappings as needed
    }
    
    # Compare responses
    comparison = runner.compare_responses(direct_data, pygovpub_data, mapping_rules)
    
    # Log comparison results
    print(f"Response comparison - Match percentage: {comparison['match_percentage']:.2f}%")
    if comparison['match_percentage'] < 100:
        print(f"Differences found: {len(comparison['differences'])}")
        print(json.dumps(comparison['differences'], indent=2))
    
    return {
        'direct_data': direct_data,
        'pygovpub_data': pygovpub_data,
        'comparison': comparison
    }

# Cell 8: Authentication Test Implementation
def test_api_authentication(runner):
    """Test API authentication functionality (AUTH-001)"""
    # Test Congress.gov authentication
    congress_url = f"{API_ENDPOINTS['BILL_STATUS']}/117/hr/1"
    congress_response = runner.congress_session.get(congress_url)
    runner.update_rate_limits(congress_response, 'congress')
    
    # Test GovInfo authentication
    govinfo_url = f"{API_ENDPOINTS['GOVINFO_COLLECTIONS']}"
    govinfo_params = {'api_key': runner.govinfo_api_key}
    govinfo_response = runner.govinfo_session.get(govinfo_url, params=govinfo_params)
    
    # Test PyGovPub authentication
    pygovpub_bill_url = f"{runner.pygovpub_base_url}{PYGOVPUB_ENDPOINTS['BILL_STATUS']}/117/hr/1"
    pygovpub_bill_response = runner.pygovpub_session.get(pygovpub_bill_url)
    
    pygovpub_collections_url = f"{runner.pygovpub_base_url}{PYGOVPUB_ENDPOINTS['GOVINFO_COLLECTIONS']}"
    pygovpub_collections_response = runner.pygovpub_session.get(pygovpub_collections_url)
    
    # Validate responses
    assert congress_response.status_code == 200, "Congress.gov authentication failed"
    assert govinfo_response.status_code == 200, "GovInfo authentication failed"
    assert pygovpub_bill_response.status_code == 200, "PyGovPub bill endpoint authentication failed"
    assert pygovpub_collections_response.status_code == 200, "PyGovPub collections endpoint authentication failed"
    
    return {
        'congress': congress_response.status_code,
        'govinfo': govinfo_response.status_code,
        'pygovpub_bill': pygovpub_bill_response.status_code,
        'pygovpub_collections': pygovpub_collections_response.status_code
    }
```

# Cell 9: Data Transformation Validation
def test_data_transformation_integrity(runner, congress=117, bill_type='hr', bill_number=1):
    """Test data transformation integrity between source APIs and PyGovPub"""
    # Get data from direct API
    direct_url = f"{API_ENDPOINTS['BILL_STATUS']}/{congress}/{bill_type}/{bill_number}"
    direct_response = runner.congress_session.get(direct_url)
    direct_data = direct_response.json()
    
    # Get data from PyGovPub API
    pygovpub_url = f"{runner.pygovpub_base_url}{PYGOVPUB_ENDPOINTS['BILL_STATUS']}/{congress}/{bill_type}/{bill_number}"
    pygovpub_response = runner.pygovpub_session.get(pygovpub_url)
    pygovpub_data = pygovpub_response.json()
    
    # Define comprehensive field mapping between source API and PyGovPub
    field_mapping = {
        # Basic bill information
        'bill.congress': 'bill.congress',
        'bill.type': 'bill.type',
        'bill.number': 'bill.number',
        'bill.title': 'bill.title',
        'bill.updateDate': 'bill.updated_date',
        
        # Sponsors and cosponsors
        'bill.sponsors': 'bill.sponsors',
        'bill.cosponsors': 'bill.cosponsors',
        
        # Actions and status
        'bill.actions': 'bill.actions',
        'bill.latestAction': 'bill.latest_action',
        
        # Committees
        'bill.committees': 'bill.committees',
        
        # Related bills and amendments
        'bill.relatedBills': 'bill.related_bills',
        'bill.amendments': 'bill.amendments',
        
        # Policy areas and subjects
        'bill.policyArea': 'bill.policy_area',
        'bill.subjects': 'bill.subjects',
        
        # Summaries
        'bill.summaries': 'bill.summaries',
        
        # Texts
        'bill.textVersions': 'bill.text_versions'
    }
    
    # Define critical fields that must be preserved with 100% accuracy
    critical_fields = [
        'bill.congress',
        'bill.type',
        'bill.number',
        'bill.title',
        'bill.sponsors',
        'bill.latestAction',
        'bill.actions'
    ]
    
    # Compare responses with detailed field mapping
    comparison = runner.compare_responses(direct_data, pygovpub_data, field_mapping)
    
    # Verify critical fields are preserved
    critical_field_preservation = True
    critical_field_issues = []
    
    for field in critical_fields:
        if field in comparison['differences'].get('values_changed', {}) or \
           field in comparison['differences'].get('dictionary_item_removed', {}):
            critical_field_preservation = False
            critical_field_issues.append(field)
    
    # Generate detailed report
    report = {
        'endpoint': f"bill/{congress}/{bill_type}/{bill_number}",
        'match_percentage': comparison['match_percentage'],
        'field_coverage': 100 - (len(comparison['differences'].get('dictionary_item_removed', {})) / comparison['total_fields'] * 100 if comparison['total_fields'] > 0 else 0),
        'critical_fields_preserved': critical_field_preservation,
        'critical_field_issues': critical_field_issues,
        'differences': comparison['differences']
    }
    
    # Print summary
    print(f"Data Transformation Validation - {report['endpoint']}")
    print(f"Match Percentage: {report['match_percentage']:.2f}%")
    print(f"Field Coverage: {report['field_coverage']:.2f}%")
    print(f"Critical Fields Preserved: {'Yes' if report['critical_fields_preserved'] else 'No'}")
    
    if not report['critical_fields_preserved']:
        print(f"Critical Field Issues: {', '.join(report['critical_field_issues'])}")
    
    return report

# Cell 10: Batch Comparison Testing
def run_batch_comparison_tests(runner, test_cases):
    """Run a batch of comparison tests across multiple endpoints and resources"""
    results = []
    
    for test_case in test_cases:
        endpoint_type = test_case['endpoint_type']
        params = test_case['params']
        
        if endpoint_type == 'bill':
            result = test_data_transformation_integrity(
                runner, 
                congress=params.get('congress', 117),
                bill_type=params.get('bill_type', 'hr'),
                bill_number=params.get('bill_number', 1)
            )
        # Add other endpoint types as needed
        
        results.append(result)
    
    # Aggregate results
    avg_match_percentage = sum(r['match_percentage'] for r in results) / len(results)
    avg_field_coverage = sum(r['field_coverage'] for r in results) / len(results)
    critical_fields_preserved = all(r['critical_fields_preserved'] for r in results)
    
    print("\nBatch Comparison Summary:")
    print(f"Average Match Percentage: {avg_match_percentage:.2f}%")
    print(f"Average Field Coverage: {avg_field_coverage:.2f}%")
    print(f"All Critical Fields Preserved: {'Yes' if critical_fields_preserved else 'No'}")
    
    # Visualize results
    visualize_comparison_results(results)
    
    return {
        'results': results,
        'avg_match_percentage': avg_match_percentage,
        'avg_field_coverage': avg_field_coverage,
        'critical_fields_preserved': critical_fields_preserved
    }

```

## 4. Implementation Plan
1. **API Testing Framework**:
   - Requests library for endpoint validation
   - Pytest integration for test automation
   - JSON Schema validation for response formats
   - Authentication handling for both APIs
   - DeepDiff for response comparison and data integrity validation

2. **Data Visualization**:
   - Pandas for response time metrics and test coverage analysis
   - Matplotlib for trend visualization and performance metrics
   - Tableau Public for stakeholder reports and coverage dashboards

3. **User Story Validation**:
   - Explicit mapping between test cases and user story requirements
   - Traceability matrix for requirement coverage
   - Test case categorization by functional domain

## 5. Validation Criteria
| User Story | Validation Metric | Success Threshold |
|------------|-------------------|-------------------|
| AUTH-001 | Authentication Success | 100% success rate |
| AUTH-001 | Rate Limit Tracking | 100% accuracy |
| CORE-001 | Schema Compliance | 100% required fields |
| CORE-001 | Data Transformation Accuracy | ≥95% field match with source |
| CORE-001 | Critical Data Preservation | 100% of critical fields preserved |
| CORE-002 | Error Recovery | 95% recovery rate |
| DX-001 | Health Check Accuracy | 100% detection rate |
| DX-002 | CLI Command Success | 100% command execution |
| DX-004 | Log Capture | 100% event logging |
| LM-BT-001 | Response Completeness | 100% required fields |
| LM-BT-001 | Status Accuracy | 100% match with source |
| LM-BT-001 | Data Integrity | ≥98% field value preservation |

## 6. Safety Protocols
- **Rate Limiting**: Automatic 429 handling with exponential backoff
  ```python
  def rate_limit_handler(response, retry_after=None):
      if response.status_code == 429:
          retry_after = retry_after or int(response.headers.get('Retry-After', 60))
          time.sleep(retry_after)
          return True
      return False
  ```

- **Data Sanitization**:
  ```python
  def sanitize_response(data):
      """Remove sensitive headers and data"""
      if isinstance(data, dict):
          return {k:sanitize_response(v) for k,v in data.items() 
                 if not k.startswith('X-') and k not in ['api_key', 'key', 'secret']}
      elif isinstance(data, list):
          return [sanitize_response(item) for item in data]
      return data
  ```

- **Credential Management**: 
  - Environment variable storage with dotenv
  - Secure key rotation handling
  - Masked logging of sensitive information

## 7. Test Execution Strategy
1. **Preparation Phase**:
   - Configure API credentials securely
   - Establish baseline performance metrics
   - Define test data sets for each user story

2. **Execution Phase**:
   - Run authentication tests first (AUTH-001)
   - Execute core functionality tests (CORE-001, CORE-002)
   - Validate legislative data endpoints (LM-BT-001)
   - Test developer experience features (DX-001, DX-002, DX-004)

3. **Analysis Phase**:
   - Generate coverage reports against user stories
   - Identify any gaps in test coverage
   - Document performance baselines
   - Create visualization of test results

## 8. Next Steps
- [ ] Obtain API credentials for both Congress.gov and GovInfo.gov
- [ ] Establish comprehensive test dataset covering all user stories
- [ ] Implement Jupyter notebook with all test cells
- [ ] Create field mapping documentation between source APIs and PyGovPub normalized API
- [ ] Develop data integrity validation metrics and thresholds
- [ ] Schedule validation window with appropriate rate limit considerations
- [ ] Document results and update test coverage matrix
- [ ] Generate data transformation accuracy reports

## 9. Data Integrity Verification

### Field Mapping Documentation
To ensure proper comparison between source APIs and PyGovPub's normalized API, we'll maintain a comprehensive field mapping document that tracks:

- Source API field names and paths
- Corresponding PyGovPub field names and paths
- Transformation rules applied (if any)
- Field importance classification (critical, important, optional)
- Data type expectations and validation rules

### Comparison Metrics
For each endpoint comparison, we'll track the following metrics:

1. **Field Coverage**: Percentage of source API fields that have corresponding fields in PyGovPub
2. **Value Accuracy**: Percentage of fields where values match exactly or meet transformation rules
3. **Critical Field Preservation**: 100% of fields marked as critical must be preserved with accurate values
4. **Schema Consistency**: PyGovPub responses must maintain consistent schema across similar requests
5. **Transformation Fidelity**: For fields that undergo transformation, verify the transformation logic preserves the semantic meaning

### Visualization of Comparison Results
```python
def visualize_comparison_results(comparison_data):
    """Generate visualizations of API comparison results"""
    # Create a DataFrame from comparison results
    df = pd.DataFrame(comparison_data)
    
    # Plot match percentages by endpoint
    plt.figure(figsize=(12, 6))
    plt.bar(df['endpoint'], df['match_percentage'])
    plt.axhline(y=95, color='r', linestyle='--', label='Minimum Threshold (95%)')
    plt.title('API Response Match Percentage by Endpoint')
    plt.xlabel('Endpoint')
    plt.ylabel('Match Percentage (%)')
    plt.ylim(0, 100)
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Plot field coverage by endpoint
    plt.figure(figsize=(12, 6))
    plt.bar(df['endpoint'], df['field_coverage'])
    plt.axhline(y=98, color='r', linestyle='--', label='Minimum Threshold (98%)')
    plt.title('Field Coverage by Endpoint')
    plt.xlabel('Endpoint')
    plt.ylabel('Field Coverage (%)')
    plt.ylim(0, 100)
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return plt
```