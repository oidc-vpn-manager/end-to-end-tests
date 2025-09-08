"""
End-to-end tests for Certificate Transparency admin interface.

Tests the ability to view and manage certificate transparency logs
through the admin web interface using Playwright.
"""

import pytest
from playwright.sync_api import Page, expect


class TestCertificateTransparencyAdmin:
    """Test suite for Certificate Transparency admin functionality."""

    def test_admin_certificates_page_accessible(self, page: Page):
        """Test that the Certificate Transparency page is accessible to admin users."""
        # Navigate to the application
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        # Should be redirected to OIDC login page
        expect(page.locator("h1")).to_contain_text("Login - kinda")
        
        # Click the admin user login button
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        # Wait for redirect back to frontend
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url("http://localhost/")
        
        # Look for Admin dropdown in navigation (use exact text match)
        admin_dropdown = page.locator("button:has-text('Admin')").first
        expect(admin_dropdown).to_be_visible()
        
        # Hover over the admin dropdown to reveal the menu
        admin_dropdown.hover()
        
        # Click on Certificate Transparency link (now visible after hover)
        cert_link = page.locator("a:has-text('Certificate Transparency')")
        expect(cert_link).to_be_visible()
        cert_link.click()
        
        # Should be on Certificate Transparency page
        page.wait_for_load_state("networkidle")
        expect(page).to_have_url("http://localhost/certificates/")
        expect(page.locator("h1")).to_contain_text("Certificate Transparency Log")

    def test_certificates_page_shows_content(self, page: Page):
        """Test that the certificates page displays content correctly."""
        # Authenticate and navigate to certificates page
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        # Click the admin user login button on OIDC page
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        # Wait for redirect and navigate to certificates
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/certificates/")
        page.wait_for_load_state("networkidle")
        
        # Check page content
        expect(page.locator("h1")).to_contain_text("Certificate Transparency Log")
        
        # Should have filter form
        expect(page.locator("form.filters-form")).to_be_visible()
        expect(page.locator("h3:has-text('Filter Certificates')")).to_be_visible()
        
        # Should have certificate type dropdown
        type_dropdown = page.locator("select[name='type']")
        expect(type_dropdown).to_be_visible()
        
        # Should have subject filter input
        subject_input = page.locator("input[name='subject']")
        expect(subject_input).to_be_visible()
        
        # Should have date filters
        from_date_input = page.locator("input[name='from_date']")
        expect(from_date_input).to_be_visible()
        
        # Should have apply filters button
        apply_button = page.locator("button:has-text('Apply Filters')")
        expect(apply_button).to_be_visible()

    def test_certificate_filtering(self, page: Page):
        """Test filtering functionality."""
        # Authenticate and navigate to certificates page
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/certificates/")
        page.wait_for_load_state("networkidle")
        
        # Test filtering by certificate type
        type_dropdown = page.locator("select[name='type']")
        type_dropdown.select_option("client")
        
        # Test filtering by subject
        subject_input = page.locator("input[name='subject']")
        subject_input.fill("test@example.com")
        
        # Apply filters
        apply_button = page.locator("button:has-text('Apply Filters')")
        apply_button.click()
        
        page.wait_for_load_state("networkidle")
        
        # Check that URL contains filter parameters
        assert "type=client" in page.url
        assert "subject=test%40example.com" in page.url

    def test_certificate_listing_display(self, page: Page):
        """Test that certificate listing displays appropriately."""
        # Authenticate and navigate to certificates page
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/certificates/")
        page.wait_for_load_state("networkidle")
        
        # Should have a table for results (even if empty)
        # The table might not be visible if there are no certificates
        # So we check for either the table or the "no certificates" message
        table = page.locator("table")
        no_cert_message = page.locator("div:has-text('No certificates found matching the current filters')")
        
        # Either table should be visible OR no certificates message should be visible
        if table.count() > 0:
            expect(table).to_be_visible()
        else:
            expect(no_cert_message.first).to_be_visible()
        
        # If there are statistics, they should be displayed
        stats_section = page.locator(".stats-summary")
        if stats_section.count() > 0:
            expect(stats_section).to_be_visible()
            expect(page.locator("strong:has-text('Total Certificates')")).to_be_visible()

    def test_clear_filters_functionality(self, page: Page):
        """Test the clear filters functionality."""
        # Authenticate and navigate to certificates page
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/certificates/")
        page.wait_for_load_state("networkidle")
        
        # Apply some filters first
        type_dropdown = page.locator("select[name='type']")
        type_dropdown.select_option("server")
        
        subject_input = page.locator("input[name='subject']")
        subject_input.fill("example.com")
        
        apply_button = page.locator("button:has-text('Apply Filters')")
        apply_button.click()
        page.wait_for_load_state("networkidle")
        
        # Now clear filters - use the button in the filters form (more specific selector)
        clear_button = page.locator("a.button:has-text('Clear Filters')")
        expect(clear_button).to_be_visible()
        clear_button.click()
        
        page.wait_for_load_state("networkidle")
        
        # Should be back to clean URL
        expect(page).to_have_url("http://localhost/certificates/")
        
        # Form fields should be reset
        expect(type_dropdown).to_have_value("")
        expect(subject_input).to_have_value("")

    def test_certificate_detail_navigation(self, page: Page):
        """Test navigation to certificate detail page (if certificates exist)."""
        # Authenticate and navigate to certificates page
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/certificates/")
        page.wait_for_load_state("networkidle")
        
        # Look for "View Details" buttons
        detail_buttons = page.locator("a:has-text('View Details')")
        
        if detail_buttons.count() > 0:
            # If certificates exist, test clicking on a detail button
            detail_buttons.first.click()
            page.wait_for_load_state("networkidle")
            
            # Should be on certificate detail page
            expect(page.locator("h1")).to_contain_text("Certificate Details")
            expect(page.locator("a:has-text('Back to Certificate List')")).to_be_visible()
            
            # Test back navigation
            back_button = page.locator("a:has-text('Back to Certificate List')")
            back_button.click()
            page.wait_for_load_state("networkidle")
            
            expect(page).to_have_url("http://localhost/certificates/")

    def test_admin_navigation_dropdown(self, page: Page):
        """Test that the admin navigation dropdown includes Certificate Transparency link."""
        # Authenticate as admin
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        
        # Check admin dropdown contains Certificate Transparency link
        admin_dropdown = page.locator("button:has-text('Admin')").first
        expect(admin_dropdown).to_be_visible()
        
        # Hover over the admin dropdown to reveal the menu
        admin_dropdown.hover()
        
        # Should see both PSK and Certificate Transparency links
        psk_link = page.locator("a:has-text('Pre-Shared Keys')")
        cert_link = page.locator("a:has-text('Certificate Transparency')")
        
        expect(psk_link).to_be_visible()
        expect(cert_link).to_be_visible()

    def test_non_admin_cannot_access_certificates(self, page: Page):
        """Test that non-admin users cannot access the certificates page."""
        # Try to access the page directly without authentication
        page.goto("http://localhost/certificates/")
        page.wait_for_load_state("networkidle")
        
        # Should be redirected to login or get an error
        # The specific behavior depends on the authentication implementation
        # but it should NOT show the Certificate Transparency Log page
        page_content = page.locator("body").text_content()
        assert "Certificate Transparency Log" not in page_content

    def test_date_filter_inputs(self, page: Page):
        """Test that date filter inputs work correctly."""
        # Authenticate and navigate to certificates page
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/certificates/")
        page.wait_for_load_state("networkidle")
        
        # Test date inputs
        from_date = page.locator("input[name='from_date']")
        to_date = page.locator("input[name='to_date']")
        
        from_date.fill("2025-01-01")
        to_date.fill("2025-12-31")
        
        apply_button = page.locator("button:has-text('Apply Filters')")
        apply_button.click()
        
        page.wait_for_load_state("networkidle")
        
        # Check that URL contains date parameters
        assert "from_date=2025-01-01" in page.url
        assert "to_date=2025-12-31" in page.url

    def test_revoked_certificate_filter(self, page: Page):
        """Test filtering for revoked certificates."""
        # Authenticate and navigate to certificates page
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/certificates/")
        page.wait_for_load_state("networkidle")
        
        # Test include_revoked dropdown
        revoked_dropdown = page.locator("select[name='include_revoked']")
        expect(revoked_dropdown).to_be_visible()
        
        # Should default to "Yes" (include revoked)
        expect(revoked_dropdown).to_have_value("true")
        
        # Change to exclude revoked
        revoked_dropdown.select_option("false")
        
        apply_button = page.locator("button:has-text('Apply Filters')")
        apply_button.click()
        
        page.wait_for_load_state("networkidle")
        
        # Check that URL contains revoked parameter
        assert "include_revoked=false" in page.url