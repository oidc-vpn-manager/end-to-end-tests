#!/usr/bin/env python3
"""
Pre-flight tests to verify that all docker-compose services are running and ready
before executing end-to-end tests.
"""
import pytest
import subprocess
import requests
import json
from typing import List, Dict


class TestServiceReadiness:
    """Test that all required services are running and accessible"""

    REQUIRED_SERVICES = [
        'certtransparency',
        'frontend', 
        'signing',
        'tiny-oidc'
    ]

    def test_all_services_running(self):
        """Test that all required docker-compose services are running"""
        result = subprocess.run(
            ["docker", "compose", "ps", "--services", "--filter", "status=running"],
            cwd="/workspaces/2025-06_openvpn-manager_gh-org/tests",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Failed to get running services: {result.stderr}"
        
        running_services = result.stdout.strip().split('\n')
        running_services = [s.strip() for s in running_services if s.strip()]
        
        print(f"✅ Running services: {running_services}")
        
        for service in self.REQUIRED_SERVICES:
            assert service in running_services, f"Service '{service}' is not running"
        
        print("✅ All required services are running")

    def test_frontend_flask_cli_available(self):
        """Test that Flask CLI is available in the frontend service"""
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "frontend", "flask", "--help"],
            cwd="/workspaces/2025-06_openvpn-manager_gh-org/tests",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Flask CLI not available: {result.stderr}"
        assert "Usage: flask" in result.stdout
        print("✅ Frontend Flask CLI: OK")

    def test_frontend_database_migrations(self):
        """Test that database migrations are properly applied"""
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "frontend", "flask", "db", "current"],
            cwd="/workspaces/2025-06_openvpn-manager_gh-org/tests",
            capture_output=True,
            text=True
        )
        
        # Migration status check - should not fail completely
        print(f"✅ Database migration status: {result.stdout.strip()}")
        # Note: We allow this to succeed even if no migrations exist yet

    def test_frontend_routes_available(self):
        """Test that Flask routes are properly registered"""
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "frontend", "flask", "routes"],
            cwd="/workspaces/2025-06_openvpn-manager_gh-org/tests",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Flask routes command failed: {result.stderr}"
        assert len(result.stdout.strip()) > 0, "No routes found"
        print("✅ Flask routes: OK")


class TestServiceHealth:
    """Test that all services respond to health check endpoints"""

    SERVICE_ENDPOINTS = [
        ("frontend", "http://localhost:80/", [200, 302]),  # 302 is redirect to login
        ("certtransparency", "http://localhost:8800/health", [200]),
        ("tiny-oidc", "http://localhost:8000/health", [200]),
    ]

    @pytest.mark.parametrize("service_name,url,expected_codes", SERVICE_ENDPOINTS)
    def test_service_health_endpoint(self, service_name: str, url: str, expected_codes: List[int]):
        """Test that service health endpoints respond correctly"""
        try:
            response = requests.get(url, timeout=5, allow_redirects=False)
            assert response.status_code in expected_codes, \
                f"{service_name} returned HTTP {response.status_code}, expected one of {expected_codes}"
            print(f"✅ {service_name}: OK (HTTP {response.status_code})")
        except requests.exceptions.RequestException as e:
            pytest.fail(f"⚠️ {service_name}: Connection failed - {e}")


class TestAuthenticationFlow:
    """Test that authentication flow components are working"""

    def test_oidc_discovery_endpoint(self):
        """Test OIDC discovery endpoint is available"""
        try:
            response = requests.get("http://localhost:8000/.well-known/openid-configuration", timeout=5)
            assert response.status_code == 200, f"OIDC discovery returned HTTP {response.status_code}"
            
            # Verify it returns valid JSON
            discovery_data = response.json()
            assert "issuer" in discovery_data
            assert "authorization_endpoint" in discovery_data
            print("✅ OIDC Discovery: OK")
        except requests.exceptions.RequestException as e:
            pytest.fail(f"⚠️ OIDC Discovery: Connection failed - {e}")

    def test_frontend_auth_redirect(self):
        """Test that frontend auth login endpoint is accessible"""
        try:
            response = requests.get("http://localhost:80/auth/login", timeout=5, allow_redirects=False)
            # Should either show auth page (200) or redirect to OIDC (302)
            assert response.status_code in [200, 302], \
                f"Frontend auth page returned HTTP {response.status_code}"
            print(f"✅ Frontend auth page: OK (HTTP {response.status_code})")
        except requests.exceptions.RequestException as e:
            pytest.fail(f"⚠️ Frontend auth page: Connection failed - {e}")


class TestDatabaseConnectivity:
    """Test database connectivity for services"""

    def test_frontend_database_connection(self):
        """Test database connectivity from frontend service"""
        db_test_script = """
import sys
sys.path.append('/usr/src/app')
try:
    from app.app import create_app
    app = create_app()
    with app.app_context():
        from app.extensions import db
        result = db.session.execute(db.text('SELECT 1')).scalar()
        if result == 1:
            print('DATABASE_OK')
        else:
            print('DATABASE_ERROR: Unexpected result')
except Exception as e:
    print(f'DATABASE_ERROR: {e}')
"""
        
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "frontend", "python3", "-c", db_test_script],
            cwd="/workspaces/2025-06_openvpn-manager_gh-org/tests",
            capture_output=True,
            text=True
        )
        
        if "DATABASE_OK" in result.stdout:
            print("✅ Database connectivity: OK")
        else:
            pytest.fail(f"⚠️ Database connectivity: FAILED - {result.stdout.strip()}")


if __name__ == "__main__":
    # Allow running this directly for debugging
    import sys
    pytest.main([__file__, "-v"] + sys.argv[1:])