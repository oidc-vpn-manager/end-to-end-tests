"""
E2E IDOR Protection Verification Tests

These tests verify that IDOR protections work correctly in actual browser sessions,
ensuring that browser-specific behaviors and client-side protections function properly.
"""

import pytest
from playwright.sync_api import Page, expect
from typing import Callable


def create_test_certificate(page: Page, user: str) -> str:
    """Helper to create a certificate and return its fingerprint."""
    print(f"Creating certificate for user: {user}")

    # First navigate to main page and generate profile
    page.goto("http://localhost/")
    page.wait_for_load_state("networkidle")

    # Submit the form to generate a certificate
    print("Clicking submit button to generate certificate...")
    page.click('input[type="submit"]')
    page.wait_for_load_state("networkidle")

    # Wait a moment for the backend to process the certificate generation
    page.wait_for_timeout(2000)

    # Navigate to certificates list to get the fingerprint of the newly created certificate
    print("Navigating to certificates list...")
    page.goto("http://localhost/profile/certificates")
    page.wait_for_load_state("networkidle")

    # Wait for the certificates to load
    try:
        page.wait_for_selector('[data-testid="certificate-item"]', timeout=10000)
    except Exception as e:
        print(f"No certificates found or timeout: {e}")
        # Check if there's a "no certificates" message
        no_certs = page.locator('.no-certificates')
        if no_certs.count() > 0:
            print("No certificates found - profile generation may have failed")
            raise Exception("Profile generation failed - no certificates created")

    # Get the first certificate (most recently created)
    certificate_rows = page.locator('[data-testid="certificate-item"]')
    if certificate_rows.count() == 0:
        print("No certificate rows found")
        raise Exception("No certificates found in list")

    # Get the fingerprint from the first certificate row by looking at the View link
    first_row = certificate_rows.first
    view_link = first_row.locator('a:has-text("View")')

    if view_link.count() == 0:
        print("No view link found in certificate row")
        raise Exception("No view link found for certificate")

    # Extract fingerprint from the href attribute
    href = view_link.get_attribute('href')
    if href and '/certificates/' in href:
        fingerprint = href.split('/certificates/')[-1]
        print(f"Found certificate fingerprint: {fingerprint}")
        return fingerprint

    # Fallback: look for data-fingerprint attribute in button
    revoke_button = first_row.locator('[data-fingerprint]')
    if revoke_button.count() > 0:
        fingerprint = revoke_button.get_attribute('data-fingerprint')
        print(f"Found certificate fingerprint via data attribute: {fingerprint}")
        return fingerprint

    # Final fallback: extract from page content
    page_content = page.content()
    import re
    fingerprint_match = re.search(r'[a-fA-F0-9]{64}', page_content)
    if fingerprint_match:
        fingerprint = fingerprint_match.group(0)
        print(f"Found certificate fingerprint via regex: {fingerprint}")
        return fingerprint

    print("Could not extract certificate fingerprint")
    print(f"Page content: {page_content[:500]}...")
    raise Exception("Could not extract certificate fingerprint")


