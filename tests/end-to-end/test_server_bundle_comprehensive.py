#!/usr/bin/env python3
"""
Comprehensive end-to-end test for server bundle issuing using Playwright to generate PSKs.
"""

import pytest
import subprocess
import tempfile
import os
from playwright.sync_api import expect, Page


def test_server_bundle_with_playwright_psk_generation(authenticated_page, cli_browser_integration, repository_root):
    """Test complete server bundle workflow using Playwright to generate PSK"""

    # Check if CLI client exists
    cli_path = str(repository_root / "tools" / "get_openvpn_config" / "get_openvpn_server_config.py")
    if not os.path.exists(cli_path):
        pytest.fail("CLI client not found")
    
    # Step 1: Use Playwright to generate a PSK via admin UI
    admin_page = authenticated_page("admin")
    import time
    description = f"Playwright Test Server {int(time.time())}"
    
    # Navigate to PSK management page
    admin_page.goto("http://localhost/admin/psk")
    
    # Click "New PSK" button
    new_psk_button = admin_page.locator("a:has-text('New PSK')")
    expect(new_psk_button).to_be_visible(timeout=10000)
    new_psk_button.click()
    
    # Fill out PSK form fields
    description_field = admin_page.locator("input[name='description']")
    description_field.fill(description)
    
    # Select a template set (use the first available option)
    template_select = admin_page.locator("select[name='template_set']")
    template_select.select_option(index=0)
    
    # Submit form
    submit_button = admin_page.locator("button[type='submit'], input[type='submit']")
    submit_button.click()
    admin_page.wait_for_load_state("networkidle")
    
    # Should be on PSK creation success page
    expect(admin_page.locator("body")).to_contain_text("Pre-Shared Key Created Successfully", timeout=5000)
    
    # Extract PSK from the success page - it's shown in the command template
    page_content = admin_page.locator("body").inner_text()
    
    # Look for PSK in the command template: "--psk XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"  
    import re
    psk_match = re.search(r'--psk\s+([a-f0-9\-]{36})', page_content)
    if not psk_match:
        pytest.fail("Could not extract PSK from success page content")
    
    psk_key = psk_match.group(1)
    
    # Now return to PSK list to verify it was created
    return_button = admin_page.locator("a:has-text('Return to PSK Management')")
    expect(return_button).to_be_visible()
    return_button.click()
    admin_page.wait_for_load_state("networkidle")
    
    # Verify PSK appears in the list
    description_row = admin_page.locator(f"tr:has-text('{description}')")
    expect(description_row).to_be_visible(timeout=5000)
    
    print(f"Extracted PSK via Playwright: {psk_key[:8]}...")
    
    # Step 2: Use CLI with the extracted PSK (no hostname needed)
    cli_command = f"python3 {cli_path}  --server-url http://localhost --psk {psk_key} --target-dir /tmp/playwright-server-bundle --force"
    
    try:
        process, captured_url = cli_browser_integration.run_cli_command(cli_command, timeout=15)
        
        # PSK authentication shouldn't require browser
        assert captured_url is None or captured_url == "", "PSK profile should not require browser auth"
        
        if process.returncode is not None:
            if process.returncode == 0:
                # Success - verify files were created
                target_dir = "/tmp/playwright-server-bundle"
                if os.path.exists(target_dir):
                    files = []
                    for root, dirs, filenames in os.walk(target_dir):
                        files.extend(filenames)
                    
                    assert len(files) > 0, "Server bundle should create files"
                    print(f"✓ Playwright + CLI server bundle test successful! Files: {files}")
                    
                    # Verify expected file types
                    expected_types = ['.crt', '.key', '.conf', '.pem']
                    found_types = [ext for ext in expected_types if any(f.endswith(ext) for f in files)]
                    assert len(found_types) >= 2, f"Expected server files. Found types: {found_types}"
                    
                else:
                    pytest.fail("CLI reported success but target directory not found")
            else:
                # Check error output
                error_output = process.stderr if process.stderr else process.stdout
                if "500" in error_output or "internal server error" in error_output.lower():
                    pytest.fail(f"Server bundle API not fully implemented: {error_output}")
                else:
                    pytest.fail(f"Unexpected CLI failure: {error_output}")
        else:
            pytest.fail("CLI process timed out")
            
    except subprocess.TimeoutExpired:
        pytest.fail("CLI process timed out")


