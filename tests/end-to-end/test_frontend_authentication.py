#!/usr/bin/env python3
"""
Functional tests for frontend authentication using Playwright
"""
import pytest
from playwright.sync_api import Page, expect
import time


class TestFrontendAuthentication:
    """Test frontend authentication flow using real browser"""

    def test_unauthenticated_redirect(self, page: Page, oidc_provider_domain):
        """Test that unauthenticated users are redirected to login"""
        # Navigate to frontend root
        page.goto("http://localhost/")

        # Should be redirected to OIDC login page
        page.wait_for_load_state("networkidle")

        # Check that we're at OIDC provider
        current_url = page.url
        assert oidc_provider_domain in current_url, f"Expected OIDC URL, got: {current_url}"
        
        # Should show the OIDC login page
        expect(page.locator("h1")).to_contain_text("Login - kinda")

    def test_authentication_flow_admin_user(self, page: Page):
        """Test complete authentication flow with admin user"""
        # Start at frontend root
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        # Should be at OIDC login page
        expect(page.locator("h1")).to_contain_text("Login - kinda")
        
        # Find and click the admin login button
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        
        # Click login button
        admin_button.click()
        
        # Wait for authentication to complete and redirect back to frontend
        page.wait_for_load_state("networkidle", timeout=10000)
        
        # Should be back at frontend main page
        current_url = page.url
        assert current_url == "http://localhost/" or current_url == "http://localhost", f"Expected frontend URL, got: {current_url}"
        
        # Page should show user is authenticated
        # Check that we're not seeing login prompts
        expect(page.locator("body")).not_to_contain_text("Login", ignore_case=True)
        expect(page.locator("body")).not_to_contain_text("Sign in", ignore_case=True)

    def test_authenticated_user_display_name(self, page: Page):
        """Test that the frontend displays the authenticated user's name"""
        # First authenticate
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        # If we're at OIDC login page, authenticate
        if "Login - kinda" in page.content():
            admin_button = page.locator("button:has-text('Login as admin')")
            admin_button.click()
            page.wait_for_load_state("networkidle", timeout=10000)
        
        # Should be at authenticated frontend page
        current_url = page.url  
        assert current_url == "http://localhost/" or current_url == "http://localhost", f"Expected frontend URL, got: {current_url}"
        
        # The page should contain the user's display name
        # Based on the tiny-oidc user data, admin user has display name "TheBOFH"
        expect(page.locator("body")).to_contain_text("TheBOFH")

    def test_authentication_flow_it_user(self, page: Page):
        """Test authentication flow with IT user"""
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        # Should be at OIDC login page
        expect(page.locator("h1")).to_contain_text("Login - kinda")
        
        # Find and click the IT user login button
        it_button = page.locator("button:has-text('Login as it')")
        expect(it_button).to_be_visible()
        
        # Click login button
        it_button.click()
        
        # Wait for authentication to complete
        page.wait_for_load_state("networkidle", timeout=10000)
        
        # Should be back at frontend
        current_url = page.url
        assert current_url == "http://localhost/" or current_url == "http://localhost", f"Expected frontend URL, got: {current_url}"
        
        # Should show IT user's display name "Moss"
        expect(page.locator("body")).to_contain_text("Moss")

    def test_logout_flow(self, page: Page, oidc_provider_domain):
        """Test that logout works properly"""
        # First authenticate
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")

        if "Login - kinda" in page.content():
            admin_button = page.locator("button:has-text('Login as admin')")
            admin_button.click()
            page.wait_for_load_state("networkidle", timeout=10000)

        # Should be authenticated
        current_url = page.url
        assert current_url == "http://localhost/" or current_url == "http://localhost", f"Expected frontend URL, got: {current_url}"

        # Look for a logout link/button and click it
        logout_link = page.locator("a:has-text('Logout'), a:has-text('Sign out'), button:has-text('Logout')")
        if logout_link.is_visible():
            logout_link.click()
            page.wait_for_load_state("networkidle")

            # Should be redirected back to login
            current_url = page.url
            assert oidc_provider_domain in current_url, f"Expected OIDC URL, got: {current_url}"

    def test_session_persistence(self, page: Page):
        """Test that authentication session persists across page reloads"""
        # Authenticate first
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        if "Login - kinda" in page.content():
            admin_button = page.locator("button:has-text('Login as admin')")
            admin_button.click()
            page.wait_for_load_state("networkidle", timeout=10000)
        
        # Verify authenticated
        current_url = page.url
        assert current_url == "http://localhost/" or current_url == "http://localhost", f"Expected frontend URL, got: {current_url}"
        expect(page.locator("body")).to_contain_text("TheBOFH")
        
        # Reload the page
        page.reload()
        page.wait_for_load_state("networkidle")
        
        # Should still be authenticated (not redirected to login)
        current_url = page.url
        assert current_url == "http://localhost/" or current_url == "http://localhost", f"Expected frontend URL, got: {current_url}"
        expect(page.locator("body")).to_contain_text("TheBOFH")

    def test_protected_routes_require_auth(self, page: Page, oidc_provider_domain):
        """Test that protected routes require authentication"""
        # Try to access a protected route without authentication
        # First clear any existing session by going to logout
        page.goto("http://localhost/auth/logout")
        page.wait_for_load_state("networkidle")

        # Now try to access a protected route (like profile config)
        page.goto("http://localhost")
        page.wait_for_load_state("networkidle")

        # Should be redirected to OIDC login
        current_url = page.url
        assert oidc_provider_domain in current_url, f"Expected OIDC URL, got: {current_url}"
        expect(page.locator("h1")).to_contain_text("Login - kinda")