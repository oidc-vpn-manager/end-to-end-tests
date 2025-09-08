"""
Test authentication context switching to verify user sessions work correctly.

This test validates that we can properly switch between different user contexts
and confirm the authentication state at each step.
"""

import pytest
from playwright.sync_api import Page, expect
from conftest import login_as


class TestAuthenticationContextSwitching:
    """Test proper authentication context switching between users."""

    def test_authentication_context_switching_flow(self, page: Page):
        """
        Test complete authentication context switching flow:
        1. Login as 'accounts' user and confirm identity
        2. Logout completely (TinyOIDC first, then Frontend)  
        3. Confirm redirect to login page
        4. Login as 'admin' user and confirm identity
        5. Verify admin-specific functionality is accessible
        """
        
        print("=== STEP 1: Login as 'accounts' user ===")
        
        # Step 1: Login as accounts user
        login_as("accounts", page)
        
        # Verify we're logged in as accounts user
        page.goto("http://localhost/", wait_until="networkidle")
        expect(page.locator("h1")).to_contain_text("VPN Service")
        
        # Debug: Take screenshot and check page content
        print("DEBUG: Page title:", page.title())
        print("DEBUG: Current URL:", page.url)
        
        # Verify authentication by accessing a protected page
        page.goto("http://localhost/profile/certificates", wait_until="networkidle")
        
        # Should successfully access the page (not redirected to login)
        expect(page.locator("h1")).to_contain_text("My Certificates")
        
        print("✓ Confirmed authenticated as accounts user - can access protected profile page")
        
        # Check that we can't access admin functions as accounts user
        page.goto("http://localhost/admin/certificates", wait_until="networkidle")
        
        # Should be denied access or redirected (admin only page)
        page_content = page.content()
        is_admin_page = "Certificate Transparency" in page_content and "subject-filter" in page_content
        assert not is_admin_page, "Accounts user should not be able to access admin certificates page"
        
        print("✓ Confirmed logged in as accounts user - cannot access admin pages")
        
        print("=== STEP 2: Complete logout (TinyOIDC first, then Frontend) ===")
        
        # Step 2: Logout completely - TinyOIDC first 
        page.goto("http://tinyoidc.authenti-kate.org/logout", wait_until="networkidle")
        page.wait_for_timeout(1000)
        
        # Then frontend logout
        page.goto("http://localhost/auth/logout", wait_until="networkidle") 
        page.wait_for_timeout(1000)
        
        # Clear cookies to ensure clean state
        page.context.clear_cookies()
        
        print("✓ Completed full logout")
        
        print("=== STEP 3: Confirm redirect to login page ===")
        
        # Step 3: Verify we're logged out by going to frontend
        page.goto("http://localhost/", wait_until="networkidle")
        
        # Should be redirected to TinyOIDC login page
        expect(page.locator("h1")).to_contain_text("Login - kinda")
        
        # Should see login buttons for different users
        expect(page.locator('button:has-text("Login as admin")')).to_be_visible()
        expect(page.locator('button:has-text("Login as accounts")')).to_be_visible()
        
        print("✓ Confirmed redirected to login page when not authenticated")
        
        print("=== STEP 4: Login as 'admin' user ===")
        
        # Step 4: Login as admin user (different from before)
        admin_button = page.locator('button:has-text("Login as admin")')
        admin_button.click()
        page.wait_for_load_state("networkidle", timeout=15000)
        
        # Should be redirected back to frontend
        expect(page.locator("h1")).to_contain_text("VPN Service")
        
        print("✓ Completed admin login")
        
        print("=== STEP 5: Verify admin identity and access ===")
        
        # Step 5: Verify we're now logged in as admin by accessing admin functionality
        page.goto("http://localhost/admin/certificates", wait_until="networkidle")
        
        # Should be on admin certificates page (not redirected to login)
        expect(page.locator("h1")).to_contain_text("Administrate Issued Certificates")
        
        # Should have admin-specific elements
        expect(page.locator('input[name="subject"]')).to_be_visible()
        
        # Also verify we can still access user profile
        page.goto("http://localhost/profile/certificates", wait_until="networkidle")
        expect(page.locator("h1")).to_contain_text("My Certificates")
        
        print("✓ Confirmed logged in as admin user - can access both admin and user pages")
        print("✓ Confirmed admin functionality accessible")
        
        print("=== SUCCESS: Authentication context switching works correctly! ===")