def test_server_bundle_psk_ui_workflow(authenticated_page):
    """Test PSK generation UI workflow for server bundles"""
    
    admin_page = authenticated_page("admin")
    import time
    description = f"PSK UI Test {int(time.time())}"
    
    # Step 1: Navigate to PSK page
    admin_page.goto("http://localhost/admin/psk")
    
    # Check page loaded correctly
    expect(admin_page.locator("h1")).to_contain_text("Pre-Shared Keys", timeout=10000)
    
    # Step 2: Create new PSK
    new_psk_link = admin_page.locator("a:has-text('New PSK')")
    expect(new_psk_link).to_be_visible()
    new_psk_link.click()
    
    # Fill form - only description field now (hostname was removed from PSK)
    description_field = admin_page.locator("input[name='description']")
    description_field.fill(description)
    
    # Select template set (first option)
    template_select = admin_page.locator("select[name='template_set']")
    template_select.select_option(index=0)
    
    # Submit - use input[type='submit'] as that's what the form actually has
    submit_button = admin_page.locator("input[type='submit']")
    submit_button.click()
    admin_page.wait_for_load_state("networkidle")
    
    # Step 3: Verify PSK was created (should be on success page)
    expect(admin_page.locator("body")).to_contain_text("Pre-Shared Key Created Successfully")
    
    # Step 4: Click "Return to PSK Management" to go back to list
    return_button = admin_page.locator("a:has-text('Return to PSK Management')")
    expect(return_button).to_be_visible()
    return_button.click()
    admin_page.wait_for_load_state("networkidle")
    
    # Step 5: Should now be back on PSK list - look for description instead of hostname
    description_row = admin_page.locator(f"tr:has-text('{description}')")
    expect(description_row).to_be_visible()
    
    # Step 4: Test PSK modal/copy functionality
    copy_buttons = description_row.locator("button:has-text('Copy'), a:has-text('Copy')")
    if copy_buttons.count() > 0:
        copy_buttons.first.click()
        
        # Modal should appear
        modal = admin_page.locator(".modal, .popup, [id*='modal']")
        if modal.count() > 0:
            expect(modal).to_be_visible(timeout=5000)
            
            # Look for PSK value in modal
            psk_text = modal.inner_text()
            assert len(psk_text) > 20, "Modal should contain PSK"
            
            # Close modal
            close_button = modal.locator("button:has-text('Close'), button:has-text('×')")
            if close_button.count() > 0:
                close_button.click()
    
    print(f"✓ PSK UI workflow test completed for {description}")


def test_server_bundle_file_validation(authenticated_page, repository_root):
    """Test server bundle file structure validation by creating and validating a bundle"""

    # This test creates its own server bundle to ensure consistent validation
    # Step 1: Create a PSK via admin UI
    admin_page = authenticated_page("admin")
    import time
    description = f"File Validation Test {int(time.time())}"

    # Navigate to PSK management page
    admin_page.goto("http://localhost/admin/psk")

    # Click "New PSK" button
    new_psk_button = admin_page.locator("a:has-text('New PSK')")
    expect(new_psk_button).to_be_visible(timeout=10000)
    new_psk_button.click()

    # Fill out PSK form fields
    description_field = admin_page.locator("input[name='description']")
    description_field.fill(description)

    # Select a template set (use the first available option)
    template_select = admin_page.locator("select[name='template_set']")
    template_select.select_option(index=0)

    # Submit form
    submit_button = admin_page.locator("button[type='submit'], input[type='submit']")
    submit_button.click()
    admin_page.wait_for_load_state("networkidle")

    # Should be on PSK creation success page
    expect(admin_page.locator("body")).to_contain_text("Pre-Shared Key Created Successfully", timeout=5000)

    # Extract PSK from the success page
    page_content = admin_page.locator("body").inner_text()
    import re
    psk_match = re.search(r'--psk\s+([a-f0-9\-]{36})', page_content)
    assert psk_match is not None, "Could not extract PSK from success page content"
    psk_key = psk_match.group(1)

    print(f"Created PSK for validation: {psk_key[:8]}...")

    # Step 2: Create server bundle using the PSK
    cli_path = str(repository_root / "tools" / "get_openvpn_config" / "get_openvpn_server_config.py")
    assert os.path.exists(cli_path), f"CLI client not found: {cli_path}"

    target_dir = "/tmp/validation-server-bundle"
    # Clean up any previous test data
    import shutil
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)

    cli_command = f"python3 {cli_path} --server-url http://localhost --psk {psk_key} --target-dir {target_dir} --force"

    result = subprocess.run(cli_command, shell=True, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"Server bundle creation failed: {result.stderr}"

    # Step 3: Validate the created bundle
    assert os.path.exists(target_dir), "Server bundle directory should exist"

    files = []
    for root, dirs, filenames in os.walk(target_dir):
        files.extend([(root, f) for f in filenames])

    assert len(files) > 0, "Server bundle should contain files"

    print(f"Validating server bundle files in {target_dir}:")

    # Check for expected file types
    cert_files = [f for root, f in files if f.endswith(('.crt', '.pem'))]
    key_files = [f for root, f in files if f.endswith('.key')]
    config_files = [f for root, f in files if f.endswith(('.conf', '.ovpn'))]

    print(f"  Certificates: {cert_files}")
    print(f"  Keys: {key_files}")
    print(f"  Configs: {config_files}")

    # Basic validation
    assert len(cert_files) > 0, f"No certificate files found in {target_dir}"
    assert len(key_files) > 0, f"No key files found in {target_dir}"

    # Validate file contents are not empty
    for root, filename in files:
        filepath = os.path.join(root, filename)
        file_size = os.path.getsize(filepath)
        assert file_size > 0, f"File {filename} is empty"

        # Basic content validation for specific file types
        if filename.endswith('.crt') or filename.endswith('.pem'):
            with open(filepath, 'r') as f:
                content = f.read()
                assert "-----BEGIN" in content, f"Invalid certificate format in {filename}"

    print(f"✓ Server bundle files in {target_dir} are valid")

    # Clean up
    shutil.rmtree(target_dir)