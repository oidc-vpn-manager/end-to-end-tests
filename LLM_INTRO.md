# OpenVPN Manager

This file provides guidance to any LLM tooling when working with code in this repository.

**CRITICAL: Before starting, please read `LLM_RULES.md` and confirm you've read the rules.**

## Project Overview

OpenVPN Manager is an enterprise certificate management system with three core microservices:
- **Frontend Service** (`services/frontend/`) - Web UI and API gateway (ports 8450/8540/8600)
- **Signing Service** (`services/signing/`) - Certificate signing operations (port 8500) 
- **Certificate Transparency Service** (`services/certtransparency/`) - Audit logging (port 8800)

Supporting tools:
- **PKI Tool** (`tools/pki_tool/`) - Offline CA generation
- **Get OpenVPN Config** (`tools/get_openvpn_config/`) - Client CLI tool

## Component-Specific Documentation

For detailed guidance when working with individual services and tools, refer to their component-specific LLM_INTRO.md files:

### Services
- **Frontend Service**: `services/frontend/LLM_INTRO.md` - Web UI, API gateway, authentication, database models
- **Signing Service**: `services/signing/LLM_INTRO.md` - Certificate signing, cryptographic operations, PKI management
- **Certificate Transparency Service**: `services/certtransparency/LLM_INTRO.md` - Audit logging, certificate transparency, compliance

### Tools
- **PKI Tool**: `tools/pki_tool/LLM_INTRO.md` - CA generation, key management, cryptographic standards
- **Get OpenVPN Config**: `tools/get_openvpn_config/LLM_INTRO.md` - Client tool, OIDC/PSK authentication, configuration retrieval

These component-specific files provide granular details including architecture, dependencies, development workflows, API documentation, configuration, security features, testing requirements, and troubleshooting guidance for each individual component.

## Documentation Analysis Resources

The following comprehensive analysis documents are available for understanding codebase architecture and maintenance:

- **`docstring_audit_report.md`** - Comprehensive docstring quality analysis and improvement recommendations
- **`function_call_mapping.md`** - Complete mapping of function dependencies across all services
- **`route_to_function_chains.md`** - Detailed execution chains from Flask routes/CLI commands to leaf functions
- **`unused_functions_analysis.md`** - Technical debt analysis identifying potentially unused code
- **`docstring_improvements_summary.md`** - Summary of all documentation enhancements made

These documents provide:
- **Route Tracing**: Complete visibility from API endpoints to cryptographic operations
- **Architecture Insights**: Performance hotspots and cross-cutting security concerns
- **Code Health**: 96%+ function utilization rate indicating excellent code discipline
- **Security Documentation**: Timing attack prevention and injection countermeasures

## Development Commands

### Testing
- `make test` - Full test suite (unit, integration, E2E)
- `make just_test_without_e2e` - Unit and integration tests only
- `make just_test_e2e` - End-to-end tests with Playwright
- `make test_certtransparency` - Certificate transparency service tests
- `make test_frontend` - Frontend service tests  
- `make test_signing` - Signing service tests
- `make test_get_openvpn_config` - CLI tool tests
- `make test_pki_tool` - PKI tool tests

### Docker Operations
- `make rebuild_docker` - Clean rebuild all containers (removes volumes)
- `make start_docker` - Start services with docker-compose
- `make check_services_ready` - Pre-flight readiness tests

### Database Operations
- `make createmigrations` - Create Flask-Migrate database migrations

### Development Setup
```bash
cd tests
docker compose up -d
make test_setup  # Install playwright, create result dirs
```

## Architecture Notes

### Microservice Communication
- Services use shared API keys for authentication
- Frontend orchestrates between signing and CT services
- All certificate operations are logged to CT service for audit trail

### Service Separation Patterns
Frontend supports three deployment modes:
- **Combined**: All functionality in one service (default)
- **User Service**: `ADMIN_URL_BASE` set, serves user routes only
- **Admin Service**: `USER_URL_BASE` set, serves admin routes only

### Database Schema
- Frontend: PostgreSQL with users, PSKs, download tokens
- CT Service: PostgreSQL with certificate records and metadata
- Signing: File-based CA key storage with encrypted private keys

### Security Architecture
- OIDC authentication with group-based RBAC
- Service isolation with API authentication
- Certificate Transparency logging for all operations
- Encrypted CA private keys with passphrase protection

## Testing Standards

**100% test coverage requirement** - All code must pass:
- Unit tests for individual functions
- Integration tests for service interactions
- E2E tests with Playwright for web UI
- Security tests covering OWASP Top 10 vulnerabilities

Tests must achieve 100% pass rate with no errors, warnings, or skipped tests. Test results stored in `suite_test_results/` directory.

### Security Testing
- **44 comprehensive security tests** covering red team, blue team, and bug bounty perspectives
- **Real vulnerability discovery and remediation** during development
- **Timing attack prevention** with constant-time comparison algorithms
- **Input validation coverage** including Unicode, oversized payloads, and malformed data

## Configuration Templates

### User Profiles
Templates in format: `0000.GroupName.ovpn` where digits indicate priority
Uses Jinja2 templating with OIDC group matching

### Server Bundles  
Templates in format: `Selection.0000.ovpn` grouped by prefix
Generated as TAR archives with certificates and configuration

## API Design

All APIs versioned at `/api/vX/` path with Swagger documentation at `/api/` index.
Key endpoints:
- `POST /api/v1/profile` - User certificate generation
- `GET /api/v1/server-bundle/{psk}` - Server bundle retrieval  
- `GET /api/v1/certificates` - CT log queries

## Development Principles

- UTC timezone and ISO 8601 timestamps throughout
- Security-first design following OWASP guidelines
- Append-only CT logging with no data modification allowed
- Microservice architecture with clear service boundaries
- Complete audit trail for all certificate operations
- Commits must NEVER mention the LLM tooling being used
- All functions require comprehensive docstrings with examples, security considerations, and parameter documentation
- Maintain complete route-to-function execution chains for debugging in docs/function_call_mapping.md
