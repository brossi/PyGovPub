"""
Locust load testing file for PyGovPub API.

This file defines load testing scenarios for the PyGovPub API endpoints.
"""

from locust import HttpUser, task, between


class APIUser(HttpUser):
    """Simulated API user for load testing."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup before tests run."""
        # Add API key to all subsequent requests
        self.client.headers.update({
            "X-API-Key": "test_api_key"
        })
    
    @task(3)
    def search_bills(self):
        """Test bill search endpoint."""
        self.client.get("/api/v1/bills/search")
    
    @task(2)
    def get_bill(self):
        """Test get bill endpoint."""
        self.client.get("/api/v1/bills/HR1234-117")
    
    @task(1)
    def verify_document(self):
        """Test document verification endpoint."""
        self.client.get("/api/v1/documents/BILLS-117hr1234ih/verify")
    
    @task(1)
    def get_member(self):
        """Test get member endpoint."""
        self.client.get("/api/v1/members/S000148")
    
    @task(1)
    def health_check(self):
        """Test health check endpoint."""
        self.client.get("/health")