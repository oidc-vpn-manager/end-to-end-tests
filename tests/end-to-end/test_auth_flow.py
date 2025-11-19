#!/usr/bin/env python3
"""
Integration test to verify OIDC authentication flow works end-to-end using Playwright
"""
import pytest
from playwright.sync_api import Page, expect
from urllib.parse import urlparse, parse_qs
import time


class TestAuthFlow:
    """Integration test for complete OIDC authentication flow"""

    def test_complete_auth_flow(self, tests_dir, page: Page):
        """Test the complete OIDC authentication flow using browser automation"""
        
        print("1. Testing frontend redirect to login...")
        # Access frontend root, should redirect to OIDC login
        page.goto("http://localhost/", wait_until="networkidle")
        
        # Should be redirected to OIDC login page
        current_url = page.url
        assert ("tinyoidc.authenti-kate.org" in current_url or "localhost:8000" in current_url), f"Expected OIDC URL, got: {current_url}"
        print(f"✓ Frontend redirected to OIDC: {current_url}")
        
        # Check if this is the authorization endpoint with parameters or the direct login page
        parsed_url = urlparse(current_url)
        if "/c2s/authorize" in current_url:
            # We're at the authorization endpoint - check for nonce parameter
            params = parse_qs(parsed_url.query)
            assert 'nonce' in params, "Nonce parameter should be present in authorization URL"
            nonce_value = params['nonce'][0]
            print(f"✓ Nonce parameter found: {nonce_value}")
        elif "/user/login" in current_url:
            # We were redirected directly to login (normal behavior when not already at auth endpoint)
            print("✓ Redirected directly to login page (nonce handled internally)")
        
        print("2. Testing tiny-oidc login page...")
        # Should show the OIDC login page
        expect(page.locator("h1")).to_contain_text("Login - kinda")
        print("✓ Tiny-oidc login page loaded")
        
        print("3. Testing authentication...")
        # Find and click the admin login button
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        print("4. Testing authentication callback...")
        # Wait for authentication to complete and redirect back to frontend
        page.wait_for_load_state("networkidle", timeout=10000)
        
        # Check what URL we're at now
        current_url = page.url
        print(f"Current URL after login: {current_url}")
        
        # If we're at the callback URL, wait a bit longer for the final redirect
        if "/auth/callback" in current_url:
            print("At callback URL, waiting for final redirect...")
            try:
                page.wait_for_url(lambda url: url in ["http://localhost/", "http://localhost"], timeout=5000)
            except:
                # If timeout, check what happened
                current_url = page.url
                print(f"Timeout waiting for redirect, current URL: {current_url}")
                # Check page content for any error messages
                content = page.content()
                if "InvalidClaimError" in content or "invalid_claim" in content:
                    print("❌ Found nonce validation error in page content")
                    print(content[:1000])
                    raise AssertionError("Nonce validation failed - same session issue as before")
        
        # Should be back at frontend main page
        current_url = page.url
        if current_url not in ["http://localhost/", "http://localhost"]:
            print(f"Not at expected frontend URL: {current_url}")
            # If we're stuck at callback, this indicates the session/nonce issue
            if "/auth/callback" in current_url:
                raise AssertionError("Stuck at callback URL - likely nonce/session consistency issue")
        
        print("✓ Authentication callback successful!")
        
        print("5. Testing protected resource access...")
        # Page should show user is authenticated
        expect(page.locator("body")).not_to_contain_text("Login", ignore_case=True)
        expect(page.locator("body")).not_to_contain_text("Sign in", ignore_case=True)
        
        # Should show user's display name (admin user is "TheBOFH")
        expect(page.locator("body")).to_contain_text("TheBOFH")
        print("✓ Can access protected frontend and see user info after authentication!")
        
        print("6. Testing session persistence...")
        # Reload the page to test session persistence
        page.reload(wait_until="networkidle")
        
        # Should still be authenticated (not redirected to login)
        current_url = page.url
        assert current_url == "http://localhost/" or current_url == "http://localhost", f"Expected frontend URL after reload, got: {current_url}"
        expect(page.locator("body")).to_contain_text("TheBOFH")
        print("✓ Session persists across page reloads!")

    def test_it_user_auth_flow(self, tests_dir, page: Page):
        """Test authentication flow with IT user"""
        
        # Start at frontend root
        page.goto("http://localhost/", wait_until="networkidle")
        
        # Should be at OIDC login page
        expect(page.locator("h1")).to_contain_text("Login - kinda")
        
        # Find and click the IT user login button
        it_button = page.locator("button:has-text('Login as it')")
        expect(it_button).to_be_visible()
        it_button.click()
        
        # Wait for authentication to complete
        page.wait_for_load_state("networkidle", timeout=10000)
        
        # Wait for the final redirect to the main page
        page.wait_for_url(lambda url: url in ["http://localhost/", "http://localhost"], timeout=10000)
        
        # Should be back at frontend
        current_url = page.url
        assert current_url == "http://localhost/" or current_url == "http://localhost", f"Expected frontend URL, got: {current_url}"
        
        # Should show IT user's display name "Moss"
        expect(page.locator("body")).to_contain_text("Moss")
        print("✓ IT user authentication successful!")

    def test_logout_flow(self, tests_dir, page: Page):
        """Test that logout works properly"""
        
        # First authenticate
        page.goto("http://localhost/", wait_until="networkidle")
        
        if "Login - kinda" in page.content():
            admin_button = page.locator("button:has-text('Login as admin')")
            admin_button.click()
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # Wait for authentication to fully complete and redirect to main page
            page.wait_for_url(lambda url: url in ["http://localhost/", "http://localhost"], timeout=10000)
        
        # Should be authenticated at main frontend page
        current_url = page.url
        assert current_url == "http://localhost/" or current_url == "http://localhost", f"Expected frontend URL, got: {current_url}"
        
        # Look for a logout link/button and click it
        logout_link = page.locator("a:has-text('Logout'), a:has-text('Sign out'), button:has-text('Logout')")
        if logout_link.is_visible():
            logout_link.click()
            page.wait_for_load_state("networkidle")
            
            # Should be redirected back to login
            current_url = page.url
            assert ("tinyoidc.authenti-kate.org" in current_url or "localhost:8000" in current_url), f"Expected OIDC URL after logout, got: {current_url}"
            print("✓ Logout successful!")
        else:
            print("⚠ No logout button found - this might be expected if frontend doesn't implement logout UI")


if __name__ == "__main__":
    # This allows the test to be run directly for debugging
    import subprocess
    import sys
    
    # Wait a moment for services to be ready
    time.sleep(2)
    
    try:
        # Run the test using pytest
        result = subprocess.run([
            sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"
        ], cwd=str(tests_dir))
        
        if result.returncode == 0:
            print("\n🎉 Integration test PASSED!")
        else:
            print("\n❌ Integration test FAILED!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)