#!/usr/bin/env python3
"""
Configuration for functional tests
"""
import pytest
import requests
import os
import subprocess
import time
import fcntl
from pathlib import Path
from http.cookies import SimpleCookie
from playwright.sync_api import Playwright, Browser, BrowserContext, Page


@pytest.fixture(scope="session")
def repository_root():
    """
    Dynamically determine the repository root directory.
    This works regardless of whether tests are run from /home/user/... or /workspaces/...

    Returns:
        Path: Absolute path to the repository root
    """
    # Start from the current file's location and traverse up to find the repo root
    current_file = Path(__file__).resolve()

    # tests/end-to-end/conftest.py -> tests/ -> repo_root/
    repo_root = current_file.parent.parent.parent

    # Verify this is actually the repository root by checking for key files
    assert (repo_root / "LLM_INTRO.md").exists(), f"Repository root not found from {current_file}"
    assert (repo_root / "tests").exists(), f"Tests directory not found in {repo_root}"

    return repo_root


@pytest.fixture(scope="session")
def tests_dir(repository_root):
    """
    Get the tests directory path.

    Returns:
        Path: Absolute path to the tests directory
    """
    return repository_root / "tests"


@pytest.fixture(scope="session")
def tools_dir(repository_root):
    """
    Get the tools directory path.

    Returns:
        Path: Absolute path to the tools directory
    """
    return repository_root / "tools"


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for tests"""
    return {
        **browser_context_args,
        "ignore_https_errors": True,
        "viewport": {"width": 1280, "height": 720},
    }


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    """Create a fresh page for each test"""
    page = context.new_page()
    
    # Set longer timeout for authentication flows
    page.set_default_timeout(30000)
    
    yield page
    
    # Clean up
    page.close()


@pytest.fixture(autouse=True)
def clear_session_before_each_test(page: Page):
    """Clear any existing session before each test"""
    def cleanup_session(phase=""):
        """Clean up sessions with proper error handling and debugging"""
        if phase:
            print(f"Session cleanup {phase}...")
        
        # Step 1: Logout from tiny-oidc first
        try:
            page.goto("http://localhost:8000/user/logout", timeout=10000)
            page.wait_for_load_state("networkidle", timeout=5000)
            print(f"  ✓ Tiny-oidc logout completed")
        except Exception as e:
            print(f"  ! Tiny-oidc logout failed: {e}")
        
        # Step 2: Then logout from frontend
        try:
            page.goto("http://localhost/auth/logout", timeout=10000)
            page.wait_for_load_state("networkidle", timeout=5000)
            print(f"  ✓ Frontend logout completed")
        except Exception as e:
            print(f"  ! Frontend logout failed: {e}")
        
        # Step 3: Clear browser storage (cookies, etc)
        try:
            context = page.context
            context.clear_cookies()
            context.clear_permissions()
            print(f"  ✓ Browser storage cleared")
        except Exception as e:
            print(f"  ! Browser storage cleanup failed: {e}")
        
        # Add a small delay to ensure session cleanup is complete
        try:
            import time
            time.sleep(0.5)
        except:
            pass
    
    # Clean up before test
    cleanup_session("before test")
    
    yield
    
    # Clean up after test
    cleanup_session("after test")



@pytest.fixture(scope="function")
def authenticated_page(browser: Browser):
    """
    Fixture to provide an authenticated Playwright Page for a specific user type.
    This creates a new browser context for each user to ensure isolation.
    """
    created_contexts = []
    
    def _authenticated_page(user_type: str):
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 720},
        )
        created_contexts.append(context)
        page = context.new_page()
        page.set_default_timeout(30000)

        # Perform login within this new context
        login_as(user_type, page)

        return page
    
    yield _authenticated_page
    
    # Cleanup all created contexts
    for context in created_contexts:
        try:
            context.close()
        except:
            pass

def login_as(user_type: str, page: Page):
    """
    Helper function to properly log in as specified user following the full flow:
    1. Logout tinyoidc
    2. Logout frontend 
    3. Clear cookies
    4. Login frontend (via tinyoidc)
    
    Args:
        user_type: The user type to login as ('admin', 'it', 'accounts', etc.)
        page: Playwright page object
    """
    from playwright.sync_api import expect
    import time
    
    print(f"DEBUG: Starting {user_type} login process...")
    
    # Perform login within the current page (which is already in a fresh context)
    print(f"  → Starting fresh {user_type} login...")
    page.goto("http://localhost/", wait_until="networkidle")
    
    # Should be redirected to tiny-oidc login page
    try:
        expect(page.locator("h1")).to_contain_text("Login - kinda", timeout=10000)
        login_button = page.locator(f'button:has-text("Login as {user_type}")')
        expect(login_button).to_be_visible(timeout=5000)
        login_button.click()
        page.wait_for_load_state("networkidle", timeout=15000)
        print(f"  ✓ {user_type} login completed")
        
        # Verify we're logged in by checking for user menu or admin content
        # This will help catch authentication issues early
        if user_type == "admin":
            try:
                # Look for user menu dropdown or admin navigation
                user_menu = page.locator(".dropdown-button")
                if user_menu.count() > 0:
                    print("  ✓ Admin authentication verified - user menu visible")
                else:
                    print("  ! Warning: User menu not found after admin login")
            except Exception as e:
                print(f"  ! Login verification warning: {e}")
            
    except Exception as e:
        print(f"  ✗ {user_type} login failed: {e}")
        raise Exception(f"Failed to login as {user_type}: {e}")
    
    return page


# Convenience functions for backward compatibility
def login_as_admin(page: Page):
    """Convenience function for admin login"""
    return login_as("admin", page)


def login_as_user(page: Page, user_type="it"):
    """Convenience function for regular user login"""
    return login_as(user_type, page)


@pytest.fixture(scope="function")
def api_client():
    """
    API client for direct HTTP requests to services
    """
    class APIClient:
        def __init__(self):
            self.base_url = "http://localhost"
            self.session = requests.Session()
            self.session.verify = False  # Ignore SSL for testing
            
        def login(self, username="admin", password=None):
            """Login and get session cookies"""
            try:
                # Start authentication flow
                login_url = f"{self.base_url}/"
                response = self.session.get(login_url, allow_redirects=True, timeout=10)
                
                # If redirected to tiny-oidc, complete the login
                if "localhost:8000" in response.url or "tiny-oidc" in response.url:
                    # Submit login form to tiny-oidc
                    oidc_response = self.session.post(
                        f"http://localhost:8000/user/login",
                        data={"username": username},
                        allow_redirects=True,
                        timeout=10
                    )
                    return oidc_response
                
                return response
                
            except Exception as e:
                # Return a mock response for testing
                class MockResponse:
                    def __init__(self, status_code):
                        self.status_code = status_code
                        self.text = f"Mock response: {e}"
                
                return MockResponse(500)
            
        def get(self, path, **kwargs):
            """GET request to frontend service"""
            url = f"{self.base_url}{path}"
            return self.session.get(url, **kwargs)
            
        def post(self, path, **kwargs):
            """POST request to frontend service"""
            url = f"{self.base_url}{path}"
            return self.session.post(url, **kwargs)
    
    return APIClient()


@pytest.fixture(scope="function")
def cli_browser_integration(page: Page, repository_root):
    """
    Helper fixture for CLI commands that need browser integration
    """
    class CLIBrowserIntegration:
        def __init__(self, page, repository_root):
            self.page = page
            self.mock_xdg_open_path = str(repository_root / "tests" / "end-to-end" / "mock-xdg-open.sh")
            self.capture_file = "/tmp/xdg-open-captured-url.txt"
            self.log_file = "/tmp/xdg-open-capture.log"
            
        def setup_mock_xdg_open(self):
            """Setup PATH to use our mock xdg-open"""
            # Clear any previous captures
            if os.path.exists(self.capture_file):
                os.remove(self.capture_file)
                
            # Set PATH to prioritize our mock script
            test_bin_dir = os.path.dirname(self.mock_xdg_open_path)
            current_path = os.environ.get('PATH', '')
            os.environ['PATH'] = f"{test_bin_dir}:{current_path}"
            
            # Create symlink so our script is found as 'xdg-open'
            mock_link = os.path.join(test_bin_dir, "xdg-open")
            if os.path.exists(mock_link):
                os.remove(mock_link)
            os.symlink(self.mock_xdg_open_path, mock_link)
            os.chmod(mock_link, 0o755)
            
        def run_cli_command(self, command, timeout=30):
            """
            Run a CLI command that might trigger xdg-open or output auth URL
            Returns (process_result, captured_url)
            """
            captured_url = None

            # Always setup mock xdg-open to prevent browser popups
            self.setup_mock_xdg_open()

            # If this is a profile command with OIDC authentication, add --output-auth-url stderr for reliable URL capture
            if ('get-oidc-profile' in command or 'get_openvpn_profile.py' in command) and '--output-auth-url' not in command:
                command = command + ' --output-auth-url stderr'
            
            # Run the CLI command
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            # Check for AUTH_URL in stderr output
            if process.stderr:
                for line in process.stderr.split('\n'):
                    if line.startswith('AUTH_URL: '):
                        captured_url = line.replace('AUTH_URL: ', '').strip()
                        break
            
            # Fallback: Check if a URL was captured via xdg-open mock
            if not captured_url:
                self.setup_mock_xdg_open()
                if os.path.exists(self.capture_file):
                    with open(self.capture_file, 'r') as f:
                        captured_url = f.read().strip()
                        
            return process, captured_url

        def start_cli_command_background(self, command):
            """
            Start a CLI command in background and return process handle and captured auth URL
            Returns (process_handle, captured_url)
            """
            captured_url = None

            # Always setup mock xdg-open to prevent browser popups
            self.setup_mock_xdg_open()

            # If this is a profile command with OIDC authentication, add --output-auth-url stderr for reliable URL capture
            if ('get-oidc-profile' in command or 'get_openvpn_profile.py' in command) and '--output-auth-url' not in command:
                command = command + ' --output-auth-url stderr'

            # Start the CLI command in background
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Give the CLI a moment to start and output the auth URL
            import time
            time.sleep(2)

            # Check if we can read stderr data (the auth URL should be output quickly)
            try:
                # Use poll to check if process has terminated early
                if process.poll() is None:
                    # Process still running, try to read stderr for auth URL
                    stderr_so_far = ""
                    import select
                    import os

                    # Make stderr non-blocking
                    fd = process.stderr.fileno()
                    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

                    try:
                        stderr_data = process.stderr.read()
                        if stderr_data:
                            stderr_so_far = stderr_data
                    except BlockingIOError:
                        pass  # No data available yet

                    # Parse auth URL from stderr
                    for line in stderr_so_far.split('\n'):
                        if line.startswith('AUTH_URL: '):
                            captured_url = line.replace('AUTH_URL: ', '').strip()
                            break

            except Exception as e:
                print(f"Error reading CLI stderr: {e}")

            return process, captured_url

        def navigate_to_captured_url(self, captured_url, wait_for_load=True):
            """Navigate Playwright page to captured URL"""
            if captured_url:
                self.page.goto(captured_url)
                if wait_for_load:
                    self.page.wait_for_load_state("networkidle")
                return True
            return False
            
        def cleanup(self):
            """Clean up mock xdg-open setup"""
            test_bin_dir = os.path.dirname(self.mock_xdg_open_path)
            mock_link = os.path.join(test_bin_dir, "xdg-open")
            if os.path.exists(mock_link):
                os.remove(mock_link)
                
            # Clean up capture files
            for filepath in [self.capture_file, self.log_file]:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    
    integration = CLIBrowserIntegration(page, repository_root)
    yield integration
    integration.cleanup()