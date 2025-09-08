"""
End-to-end tests to verify certificate details are displayed correctly in admin interface.

This test ensures that certificate information (subject, issuer, validity dates)
is properly parsed and displayed instead of showing "N/A".
"""

import pytest
from playwright.sync_api import Page, expect


def logout_user(page: Page):
    """
    Helper function to properly logout from both tiny-oidc and frontend.
    """
    # First logout from tiny-oidc to prevent auto-login
    page.goto("http://tinyoidc.authenti-kate.org/user/logout", wait_until="networkidle")
    page.wait_for_timeout(1000)
    
    # Then logout from frontend to close the session
    page.goto("http://localhost/auth/logout", wait_until="networkidle")
    page.wait_for_timeout(1000)


def create_certificate_for_user(page: Page, username: str) -> str:
    """
    Helper function to create a certificate for a user and return the fingerprint.
    """
    # Authenticate as the specified user
    page.goto("http://localhost/", wait_until="networkidle")
    expect(page.locator("h1")).to_contain_text("Login - kinda")
    
    # Login as the specified user
    user_button = page.locator(f'button:has-text("Login as {username}")')
    expect(user_button).to_be_visible()
    user_button.click()
    page.wait_for_load_state("networkidle", timeout=10000)
    
    # Go to certificate generation page
    page.goto("http://localhost/")
    page.wait_for_load_state("networkidle")
    
    # Submit the form to generate a certificate
    page.click('input[type="submit"]')
    page.wait_for_load_state("networkidle")
    
    # Add a small wait to allow backend processing
    page.wait_for_timeout(2000)
    
    # Now go to user certificates page to find the newly created certificate
    page.goto("http://localhost/profile/certificates")
    page.wait_for_load_state("networkidle")
    
    # Should show at least one certificate
    certificates = page.locator('[data-testid="certificate-item"]')
    assert certificates.count() > 0, f"No certificates found after certificate generation for user {username}"
    
    # Extract fingerprint from the first (most recent) certificate's View link
    first_certificate = certificates.first
    view_link = first_certificate.locator('a[href*="/certificates/"]')
    assert view_link.count() > 0, f"No view link found for certificate created by user {username}"
    
    href = view_link.get_attribute('href')
    import re
    fingerprint_match = re.search(r'/certificates/([A-F0-9]+)', href)
    assert fingerprint_match, f"Could not extract fingerprint from view link: {href}"
    
    certificate_fingerprint = fingerprint_match.group(1)
    print(f"DEBUG: Created certificate for user {username} with fingerprint: {certificate_fingerprint}")
    
    # Logout the user properly after creating certificate
    logout_user(page)
    
    return certificate_fingerprint