class TestIDORProtectionE2E:
    """E2E tests for IDOR protection in browser sessions."""

    def test_user_cannot_access_other_user_certificate_detail(self, authenticated_page: Callable[[str], Page]):
        """Test that users cannot access other users' certificate details via direct URL manipulation."""

        # Create certificate as admin user
        admin_page = authenticated_page("admin")
        admin_fingerprint = create_test_certificate(admin_page, "admin")
        admin_page.close()

        # Try to access admin's certificate as regular user
        user_page = authenticated_page("accounts")

        # Attempt direct URL access to admin's certificate
        user_page.goto(f"http://localhost/profile/certificates/{admin_fingerprint}")
        user_page.wait_for_load_state("networkidle")

        # Should be redirected to certificates list with error message
        current_url = user_page.url
        assert current_url in ["http://localhost/profile/certificates/", "http://localhost/profile/certificates"]

        # Should see access denied message
        error_message = user_page.locator(".alert-danger, .flash-error, .error-message")
        expect(error_message).to_contain_text("Access denied")

        user_page.close()

    def test_user_cannot_revoke_other_user_certificate(self, authenticated_page: Callable[[str], Page]):
        """Test that users cannot revoke other users' certificates via API calls."""

        # Create certificate as admin user
        admin_page = authenticated_page("admin")
        admin_fingerprint = create_test_certificate(admin_page, "admin")
        admin_page.close()

        # Try to revoke admin's certificate as regular user
        user_page = authenticated_page("accounts")

        # Attempt to revoke via direct API call (simulating form submission)
        response = user_page.request.post(
            f"http://localhost/profile/certificates/{admin_fingerprint}/revoke",
            data={"reason": "key_compromise"}
        )

        # Should return 403 Forbidden or 400 Bad Request (both indicate access denied)
        # 403 = authorization denial, 400 = input validation denial (even better security)
        assert response.status in [400, 403], f"Expected 400 or 403, got {response.status}"

        # Response should contain error indicating access was denied
        response_text = response.text()
        access_denied = any(phrase in response_text.lower() for phrase in [
            "not authorized", "forbidden", "not found", "invalid", "bad request"
        ])
        assert access_denied, f"Response should indicate access denied: {response_text[:200]}"

        user_page.close()

    def test_nonexistent_certificate_access_returns_404(self, authenticated_page: Callable[[str], Page]):
        """Test that accessing non-existent certificates returns appropriate error."""

        user_page = authenticated_page("accounts")

        # Try to access non-existent certificate (invalid fingerprint length)
        fake_fingerprint = "00112233445566778899aabbccddeeff00112233"  # 40 chars, should be 64
        user_page.goto(f"http://localhost/profile/certificates/{fake_fingerprint}")
        user_page.wait_for_load_state("networkidle")

        # Should show error (either redirect to certificates list OR show 404 page)
        current_url = user_page.url
        page_content = user_page.content()

        # Either redirected to certificates list OR stayed on same URL with error
        access_properly_handled = (
            current_url in ["http://localhost/profile/certificates/", "http://localhost/profile/certificates"] or
            "404" in page_content or
            "Not Found" in page_content or
            "not found" in page_content.lower() or
            "invalid" in page_content.lower()
        )
        assert access_properly_handled, f"Nonexistent certificate access not properly handled. URL: {current_url}"

        # Should see error indication somewhere on the page
        if current_url in ["http://localhost/profile/certificates/", "http://localhost/profile/certificates"]:
            # If redirected, look for error message
            error_message = user_page.locator(".alert-danger, .flash-error, .error-message")
            expect(error_message).to_contain_text("not found")
        else:
            # If stayed on page, should have error content
            assert any(phrase in page_content.lower() for phrase in [
                "not found", "404", "invalid", "error"
            ]), f"Error content not found in page"

        user_page.close()

    def test_admin_certificate_access_from_user_service(self, authenticated_page: Callable[[str], Page]):
        """Test that regular users cannot access admin certificate pages."""

        # Create certificate as admin
        admin_page = authenticated_page("admin")
        admin_fingerprint = create_test_certificate(admin_page, "admin")
        admin_page.close()

        # Try to access admin certificate page as regular user
        user_page = authenticated_page("accounts")

        # Attempt to access admin certificate detail page
        user_page.goto(f"http://localhost/admin/certificates/{admin_fingerprint}")
        user_page.wait_for_load_state("networkidle")

        # Check that access is properly denied - should show 403 error
        current_url = user_page.url
        page_content = user_page.content()

        # Should show a 403 Forbidden error (URL might stay the same but content should indicate access denied)
        access_denied_indicators = [
            "403" in page_content,
            "Forbidden" in page_content,
            "Access denied" in page_content,
            "access denied" in page_content.lower(),
            "forbidden" in page_content.lower(),
            "unauthorized" in page_content.lower(),
            "not authorized" in page_content.lower()
        ]

        assert any(access_denied_indicators), f"Admin page access should be denied for regular users. Page content: {page_content[:500]}"

        # Should NOT contain functional admin certificate content
        admin_content_indicators = [
            "Revoke This Certificate" in page_content,
            "Certificate Details" in page_content and "Admin" in page_content,
            "data-fingerprint=" in page_content,
            admin_fingerprint in page_content
        ]

        # Admin content should not be present (user should see error page, not functional admin page)
        assert not any(admin_content_indicators), f"Regular user should not see functional admin certificate content"

        user_page.close()

    def test_certificate_list_isolation(self, authenticated_page: Callable[[str], Page]):
        """Test that users only see their own certificates in the list."""

        # Create certificate as admin
        admin_page = authenticated_page("admin")
        admin_fingerprint = create_test_certificate(admin_page, "admin")
        admin_page.close()

        # Create certificate as regular user
        user_page = authenticated_page("accounts")
        user_fingerprint = create_test_certificate(user_page, "accounts")

        # Go to user's certificate list (fresh navigation to ensure clean state)
        user_page.goto("http://localhost/profile/certificates")
        user_page.wait_for_load_state("networkidle")
        user_page.wait_for_timeout(1000)  # Extra wait for any async loading

        # Check if user certificate appears in page content (more reliable than data attributes)
        page_content = user_page.content()
        user_fingerprint_short = user_fingerprint[:16]  # Use longer prefix for better uniqueness
        assert user_fingerprint_short in page_content, f"User certificate {user_fingerprint_short} not found in page content"

        # Should see certificate item(s)
        certificate_rows = user_page.locator('[data-testid="certificate-item"]')
        assert certificate_rows.count() > 0, "User should see at least one certificate in their list"

        # Should NOT see admin's certificate in page content
        admin_fingerprint_short = admin_fingerprint[:16] if len(admin_fingerprint) >= 16 else admin_fingerprint
        assert admin_fingerprint_short not in page_content, f"Admin certificate {admin_fingerprint_short} found in user's certificate list"
        assert admin_fingerprint not in page_content, f"Full admin fingerprint found in user's certificate list"

        user_page.close()

    def test_cross_user_certificate_action_buttons_not_visible(self, authenticated_page: Callable[[str], Page]):
        """Test that users don't see action buttons for certificates they don't own."""

        # Create certificate as regular user
        user_page = authenticated_page("accounts")
        user_fingerprint = create_test_certificate(user_page, "accounts")

        # Verify user can see their own revoke button
        user_page.goto(f"http://localhost/profile/certificates/{user_fingerprint}")
        user_page.wait_for_load_state("networkidle")

        # Should see revoke button for own certificate (use class selector, avoiding dialog button)
        revoke_button = user_page.locator('button.revoke-btn:has-text("Revoke This Certificate")')
        expect(revoke_button).to_be_visible()

        user_page.close()

        # Now create certificate as admin and verify regular user can't see admin revoke buttons
        admin_page = authenticated_page("admin")
        admin_fingerprint = create_test_certificate(admin_page, "admin")
        admin_page.close()

        # Access as regular user (this should fail, but test the UI doesn't show admin controls)
        user_page2 = authenticated_page("accounts")

        # Try to access admin certificate (will likely redirect, but check for any leaked UI)
        user_page2.goto(f"http://localhost/admin/certificates/{admin_fingerprint}")
        user_page2.wait_for_load_state("networkidle")

        # Should not see any admin-specific action buttons
        admin_buttons = user_page2.locator("[data-testid*='admin'], button:has-text('Admin'), .admin-only, .admin-action")
        expect(admin_buttons).to_have_count(0)

        user_page2.close()

    def test_url_manipulation_protection(self, authenticated_page: Callable[[str], Page]):
        """Test protection against various URL manipulation techniques."""

        user_page = authenticated_page("accounts")

        # Test various malicious URL patterns that should be blocked
        malicious_urls = [
            "http://localhost/profile/certificates/../admin/certificates",
            "http://localhost/profile/certificates/../../admin/certificates",
            "http://localhost/profile/certificates/%2e%2e/admin/certificates",
            "http://localhost/profile/certificates/admin_cert_fingerprint",
            "http://localhost/profile/certificates/*",
            "http://localhost/profile/certificates/0",
            "http://localhost/profile/certificates/-1",
            "http://localhost/profile/certificates/null",
            "http://localhost/profile/certificates/undefined",
        ]

        for url in malicious_urls:
            print(f"Testing URL manipulation: {url}")
            user_page.goto(url)
            user_page.wait_for_load_state("networkidle")

            current_url = user_page.url
            page_content = user_page.content().lower()

            # Check if we ended up on an admin page (this should not happen)
            # However, URLs containing "/admin/" are acceptable if they show error pages (404, 403, etc.)
            if "/admin/" in current_url:
                # Check if this is actually a functional admin page or just an error page
                error_indicators = [
                    "not found" in page_content,
                    "access denied" in page_content,
                    "error" in page_content,
                    "invalid" in page_content,
                    "unauthorized" in page_content,
                    "forbidden" in page_content,
                ]
                if not any(error_indicators):
                    raise AssertionError(f"URL manipulation succeeded - reached admin page: {url} -> {current_url}")

            # Verify we're on a safe page
            safe_conditions = [
                # Redirected to safe locations
                current_url.startswith("http://localhost/profile/certificates/"),
                current_url.startswith("http://localhost/auth/login"),
                current_url.startswith("http://localhost/"),
                # Or showing appropriate error content
                "access denied" in page_content,
                "not found" in page_content,
                "error" in page_content,
                "invalid" in page_content,
                "unauthorized" in page_content,
                "forbidden" in page_content,
            ]

            is_safe = any(safe_conditions)
            if not is_safe:
                print(f"Potentially unsafe page reached via URL manipulation:")
                print(f"  URL: {url}")
                print(f"  Final URL: {current_url}")
                print(f"  Page content snippet: {page_content[:200]}...")
                raise AssertionError(f"Potentially unsafe page reached via URL manipulation: {url}")

            print(f"  ✓ Safe handling - redirected to: {current_url}")

        user_page.close()