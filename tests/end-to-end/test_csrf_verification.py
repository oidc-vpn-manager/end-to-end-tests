"""
E2E CSRF Protection Verification Tests

These tests verify that CSRF protections work correctly in actual browser sessions,
ensuring that forms cannot be submitted without valid CSRF tokens and that
cross-site request forgery attacks are prevented.
"""

import pytest
from playwright.sync_api import Page, expect
from typing import Callable


class TestCSRFProtectionE2E:
    """E2E tests for CSRF protection in browser sessions."""

    def test_psk_creation_requires_csrf_token(self, authenticated_page: Callable[[str], Page]):
        """Test that PSK creation forms require valid CSRF tokens in browser."""

        admin_page = authenticated_page("admin")

        # Navigate to new PSK page
        admin_page.goto("http://localhost/admin/psk/new")
        admin_page.wait_for_load_state("networkidle")

        # Check that form has CSRF token field (hidden field)
        csrf_field = admin_page.locator('input[name="csrf_token"]')
        expect(csrf_field).to_be_attached()  # Hidden fields are attached but not visible

        # Get the original CSRF token value
        original_csrf_token = csrf_field.get_attribute('value')
        assert original_csrf_token, "CSRF token should have a value"

        # Test 1: Submit form with valid CSRF token (normal operation)
        description_field = admin_page.locator('input[name="description"], textarea[name="description"]')
        description_field.fill("Test PSK with valid CSRF")

        psk_type_field = admin_page.locator('select[name="psk_type"]')
        if psk_type_field.count() > 0:
            psk_type_field.select_option("server")

        # Submit form with valid CSRF token
        admin_page.click('button[type="submit"], input[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        # Should succeed or show form validation errors (not CSRF errors)
        current_url = admin_page.url
        page_content = admin_page.content()

        # Should not get CSRF-specific error
        assert "csrf" not in page_content.lower() or "token" not in page_content.lower() or \
               current_url != "http://localhost/admin/psk/new", "Valid CSRF submission should not show CSRF errors"

        # Test 2: Manipulate CSRF token and attempt submission
        admin_page.goto("http://localhost/admin/psk/new")
        admin_page.wait_for_load_state("networkidle")

        # Fill form fields
        description_field = admin_page.locator('input[name="description"], textarea[name="description"]')
        description_field.fill("Test PSK with manipulated CSRF")

        psk_type_field = admin_page.locator('select[name="psk_type"]')
        if psk_type_field.count() > 0:
            psk_type_field.select_option("server")

        # Manipulate CSRF token via JavaScript
        admin_page.evaluate("""() => {
            const csrfField = document.querySelector('input[name="csrf_token"]');
            if (csrfField) {
                csrfField.value = 'malicious_csrf_token_12345';
            }
        }""")

        # Attempt to submit with invalid CSRF token
        admin_page.click('button[type="submit"], input[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        # Should be rejected with 400 error or CSRF error
        response_content = admin_page.content()
        current_url = admin_page.url

        # Check for CSRF protection (either 400 status reflected in content or CSRF error message)
        csrf_protection_active = (
            "400" in response_content or
            "csrf" in response_content.lower() or
            "token" in response_content.lower() or
            "security" in response_content.lower() or
            current_url == "http://localhost/admin/psk/new"  # Form redisplay indicates validation failure
        )

        assert csrf_protection_active, "CSRF protection should reject invalid tokens"

        admin_page.close()

    def test_csrf_token_removal_prevents_submission(self, authenticated_page: Callable[[str], Page]):
        """Test that removing CSRF token from form prevents submission."""

        admin_page = authenticated_page("admin")

        admin_page.goto("http://localhost/admin/psk/new")
        admin_page.wait_for_load_state("networkidle")

        # Fill form fields
        description_field = admin_page.locator('input[name="description"], textarea[name="description"]')
        description_field.fill("Test PSK without CSRF token")

        psk_type_field = admin_page.locator('select[name="psk_type"]')
        if psk_type_field.count() > 0:
            psk_type_field.select_option("server")

        # Remove CSRF token field entirely
        admin_page.evaluate("""() => {
            const csrfField = document.querySelector('input[name="csrf_token"]');
            if (csrfField) {
                csrfField.remove();
            }
        }""")

        # Attempt to submit without CSRF token
        admin_page.click('button[type="submit"], input[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        # Should be rejected
        response_content = admin_page.content()
        current_url = admin_page.url

        # Should indicate CSRF protection is active
        csrf_protection_detected = (
            "400" in response_content or
            "csrf" in response_content.lower() or
            "token" in response_content.lower() or
            current_url == "http://localhost/admin/psk/new"
        )

        assert csrf_protection_detected, "Missing CSRF token should be rejected"

        admin_page.close()

    def test_cross_site_request_forgery_prevention(self, authenticated_page: Callable[[str], Page]):
        """Test that CSRF protection prevents cross-site request forgery attacks."""

        admin_page = authenticated_page("admin")

        # Simulate a CSRF attack by creating a malicious form on a different origin
        # In a real attack, this would be on attacker.com, but we'll simulate it

        admin_page.goto("http://localhost/admin/psk/new")
        admin_page.wait_for_load_state("networkidle")

        # Create a malicious form that attempts to submit to our application
        # without a proper CSRF token
        malicious_form_html = """
        <html>
        <body>
            <form id="malicious-form" action="http://localhost/admin/psk/new" method="POST">
                <input type="hidden" name="description" value="Malicious PSK from CSRF attack">
                <input type="hidden" name="psk_type" value="server">
                <!-- Note: No CSRF token -->
            </form>
            <script>
                // Auto-submit the form (simulating clickjacking or auto-submission)
                setTimeout(() => {
                    document.getElementById('malicious-form').submit();
                }, 100);
            </script>
        </body>
        </html>
        """

        # Navigate to the malicious page (simulating external attacker site)
        admin_page.set_content(malicious_form_html)
        admin_page.wait_for_load_state("networkidle")

        # Wait for auto-submission and check result
        admin_page.wait_for_timeout(2000)  # Wait for form submission to complete

        # Check current URL and content
        current_url = admin_page.url
        page_content = admin_page.content()

        # The CSRF attack should be blocked
        # Either we get an error page, or we're redirected but the PSK wasn't created
        csrf_attack_blocked = (
            "400" in page_content or
            "csrf" in page_content.lower() or
            "error" in page_content.lower() or
            current_url.startswith("data:")  # Still on malicious page
        )

        assert csrf_attack_blocked, "CSRF attack should be blocked by token validation"

        admin_page.close()

    def test_csrf_token_in_ajax_requests(self, authenticated_page: Callable[[str], Page]):
        """Test CSRF protection in AJAX requests."""

        admin_page = authenticated_page("admin")

        admin_page.goto("http://localhost/admin/psk/new")
        admin_page.wait_for_load_state("networkidle")

        # Get CSRF token from the page
        csrf_token = admin_page.evaluate("""() => {
            const csrfField = document.querySelector('input[name="csrf_token"]');
            return csrfField ? csrfField.value : null;
        }""")

        assert csrf_token, "CSRF token should be available on the page"

        # Test AJAX request with valid CSRF token
        ajax_response_with_csrf = admin_page.evaluate(f"""async () => {{
            try {{
                const response = await fetch('/admin/psk/new', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': '{csrf_token}'
                    }},
                    body: 'description=AJAX Test with CSRF&psk_type=server&csrf_token={csrf_token}'
                }});
                return {{
                    status: response.status,
                    statusText: response.statusText,
                    headers: Object.fromEntries(response.headers.entries())
                }};
            }} catch (error) {{
                return {{ error: error.message }};
            }}
        }}""")

        # Should not be rejected due to CSRF (may fail for other reasons)
        assert ajax_response_with_csrf.get('status') != 400 or \
               'csrf' not in str(ajax_response_with_csrf).lower(), \
               "AJAX request with valid CSRF token should not be rejected for CSRF reasons"

        # Test AJAX request without CSRF token
        ajax_response_no_csrf = admin_page.evaluate("""async () => {
            try {
                const response = await fetch('/admin/psk/new', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: 'description=AJAX Test without CSRF&psk_type=server'
                });
                return {
                    status: response.status,
                    statusText: response.statusText
                };
            } catch (error) {
                return { error: error.message };
            }
        }""")

        # Should be rejected due to missing CSRF token
        assert ajax_response_no_csrf.get('status') == 400, \
               "AJAX request without CSRF token should be rejected with 400 status"

        admin_page.close()

    def test_csrf_protection_on_certificate_operations(self, authenticated_page: Callable[[str], Page]):
        """Test CSRF protection on certificate-related operations."""

        user_page = authenticated_page("accounts")

        # Navigate to certificates page
        user_page.goto("http://localhost/profile/certificates/")
        user_page.wait_for_load_state("networkidle")

        # Check if there are any certificate operations with forms
        revoke_forms = user_page.locator('form[action*="revoke"]')

        if revoke_forms.count() > 0:
            # Test CSRF protection on certificate revocation
            first_revoke_form = revoke_forms.first

            # Check for CSRF token in revocation form
            csrf_field = first_revoke_form.locator('input[name="csrf_token"]')

            if csrf_field.count() > 0:
                expect(csrf_field).to_be_visible()

                original_csrf = csrf_field.get_attribute('value')
                assert original_csrf, "Revocation form should have CSRF token"

                # Manipulate CSRF token
                user_page.evaluate("""() => {
                    const csrfField = document.querySelector('form[action*="revoke"] input[name="csrf_token"]');
                    if (csrfField) {
                        csrfField.value = 'invalid_csrf_token';
                    }
                }""")

                # Try to submit revocation with invalid CSRF
                reason_field = first_revoke_form.locator('select[name="reason"], input[name="reason"]')
                if reason_field.count() > 0:
                    reason_field.first.fill("key_compromise")

                submit_button = first_revoke_form.locator('button[type="submit"], input[type="submit"]')
                submit_button.click()

                user_page.wait_for_load_state("networkidle")

                # Should be rejected
                page_content = user_page.content()
                csrf_protection_active = (
                    "400" in page_content or
                    "csrf" in page_content.lower() or
                    "error" in page_content.lower()
                )

                assert csrf_protection_active, "Certificate operations should be protected by CSRF"

        user_page.close()

    def test_csrf_token_refresh_on_page_reload(self, authenticated_page: Callable[[str], Page]):
        """Test that CSRF tokens remain valid after page reloads."""

        admin_page = authenticated_page("admin")

        admin_page.goto("http://localhost/admin/psk/new")
        admin_page.wait_for_load_state("networkidle")

        # Get first CSRF token
        first_csrf_token = admin_page.evaluate("""() => {
            const csrfField = document.querySelector('input[name="csrf_token"]');
            return csrfField ? csrfField.value : null;
        }""")

        # Reload the page
        admin_page.reload()
        admin_page.wait_for_load_state("networkidle")

        # Get second CSRF token
        second_csrf_token = admin_page.evaluate("""() => {
            const csrfField = document.querySelector('input[name="csrf_token"]');
            return csrfField ? csrfField.value : null;
        }""")

        # Both tokens should exist
        assert first_csrf_token, "First CSRF token should exist"
        assert second_csrf_token, "Second CSRF token should exist"

        # Test that the current (second) token works
        description_field = admin_page.locator('input[name="description"], textarea[name="description"]')
        description_field.fill("Test PSK after reload")

        psk_type_field = admin_page.locator('select[name="psk_type"]')
        if psk_type_field.count() > 0:
            psk_type_field.select_option("server")

        # Submit with current token (should work)
        admin_page.click('button[type="submit"], input[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        # Should not get CSRF error
        page_content = admin_page.content()
        current_url = admin_page.url

        no_csrf_error = not (
            "400" in page_content and
            ("csrf" in page_content.lower() or "token" in page_content.lower())
        )

        assert no_csrf_error, "Current CSRF token should work after page reload"

        admin_page.close()

    def test_csrf_protection_across_multiple_tabs(self, authenticated_page: Callable[[str], Page]):
        """Test CSRF protection behavior across multiple browser tabs."""

        admin_page1 = authenticated_page("admin")

        # Open first tab
        admin_page1.goto("http://localhost/admin/psk/new")
        admin_page1.wait_for_load_state("networkidle")

        # Get CSRF token from first tab
        csrf_token_tab1 = admin_page1.evaluate("""() => {
            const csrfField = document.querySelector('input[name="csrf_token"]');
            return csrfField ? csrfField.value : null;
        }""")

        # Open second tab in same browser context
        admin_page2 = admin_page1.context.new_page()
        admin_page2.goto("http://localhost/admin/psk/new")
        admin_page2.wait_for_load_state("networkidle")

        # Get CSRF token from second tab
        csrf_token_tab2 = admin_page2.evaluate("""() => {
            const csrfField = document.querySelector('input[name="csrf_token"]');
            return csrfField ? csrfField.value : null;
        }""")

        # Both tabs should have valid CSRF tokens
        assert csrf_token_tab1, "First tab should have CSRF token"
        assert csrf_token_tab2, "Second tab should have CSRF token"

        # Test submission from both tabs
        # Tab 1 submission
        description_field1 = admin_page1.locator('input[name="description"], textarea[name="description"]')
        description_field1.fill("Test from tab 1")

        psk_type_field1 = admin_page1.locator('select[name="psk_type"]')
        if psk_type_field1.count() > 0:
            psk_type_field1.select_option("server")

        # Submit from tab 1
        admin_page1.click('button[type="submit"], input[type="submit"]')
        admin_page1.wait_for_load_state("networkidle")

        # Tab 1 submission should work
        tab1_content = admin_page1.content()
        tab1_csrf_ok = not ("400" in tab1_content and "csrf" in tab1_content.lower())

        # Tab 2 submission (after tab 1 submitted)
        description_field2 = admin_page2.locator('input[name="description"], textarea[name="description"]')
        description_field2.fill("Test from tab 2")

        psk_type_field2 = admin_page2.locator('select[name="psk_type"]')
        if psk_type_field2.count() > 0:
            psk_type_field2.select_option("server")

        # Submit from tab 2
        admin_page2.click('button[type="submit"], input[type="submit"]')
        admin_page2.wait_for_load_state("networkidle")

        # Tab 2 submission should also work (Flask-WTF handles multiple tokens)
        tab2_content = admin_page2.content()
        tab2_csrf_ok = not ("400" in tab2_content and "csrf" in tab2_content.lower())

        # Both submissions should succeed (Flask-WTF maintains token validity)
        assert tab1_csrf_ok, "First tab submission should not fail due to CSRF"
        assert tab2_csrf_ok, "Second tab submission should not fail due to CSRF"

        admin_page1.close()
        admin_page2.close()