class TestCertificateDisplayFixes:
    """Test suite to verify certificate details display correctly."""

    def test_certificate_list_shows_subject_and_validity(self, page: Page):
        """Test that certificate list shows proper subject and validity dates."""
        # Authenticate as admin
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/admin/certificates")
        page.wait_for_load_state("networkidle")
        
        # Check that we have certificates listed
        certificates_table = page.locator("table")
        if certificates_table.count() > 0:
            # Look for certificate rows
            cert_rows = page.locator("tbody tr")
            if cert_rows.count() > 0:
                # Check the first certificate row
                first_row = cert_rows.first
                
                # Check Subject column (first column) - should not be "N/A"
                subject_cell = first_row.locator("td").first
                subject_text = subject_cell.text_content()
                assert subject_text and subject_text.strip() != "N/A", f"Subject should not be N/A, got: {subject_text}"
                
                # Check that it contains a valid identifier (email, domain, or descriptive name)
                assert ("@" in subject_text or "." in subject_text or len(subject_text.strip()) > 5), f"Subject should contain valid identifier, got: {subject_text}"
                
                # Check Expires column (5th column) - should show a date, not "N/A"  
                expires_cell = first_row.locator("td").nth(4)
                expires_text = expires_cell.text_content()
                assert expires_text and "N/A" not in expires_text, f"Expires date should not be N/A, got: {expires_text}"
                
                # Should contain a year (2025 or 2026)
                assert ("2025" in expires_text or "2026" in expires_text), f"Expires should contain valid year, got: {expires_text}"

    def test_certificate_detail_shows_complete_information(self, page: Page):
        """Test that certificate detail page shows complete certificate information."""
        # Authenticate as admin and navigate to certificates
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/admin/certificates")
        page.wait_for_load_state("networkidle")
        
        # Look for "View Details" buttons
        detail_buttons = page.locator("a:has-text('View Details')")
        
        if detail_buttons.count() > 0:
            # Click on the first certificate detail
            detail_buttons.first.click()
            page.wait_for_load_state("networkidle")
            
            # Should be on certificate detail page
            expect(page.locator("h1")).to_contain_text("Certificate Details")
            
            # Check that the main heading shows a proper subject, not "Unknown Subject"
            main_heading = page.locator("h2")
            heading_text = main_heading.text_content()
            assert heading_text and "Unknown Subject" not in heading_text, f"Should show proper subject, got: {heading_text}"
            
            # Check Subject Information section
            subject_section = page.locator("h3:has-text('Subject Information')").locator("..")
            
            # Common Name should not be N/A
            cn_row = subject_section.locator("tr:has-text('Common Name (CN)')")
            if cn_row.count() > 0:
                cn_value = cn_row.locator("td").last.text_content()
                assert cn_value and cn_value.strip() != "N/A", f"Subject CN should not be N/A, got: {cn_value}"
                assert ("@" in cn_value or "." in cn_value or len(cn_value.strip()) > 5), f"Subject CN should be valid identifier, got: {cn_value}"
            
            # Check Issuer Information section
            issuer_section = page.locator("h3:has-text('Issuer Information')").locator("..")
            
            # Issuer Common Name should not be N/A
            issuer_cn_row = issuer_section.locator("tr:has-text('Common Name (CN)')")
            if issuer_cn_row.count() > 0:
                issuer_cn_value = issuer_cn_row.locator("td").last.text_content()
                assert issuer_cn_value and issuer_cn_value.strip() != "N/A", f"Issuer CN should not be N/A, got: {issuer_cn_value}"
            
            # Check Validity Period section  
            validity_section = page.locator("h3:has-text('Validity Period')").locator("..")
            
            # Valid From should not be N/A
            valid_from_row = validity_section.locator("tr:has-text('Valid From')")
            if valid_from_row.count() > 0:
                valid_from_value = valid_from_row.locator("td").last.text_content()
                assert valid_from_value and valid_from_value.strip() != "N/A", f"Valid From should not be N/A, got: {valid_from_value}"
                assert ("2025" in valid_from_value), f"Valid From should contain 2025, got: {valid_from_value}"
            
            # Valid Until should not be N/A
            valid_until_row = validity_section.locator("tr:has-text('Valid Until')")
            if valid_until_row.count() > 0:
                valid_until_value = valid_until_row.locator("td").last.text_content()
                assert valid_until_value and valid_until_value.strip() != "N/A", f"Valid Until should not be N/A, got: {valid_until_value}"
                assert ("2026" in valid_until_value or "2025" in valid_until_value), f"Valid Until should contain valid year, got: {valid_until_value}"

    def test_specific_certificate_by_fingerprint(self, page: Page):
        """Test accessing a specific certificate by its fingerprint."""
        # Create a certificate for admin user dynamically
        print("DEBUG: Creating certificate for admin user")
        fingerprint = create_certificate_for_user(page, "admin")
        
        # Authenticate as admin to access the certificate details
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        
        # Navigate directly to certificate detail
        page.goto(f"http://localhost/admin/certificates/{fingerprint}")
        page.wait_for_load_state("networkidle")
        
        # Should show certificate details, not an error
        expect(page.locator("h1")).to_contain_text("Certificate Details")
        
        # Should not show "Certificate not found"
        page_content = page.locator("body").text_content()
        assert "Certificate not found" not in page_content
        
        # Should show the certificate fingerprint
        fingerprint_element = page.locator("code:has-text('" + fingerprint + "')")
        expect(fingerprint_element).to_be_visible()
        
        # Main heading should show a proper subject
        main_heading = page.locator("h2")
        heading_text = main_heading.text_content()
        assert "admin@example.org" in heading_text, f"Should show admin email in subject, got: {heading_text}"