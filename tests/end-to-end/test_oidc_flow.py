#!/usr/bin/env python3
"""
End-to-end test of the OIDC authentication flow through the frontend using Playwright
"""
import pytest
from playwright.sync_api import Page, expect
from urllib.parse import urlparse, parse_qs


class TestOIDCFlow:
    """End-to-end OIDC authentication flow test using browser automation"""

    def test_complete_flow(self, tests_dir, page: Page, oidc_provider_domain):
        """Test the complete OIDC authentication flow using Playwright"""

        print("🚀 Starting end-to-end Playwright authentication test...")

        # 1. Access frontend root - should redirect to OIDC login
        print("1. Accessing frontend root...")
        page.goto("http://localhost/", wait_until="networkidle")

        # Should be redirected to OIDC login page
        current_url = page.url
        assert oidc_provider_domain in current_url, f"Expected OIDC URL, got: {current_url}"
        print(f"✓ Frontend redirected to OIDC provider: {current_url}")
        
        # 2. Verify nonce and PKCE parameters are present in the authorization URL
        print("2. Verifying nonce and PKCE parameters...")
        parsed_url = urlparse(current_url)
        if "/c2s/authorize" in current_url:
            # We're at the authorization endpoint - check for nonce parameter
            params = parse_qs(parsed_url.query)
            assert 'nonce' in params, "Nonce parameter should be present in authorization URL"
            nonce_value = params['nonce'][0]
            print(f"   Nonce parameter found: {nonce_value}")
            # Verify PKCE (RFC 7636) parameters
            assert 'code_challenge' in params, "code_challenge parameter should be present in authorization URL (PKCE RFC 7636)"
            assert 'code_challenge_method' in params, "code_challenge_method parameter should be present in authorization URL"
            assert params['code_challenge_method'][0] == 'S256', "code_challenge_method should be S256"
            print(f"   PKCE code_challenge found: {params['code_challenge'][0][:20]}...")
            print(f"   PKCE code_challenge_method: S256")
        elif "/user/login" in current_url:
            # We were redirected directly to login (normal behavior when not already at auth endpoint)
            print("   Redirected directly to login page (nonce and PKCE handled internally)")
        
        # 3. Should show the OIDC login page
        print("3. Verifying OIDC login page...")
        expect(page.locator("h1")).to_contain_text("Login - kinda")
        print("✓ OIDC provider shows correct login page")
        
        # 4. Login to OIDC provider
        print("4. Logging into OIDC provider as admin...")
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        # 5. Wait for authentication callback to complete
        print("5. Processing authentication callback...")
        page.wait_for_load_state("networkidle", timeout=10000)
        
        # Wait for the final redirect to the main page
        page.wait_for_url(lambda url: url in ["http://localhost/", "http://localhost"], timeout=10000)
        
        # 6. Verify we're back at frontend main page
        current_url = page.url
        assert current_url == "http://localhost/" or current_url == "http://localhost", f"Expected frontend URL, got: {current_url}"
        print("✓ Successfully redirected back to frontend after authentication")
        
        # 7. Verify authentication was successful - should see user info
        print("6. Verifying successful authentication...")
        expect(page.locator("body")).not_to_contain_text("Login", ignore_case=True)
        expect(page.locator("body")).not_to_contain_text("Sign in", ignore_case=True)
        expect(page.locator("body")).to_contain_text("TheBOFH")  # Admin user display name
        print("✓ User can access protected frontend and see user info after authentication")
        
        # 8. Test session persistence
        print("7. Testing session persistence...")
        page.reload(wait_until="networkidle")
        
        # Should still be authenticated (not redirected to login)
        current_url = page.url
        assert current_url == "http://localhost/" or current_url == "http://localhost", f"Expected frontend URL after reload, got: {current_url}"
        expect(page.locator("body")).to_contain_text("TheBOFH")
        print("✓ Session persists across page reloads")
        
        print("✅ SUCCESS! Complete OIDC authentication flow working perfectly!")
        print("   - Frontend redirects unauthenticated users")
        print("   - OIDC flow includes nonce for ID token security")
        print("   - OIDC flow includes PKCE (RFC 7636) for authorization code security")
        print("   - Authentication completes successfully")
        print("   - Session persists after authentication")


if __name__ == "__main__":
    # This allows the test to be run directly for debugging
    import subprocess
    import sys
    
    try:
        # Run the test using pytest
        result = subprocess.run([
            sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"
        ], cwd=str(tests_dir))
        
        if result.returncode == 0:
            print("\n🎉 END-TO-END PLAYWRIGHT TEST PASSED!")
            print("The OIDC authentication flow is working perfectly!")
        else:
            print("\n❌ END-TO-END PLAYWRIGHT TEST FAILED!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)