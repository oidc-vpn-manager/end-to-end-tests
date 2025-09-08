#!/usr/bin/env python3
"""
Quick test to check if groups are now being detected after auth fix
"""
import tempfile
import os
from playwright.sync_api import sync_playwright

def test_groups():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # Navigate and authenticate
        page.goto("http://localhost/")
        page.wait_for_load_state("networkidle")
        
        # Login 
        admin_button = page.locator("button:has-text('Login as admin')")
        admin_button.click()
        page.wait_for_load_state("networkidle")
        
        # Go to profile config
        page.click("a:has-text('Profile')")
        page.wait_for_load_state("networkidle")
        
        # Check what template is being used by downloading
        with page.expect_download() as download_info:
            page.click("button[type='submit'], input[type='submit'], button:has-text('Generate')")
        
        download = download_info.value
        
        # Save and examine content
        with tempfile.NamedTemporaryFile(suffix='.ovpn', delete=False) as tmp_file:
            download.save_as(tmp_file.name)
            
            with open(tmp_file.name, 'r') as f:
                content = f.read()
                
            # Check what server hostname we got
            import re
            remote_lines = re.findall(r'^remote\s+([^\s]+)\s+(\d+)', content, re.MULTILINE)
            print(f"=== REMOTE SERVER DETECTED ===")
            for hostname, port in remote_lines:
                print(f"Server: {hostname}:{port}")
            
            if "vpn.example.org" in content:
                print("✅ SUCCESS: Admin user is getting vpn.example.org (admin template)")
            elif "default.example.org" in content:
                print("❌ ISSUE: Admin user is still getting default.example.org (default template)")
            else:
                print("❓ UNKNOWN: No recognized server hostname found")
            
            # Clean up
            os.unlink(tmp_file.name)
        
        browser.close()

if __name__ == "__main__":
    test_groups()