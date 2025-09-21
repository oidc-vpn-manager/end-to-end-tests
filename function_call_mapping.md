# OpenVPN Manager - Function Call Mapping

## Overview

This document provides a comprehensive mapping of function calls and dependencies across the OpenVPN Manager codebase. It analyzes call chains from entry points (Flask routes, CLI commands) to leaf functions, helping understand code flow and dependencies.

## Analysis Methodology

- **Static Analysis**: Examined import statements and function definitions
- **Route Mapping**: Traced Flask routes to their function dependencies
- **CLI Mapping**: Analyzed command-line tools and their function chains
- **Cross-Service Calls**: Documented inter-service communication patterns

## Frontend Service Function Mapping

### Flask Routes → Function Chains

#### **Root Routes (`/`)**
```
@bp.route('/')
└── index()
    ├── current_user.is_authenticated (OIDC)
    ├── query_certtransparency_service()
    ├── render_template()
    └── flash() / redirect()

@bp.route('/bounce-to-admin')
└── bounce_to_admin()
    ├── environment.get_admin_url_base()
    └── redirect()

@bp.route('/bounce-to-user')
└── bounce_to_user()
    ├── environment.get_user_url_base()
    └── redirect()
```

#### **Authentication Routes (`/auth/*`)**
```
@bp.route('/auth/login')
└── login()
    ├── request.args.get()
    ├── oidc.client_secrets_at()
    ├── oidc.auth_redirect()
    └── session[]

@bp.route('/auth/callback')
└── callback()
    ├── oidc.get_access_token()
    ├── oidc.get_userinfo()
    ├── query_certtransparency_service()
    ├── DownloadToken.create()
    ├── db.session.commit()
    └── redirect()

@bp.route('/auth/logout')
└── logout()
    ├── session.clear()
    ├── oidc.logout()
    └── redirect()
```

#### **API v1 Routes (`/api/v1/*`)**
```
@bp.route('/api/v1/server/bundle')
└── server_bundle(psk_object)
    ├── @admin_service_only_api
    ├── @psk_required
    ├── @psk_type_required('server')
    ├── psk_object.record_usage()
    ├── generate_key_and_csr()
    ├── request_signed_certificate()
    ├── CertificateRequest.create_from_request()
    ├── process_tls_crypt_key()
    └── tarfile.open()

@bp.route('/api/v1/computer/bundle')
└── computer_bundle(psk_object)
    ├── @admin_service_only_api
    ├── @psk_required
    ├── @psk_type_required('computer')
    ├── psk_object.record_usage()
    ├── generate_key_and_csr()
    ├── request_signed_certificate()
    ├── CertificateRequest.create_from_request()
    ├── find_best_template_match()
    ├── render_config_template()
    └── Response()
```

#### **Admin Routes (`/admin/*`)**
```
@bp.route('/admin/psk')
└── list_psks()
    ├── @admin_required
    ├── PreSharedKey.query.all()
    └── render_template()

@bp.route('/admin/psk/new')
└── new_psk()
    ├── @admin_required
    ├── NewPskForm()
    ├── PreSharedKey()
    ├── db.session.add()
    ├── db.session.commit()
    └── flash()

@bp.route('/admin/certificates')
└── list_certificates()
    ├── @admin_required
    ├── query_certtransparency_service()
    ├── parse_certificate_list()
    └── render_template()

@bp.route('/admin/certificates/<fingerprint>/revoke')
└── admin_revoke_certificate(fingerprint)
    ├── @admin_required
    ├── request_certificate_revocation()
    ├── flash()
    └── redirect()
```

#### **Profile Routes (`/profile/*`)**
```
@bp.route('/profile/certificates')
└── list_user_certificates()
    ├── @login_required
    ├── query_certtransparency_service()
    ├── parse_certificate_list()
    └── render_template()

@bp.route('/profile/certificates/<fingerprint>/revoke')
└── revoke_user_certificate(fingerprint)
    ├── @login_required
    ├── request_certificate_revocation()
    ├── flash()
    └── redirect()
```

#### **Download Routes (`/download`)**
```
@bp.route('/download')
└── download_profile()
    ├── DownloadToken.query.filter_by()
    ├── token.is_valid()
    ├── generate_key_and_csr()
    ├── request_signed_certificate()
    ├── find_best_template_match()
    ├── render_config_template()
    ├── CertificateRequest.create_from_request()
    ├── db.session.delete()
    └── Response()
```

### Utility Function Dependencies

#### **Certificate Management**
```
request_signed_certificate()
├── current_app.config.get()
├── requests.post()
├── response.raise_for_status()
└── response.json()

generate_key_and_csr()
├── rsa.generate_private_key()
├── x509.CertificateSigningRequestBuilder()
├── x509.NameOID.*
└── csr.sign()

process_tls_crypt_key()
├── base64.b64decode()
├── hashlib.sha256()
└── base64.b64encode()
```

