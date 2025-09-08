#!/usr/bin/env python3
"""
End-to-end test for service separation functionality.
Tests the separation between user-facing and admin-facing services.
"""

import pytest
import requests
import time
from playwright.sync_api import expect, Page


class TestServiceSeparation:
    """Test service separation between user and admin frontends."""
    
    def test_user_service_rejects_admin_routes(self):
        """Test that user service (port 8450) rejects admin routes with 302."""
        # Test admin PSK route
        response = requests.get("http://localhost:8450/admin/psk", allow_redirects=False)
        assert response.status_code == 302, f"Expected 302, got {response.status_code}"
        
        # Test admin certificates route
        response = requests.get("http://localhost:8450/admin/certificates", allow_redirects=False)
        assert response.status_code == 302, f"Expected 302, got {response.status_code}"
        
    def test_admin_service_redirects_user_routes(self):
        """Test that admin service (port 8540) redirects user routes to user service."""
        # Test user profile route
        response = requests.get("http://localhost:8540/profile/certificates", allow_redirects=False)
        assert response.status_code == 301, f"Expected 301, got {response.status_code}"
        assert "localhost:8450" in response.headers.get('Location', ''), "Should redirect to user service"
        
    def test_user_service_api_endpoints(self):
        """Test API endpoints on user service."""
        # User service should reject server bundle API (admin function) 
        response = requests.get(
            "http://localhost:8450/api/v1/server/bundle",
            headers={"Authorization": "Bearer invalid-key"},
            allow_redirects=False
        )
        # Should get 403 (forbidden) - endpoint not available on user service
        assert response.status_code == 403, f"Expected 403 (endpoint forbidden), got {response.status_code}"
        
    def test_admin_service_api_endpoints(self):
        """Test API endpoints on admin service."""
        # Admin service should accept server bundle API (admin function)
        response = requests.get(
            "http://localhost:8540/api/v1/server/bundle", 
            headers={"Authorization": "Bearer invalid-key"},
            allow_redirects=False
        )
        # Should get 401 (unauthorized) not 403 (forbidden) - endpoint exists
        assert response.status_code == 401, f"Expected 401 (endpoint exists), got {response.status_code}"
        
        
    def test_combined_service_allows_all_routes(self):
        """Test that combined service (port 80) allows all routes (backward compatibility)."""
        # Should allow admin routes
        response = requests.get("http://localhost/admin/psk", allow_redirects=False)
        # Should get redirect to login (302) not forbidden (403)
        assert response.status_code == 302, f"Expected 302 (login redirect), got {response.status_code}"
        assert "/auth/login" in response.headers.get('Location', ''), "Should redirect to login"
        
        # Should allow user routes  
        response = requests.get("http://localhost/profile/certificates", allow_redirects=False)
        assert response.status_code == 302, f"Expected 302 (login redirect), got {response.status_code}"
        assert "/auth/login" in response.headers.get('Location', ''), "Should redirect to login"
        
        # Should allow server bundle API endpoint
        response = requests.get(
            "http://localhost/api/v1/server/bundle",
            headers={"Authorization": "Bearer invalid-key"}
        )
        assert response.status_code == 401, f"Expected 401 (unauthorized), got {response.status_code}"


