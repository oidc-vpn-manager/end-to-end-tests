"""
End-to-end tests for PSK command generation modal.

Tests the modal functionality for generating PSK usage commands
through the admin web interface using Playwright.
"""

import pytest
from playwright.sync_api import Page, expect


class TestPSKCommandModal:
    """Test suite for PSK command generation modal functionality."""

    def test_psk_modal_opens_and_closes(self, page: Page):
        """Test that the PSK command modal opens and closes correctly."""
        # Navigate to the application and authenticate as admin
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        # Click the admin user login button
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        # Wait for redirect and navigate to PSK page
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/admin/psk")
        page.wait_for_load_state("networkidle")
        
        # Check if there are any PSKs to test with
        command_buttons = page.locator("button:has-text('Get command to use the PSK for')")
        
        if command_buttons.count() > 0:
            # Test modal opening
            command_buttons.first.click()
            
            # Modal should be visible
            modal = page.locator("#commandModal")
            expect(modal).to_be_visible()
            
            # Modal should have the correct content
            expect(page.locator("#commandModal h3")).to_contain_text("Commands to use PSK for")
            expect(page.locator("#commandModal")).to_contain_text("Download the script")
            expect(page.locator("#commandModal")).to_contain_text("Run the script with your PSK")
            
            # Test closing modal with close button
            close_button = page.locator("#commandModal .close")
            expect(close_button).to_be_visible()
            close_button.click()
            
            # Modal should be hidden
            expect(modal).to_be_hidden()

    def test_psk_modal_copy_functionality(self, page: Page):
        """Test that the copy buttons in the PSK modal work correctly."""
        # Navigate to the application and authenticate as admin
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/admin/psk")
        page.wait_for_load_state("networkidle")
        
        # Check if there are any PSKs to test with
        command_buttons = page.locator("button:has-text('Get command to use the PSK for')")
        
        if command_buttons.count() > 0:
            # Open modal
            command_buttons.first.click()
            modal = page.locator("#commandModal")
            expect(modal).to_be_visible()
            
            # Test copy buttons
            copy_buttons = page.locator("#commandModal .copy-button")
            expect(copy_buttons).to_have_count(2)  # Should have 2 copy buttons
            
            # Click first copy button (curl command)
            copy_buttons.first.click()
            
            # Button text should change to "Copied!" temporarily
            expect(copy_buttons.first).to_contain_text("Copied!")
            
            # Wait a moment and check it changes back
            page.wait_for_timeout(2500)  # Wait longer than the 2 second timeout
            expect(copy_buttons.first).to_contain_text("Copy")

    def test_psk_modal_escape_key_closes(self, page: Page):
        """Test that pressing Escape key closes the modal."""
        # Navigate to the application and authenticate as admin
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/admin/psk")
        page.wait_for_load_state("networkidle")
        
        # Check if there are any PSKs to test with
        command_buttons = page.locator("button:has-text('Get command to use the PSK for')")
        
        if command_buttons.count() > 0:
            # Open modal
            command_buttons.first.click()
            modal = page.locator("#commandModal")
            expect(modal).to_be_visible()
            
            # Press Escape key
            page.keyboard.press("Escape")
            
            # Modal should be hidden
            expect(modal).to_be_hidden()

    def test_psk_modal_click_outside_closes(self, page: Page):
        """Test that clicking outside the modal closes it."""
        # Navigate to the application and authenticate as admin
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/admin/psk")
        page.wait_for_load_state("networkidle")
        
        # Check if there are any PSKs to test with
        command_buttons = page.locator("button:has-text('Get command to use the PSK for')")
        
        if command_buttons.count() > 0:
            # Open modal
            command_buttons.first.click()
            modal = page.locator("#commandModal")
            expect(modal).to_be_visible()
            
            # Click on the modal background (outside the content)
            page.locator("body").click(position={"x": 10, "y": 10})
            
            # Modal should be hidden
            expect(modal).to_be_hidden()

    def test_psk_modal_shows_correct_description(self, page: Page):
        """Test that the modal shows the correct description for the selected PSK."""
        # Navigate to the application and authenticate as admin
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/admin/psk")
        page.wait_for_load_state("networkidle")
        
        # Check if there are any PSKs to test with
        command_buttons = page.locator("button:has-text('Get command to use the PSK for')")
        
        if command_buttons.count() > 0:
            # Get the description from the first row
            first_row = page.locator("tbody tr").first
            description_cell = first_row.locator("td").first
            description = description_cell.text_content()
            
            # Open modal for this PSK
            command_buttons.first.click()
            modal = page.locator("#commandModal")
            expect(modal).to_be_visible()
            
            # Check that the modal title contains the correct description
            modal_title = page.locator("#commandModal h3")
            expect(modal_title).to_contain_text(f"Commands to use PSK for {description}")
            
            # Check that the python command contains the correct description
            python_command = page.locator("#pythonCommand")
            expect(python_command).to_contain_text(f"--description {description}")

    def test_psk_modal_contains_security_warning(self, page: Page):
        """Test that the modal contains appropriate security warnings."""
        # Navigate to the application and authenticate as admin
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/admin/psk")
        page.wait_for_load_state("networkidle")
        
        # Check if there are any PSKs to test with
        command_buttons = page.locator("button:has-text('Get command to use the PSK for')")
        
        if command_buttons.count() > 0:
            # Open modal
            command_buttons.first.click()
            modal = page.locator("#commandModal")
            expect(modal).to_be_visible()
            
            # Check for security warning
            security_warning = page.locator(".security-warning")
            expect(security_warning).to_be_visible()
            expect(security_warning).to_contain_text("Security Note")
            expect(security_warning).to_contain_text("sensitive information")

    def test_psk_modal_commands_format(self, page: Page):
        """Test that the modal shows correctly formatted commands."""
        # Navigate to the application and authenticate as admin
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/admin/psk")
        page.wait_for_load_state("networkidle")
        
        # Check if there are any PSKs to test with
        command_buttons = page.locator("button:has-text('Get command to use the PSK for')")
        
        if command_buttons.count() > 0:
            # Open modal
            command_buttons.first.click()
            modal = page.locator("#commandModal")
            expect(modal).to_be_visible()
            
            # Check that curl command is present and correctly formatted
            curl_command = page.locator(".command-block").first.locator("code")
            expect(curl_command).to_contain_text("curl -O https://raw.githubusercontent.com/openvpn-manager/get-openvpn-config/refs/heads/main/get_openvpn_config.py")
            
            # Check that python command is present and correctly formatted
            python_command = page.locator("#pythonCommand")
            expect(python_command).to_contain_text("python3 get_openvpn_config.py --description")
            expect(python_command).to_contain_text("--psk")
            expect(python_command).to_contain_text("--server-url")


    def test_modal_close_button_works(self, page: Page):
        """Test that the modal Close button works correctly."""
        # Navigate to the application and authenticate as admin
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        admin_button = page.locator("button:has-text('Login as admin')")
        expect(admin_button).to_be_visible()
        admin_button.click()
        
        page.wait_for_load_state("networkidle")
        page.goto("http://localhost/admin/psk")
        page.wait_for_load_state("networkidle")
        
        # Check if there are any PSKs to test with
        command_buttons = page.locator("button:has-text('Get command to use the PSK for')")
        
        if command_buttons.count() > 0:
            # Open modal
            command_buttons.first.click()
            modal = page.locator("#commandModal")
            expect(modal).to_be_visible()
            
            # Click the Close button in the footer
            close_button = page.locator("#commandModal .modal-footer button:has-text('Close')")
            expect(close_button).to_be_visible()
            close_button.click()
            
            # Modal should be hidden
            expect(modal).to_be_hidden()