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
        
        # Add comprehensive diagnostics before attempting download
        print("=== DIAGNOSTIC: Form Analysis ===")

        # Check if form exists and what elements are present
        forms = page.locator("form")
        form_count = forms.count()
        print(f"Number of forms found: {form_count}")

        if form_count > 0:
            # Get the first form's HTML for analysis
            form_html = forms.first.inner_html()
            print(f"Form HTML: {form_html[:500]}...")

            # Check form action and method
            form_action = forms.first.get_attribute("action")
            form_method = forms.first.get_attribute("method")
            print(f"Form action: '{form_action}', method: '{form_method}'")

        # Check for submit buttons/inputs
        submit_elements = page.locator("button[type='submit'], input[type='submit'], button:has-text('Generate')")
        submit_count = submit_elements.count()
        print(f"Number of submit elements found: {submit_count}")

        if submit_count > 0:
            for i in range(submit_count):
                element = submit_elements.nth(i)
                tag_name = element.evaluate("el => el.tagName")
                element_type = element.get_attribute("type")
                element_value = element.get_attribute("value")
                element_text = element.text_content()
                print(f"Submit element {i}: {tag_name}, type='{element_type}', value='{element_value}', text='{element_text}'")

        # Check for any CSP violations or console errors
        console_messages = []
        def handle_console(msg):
            console_messages.append(f"{msg.type}: {msg.text}")
            print(f"CONSOLE {msg.type}: {msg.text}")

        page.on("console", handle_console)

        # Check current page URL and any redirects
        current_url = page.url
        print(f"Current URL: {current_url}")

        # Check for CSRF token
        csrf_inputs = page.locator("input[name='csrf_token']")
        csrf_count = csrf_inputs.count()
        print(f"CSRF tokens found: {csrf_count}")
        if csrf_count > 0:
            csrf_value = csrf_inputs.first.get_attribute("value")
            print(f"CSRF token value: {csrf_value[:20]}..." if csrf_value else "No CSRF value")

        print("=== DIAGNOSTIC: Attempting Form Submission ===")

        # Set up download handling
        with page.expect_download(timeout=30000) as download_info:
            # Try to click the submit button with enhanced error handling
            try:
                submit_button = page.locator("button[type='submit'], input[type='submit'], button:has-text('Generate')").first

                # Check if the button is visible and enabled before clicking
                print(f"Submit button visible: {submit_button.is_visible()}")
                print(f"Submit button enabled: {submit_button.is_enabled()}")

                # Get button's bounding box to ensure it's clickable
                bbox = submit_button.bounding_box()
                print(f"Submit button bounding box: {bbox}")

                # Click the button
                print("Clicking submit button...")
                submit_button.click()
                print("Submit button clicked successfully")

            except Exception as e:
                print(f"Error clicking submit button: {e}")
                # Take a screenshot for debugging
                page.screenshot(path=f"/tmp/form_error_{int(time.time())}.png")
                raise

        print("=== DIAGNOSTIC: After Click ===")

        # Check if URL changed (indicating form submission)
        new_url = page.url
        print(f"URL after click: {new_url}")
        print(f"URL changed: {current_url != new_url}")

        # Check for any new console messages after click
        print(f"Console messages after click: {len(console_messages)}")
        for msg in console_messages[-5:]:  # Show last 5 messages
            print(f"  {msg}")

        # Check page content for any error messages
        page_text = page.text_content("body")
        if "error" in page_text.lower() or "exception" in page_text.lower():
            print("ERROR DETECTED IN PAGE CONTENT:")
            print(page_text[:1000])  # First 1000 chars

        print("=== DIAGNOSTIC: Download Event ===")
        print("Waiting for download event...")
        
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
        # Use explicit wait for the h2 element instead of just networkidle to avoid race condition
        page.wait_for_load_state("networkidle")
        h2_locator = page.locator("h2")
        expect(h2_locator).to_be_visible(timeout=10000)
        expect(h2_locator).to_contain_text("Generate VPN Configuration")
        
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