#### **Template Rendering**
```
find_best_template_match()
├── current_app.config.get()
├── os.listdir()
├── re.match()
└── open()

render_config_template()
├── jinja2.Environment()
├── template.render()
└── string processing
```

#### **Decorators**
```
@admin_required
├── current_user.is_authenticated
├── session.get()
├── check_group_membership()
└── abort(403)

@psk_required
├── request.args.get()
├── PreSharedKey.query.filter_by()
├── psk.verify_key()
├── psk.is_valid()
└── abort(401/403)
```

## Signing Service Function Mapping

### Flask Routes → Function Chains

#### **API v1 Routes (`/api/v1/*`)**
```
@bp.route('/api/v1/sign-csr')
└── sign_certificate_request()
    ├── @frontend_api_secret_required
    ├── request.get_json()
    ├── x509.load_pem_x509_csr()
    ├── load_intermediate_ca()
    ├── sign_csr()
    ├── log_certificate_to_ct()
    └── jsonify()

@bp.route('/api/v1/generate-crl')
└── generate_crl()
    ├── @frontend_api_secret_required
    ├── CRLGenerator()
    ├── crl_generator.generate_crl()
    └── jsonify()

@bp.route('/api/v1/revoke-certificate')
└── revoke_certificate()
    ├── @frontend_api_secret_required
    ├── get_ct_client()
    ├── ct_client.log_certificate_revocation()
    └── jsonify()

@bp.route('/api/v1/bulk-revoke-user-certificates')
└── bulk_revoke_user_certificates()
    ├── @frontend_api_secret_required
    ├── get_ct_client()
    ├── ct_client.get_user_certificates()
    ├── ct_client.log_certificate_revocation() (loop)
    └── jsonify()
```

### Core Utility Functions

#### **Certificate Authority Operations**
```
sign_csr()
├── datetime.now()
├── timedelta()
├── x509.CertificateBuilder()
├── x509.random_serial_number()
├── determine_signing_algorithm()
└── builder.sign()

load_intermediate_ca()
├── loadConfigValueFromFileOrEnvironment()
├── secure_key_context()
├── x509.load_pem_x509_certificate()
├── serialization.load_pem_private_key()
└── certificate validation
```

#### **Certificate Transparency Client**
```
log_certificate_to_ct()
├── get_ct_client()
├── ct_client.log_certificate()
└── error handling

get_ct_client()
├── CTLogClient()
├── loadConfigValueFromFileOrEnvironment()
└── client configuration

CTLogClient.log_certificate()
├── requests.post()
├── json payload construction
├── response.raise_for_status()
└── response.json()
```

#### **CRL Generation**
```
CRLGenerator.generate_crl()
├── get_ct_client()
├── ct_client.get_revoked_certificates()
├── x509.CertificateRevocationListBuilder()
├── x509.RevokedCertificateBuilder() (loop)
└── crl_builder.sign()
```

#### **Security & Memory Management**
```
secure_key_context()
├── key_loader_func()
├── SecureKeyManager()
├── manager.load_key()
├── yield key
└── manager.clear()

SecureKeyManager.clear()
├── secure_clear_variable()
├── secure_zero_memory()
└── gc.collect()
```

## Certificate Transparency Service Function Mapping

### Flask Routes → Function Chains

#### **API Routes (`/api/*`)**
```
@bp.route('/api/certificates')
└── list_certificates()
    ├── @certtransparency_api_secret_required
    ├── request.args validation
    ├── CertificateLog.query filtering
    ├── pagination.items
    └── jsonify()

@bp.route('/api/log-certificate')
└── log_certificate()
    ├── @certtransparency_api_secret_required
    ├── request.get_json()
    ├── certificate validation
    ├── geoip.lookup()
    ├── CertificateLog()
    ├── db.session.add()
    └── jsonify()
```

### Utility Functions

#### **Certificate Validation**
```
validate_certificate_data()
├── base64.b64decode()
├── x509.load_pem_x509_certificate()
├── certificate.subject parsing
├── certificate.not_valid_after
└── validation checks

extract_certificate_metadata()
├── certificate.subject
├── certificate.issuer
├── certificate.serial_number
├── certificate.not_valid_before/after
└── metadata dict construction
```

#### **GeoIP Lookup**
```
geoip.lookup()
├── maxminddb.open_database()
├── database.get()
├── country/city extraction
└── location dict
```

## Tools Function Mapping

### CLI Tool Entry Points

