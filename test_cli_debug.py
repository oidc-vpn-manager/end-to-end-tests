#!/usr/bin/env python3
"""
Debug script to test CLI browser integration mocking
"""
import subprocess
import os
import tempfile

def test_cli_mocking():
    """Test that CLI mocking is working properly"""
    print("Testing CLI browser integration mocking...")

    # Set up mock xdg-open
    mock_script_path = "/workspaces/2025-06_openvpn-manager_gh-org/tests/end-to-end/mock-xdg-open.sh"
    capture_file = "/tmp/xdg-open-captured-url.txt"

    # Clear any previous captures
    if os.path.exists(capture_file):
        os.remove(capture_file)

    # Set PATH to prioritize our mock script
    test_bin_dir = os.path.dirname(mock_script_path)
    current_path = os.environ.get('PATH', '')
    os.environ['PATH'] = f"{test_bin_dir}:{current_path}"

    # Create symlink so our script is found as 'xdg-open'
    mock_link = os.path.join(test_bin_dir, "xdg-open")
    if os.path.exists(mock_link):
        os.remove(mock_link)
    os.symlink(mock_script_path, mock_link)
    os.chmod(mock_link, 0o755)

    print(f"Mock xdg-open set up at: {mock_link}")

    # Test the profile script with OIDC - this should use --output-auth-url stderr
    with tempfile.TemporaryDirectory() as temp_dir:
        output_file = os.path.join(temp_dir, "test-profile.ovpn")

        cli_command = f"python3 /workspaces/2025-06_openvpn-manager_gh-org/tools/get_openvpn_config/get_openvpn_profile.py --server-url http://localhost --output {output_file} --output-auth-url stderr"

        print(f"Running command: {cli_command}")

        try:
            process = subprocess.run(
                cli_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )

            print(f"Return code: {process.returncode}")
            print(f"Stdout: {process.stdout}")
            print(f"Stderr: {process.stderr}")

            # Check for AUTH_URL in stderr
            auth_url = None
            if process.stderr:
                for line in process.stderr.split('\n'):
                    if line.startswith('AUTH_URL: '):
                        auth_url = line.replace('AUTH_URL: ', '').strip()
                        break

            if auth_url:
                print(f"✓ AUTH_URL captured from stderr: {auth_url}")
            else:
                print("! No AUTH_URL found in stderr")

            # Check if xdg-open was called (it shouldn't be with --output-auth-url stderr)
            if os.path.exists(capture_file):
                with open(capture_file, 'r') as f:
                    captured_url = f.read().strip()
                    print(f"! xdg-open was called with: {captured_url}")
            else:
                print("✓ xdg-open was not called (good!)")

        except subprocess.TimeoutExpired:
            print("! Command timed out")
        except Exception as e:
            print(f"! Command failed: {e}")

    # Clean up
    if os.path.exists(mock_link):
        os.remove(mock_link)
    if os.path.exists(capture_file):
        os.remove(capture_file)

if __name__ == "__main__":
    test_cli_mocking()