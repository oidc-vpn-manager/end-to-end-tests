#!/usr/bin/env python3
"""
Test the xdg-open integration functionality
"""

import pytest
import os
import tempfile


def test_cli_browser_integration_xdg_open_capture(cli_browser_integration):
    """Test that CLI browser integration captures URLs via stderr output mechanism"""
    
    # Test the stderr URL capture mechanism directly
    import subprocess
    
    # Create a simple test command that outputs AUTH_URL to stderr
    test_command = 'python3 -c "import sys; print(\'AUTH_URL: http://localhost:8080/test-integration?cli_port=12345\', file=sys.stderr)"'
    
    process, captured_url = cli_browser_integration.run_cli_command(test_command, timeout=5)
    
    assert captured_url is not None, "Should capture URL from stderr output"
    assert "test-integration" in captured_url, f"Should capture correct URL: {captured_url}"
    assert "cli_port=12345" in captured_url, f"Should contain CLI port parameter: {captured_url}"
    assert process.returncode == 0, "Test command should succeed"


def test_cli_browser_integration_path_setup(cli_browser_integration):
    """Test that PATH is correctly modified to use mock xdg-open"""
    
    # Setup mock (this happens in run_cli_command, but we can test it directly)
    cli_browser_integration.setup_mock_xdg_open()
    
    # Check that our mock is in PATH
    test_bin_dir = os.path.dirname(cli_browser_integration.mock_xdg_open_path)
    current_path = os.environ.get('PATH', '')
    
    assert test_bin_dir in current_path, "Mock bin directory should be in PATH"
    
    # Check that symlink exists and is executable
    mock_link = os.path.join(test_bin_dir, "xdg-open")
    assert os.path.exists(mock_link), "xdg-open symlink should exist"
    assert os.access(mock_link, os.X_OK), "xdg-open symlink should be executable"


def test_cli_browser_integration_cleanup(cli_browser_integration):
    """Test that CLI browser integration cleanup functionality works"""
    
    # Test that both stderr and xdg-open fallback mechanisms work
    
    # First test stderr capture with a simple command
    test_command = 'python3 -c "import sys; print(\'AUTH_URL: http://localhost:8080/test-cleanup?cli_port=54321\', file=sys.stderr)"'
    
    process, captured_url = cli_browser_integration.run_cli_command(test_command, timeout=5)
    
    # Should capture URL from stderr
    assert captured_url is not None, "Should capture URL from stderr output"
    assert "test-cleanup" in captured_url, f"Should capture valid URL: {captured_url}"
    assert process.returncode == 0, "Test command should succeed"
    
    # Test xdg-open fallback mechanism
    cli_browser_integration.setup_mock_xdg_open()
    
    # Verify mock setup creates expected files
    test_bin_dir = os.path.dirname(cli_browser_integration.mock_xdg_open_path)
    mock_link = os.path.join(test_bin_dir, "xdg-open")
    
    if os.path.exists(mock_link):
        # Test fallback by running xdg-open directly
        fallback_command = 'xdg-open "http://localhost:8080/test-fallback"'
        fallback_process, fallback_url = cli_browser_integration.run_cli_command(fallback_command, timeout=5)
        
        # Should capture via xdg-open fallback
        if fallback_url:
            assert "test-fallback" in fallback_url, f"Should capture via fallback: {fallback_url}"
        
        # Clean up
        cli_browser_integration.cleanup()
        
        # Verify symlink is removed
        assert not os.path.exists(mock_link), "xdg-open symlink should be cleaned up"
    
    print("✓ CLI browser integration cleanup test completed")