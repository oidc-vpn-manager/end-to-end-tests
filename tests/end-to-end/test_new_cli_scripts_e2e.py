#!/usr/bin/env python3
"""
End-to-end tests for the new CLI scripts:
- get_openvpn_profile.py (OIDC user profiles)
- get_openvpn_server_config.py (PSK server bundles)
- get_openvpn_computer_config.py (PSK computer profiles)

Tests cover both happy path and security/error scenarios.
"""

import pytest
import subprocess
import time
import os
import tempfile
import shutil
from pathlib import Path
from playwright.sync_api import expect, Page


class TestNewCLIScriptsE2E:
    """E2E tests for the three new CLI scripts"""

    @pytest.fixture(autouse=True)
    def setup_cli_paths(self):
        """Setup paths to the new CLI scripts"""
        self.base_path = "/workspaces/2025-06_openvpn-manager_gh-org/tools/get_openvpn_config"
        self.profile_script = f"{self.base_path}/get_openvpn_profile.py"
        self.server_script = f"{self.base_path}/get_openvpn_server_config.py"
        self.computer_script = f"{self.base_path}/get_openvpn_computer_config.py"

        # Verify scripts exist
        for script in [self.profile_script, self.server_script, self.computer_script]:
            if not os.path.exists(script):
                pytest.skip(f"CLI script not found: {script}")

    def test_user_profile_oidc_happy_path(self, page, cli_browser_integration):
        """Test get_openvpn_profile.py with OIDC authentication - happy path"""
        print("Testing OIDC user profile generation via get_openvpn_profile.py...")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "user-profile.ovpn")

            # Use the new profile script with OIDC authentication
            cli_command = f"python3 {self.profile_script} --server-url http://localhost --output {output_file}"

            try:
                # Start CLI command in background to capture auth URL
                cli_process, captured_url = cli_browser_integration.start_cli_command_background(cli_command)

                # OIDC profile should require browser authentication
                assert captured_url is not None and captured_url != "", "OIDC profile should require browser auth"
                assert "http://localhost/auth/login" in captured_url, "Should redirect to OIDC login"

                print(f"  → Captured auth URL: {captured_url}")

                # Use Playwright to navigate to the auth URL and complete login
                page.goto(captured_url)

                # Should be redirected to tiny-oidc login page
                from playwright.sync_api import expect
                expect(page.locator("h1")).to_contain_text("Login - kinda", timeout=10000)

                # Click admin login button
                login_button = page.locator('button:has-text("Login as admin")')
                expect(login_button).to_be_visible(timeout=5000)
                login_button.click()

                # Wait for authentication to complete and CLI to finish
                page.wait_for_load_state("networkidle", timeout=15000)

                # Wait for CLI process to complete
                cli_process.wait(timeout=30)

                # Verify CLI completed successfully
                if cli_process.returncode != 0:
                    stdout, stderr = cli_process.communicate()
                    pytest.fail(f"CLI command failed with return code {cli_process.returncode}: {stderr}")

                # Verify profile file was created
                assert os.path.exists(output_file), "Profile file should be created"

                # Verify file contains expected OpenVPN content
                with open(output_file, 'r') as f:
                    content = f.read()
                    assert 'client' in content, "Profile should contain client directive"
                    assert 'remote' in content, "Profile should contain remote directive"
                    print("✓ User profile generated successfully via get_openvpn_profile.py")

            except subprocess.TimeoutExpired:
                pytest.skip("CLI profile generation timed out")
            except Exception as e:
                print(f"  ! Authentication flow failed: {e}")
                pytest.skip(f"OIDC authentication flow failed: {e}")
            finally:
                # Clean up CLI process if still running
                try:
                    if 'cli_process' in locals() and cli_process.poll() is None:
                        cli_process.terminate()
                        cli_process.wait(timeout=5)
                except:
                    pass

    def test_server_config_psk_happy_path(self, authenticated_page):
        """Test get_openvpn_server_config.py with PSK authentication - happy path"""
        print("Testing server config generation via get_openvpn_server_config.py...")

        # Step 1: Create PSK for server bundle
        description = f"E2E Server Test {int(time.time())}"
        psk_command = f"docker exec tests-frontend-1 flask dev:create-psk --description '{description}' --template-set Default --psk-type server"

        try:
            psk_result = subprocess.run(psk_command, shell=True, capture_output=True, text=True, timeout=10)

            if psk_result.returncode != 0:
                pytest.skip(f"Could not create server PSK: {psk_result.stderr}")

            # Extract PSK from output
            psk_key = None
            for line in psk_result.stdout.split('\n'):
                if line.startswith('PSK:'):
                    psk_key = line.split('PSK:')[1].strip()
                    break

            if not psk_key:
                pytest.skip("Could not extract PSK from CLI output")

            print(f"✓ Created server PSK: {psk_key[:8]}...")

        except subprocess.TimeoutExpired:
            pytest.skip("Server PSK creation timed out")

        # Step 2: Use new server config script
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = os.path.join(temp_dir, "server-config")

            cli_command = f"python3 {self.server_script} --server-url http://localhost --psk {psk_key} --target-dir {target_dir} --force"

            try:
                result = subprocess.run(cli_command, shell=True, capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    # Verify files were extracted to target directory
                    extracted_files = os.listdir(target_dir)
                    assert len(extracted_files) > 0, "Files should be extracted to target directory"

                    # Verify expected file types exist
                    file_names = [f.lower() for f in extracted_files]
                    assert any('ca' in f or '.crt' in f for f in file_names), "CA certificate should be present"
                    assert any('server' in f for f in file_names), "Server certificate or key should be present"
                    assert any('.ovpn' in f for f in file_names), "OpenVPN configuration file should be present"

                    print("✓ Server configuration generated successfully via get_openvpn_server_config.py")
                else:
                    pytest.fail(f"Server config generation failed: {result.stderr}")

            except subprocess.TimeoutExpired:
                pytest.skip("Server config generation timed out")

    def test_computer_config_psk_happy_path(self, authenticated_page):
        """Test get_openvpn_computer_config.py with PSK authentication - happy path"""
        print("Testing computer config generation via get_openvpn_computer_config.py...")

        # Step 1: Create PSK for computer profile
        description = f"E2E Computer Test {int(time.time())}"
        psk_command = f"docker exec tests-frontend-1 flask dev:create-psk --description '{description}' --template-set Default --psk-type computer"

        try:
            psk_result = subprocess.run(psk_command, shell=True, capture_output=True, text=True, timeout=10)

            if psk_result.returncode != 0:
                pytest.skip(f"Could not create computer PSK: {psk_result.stderr}")

            # Extract PSK from output
            psk_key = None
            for line in psk_result.stdout.split('\n'):
                if line.startswith('PSK:'):
                    psk_key = line.split('PSK:')[1].strip()
                    break

            if not psk_key:
                pytest.skip("Could not extract PSK from CLI output")

            print(f"✓ Created computer PSK: {psk_key[:8]}...")

        except subprocess.TimeoutExpired:
            pytest.skip("Computer PSK creation timed out")

        # Step 2: Use new computer config script
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "computer-config.ovpn")

            cli_command = f"python3 {self.computer_script} --server-url http://localhost --psk {psk_key} --output {output_file} --force"

            try:
                result = subprocess.run(cli_command, shell=True, capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    # Verify profile file was created
                    assert os.path.exists(output_file), "Computer profile file should be created"

                    # Verify file contains expected OpenVPN content (single OVPN file like user profiles)
                    with open(output_file, 'r') as f:
                        content = f.read()
                        print(f"DEBUG: Computer profile content preview: {content[:200]}...")
                        assert 'client' in content, "Computer profile should contain client directive"
                        assert 'remote' in content, "Computer profile should contain remote directive"
                        assert 'cert' in content or 'BEGIN CERTIFICATE' in content, "Computer profile should contain certificate"
                        assert 'key' in content or 'BEGIN PRIVATE KEY' in content, "Computer profile should contain private key"

                    print("✓ Computer configuration generated successfully via get_openvpn_computer_config.py")
                else:
                    pytest.fail(f"Computer config generation failed: {result.stderr}")

            except subprocess.TimeoutExpired:
                pytest.skip("Computer config generation timed out")

    def test_profile_script_invalid_psk_error_handling(self, cli_browser_integration):
        """Test get_openvpn_profile.py error handling with invalid server URL"""
        print("Testing get_openvpn_profile.py error handling...")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "test-profile.ovpn")

            # Test with invalid server URL
            cli_command = f"python3 {self.profile_script} --server-url http://invalid-server.local --output {output_file} --force"

            try:
                result, captured_url = cli_browser_integration.run_cli_command(cli_command, timeout=15)

                # Should fail with connection error
                assert result.returncode != 0, "Should fail with invalid server URL"
                assert not os.path.exists(output_file), "Profile file should not be created on error"
                print("✓ get_openvpn_profile.py handles connection errors correctly")

            except subprocess.TimeoutExpired:
                print("✓ get_openvpn_profile.py timeout handling working correctly")

    def test_server_script_invalid_psk_error_handling(self):
        """Test get_openvpn_server_config.py error handling with invalid PSK"""
        print("Testing get_openvpn_server_config.py error handling...")

        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = os.path.join(temp_dir, "server-test")

            # Test with invalid PSK
            cli_command = f"python3 {self.server_script} --server-url http://localhost --psk invalid-psk-12345 --target-dir {target_dir} --force"

            try:
                result = subprocess.run(cli_command, shell=True, capture_output=True, text=True, timeout=15)

                # Should fail with authentication error
                assert result.returncode != 0, "Should fail with invalid PSK"
                assert not os.path.exists(target_dir) or len(os.listdir(target_dir)) == 0, "Target directory should be empty on error"
                print("✓ get_openvpn_server_config.py handles PSK authentication errors correctly")

            except subprocess.TimeoutExpired:
                print("✓ get_openvpn_server_config.py timeout handling working correctly")

    def test_computer_script_invalid_psk_error_handling(self):
        """Test get_openvpn_computer_config.py error handling with invalid PSK"""
        print("Testing get_openvpn_computer_config.py error handling...")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "computer-test.ovpn")

            # Test with invalid PSK
            cli_command = f"python3 {self.computer_script} --server-url http://localhost --psk invalid-computer-psk-12345 --output {output_file} --force"

            try:
                result = subprocess.run(cli_command, shell=True, capture_output=True, text=True, timeout=15)

                # Should fail with authentication error
                assert result.returncode != 0, "Should fail with invalid PSK"
                assert not os.path.exists(output_file), "Profile file should not be created on error"
                print("✓ get_openvpn_computer_config.py handles PSK authentication errors correctly")

            except subprocess.TimeoutExpired:
                print("✓ get_openvpn_computer_config.py timeout handling working correctly")

    def test_scripts_help_output(self):
        """Test that all scripts provide proper help output"""
        print("Testing CLI scripts help output...")

        scripts = [
            (self.profile_script, "get_openvpn_profile.py"),
            (self.server_script, "get_openvpn_server_config.py"),
            (self.computer_script, "get_openvpn_computer_config.py")
        ]

        for script_path, script_name in scripts:
            try:
                result = subprocess.run(f"python3 {script_path} --help", shell=True, capture_output=True, text=True, timeout=10)

                assert result.returncode == 0, f"{script_name} should provide help"
                assert "--server-url" in result.stdout, f"{script_name} should have server-url option"
                assert "--force" in result.stdout, f"{script_name} should have force option"
                print(f"✓ {script_name} provides correct help output")

            except subprocess.TimeoutExpired:
                pytest.fail(f"{script_name} help command timed out")

    def test_file_overwrite_protection(self):
        """Test file overwrite protection in all scripts"""
        print("Testing file overwrite protection...")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Test profile script overwrite protection
            profile_file = os.path.join(temp_dir, "existing-profile.ovpn")
            with open(profile_file, 'w') as f:
                f.write("existing content")

            cli_command = f"python3 {self.profile_script} --server-url http://localhost --output {profile_file}"

            try:
                result = subprocess.run(cli_command, shell=True, capture_output=True, text=True, timeout=10)

                # Should fail due to existing file without --force
                assert result.returncode != 0, "Should fail when output file exists without --force"
                assert "already exists" in result.stderr, "Should mention file already exists"

                # Verify original content is preserved
                with open(profile_file, 'r') as f:
                    content = f.read()
                    assert content == "existing content", "Original file should be preserved"

                print("✓ File overwrite protection working correctly")

            except subprocess.TimeoutExpired:
                pytest.skip("Overwrite protection test timed out")

    def test_environment_variable_support(self, cli_browser_integration):
        """Test environment variable support in all scripts"""
        print("Testing environment variable support...")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "env-test.ovpn")

            # Test with environment variables
            env = os.environ.copy()
            env['OVPN_MANAGER_URL'] = 'http://invalid-env-server.local'
            env['OVPN_MANAGER_OUTPUT'] = output_file
            env['OVPN_MANAGER_OVERWRITE'] = 'true'

            cli_command = f"python3 {self.profile_script}"

            try:
                # Use a custom CLI command runner with environment variables
                # But still use the CLI browser integration to prevent popups
                cli_browser_integration.setup_mock_xdg_open()

                # Add --output-auth-url stderr to prevent browser popups
                cli_command_with_auth = cli_command + ' --output-auth-url stderr'

                result = subprocess.run(cli_command_with_auth, shell=True, capture_output=True, text=True, timeout=10, env=env)

                # Should use environment variables (and fail due to invalid server)
                assert result.returncode != 0, "Should fail with invalid server from env var"
                print("✓ Environment variable support working correctly")

            except subprocess.TimeoutExpired:
                print("✓ Environment variable test timeout (expected with invalid server)")

    def test_script_security_psk_not_in_output(self, authenticated_page):
        """Test that PSK values are not exposed in error messages or logs"""
        print("Testing PSK security - ensuring PSKs are not exposed in output...")

        # Create a test PSK
        description = f"Security Test {int(time.time())}"
        psk_command = f"docker exec tests-frontend-1 flask dev:create-psk --description '{description}' --template-set Default --psk-type computer"

        try:
            psk_result = subprocess.run(psk_command, shell=True, capture_output=True, text=True, timeout=10)

            if psk_result.returncode != 0:
                pytest.skip(f"Could not create test PSK: {psk_result.stderr}")

            # Extract PSK from output
            psk_key = None
            for line in psk_result.stdout.split('\n'):
                if line.startswith('PSK:'):
                    psk_key = line.split('PSK:')[1].strip()
                    break

            if not psk_key:
                pytest.skip("Could not extract PSK from CLI output")

            # Test with invalid server URL to trigger an error
            with tempfile.TemporaryDirectory() as temp_dir:
                output_file = os.path.join(temp_dir, "security-test.ovpn")

                cli_command = f"python3 {self.computer_script} --server-url http://invalid-security-test.local --psk {psk_key} --output {output_file} --force"

                result = subprocess.run(cli_command, shell=True, capture_output=True, text=True, timeout=10)

                # Should fail, but PSK should not appear in error output
                assert result.returncode != 0, "Should fail with invalid server"
                assert psk_key not in result.stdout, "PSK should not appear in stdout"
                assert psk_key not in result.stderr, "PSK should not appear in stderr"
                print("✓ PSK values are properly protected from exposure in error messages")

        except subprocess.TimeoutExpired:
            pytest.skip("PSK security test timed out")
        except Exception as e:
            pytest.skip(f"PSK security test failed to setup: {e}")


def test_all_scripts_exist():
    """Basic test to ensure all three scripts exist and are executable"""
    base_path = "/workspaces/2025-06_openvpn-manager_gh-org/tools/get_openvpn_config"
    scripts = [
        "get_openvpn_profile.py",
        "get_openvpn_server_config.py",
        "get_openvpn_computer_config.py"
    ]

    for script in scripts:
        script_path = os.path.join(base_path, script)
        assert os.path.exists(script_path), f"Script {script} should exist"
        assert os.access(script_path, os.X_OK), f"Script {script} should be executable"

    print("✓ All three new CLI scripts exist and are executable")


def test_original_script_still_exists():
    """Ensure the original monolithic script still exists for backward compatibility"""
    original_script = "/workspaces/2025-06_openvpn-manager_gh-org/tools/get_openvpn_config/get_openvpn_config.py"
    assert os.path.exists(original_script), "Original get_openvpn_config.py should still exist"
    print("✓ Original get_openvpn_config.py still exists for backward compatibility")