#### **get_openvpn_profile.py**
```
@click.command()
└── main()
    ├── Config() initialization
    ├── config.server_url validation
    ├── config.output_path.exists() check
    ├── requests.get() health check
    ├── get_profile_with_oidc()
    └── file writing

get_profile_with_oidc()
├── _find_free_port()
├── HTTPServer() setup
├── webbrowser.open()
├── token waiting loop
├── requests.get() profile download
└── response.content
```

#### **get_openvpn_server_config.py**
```
@click.command()
└── main()
    ├── Config() initialization
    ├── get_profile_with_psk()
    ├── extract_server_files()
    └── file extraction

get_profile_with_psk()
├── requests.post()
├── Authorization header
├── response.raise_for_status()
└── response.content

extract_server_files()
├── tarfile.open()
├── tar.getmembers()
├── file classification
├── target path validation
└── tar.extractfile() + writing
```

#### **get_openvpn_computer_config.py**
```
@click.command()
└── main()
    ├── Config() initialization
    ├── get_computer_profile_with_psk()
    └── file writing

get_computer_profile_with_psk()
├── requests.post()
├── /api/v1/computer/bundle endpoint
├── Authorization header
└── response.content
```

#### **generate_pki.py**
```
@click.group()
└── cli()

@click.command()
└── generate_root()
    ├── validate_entropy_for_key_generation()
    ├── prompt_for_subject_fields()
    ├── create_private_key() (root)
    ├── create_private_key() (intermediate)
    ├── certificate generation
    └── file writing

create_private_key()
├── validate_entropy_for_key_generation()
├── key type selection (ed25519/rsa)
├── private key generation
├── passphrase encryption
└── PEM serialization
```

## Cross-Service Communication Patterns

### Frontend → Signing Service
```
Frontend API calls:
├── request_signed_certificate()
│   └── POST /api/v1/sign-csr
├── request_certificate_revocation()
│   └── POST /api/v1/revoke-certificate
└── request_bulk_certificate_revocation()
    └── POST /api/v1/bulk-revoke-user-certificates

Authentication: Bearer token (shared secret)
Error handling: SigningServiceError exceptions
Timeout: 5-30 seconds depending on operation
```

### Frontend → Certificate Transparency Service
```
Frontend API calls:
├── query_certtransparency_service()
│   └── GET /api/certificates
└── (Signing service logs certificates automatically)

Authentication: Bearer token (shared secret)
Error handling: HTTP status code checks
Pagination: limit/offset parameters
```

### Signing Service → Certificate Transparency Service
```
Signing service API calls:
├── log_certificate_to_ct()
│   └── POST /api/log-certificate
├── get_revoked_certificates()
│   └── GET /api/certificates?revoked=true
└── log_certificate_revocation()
    └── POST /api/log-revocation

Authentication: Bearer token (shared secret)
Error handling: CTLogError exceptions
Retry logic: Exponential backoff
```

### CLI Tools → Frontend Service
```
CLI tool API calls:
├── Health checks:
│   └── GET /health
├── OIDC authentication:
│   └── GET /auth/login?cli_port=<port>
├── Profile downloads:
│   └── GET /download?token=<token>
└── Server/computer bundles:
    ├── POST /api/v1/server/bundle (PSK auth)
    └── POST /api/v1/computer/bundle (PSK auth)

Authentication: OIDC tokens or PSK headers
Error handling: HTTP status codes and exceptions
Timeouts: 5-30 seconds per request
```

## Function Dependency Levels

### Level 1: Entry Points
- Flask routes (`@bp.route`)
- CLI commands (`@click.command`)
- Class constructors (`__init__`)

### Level 2: Business Logic
- Authentication decorators
- Request validation functions
- Core business operations

### Level 3: Service Integration
- Inter-service API calls
- Database operations
- External service communication

### Level 4: Utility Functions
- Cryptographic operations
- Template rendering
- Configuration management
- Logging and tracing

### Level 5: System/Library Calls
- File I/O operations
- Network requests
- Database queries
- Cryptography library calls

## Key Architectural Patterns

### **Decorator Pattern Usage**
- Authentication: `@login_required`, `@admin_required`
- API Security: `@psk_required`, `@frontend_api_secret_required`
- Service Boundaries: `@admin_service_only_api`

### **Factory Pattern Usage**
- Configuration: `Config()` classes in CLI tools
- Clients: `get_ct_client()`, `get_fernet()`
- Database models: `CertificateRequest.create_from_request()`

### **Template Method Pattern**
- Profile generation: `generate_key_and_csr()` → `request_signed_certificate()` → `render_config_template()`
- Certificate revocation: validation → service call → database update

### **Observer Pattern**
- Certificate transparency logging (automatic on certificate generation)
- Request tracking and audit logging
- Usage statistics collection

This function call mapping provides a comprehensive view of code dependencies and execution flow across the OpenVPN Manager system, enabling better understanding of system architecture and facilitating maintenance and debugging efforts.