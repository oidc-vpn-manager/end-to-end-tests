"""
End-to-end tests for the OpenVPN 3 WEB_AUTH profile provisioning flow.

Tests the /openvpn-api/profile endpoint (HEAD + GET) and the complete
WEB_AUTH workflow used by the OpenVPN Connect application to automatically
provision VPN profiles.

Coverage:
  - HEAD discovery (no token → Ovpn-WebAuth returned)
  - HEAD freshness check with unknown / garbage token → Ovpn-WebAuth returned
  - HEAD freshness check after a successful download → Ovpn-WebAuth absent
  - GET unauthenticated → OIDC login redirect
  - GET authenticated → openvpn://import-profile/… redirect
  - GET with device params forwarded by OpenVPN Connect
  - Full WEB_AUTH flow: login → openvpn:// redirect → download → VPN-Session-Token
  - Security / unhappy paths (OWASP API Top 10 lens)

Implementation note — authenticated requests:
  Playwright cookies are not reliably transferable to a bare `requests.Session`
  because Flask-Session stores the session server-side and the session-id
  cookie may have domain/path constraints that `requests` doesn't honour.
  All authenticated HTTP calls therefore use `page.request` (Playwright's
  APIRequestContext), which shares the live cookie jar with the page.
"""

import uuid
import requests
import pytest
from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost"
PROFILE_URL = f"{BASE_URL}/openvpn-api/profile"


def _requests_session(verify=False):
    """Return a plain requests.Session (no cookies, SSL verification off)."""
    session = requests.Session()
    session.verify = verify
    return session


def _login(page: Page):
    """Log in via tiny-oidc and wait until the frontend home page is reached."""
    page.goto(f"{BASE_URL}/")
    page.wait_for_load_state("networkidle")
    login_button = page.locator(
        "button:has-text('Login as it'), button:has-text('Login as admin')"
    )
    expect(login_button.first).to_be_visible(timeout=15000)
    login_button.first.click()
    page.wait_for_load_state("networkidle", timeout=15000)


# ---------------------------------------------------------------------------
# HEAD — discovery and freshness
# ---------------------------------------------------------------------------

class TestWebAuthHead:
    """HEAD /openvpn-api/profile — discovery and freshness checks."""

    def test_head_no_token_returns_ovpn_webauth_header(self):
        """
        GIVEN no VPN-Session-Token header
        WHEN HEAD /openvpn-api/profile is requested
        THEN 200 and Ovpn-WebAuth header present (signals re-auth required)
        """
        resp = _requests_session().head(PROFILE_URL)
        assert resp.status_code == 200
        assert "Ovpn-WebAuth" in resp.headers, (
            "Ovpn-WebAuth header must be present for discovery"
        )
        header_value = resp.headers["Ovpn-WebAuth"]
        # Format: "<provider_name>,external"
        assert "," in header_value, f"Expected <name>,external format, got: {header_value}"
        assert header_value.endswith(",external"), (
            f"Expected ',external' mode, got: {header_value}"
        )

    def test_head_unknown_token_returns_ovpn_webauth_header(self):
        """
        GIVEN a VPN-Session-Token for a token that does not exist in the DB
        WHEN HEAD /openvpn-api/profile is requested
        THEN 200 and Ovpn-WebAuth header present (profile not fresh)
        """
        random_token = str(uuid.uuid4())
        resp = _requests_session().head(
            PROFILE_URL, headers={"VPN-Session-Token": random_token}
        )
        assert resp.status_code == 200
        assert "Ovpn-WebAuth" in resp.headers, (
            "Unknown token should be treated as not-fresh; Ovpn-WebAuth must appear"
        )

    def test_head_garbage_token_returns_ovpn_webauth_header(self):
        """
        GIVEN a VPN-Session-Token with garbage / non-UUID data
        WHEN HEAD /openvpn-api/profile is requested
        THEN 200 and Ovpn-WebAuth header present (fail-closed on bad input)
        """
        resp = _requests_session().head(
            PROFILE_URL, headers={"VPN-Session-Token": "'; DROP TABLE download_tokens; --"}
        )
        assert resp.status_code == 200
        assert "Ovpn-WebAuth" in resp.headers

    def test_head_empty_token_returns_ovpn_webauth_header(self):
        """
        GIVEN an empty VPN-Session-Token header
        WHEN HEAD /openvpn-api/profile is requested
        THEN 200 and Ovpn-WebAuth header present
        """
        resp = _requests_session().head(
            PROFILE_URL, headers={"VPN-Session-Token": ""}
        )
        assert resp.status_code == 200
        assert "Ovpn-WebAuth" in resp.headers

    def test_head_no_body_returned(self):
        """
        GIVEN any HEAD request to /openvpn-api/profile
        WHEN the response is received
        THEN the body must be empty (HEAD semantics)
        """
        resp = _requests_session().head(PROFILE_URL)
        assert resp.status_code == 200
        assert resp.content == b"", "HEAD response must have no body"

    def test_head_ovpn_webauth_header_contains_provider_name(self):
        """
        GIVEN a discovery HEAD request
        WHEN the response Ovpn-WebAuth header is inspected
        THEN the provider name portion is non-empty (config driven by SITE_NAME)
        """
        resp = _requests_session().head(PROFILE_URL)
        assert resp.status_code == 200
        header_value = resp.headers.get("Ovpn-WebAuth", "")
        provider_name = header_value.rsplit(",", 1)[0]
        assert provider_name.strip(), (
            f"Provider name in Ovpn-WebAuth must not be empty, got: '{header_value}'"
        )