class TestServiceSeparationE2EWithAuth:
    """Test service separation with authenticated users using Playwright."""
    
    @pytest.fixture
    def authenticated_page_factory(self, browser):
        """Factory to create authenticated pages for different services."""
        created_contexts = []
        
        def _create_authenticated_page(base_url: str, user_type: str):
            context = browser.new_context(
                ignore_https_errors=True,
                viewport={"width": 1280, "height": 720},
            )
            created_contexts.append(context)
            page = context.new_page()
            page.set_default_timeout(30000)
            
            # Login using the existing pattern but with custom base URL
            page.goto(f"{base_url}/auth/login")
            
            # Go through OIDC login
            page.goto("http://localhost:8000/user/logout", wait_until="networkidle")  # Clear tiny-oidc first
            page.goto(f"{base_url}/auth/login")
            page.wait_for_load_state("networkidle", timeout=15000)
            
            # Should be redirected to tiny-oidc login
            expect(page.locator("h1")).to_contain_text("Login", timeout=10000)
            
            # Click the appropriate user login button
            user_button = page.locator(f'button:has-text("Login as {user_type}")')
            expect(user_button).to_be_visible(timeout=5000)
            user_button.click()
            page.wait_for_load_state("networkidle", timeout=15000)
            
            return page
        
        yield _create_authenticated_page
        
        # Cleanup
        for context in created_contexts:
            try:
                context.close()
            except:
                pass
    
    def test_admin_user_redirected_to_admin_service(self, authenticated_page_factory):
        """Test that admin users on user service get redirected to admin service."""
        # Get authenticated admin page on user service
        user_page = authenticated_page_factory("http://localhost:8450", "admin")
        
        # Try to access CT log on user service (should redirect admin users to admin service)
        user_page.goto("http://localhost:8450/certificates")
        
        # Should be redirected to admin service
        user_page.wait_for_load_state("networkidle", timeout=10000)
        # Check for redirect to admin service - accept both with and without trailing slash
        current_url = user_page.url
        assert current_url in ["http://localhost:8540/certificates", "http://localhost:8540/certificates/"], f"Expected redirect to admin service certificates page, got {current_url}"
        
    def test_user_service_shows_correct_branding(self, authenticated_page_factory):
        """Test that user service shows user-focused branding."""
        user_page = authenticated_page_factory("http://localhost:8450", "it")
        user_page.goto("http://localhost:8450/")
        
        # Should show user service branding - wait for page to fully load first
        user_page.wait_for_load_state("networkidle", timeout=10000)
        title = user_page.title()
        assert "VPN User Service" in title, f"Expected title to contain 'VPN User Service', got '{title}'"
        
    def test_admin_service_shows_correct_branding(self, authenticated_page_factory):
        """Test that admin service shows admin-focused branding."""
        admin_page = authenticated_page_factory("http://localhost:8540", "admin")  
        admin_page.goto("http://localhost:8540/")
        
        # Should show admin service branding - wait for page to fully load first
        admin_page.wait_for_load_state("networkidle", timeout=10000)
        title = admin_page.title()
        assert "VPN Admin Service" in title, f"Expected title to contain 'VPN Admin Service', got '{title}'"
        
    def test_user_profile_accessible_on_user_service(self, authenticated_page_factory):
        """Test that user profiles work normally on user service."""
        user_page = authenticated_page_factory("http://localhost:8450", "it")
        user_page.goto("http://localhost:8450/profile/certificates")
        
        # Should successfully load user profile page
        expect(user_page.locator("h1, h2")).to_contain_text("Certificate", timeout=10000)
        
    def test_admin_functions_accessible_on_admin_service(self, authenticated_page_factory):
        """Test that admin functions work normally on admin service."""
        admin_page = authenticated_page_factory("http://localhost:8540", "admin")
        admin_page.goto("http://localhost:8540/admin/psk")
        
        # Should successfully load admin PSK page
        expect(admin_page.locator("h1, h2")).to_contain_text("Pre-Shared", timeout=10000)
        
    def test_cross_service_redirects_preserve_query_parameters(self, authenticated_page_factory):
        """Test that redirects between services preserve query parameters."""
        admin_page = authenticated_page_factory("http://localhost:8450", "admin")
        
        # Access CT log with query parameters on user service
        admin_page.goto("http://localhost:8450/certificates?page=2&filter=active")
        
        # Should redirect to admin service with same parameters
        admin_page.wait_for_load_state("networkidle", timeout=10000)
        current_url = admin_page.url
        assert "localhost:8540" in current_url, f"Should redirect to admin service, got {current_url}"
        assert "page=2" in current_url, f"Should preserve query params, got {current_url}"
        assert "filter=active" in current_url, f"Should preserve query params, got {current_url}"


class TestServiceHealthChecks:
    """Test that health checks work on all services."""
    
    def test_all_services_healthy(self):
        """Test that all frontend services report healthy status."""
        services = [
            ("Combined", "http://localhost"),
            ("User", "http://localhost:8450"), 
            ("Admin", "http://localhost:8540")
        ]
        
        for name, base_url in services:
            response = requests.get(f"{base_url}/health")
            assert response.status_code == 200, f"{name} service health check failed"
            
            health_data = response.json()
            assert health_data["status"] == "healthy", f"{name} service not healthy: {health_data}"
            assert health_data["service"] == "frontend", f"Wrong service type: {health_data}"
            

class TestServiceConfigurationValidation:
    """Test service configuration is correct."""
    
    def test_user_service_has_admin_url_configured(self):
        """Test that user service has ADMIN_URL_BASE configured."""
        # Make a request that should trigger admin redirect for admin users
        response = requests.get("http://localhost:8450/admin/psk", allow_redirects=False)
        assert response.status_code == 302, "User service should redirect admin routes"
        
    def test_admin_service_has_user_url_configured(self):
        """Test that admin service has USER_URL_BASE configured."""
        # Make a request that should trigger user redirect
        response = requests.get("http://localhost:8540/profile/certificates", allow_redirects=False)
        assert response.status_code == 301, "Admin service should redirect user routes"
        
    def test_combined_service_has_no_separation_configured(self):
        """Test that combined service has no separation URLs configured."""
        # Combined service should accept all routes without separation redirects
        response = requests.get("http://localhost/admin/psk", allow_redirects=False)
        # Should redirect to login (302) not reject with 403
        assert response.status_code == 302, "Combined service should allow all routes"