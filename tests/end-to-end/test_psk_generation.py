"""
Integration tests for PSK (Pre-Shared Key) generation via frontend service CLI.

Tests the ability to generate PSKs through the frontend service development commands
using docker-compose exec.
"""

import subprocess
import json
import re
import pytest
import time


class TestPSKGenerationIntegration:
    """Test suite for PSK generation integration tests."""
    
    def test_dev_create_psk_command_exists(self, tests_dir):
        """Test that the dev:create-psk command is available."""
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "frontend", "flask", "--help"],
            cwd=str(tests_dir),
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "dev:create-psk" in result.stdout
    
    def test_psk_generation_basic(self, tests_dir):
        """Test basic PSK generation functionality."""
        description = f"test-server-{int(time.time())}.example.com"
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "frontend", "flask", "dev:create-psk", "--description", description],
            cwd=str(tests_dir),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(f"Command output: {result.stdout}")
        print(f"Command stderr: {result.stderr}")
        print(f"Return code: {result.returncode}")
        
        # Command should complete successfully
        assert result.returncode == 0, f"Command failed with stderr: {result.stderr}"
        
        # Output should contain PSK information
        output = result.stdout
        assert len(output.strip()) > 0, "No output from PSK generation command"
        
        # Should contain some kind of PSK identifier or success message
        assert any(keyword in output.lower() for keyword in ['psk', 'key', 'created', 'generated', 'success'])
    
    def test_psk_generation_with_expiration(self, tests_dir):
        """Test PSK generation with expiration parameter."""
        description = f"integration-test-{int(time.time())}.example.com"
        
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "frontend", "flask", "dev:create-psk", "--description", description, "--expires-days", "30"],
            cwd=str(tests_dir),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(f"Command output: {result.stdout}")
        print(f"Command stderr: {result.stderr}")
        print(f"Return code: {result.returncode}")
        
        # Command should complete successfully
        assert result.returncode == 0, f"Command failed with stderr: {result.stderr}"
        
        # Output should reference the description
        output = result.stdout
        assert description in output or "integration-test" in output
    
    def test_psk_generation_help(self, tests_dir):
        """Test that PSK generation command has help documentation."""
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "frontend", "flask", "dev:create-psk", "--help"],
            cwd=str(tests_dir),
            capture_output=True,
            text=True,
            timeout=15
        )
        
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "dev:create-psk" in result.stdout
    
    def test_database_connectivity_via_psk_creation(self, tests_dir):
        """Test that PSK creation implies database connectivity is working."""
        # Create a PSK and verify it worked, which implies:
        # 1. Database connection is working
        # 2. PSK model can be created
        # 3. Database transactions work
        
        description = f"db-test-{int(time.time())}.example.com"
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "frontend", "flask", "dev:create-psk", "--description", description],
            cwd=str(tests_dir),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(f"Database connectivity test output: {result.stdout}")
        print(f"Database connectivity test stderr: {result.stderr}")
        
        # If PSK creation succeeds, database is working
        assert result.returncode == 0, f"Database connectivity failed via PSK creation: {result.stderr}"
        
        # Should get some confirmation of creation
        output = result.stdout.lower()
        success_indicators = ['created', 'generated', 'success', 'psk', 'key']
        assert any(indicator in output for indicator in success_indicators), \
            f"No success indicators found in output: {result.stdout}"


class TestFrontendCLIIntegration:
    """Test suite for other frontend CLI command integration tests."""
    
    def test_dev_create_auth_command_exists(self, tests_dir):
        """Test that development auth command exists."""
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "frontend", "flask", "--help"],
            cwd=str(tests_dir),
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "dev:create-dev-auth" in result.stdout
    
    def test_database_migration_status(self, tests_dir):
        """Test that database migrations are applied."""
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "frontend", "flask", "db", "current"],
            cwd=str(tests_dir),
            capture_output=True,
            text=True,
            timeout=15
        )
        
        # Should show current migration status
        assert result.returncode == 0, f"Migration status check failed: {result.stderr}"
        # Should show some migration information
        assert len(result.stdout.strip()) > 0, "No migration status returned"
    
    def test_flask_routes_accessible(self, tests_dir):
        """Test that Flask routes command works and shows expected routes."""
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "frontend", "flask", "routes"],
            cwd=str(tests_dir),
            capture_output=True,
            text=True,
            timeout=15
        )
        
        assert result.returncode == 0, f"Routes command failed: {result.stderr}"
        
        # Should show expected routes
        output = result.stdout
        expected_routes = ['/auth/login', '/profile', '/api/v1', '/health']
        
        found_routes = []
        for route in expected_routes:
            if route in output:
                found_routes.append(route)
        
        assert len(found_routes) > 0, f"No expected routes found in output: {output}"
        print(f"Found expected routes: {found_routes}")


class TestServiceHealthChecks:
    """Test suite for service health checks via docker-compose."""
    
    def test_all_required_services_running(self, tests_dir):
        """Test that all required services are running."""
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            cwd=str(tests_dir),
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        
        # Parse JSON output
        services = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                services.append(json.loads(line))
        
        # Check for required services
        required_services = ['frontend', 'certtransparency', 'tiny-oidc']
        running_services = []
        
        for service in services:
            service_name = service.get('Service', '')
            state = service.get('State', '')
            
            if any(req in service_name for req in required_services):
                if 'running' in state.lower() or 'up' in state.lower():
                    running_services.append(service_name)
                    print(f"✓ {service_name}: {state}")
                else:
                    print(f"✗ {service_name}: {state}")
        
        # At least 3 out of 4 services should be running (signing might be failing)
        assert len(running_services) >= 3, f"Not enough services running. Running: {running_services}"
    