# ---------------------------------------------------------------------------
# GET — unauthenticated
# ---------------------------------------------------------------------------

class TestWebAuthGetUnauthenticated:
    """GET /openvpn-api/profile without a valid session."""

    def test_get_unauthenticated_redirects_to_login(self):
        """
        GIVEN no session cookie
        WHEN GET /openvpn-api/profile is requested
        THEN 302 redirect towards /auth/login
        """
        resp = _requests_session().get(PROFILE_URL, allow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers.get("Location", "")
        assert "auth/login" in location or "login" in location, (
            f"Expected redirect to auth/login, got: {location}"
        )

    def test_get_unauthenticated_stores_next_url_in_session(self):
        """
        GIVEN no session cookie
        WHEN GET /openvpn-api/profile is requested
        THEN redirect goes to the login endpoint (next_url is stored server-side)
        """
        resp = _requests_session().get(PROFILE_URL, allow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "").lower()

    def test_get_unauthenticated_with_device_params_redirects_to_login(self):
        """
        GIVEN device metadata query params from OpenVPN Connect
        WHEN GET /openvpn-api/profile is requested without a session
        THEN still redirects to /auth/login (device params stashed for audit)
        """
        params = {
            "deviceID": "test-device-abc123",
            "deviceModel": "TestPhone Pro",
            "deviceOS": "TestOS 15.0",
            "appVersion": "3.4.0",
        }
        resp = _requests_session().get(PROFILE_URL, params=params, allow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "").lower()

    def test_get_unauthenticated_does_not_disclose_server_info(self):
        """
        GIVEN no session cookie
        WHEN GET /openvpn-api/profile is requested
        THEN response does not disclose stack traces or internal paths
        """
        resp = _requests_session().get(PROFILE_URL, allow_redirects=False)
        assert resp.status_code == 302
        body = resp.text.lower()
        assert "traceback" not in body
        assert "exception" not in body

    def test_get_browser_redirects_to_oidc_login(self, page: Page):
        """
        GIVEN an unauthenticated browser
        WHEN Playwright navigates to /openvpn-api/profile
        THEN the browser is redirected to the OIDC login page
        """
        page.goto(PROFILE_URL)
        page.wait_for_load_state("networkidle")
        current_url = page.url
        assert (
            "auth/login" in current_url
            or "mock_oidc" in current_url
            or "login" in current_url.lower()
        ), f"Expected OIDC login redirect, ended up at: {current_url}"


# ---------------------------------------------------------------------------
# GET — authenticated (requires live Docker stack)
#
# All authenticated HTTP calls use page.request (Playwright's APIRequestContext)
# which automatically shares the browser's live cookie jar.
# ---------------------------------------------------------------------------

class TestWebAuthGetAuthenticated:
    """GET /openvpn-api/profile with a valid authenticated session."""

    def test_get_authenticated_redirects_to_openvpn_url(self, page: Page):
        """
        GIVEN a user authenticated via OIDC
        WHEN GET /openvpn-api/profile is requested
        THEN 302 redirect to openvpn://import-profile/… URL
        """
        _login(page)

        resp = page.request.get(PROFILE_URL, max_redirects=0)
        assert resp.status == 302, (
            f"Expected 302 redirect, got {resp.status}: {resp.text()[:200]}"
        )
        location = resp.headers.get("location", "")
        assert location.startswith("openvpn://import-profile/"), (
            f"Expected openvpn://import-profile/… redirect, got: {location}"
        )

    def test_get_authenticated_openvpn_url_contains_download_endpoint(self, page: Page):
        """
        GIVEN a user authenticated via OIDC
        WHEN GET /openvpn-api/profile is requested
        THEN the openvpn:// URL encodes a /download/<uuid> path-segment URL
        """
        _login(page)

        resp = page.request.get(PROFILE_URL, max_redirects=0)
        location = resp.headers.get("location", "")
        # Format: openvpn://import-profile/https://<host>/download/<uuid>
        # Path-segment form avoids macOS URL-scheme handler stripping query strings.
        assert "/download/" in location, f"Expected /download/ endpoint in URL: {location}"
        # Extract the last path segment and verify it looks like a UUID
        token_part = location.rstrip("/").split("/download/")[-1]
        assert len(token_part) == 36 and token_part.count("-") == 4, (
            f"Token in URL does not look like a UUID: {token_part!r}"
        )

    def test_get_authenticated_openvpn_url_contains_no_pii(self, page: Page):
        """
        GIVEN a user authenticated via OIDC
        WHEN GET /openvpn-api/profile is requested
        THEN the openvpn:// URL contains only the token UUID (no email / user sub)
        """
        _login(page)

        resp = page.request.get(PROFILE_URL, max_redirects=0)
        location = resp.headers.get("location", "")

        assert "@" not in location, f"Email address leaked into openvpn:// URL: {location}"
        # Token is in path-segment form: /download/<uuid>
        if "/download/" in location:
            token_part = location.rstrip("/").split("/download/")[-1]
            assert len(token_part) == 36 and token_part.count("-") == 4, (
                f"Token in URL does not look like a UUID: {token_part!r}"
            )

    def test_get_authenticated_with_device_params_still_redirects(self, page: Page):
        """
        GIVEN an authenticated user
        WHEN GET /openvpn-api/profile includes OpenVPN Connect device params
        THEN still receives the openvpn:// redirect (device params are audit-only)
        """
        _login(page)

        resp = page.request.get(
            PROFILE_URL,
            params={
                "deviceID": "e2e-test-device-001",
                "deviceModel": "E2E Test Phone",
                "deviceOS": "TestOS 16",
                "appVersion": "3.5.0",
            },
            max_redirects=0,
        )
        assert resp.status == 302
        location = resp.headers.get("location", "")
        assert location.startswith("openvpn://import-profile/"), (
            f"Expected openvpn:// redirect even with device params, got: {location}"
        )


# ---------------------------------------------------------------------------
# Full WEB_AUTH flow (login → download → freshness check)
# ---------------------------------------------------------------------------

class TestWebAuthFullFlow:
    """Complete WEB_AUTH flow: auth → download → VPN-Session-Token freshness."""

    def test_full_flow_produces_vpn_session_token(self, page: Page):
        """
        GIVEN a user authenticated via OIDC
        WHEN the full WEB_AUTH flow runs (GET profile → download)
        THEN /download returns a VPN-Session-Token response header
        """
        _login(page)

        # GET /openvpn-api/profile → 302 openvpn://import-profile/<download_url>
        resp = page.request.get(PROFILE_URL, max_redirects=0)
        assert resp.status == 302
        openvpn_url = resp.headers.get("location", "")
        assert openvpn_url.startswith("openvpn://import-profile/"), (
            f"Expected openvpn:// redirect, got: {openvpn_url}"
        )

        # Extract the inner https:// download URL
        download_url = openvpn_url.replace("openvpn://import-profile/", "", 1)
        assert download_url.startswith("http"), (
            f"Inner download URL should be http(s), got: {download_url}"
        )

        # Fetch the .ovpn profile — page.request follows redirects and carries cookies
        download_resp = page.request.get(download_url)
        assert download_resp.status == 200, (
            f"Download failed: {download_resp.status} {download_resp.text()[:200]}"
        )

        # VPN-Session-Token must be in the download response
        session_token = download_resp.headers.get("vpn-session-token", "")
        assert session_token, "Download response must include a non-empty VPN-Session-Token"
        assert len(session_token) == 36 and session_token.count("-") == 4, (
            f"VPN-Session-Token should be a UUID, got: {session_token!r}"
        )

    def test_full_flow_session_token_gives_fresh_head_response(self, page: Page):
        """
        GIVEN a successful profile download that produced a VPN-Session-Token
        WHEN HEAD /openvpn-api/profile is sent with that token
        THEN Ovpn-WebAuth header is absent (profile is fresh)
        """
        _login(page)

        resp = page.request.get(PROFILE_URL, max_redirects=0)
        assert resp.status == 302
        openvpn_url = resp.headers.get("location", "")
        download_url = openvpn_url.replace("openvpn://import-profile/", "", 1)

        # Download the profile — marks token as collected + stores cert_expiry
        download_resp = page.request.get(download_url)
        assert download_resp.status == 200
        session_token = download_resp.headers.get("vpn-session-token", "")
        assert session_token, "Must have received a VPN-Session-Token to test freshness"

        # HEAD with the VPN-Session-Token → Ovpn-WebAuth must be absent
        head_resp = _requests_session().head(
            PROFILE_URL, headers={"VPN-Session-Token": session_token}
        )
        assert head_resp.status_code == 200
        assert "Ovpn-WebAuth" not in head_resp.headers, (
            f"Ovpn-WebAuth should be absent for a fresh profile, "
            f"but got: {head_resp.headers.get('Ovpn-WebAuth')}"
        )

    def test_full_flow_download_returns_valid_ovpn_content(self, page: Page):
        """
        GIVEN a successful WEB_AUTH flow
        WHEN the .ovpn profile is downloaded
        THEN it contains a valid OpenVPN client configuration
        """
        _login(page)

        resp = page.request.get(PROFILE_URL, max_redirects=0)
        openvpn_url = resp.headers.get("location", "")
        download_url = openvpn_url.replace("openvpn://import-profile/", "", 1)

        download_resp = page.request.get(download_url)
        assert download_resp.status == 200

        content = download_resp.text()
        assert "client" in content, "Profile must contain 'client' directive"
        assert "<ca>" in content, "Profile must contain <ca> block"
        assert "<cert>" in content, "Profile must contain <cert> block"
        assert "<key>" in content, "Profile must contain <key> block"
        assert "-----BEGIN CERTIFICATE-----" in content
        assert "-----END CERTIFICATE-----" in content

    def test_full_flow_download_token_is_single_use(self, page: Page):
        """
        GIVEN a one-time download token obtained via WEB_AUTH
        WHEN the /download endpoint is called a second time with the same token
        THEN 410 Gone (token already used)
        """
        _login(page)

        resp = page.request.get(PROFILE_URL, max_redirects=0)
        openvpn_url = resp.headers.get("location", "")
        download_url = openvpn_url.replace("openvpn://import-profile/", "", 1)

        # First download — should succeed
        first = page.request.get(download_url)
        assert first.status == 200

        # Second download with same token — must be rejected
        second = page.request.get(download_url)
        assert second.status == 410, (
            f"Second use of the same token should return 410, got {second.status}"
        )


# ---------------------------------------------------------------------------
# Security / unhappy paths
# ---------------------------------------------------------------------------

class TestWebAuthSecurity:
    """Security and unhappy-path tests (OWASP API Top 10 lens)."""

    def test_xss_in_device_params_does_not_appear_in_redirect(self):
        """
        GIVEN XSS payload in OpenVPN Connect device params
        WHEN unauthenticated GET /openvpn-api/profile is requested
        THEN the redirect response body does not echo the payload
        """
        xss_payload = "<script>alert('xss')</script>"
        resp = _requests_session().get(
            PROFILE_URL,
            params={"deviceID": xss_payload, "deviceModel": xss_payload},
            allow_redirects=False,
        )
        assert resp.status_code == 302
        body = resp.text
        assert xss_payload not in body, (
            "XSS payload must not appear in the redirect response body"
        )
        assert "<script>" not in body

    def test_download_without_token_returns_400(self):
        """
        GIVEN a direct GET /download with no token
        WHEN the request is made
        THEN 400 Bad Request
        """
        resp = _requests_session().get(f"{BASE_URL}/download")
        assert resp.status_code == 400

    def test_download_with_invalid_token_returns_400(self):
        """
        GIVEN a direct GET /download with a random UUID token
        WHEN the request is made
        THEN 400 Bad Request (token not found)
        """
        resp = _requests_session().get(
            f"{BASE_URL}/download", params={"token": str(uuid.uuid4())}
        )
        assert resp.status_code == 400

    def test_download_with_sql_injection_token_returns_400(self):
        """
        GIVEN a GET /download with a SQL injection attempt as token
        WHEN the request is made
        THEN 400 Bad Request (not 500, no DB error leakage)
        """
        resp = _requests_session().get(
            f"{BASE_URL}/download",
            params={"token": "' OR '1'='1"},
        )
        assert resp.status_code == 400, (
            f"SQL injection in token should return 400, not {resp.status_code}"
        )
        assert "traceback" not in resp.text.lower()
        assert "exception" not in resp.text.lower()

    def test_head_does_not_expose_server_version(self):
        """
        GIVEN a HEAD /openvpn-api/profile request
        WHEN response headers are inspected
        THEN Server header does not reveal detailed version information
        """
        import re
        resp = _requests_session().head(PROFILE_URL)
        server_header = resp.headers.get("Server", "")
        assert not re.search(r"Werkzeug/\d", server_header), (
            f"Server header leaks Werkzeug version: {server_header}"
        )

    def test_get_unauthenticated_no_csrf_token_in_redirect(self):
        """
        GIVEN an unauthenticated GET to /openvpn-api/profile
        WHEN the redirect response is inspected
        THEN no sensitive tokens (CSRF, session) are present in the redirect URL
        """
        resp = _requests_session().get(PROFILE_URL, allow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers.get("Location", "")
        assert "csrf_token" not in location.lower()
        assert "session=" not in location.lower()

    def test_post_to_profile_endpoint_not_allowed(self):
        """
        GIVEN a POST request to /openvpn-api/profile
        WHEN the request is made
        THEN 405 Method Not Allowed (HEAD and GET only)
        """
        resp = _requests_session().post(PROFILE_URL)
        assert resp.status_code == 405, (
            f"POST to /openvpn-api/profile should be 405, got {resp.status_code}"
        )

    def test_put_to_profile_endpoint_not_allowed(self):
        """
        GIVEN a PUT request to /openvpn-api/profile
        WHEN the request is made
        THEN 405 Method Not Allowed
        """
        resp = _requests_session().put(PROFILE_URL)
        assert resp.status_code == 405

    def test_delete_to_profile_endpoint_not_allowed(self):
        """
        GIVEN a DELETE request to /openvpn-api/profile
        WHEN the request is made
        THEN 405 Method Not Allowed
        """
        resp = _requests_session().delete(PROFILE_URL)
        assert resp.status_code == 405
