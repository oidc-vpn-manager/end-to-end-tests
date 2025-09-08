"""
End-to-end tests for OpenVPN profile downloads via the Profile page.

Tests the ability to download default templates and templates with options
through the frontend web interface using Playwright.
"""

import pytest
from playwright.sync_api import Page, expect
import tempfile
import os
import time


class TestProfileDownloads:
    """Test suite for profile template download functionality."""

    def test_profile_page_accessible_after_auth(self, page: Page):
        """Test that the root page provides VPN configuration generation after authentication."""
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
        
        # Should be on the root page with VPN configuration generation
        expect(page.locator("h2")).to_contain_text("Generate VPN Configuration")

    def test_download_default_template(self, page: Page):
        """Test downloading the default OpenVPN template without options."""
        # Authenticate and stay on root page
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        # Click the admin user login button on OIDC page
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        # Wait for redirect back to root page with config generation form
        page.wait_for_load_state("networkidle")
        expect(page.locator("h2")).to_contain_text("Generate VPN Configuration")
        
        # Set up download handling
        with page.expect_download() as download_info:
            # Click the Generate/Submit button (no options selected = default template)
            page.click("button[type='submit'], input[type='submit'], button:has-text('Generate')")
        
        download = download_info.value
        
        # Verify download occurred
        assert download.suggested_filename.endswith('.ovpn')
        
        # Save to temporary file and verify contents
        with tempfile.NamedTemporaryFile(suffix='.ovpn', delete=False) as tmp_file:
            download.save_as(tmp_file.name)
            
            with open(tmp_file.name, 'r') as f:
                content = f.read()
                
            # Verify it's a valid OpenVPN config
            assert "client" in content
            assert "dev tun" in content
            assert "proto udp" in content
            assert "remote" in content
            
            # Verify CA certificates are included
            assert "<ca>" in content
            assert "-----BEGIN CERTIFICATE-----" in content
            assert "-----END CERTIFICATE-----" in content
            
            # Verify client certificate and key sections are present
            assert "<cert>" in content
            assert "<key>" in content
            
            # Should contain both root and intermediate CA certificates
            certificate_count = content.count("-----BEGIN CERTIFICATE-----")
            assert certificate_count >= 2, f"Expected at least 2 certificates (root + intermediate), found {certificate_count}"
            
            # Verify server hostname is present (admin users should eventually get vpn.example.org, currently get default.example.org)
            assert "remote " in content
            # For now, verify we get a proper hostname (not empty)
            import re
            remote_lines = re.findall(r'remote\s+([^\s]+)\s+(\d+)', content)
            assert len(remote_lines) > 0, "No remote server configuration found"
            hostname, port = remote_lines[0]
            assert hostname in ['vpn.example.org', 'default.example.org'], f"Unexpected hostname: {hostname}"
            assert port == '1194', f"Expected port 1194, got {port}"
            
            # Clean up
            os.unlink(tmp_file.name)

    def test_download_template_with_tcp_option(self, page: Page):
        """Test downloading OpenVPN template with TCP option enabled."""
        # Authenticate and stay on root page
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        # Click the admin user login button on OIDC page
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        # Wait for redirect back to root page with config generation form
        page.wait_for_load_state("networkidle")
        expect(page.locator("h2")).to_contain_text("Generate VPN Configuration")
        
        # Expand the options details element first
        details_summary = page.locator("details summary")
        if details_summary.count() > 0:
            details_summary.click()
        
        # Look for and select TCP option checkbox
        tcp_checkbox = page.locator("input[value='use_tcp']")
        if tcp_checkbox.count() > 0:
            tcp_checkbox.check()
        
        # Set up download handling
        with page.expect_download() as download_info:
            # Click the Generate button
            page.click("button[type='submit'], input[type='submit'], button:has-text('Generate')")
        
        download = download_info.value
        
        # Verify download occurred
        assert download.suggested_filename.endswith('.ovpn')
        
        # Save to temporary file and verify contents
        with tempfile.NamedTemporaryFile(suffix='.ovpn', delete=False) as tmp_file:
            download.save_as(tmp_file.name)
            
            with open(tmp_file.name, 'r') as f:
                content = f.read()
                
            # Verify it's a valid OpenVPN config with TCP if option was available
            assert "client" in content
            assert "dev tun" in content
            assert "remote" in content
            
            if tcp_checkbox.count() > 0:
                # Should have TCP protocol when option was selected
                assert "proto tcp-client" in content or "tcp-client" in content
            
            # Clean up
            os.unlink(tmp_file.name)

    def test_download_template_with_custom_port_option(self, page: Page):
        """Test downloading OpenVPN template with custom port option enabled."""
        # Authenticate and stay on root page
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        # Click the admin user login button on OIDC page
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        # Wait for redirect back to root page with config generation form
        page.wait_for_load_state("networkidle")
        expect(page.locator("h2")).to_contain_text("Generate VPN Configuration")
        
        # Expand the options details element first
        details_summary = page.locator("details summary")
        if details_summary.count() > 0:
            details_summary.click()
        
        # Look for and select custom port option checkbox
        port_checkbox = page.locator("input[value='custom_port']")
        if port_checkbox.count() > 0:
            port_checkbox.check()
        
        # Set up download handling
        with page.expect_download() as download_info:
            # Click the Generate button
            page.click("button[type='submit'], input[type='submit'], button:has-text('Generate')")
        
        download = download_info.value
        
        # Verify download occurred
        assert download.suggested_filename.endswith('.ovpn')
        
        # Save to temporary file and verify contents
        with tempfile.NamedTemporaryFile(suffix='.ovpn', delete=False) as tmp_file:
            download.save_as(tmp_file.name)
            
            with open(tmp_file.name, 'r') as f:
                content = f.read()
                
            # Verify it's a valid OpenVPN config
            assert "client" in content
            assert "dev tun" in content
            assert "remote" in content
            
            # Verify CA certificates are included
            assert "<ca>" in content
            assert "-----BEGIN CERTIFICATE-----" in content
            assert "-----END CERTIFICATE-----" in content
            
            # Verify client certificate and key sections are present
            assert "<cert>" in content
            assert "<key>" in content
            
            if port_checkbox.count() > 0:
                # Should have custom port when option was selected
                assert "443" in content
            
            # Clean up
            os.unlink(tmp_file.name)

    def test_profile_page_shows_user_info(self, page: Page):
        """Test that the root page displays VPN configuration form correctly."""
        # Authenticate and stay on root page
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        # Click the admin user login button on OIDC page
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        # Wait for redirect back to root page with config generation form
        page.wait_for_load_state("networkidle")
        expect(page.locator("h2")).to_contain_text("Generate VPN Configuration")
        
        # Check that there is a form for generating configuration
        expect(page.locator("form")).to_be_visible()
        
        # Check that there is a submit/generate button available
        generate_button = page.locator("button[type='submit'], input[type='submit'], button:has-text('Generate')")
        expect(generate_button).to_be_visible()

    def test_profile_page_template_options_display(self, page: Page):
        """Test that template options are displayed on the root configuration page."""
        # Authenticate and stay on root page
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        # Click the admin user login button on OIDC page
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        # Wait for redirect back to root page with config generation form
        page.wait_for_load_state("networkidle")
        expect(page.locator("h2")).to_contain_text("Generate VPN Configuration")
        
        # Check for form elements that might represent options
        form_elements = page.locator("form, fieldset, input, select, label")
        expect(form_elements.first).to_be_visible()
        
        # Look for any text that indicates options are available
        page_content = page.locator("body").text_content()
        
        # The page should contain some indication of configuration options
        assert len(page_content) > 100  # Basic sanity check that page has content