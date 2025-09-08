# OpenVPN Manager Test Suite

This directory contains comprehensive tests for the OpenVPN Manager authentication system.

## Test Structure

```
tests/
├── unit/                    # Unit tests for individual components
├── integration/             # Integration tests for service interactions  
├── functional/              # End-to-end browser tests with Playwright
├── test_frontend_integration.py  # Existing integration tests
├── test_psk_generation.py   # Existing CLI tests
└── tiny-oidc/              # Mock OIDC provider for testing
```

## Available Test Commands

### Individual Test Suites

- `make test-unit` - Run unit tests for OIDC authentication
- `make test-integration` - Run integration tests for OIDC flows
- `make test-functional` - Run functional tests with Playwright
- `make test-nonce` - Run specific nonce validation tests
- `make test-auth-full` - Run complete authentication test suite

### Existing Test Commands

- `make integration-test` - Run full integration tests (requires docker-compose)
- `make integration-test-quick` - Run integration tests on already running services
- `make playwright-test` - Run Playwright frontend tests (CI/CD)
- `make cli-test` - Run CLI integration tests

## Test Setup

```bash
make integration-setup
```

This will:
- Install test dependencies (pytest, playwright, requests, etc.)
- Install Playwright browsers
- Set up the test environment

## Running Tests

1. **Start the services:**
   ```bash
   cd tests
   docker-compose up -d
   ```

2. **Run specific test suites:**
   ```bash
   make test-unit                # Unit tests
   make test-integration        # Integration tests  
   make test-functional         # Browser tests
   make test-auth-full         # All authentication tests
   ```

## Authentication Test Coverage

### ✅ Fixed Issues

1. **Nonce Handling** - Fixed `MissingClaimError: missing_claim: Missing 'nonce' claim`
   - Modified tiny-oidc to capture and store nonce parameter
   - Updated Authorization model to include nonce field
   - Modified token generation to include nonce in ID tokens

2. **State Parameter Validation** - Ensured CSRF protection works correctly
   - Verified state parameter preservation through auth flow
   - Confirmed state validation in callback processing

### 🧪 Test Coverage

- **Unit Tests**: Validate nonce inclusion in ID tokens
- **Integration Tests**: Test complete OIDC flows with various scenarios
- **Functional Tests**: Browser-based authentication with real user interactions

### 🔍 Test Scenarios

The functional tests cover:
- Unauthenticated user redirection to OIDC
- Complete authentication flow with admin user
- User display name verification after authentication
- Authentication with different user types (admin, IT, accounts)
- Session persistence across page reloads
- Logout functionality
- Protected route access control

## Known Limitations

1. **Network Configuration**: In the current setup, there's a hostname mismatch between internal Docker networking (`tiny-oidc:8000`) and external browser access (`localhost:8000`). This is expected in a test environment and will be resolved in production with a proper public OIDC provider.

2. **Authorization Code Expiry**: The tiny-oidc server has short authorization code expiry times, which can cause timing issues in some tests.

## Production Deployment

In production, the tiny-oidc service will be replaced with a real OIDC provider (Okta, Keycloak, etc.) which will have:
- Consistent public hostname
- Proper certificate management
- Standard OIDC compliance
- Configurable token expiry times

The authentication fixes implemented here (particularly nonce handling) ensure compatibility with all standard OIDC providers.