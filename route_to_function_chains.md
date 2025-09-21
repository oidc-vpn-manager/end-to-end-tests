# OpenVPN Manager - Route to Function Chains Mapping

## Overview

This document provides a detailed mapping from Flask routes and CLI commands to all functions they invoke, creating complete call chains from entry points to leaf functions. This is essential for understanding code flow, debugging, and impact analysis.

## Frontend Service Route Chains

### **Public/Landing Routes**

#### `GET /` (Root Index)
```
Route: @bp.route('/', methods=['GET', 'POST'])
Handler: index()
│
├── Authentication Check
│   ├── current_user.is_authenticated (Flask-Login/OIDC)
│   └── session.get('userinfo') (Flask Session)
│
├── Certificate Transparency Query
│   ├── query_certtransparency_service()
│   │   ├── current_app.config.get('CERTTRANSPARENCY_SERVICE_URL')
│   │   ├── current_app.config.get('CERTTRANSPARENCY_SERVICE_API_SECRET')
│   │   ├── requests.get()
│   │   ├── response.raise_for_status()
│   │   └── response.json()
│   │
│   └── parse_certificate_list()
│       ├── json data processing
│       ├── certificate.get() operations
│       └── list comprehensions
│
├── Template Rendering
│   ├── render_template()
│   ├── template variable preparation
│   └── Jinja2 template processing
│
└── Error Handling
    ├── flash() for error messages
    ├── current_app.logger.error()
    └── redirect() for fallbacks
```

#### `GET /bounce-to-admin`
```
Route: @bp.route('/bounce-to-admin')
Handler: bounce_to_admin()
│
├── URL Configuration
│   ├── environment.get_admin_url_base()
│   │   ├── current_app.config.get('ADMIN_URL_BASE')
│   │   └── os.environ.get() fallback
│   │
│   └── URL construction with request.args
│
└── Response
    └── redirect() with constructed URL
```

#### `GET /bounce-to-user`
```
Route: @bp.route('/bounce-to-user')
Handler: bounce_to_user()
│
├── URL Configuration
│   ├── environment.get_user_url_base()
│   │   ├── current_app.config.get('USER_URL_BASE')
│   │   └── os.environ.get() fallback
│   │
│   └── URL construction with request.args
│
└── Response
    └── redirect() with constructed URL
```

### **Authentication Routes**

#### `GET /auth/login`
```
Route: @bp.route('/auth/login')
Handler: login()
│
├── Parameter Processing
│   ├── request.args.get('cli_port')
│   ├── request.args.get('optionset')
│   ├── request.args.get('redirect_uri')
│   └── session storage operations
│
├── OIDC Configuration
│   ├── oidc.client_secrets_at()
│   │   └── JSON file reading and parsing
│   │
│   └── oidc.auth_redirect()
│       ├── OAuth2 state generation
│       ├── URL parameter encoding
│       └── redirect URL construction
│
└── Error Handling
    ├── current_app.logger.error()
    ├── flash() for user messages
    └── redirect() for fallback pages
```

#### `GET /auth/callback`
```
Route: @bp.route('/auth/callback')
Handler: callback()
│
├── OIDC Token Exchange
│   ├── oidc.get_access_token()
│   │   ├── requests.post() to token endpoint
│   │   ├── authorization code validation
│   │   └── token response processing
│   │
│   └── oidc.get_userinfo()
│       ├── requests.get() to userinfo endpoint
│       ├── Bearer token authentication
│       └── user profile extraction
│
├── User Session Management
│   ├── session['userinfo'] = userinfo
│   ├── session['groups'] = group processing
│   └── session persistence
│
├── Certificate Statistics Query
│   ├── query_certtransparency_service()
│   │   └── [Same as above]
│   │
│   └── user certificate counting
│
├── Download Token Generation
│   ├── DownloadToken.create()
│   │   ├── uuid.uuid4() generation
│   │   ├── datetime.now() + timedelta()
│   │   └── database object creation
│   │
│   ├── db.session.add()
│   └── db.session.commit()
│
└── CLI vs Web Flow Handling
    ├── CLI redirect with token
    └── Web redirect to profile/admin
```

#### `GET /auth/logout`
```
Route: @bp.route('/auth/logout')
Handler: logout()
│
├── Session Cleanup
│   ├── session.clear()
│   └── Flask session invalidation
│
├── OIDC Logout
│   ├── oidc.logout()
│   │   ├── logout URL construction
│   │   └── redirect to OIDC provider
│   │
│   └── Optional logout callback handling
│
└── Final Redirect
    └── redirect() to landing page
```

### **API v1 Routes**

#### `POST /api/v1/server/bundle`
```
Route: @bp.route('/api/v1/server/bundle', methods=['GET', 'POST'])
Decorators: @admin_service_only_api, @psk_required, @psk_type_required('server')
Handler: server_bundle(psk_object)
│
├── Decorator Chain Execution
│   ├── admin_service_only_api()
│   │   ├── environment.is_admin_service_only()
│   │   └── abort(404) if not admin service
│   │
│   ├── psk_required()
│   │   ├── request.args.get('psk') or request.form.get('psk')
│   │   ├── PreSharedKey.query.filter_by().first()
│   │   ├── psk.verify_key() [HMAC constant-time comparison]
│   │   ├── psk.is_valid() [expiration and enabled checks]
│   │   └── abort(401/403) on validation failure
│   │
│   └── psk_type_required('server')
│       ├── psk_object.psk_type comparison
│       └── abort(403) if type mismatch
│
├── Tracing and Usage Recording
│   ├── trace() call with metadata
│   ├── psk_object.record_usage()
│   │   ├── datetime.now(timezone.utc)
│   │   └── use_count increment
│   │
│   ├── db.session.commit()
│   └── database persistence
│
├── Certificate Generation Flow
│   ├── datetime.now(timezone.utc) for timestamp
│   │
│   ├── generate_key_and_csr()
│   │   ├── rsa.generate_private_key() or ec.generate_private_key()
│   │   ├── x509.CertificateSigningRequestBuilder()
│   │   ├── x509.NameOID.COMMON_NAME subject
│   │   ├── csr.public_key() assignment
│   │   └── csr.sign() with private key
│   │
│   ├── CSR PEM Encoding
│   │   ├── serialization.Encoding.PEM
│   │   └── .decode('utf-8')
│   │
│   ├── Client IP Extraction
│   │   ├── request.remote_addr
│   │   ├── request.headers.get('X-Forwarded-For')
│   │   ├── IP parsing and validation
│   │   └── forwarded IP selection
│   │
│   └── request_signed_certificate()
│       ├── current_app.config.get('SIGNING_SERVICE_URL')
│       ├── current_app.config.get('SIGNING_SERVICE_API_SECRET')
│       ├── endpoint URL construction
│       ├── requests.post() with JSON payload
│       ├── timeout=5 configuration
│       ├── response.raise_for_status()
│       ├── response.json() parsing
│       └── certificate extraction
│
├── Certificate Request Tracking
│   ├── CertificateRequest.create_from_request()
│   │   ├── user_agent_detection.detect_user_agent()
│   │   ├── user_agent_detection.detect_os()
│   │   ├── request metadata extraction
│   │   ├── database model instantiation
│   │   └── field population
│   │
│   ├── cert_request.signing_successful = True
│   ├── db.session.add()
│   └── commit with error handling
│
├── Private Key Processing
│   ├── serialization.Encoding.PEM
│   ├── serialization.PrivateFormat.PKCS8
│   ├── serialization.NoEncryption()
│   └── .decode('utf-8')
│
├── CA Certificate Chain Assembly
│   ├── current_app.config.get('ROOT_CA_CERTIFICATE')
│   ├── current_app.config.get('INTERMEDIATE_CA_CERTIFICATE')
│   ├── string concatenation
│   └── .strip() cleanup
│
├── TLS-Crypt Key Processing
│   ├── current_app.config.get('OPENVPN_TLS_CRYPT_KEY')
│   └── master key extraction
│
├── Server Configuration Template Matching
│   ├── current_app.config.get('SERVER_TEMPLATES_DIR')
│   ├── os.path.exists() validation
│   ├── os.path.basename() sanitization
│   ├── re.match(r'^[a-zA-Z0-9_-]+$') validation
│   ├── os.listdir() directory scanning
│   ├── filename filtering (.ovpn and prefix matching)
│   ├── os.path.join() path construction
│   ├── open() and read() file operations
│   └── configuration collection
│
├── TAR Archive Creation
│   ├── io.BytesIO() buffer creation
│   ├── tarfile.open() with gzip compression
│   │
│   ├── CA Chain Addition
│   │   ├── tarfile.TarInfo('ca-chain.crt')
│   │   ├── size calculation
│   │   ├── io.BytesIO() for content
│   │   └── tar.addfile()
│   │
│   ├── Server Certificate Addition
│   │   ├── tarfile.TarInfo('server.crt')
│   │   └── [similar process]
│   │
│   ├── Server Private Key Addition
│   │   ├── tarfile.TarInfo('server.key')
│   │   └── [similar process]
│   │
│   ├── TLS-Crypt Key Addition (if present)
│   │   ├── tarfile.TarInfo('tls-crypt.key')
│   │   └── [similar process]
│   │
│   └── Server Configuration Files Addition
│       ├── Loop through server_configs
│       ├── tarfile.TarInfo(filename)
│       └── content addition
│
├── Response Generation
│   ├── tar_buffer.seek(0)
│   ├── tar_buffer.getvalue()
│   └── Response() with application/gzip mimetype
│
└── Error Handling
    ├── SigningServiceError exception handling
    │   ├── cert_request.signing_successful = False
    │   ├── cert_request.signing_error_message assignment
    │   ├── db.session.rollback() on failure
    │   └── jsonify(error="Signing service unavailable") 503
    │
    └── General Exception handling
        ├── Similar cert_request error marking
        ├── current_app.logger.error() logging
        └── jsonify(error="An internal error occurred") 500
```

#### `POST /api/v1/computer/bundle`
```
Route: @bp.route('/api/v1/computer/bundle', methods=['GET', 'POST'])
Decorators: @admin_service_only_api, @psk_required, @psk_type_required('computer')
Handler: computer_bundle(psk_object)
│
├── [Decorator Chain - Same as server_bundle]
│
├── [Tracing and Usage Recording - Same as server_bundle]
│
├── Certificate Generation Flow
│   ├── [Similar to server_bundle but with 'computer' prefix]
│   └── certificate_type='client' in signing request
│
├── [Certificate Request Tracking - Similar to server_bundle]
│   └── certificate_type='computer' in tracking
│
├── [Private Key and CA Processing - Same as server_bundle]
│
├── TLS-Crypt Key Processing
│   ├── current_app.config.get('OPENVPN_TLS_CRYPT_KEY')
│   ├── process_tls_crypt_key()
│   │   ├── base64.b64decode() master key
│   │   ├── hashlib.sha256() device-specific hash
│   │   ├── derived key generation
│   │   └── base64.b64encode() device key
│   │
│   └── version detection
│
├── Template Context Preparation
│   ├── base_context dictionary construction
│   │   ├── common_name assignment
│   │   ├── description from PSK
│   │   ├── ca_cert_pem, device_cert_pem, device_key_pem
│   │   ├── tlscrypt_key and version
│   │   ├── userinfo simulation
│   │   └── default template variables
│   │
│   └── template variable alias setup
│
├── Template Selection and Rendering
│   ├── user_group_memberships = [psk_object.template_set]
│   ├── find_best_template_match()
│   │   ├── current_app.config.get('USER_TEMPLATES_DIR')
│   │   ├── os.listdir() template scanning
│   │   ├── template priority parsing (numeric prefix)
│   │   ├── group membership matching
│   │   ├── template selection logic
│   │   └── file reading
│   │
│   ├── render_config_template()
│   │   ├── jinja2.Environment() setup
│   │   ├── jinja2.StrictUndefined for error catching
│   │   ├── template.render() with context
│   │   ├── undefined variable detection
│   │   └── rendered content return
│   │
│   └── current_app.logger.info() success logging
│
├── Single OVPN File Response
│   ├── download_filename construction
│   └── Response() with application/x-openvpn-profile mimetype
│
└── [Error Handling - Same pattern as server_bundle]
```

### **Admin Routes**

#### `GET /admin/psk`
```
Route: @bp.route('/admin/psk')
Decorators: @admin_required
Handler: list_psks()
│
├── Authentication and Authorization
│   ├── admin_required()
│   │   ├── current_user.is_authenticated check
│   │   ├── session.get('userinfo') validation
│   │   ├── session.get('groups') extraction
│   │   ├── admin group membership check
│   │   └── abort(403) if not admin
│   │
│   └── RBAC validation
│
├── Database Query
│   ├── PreSharedKey.query.all()
│   │   ├── SQLAlchemy ORM query construction
│   │   ├── database connection via db.session
│   │   └── result set retrieval
│   │
│   └── query result processing
│
├── Template Rendering
│   ├── render_template('admin/psk_list.html')
│   ├── context variable preparation
│   └── Jinja2 template processing
│
└── Response Generation
    └── HTML response with PSK list
```

#### `POST /admin/psk/new`
```
Route: @bp.route('/admin/psk/new', methods=['GET', 'POST'])
Decorators: @admin_required
Handler: new_psk()
│
├── [Authentication - Same as list_psks]
│
├── Form Processing
│   ├── NewPskForm() instantiation
│   │   ├── WTForms form class
│   │   ├── CSRF token validation
│   │   └── field validation
│   │
│   ├── form.validate_on_submit()
│   │   ├── HTTP method check
│   │   ├── CSRF validation
│   │   ├── field validation rules
│   │   └── validation result
│   │
│   └── form data extraction
│
├── PSK Creation (on valid form)
│   ├── PreSharedKey() instantiation
│   │   ├── form.data field mapping
│   │   ├── SecureModelMixin validation
│   │   ├── mass assignment protection
│   │   ├── uuid.uuid4() key generation
│   │   ├── hashlib.sha256() key hashing
│   │   └── key truncation for display
│   │
│   ├── Database Operations
│   │   ├── db.session.add()
│   │   ├── db.session.commit()
│   │   └── exception handling
│   │
│   ├── Success Feedback
│   │   ├── flash() success message
│   │   └── plaintext_key display
│   │
│   └── redirect() to PSK list
│
├── Form Display (GET or invalid form)
│   ├── render_template('admin/new_psk.html')
│   ├── form object passing
│   └── template rendering
│
└── Error Handling
    ├── Database exception handling
    ├── flash() error messages
    └── error page rendering
```

#### `POST /admin/certificates/<fingerprint>/revoke`
```
Route: @bp.route('/admin/certificates/<fingerprint>/revoke', methods=['POST'])
Decorators: @admin_required
Handler: admin_revoke_certificate(fingerprint)
│
├── [Authentication - Same as other admin routes]
│
├── Input Validation
│   ├── fingerprint parameter extraction
│   ├── request.form.get('reason') validation
│   ├── session.get('userinfo') for revoked_by
│   └── input sanitization
│
├── Certificate Revocation
│   ├── request_certificate_revocation()
│   │   ├── current_app.config.get('SIGNING_SERVICE_URL')
│   │   ├── current_app.config.get('SIGNING_SERVICE_API_SECRET')
│   │   ├── endpoint_url construction
│   │   ├── requests.post() with timeout=10
│   │   ├── JSON payload with fingerprint/reason/revoked_by
│   │   ├── response status code handling (404, 400, 503)
│   │   ├── response.raise_for_status()
│   │   ├── response.json() parsing
│   │   └── success logging
│   │
│   └── error handling and logging
│
├── User Feedback
│   ├── flash() success message
│   └── flash() error message on failure
│
└── Response
    └── redirect() to certificate list
```

### **Profile Routes**

#### `GET /profile/certificates`
```
Route: @bp.route('/profile/certificates')
Decorators: @login_required
Handler: list_user_certificates()
│
├── Authentication
│   ├── login_required()
│   │   ├── current_user.is_authenticated check
│   │   ├── session.get('userinfo') validation
│   │   └── redirect() to login if not authenticated
│   │
│   └── user session validation
│
├── User Certificate Query
│   ├── session.get('userinfo') email extraction
│   ├── query_certtransparency_service()
│   │   ├── [Same CT service query as index]
│   │   └── user email filtering
│   │
│   ├── parse_certificate_list()
│   │   ├── certificate data processing
│   │   ├── status determination (valid/expired/revoked)
│   │   ├── date parsing and formatting
│   │   └── display preparation
│   │
│   └── certificate counting and statistics
│
├── Template Rendering
│   ├── render_template('profile/certificates.html')
│   ├── user certificates context
│   └── template processing
│
└── Error Handling
    ├── CT service unavailability
    ├── parsing errors
    └── fallback rendering
```

#### `POST /profile/certificates/<fingerprint>/revoke`
```
Route: @bp.route('/profile/certificates/<fingerprint>/revoke', methods=['POST'])
Decorators: @login_required
Handler: revoke_user_certificate(fingerprint)
│
├── [Authentication - Same as list_user_certificates]
│
├── Authorization Check
│   ├── session.get('userinfo') email extraction
│   ├── certificate ownership verification
│   └── abort(403) if not owner
│
├── Input Processing
│   ├── fingerprint parameter validation
│   ├── request.form.get('reason') with default
│   └── user email as revoked_by
│
├── [Certificate Revocation - Same as admin_revoke_certificate]
│
├── [User Feedback - Same as admin]
│
└── Response
    └── redirect() to user certificate list
```

### **Download Routes**

#### `GET /download`
```
Route: @bp.route('/download')
Handler: download_profile()
│
├── Token Validation
│   ├── request.args.get('token') extraction
│   ├── DownloadToken.query.filter_by().first()
│   │   ├── SQLAlchemy query construction
│   │   ├── database lookup
│   │   └── token object retrieval
│   │
│   ├── token.is_valid() validation
│   │   ├── expiration check (datetime comparison)
│   │   ├── used status check
│   │   └── validation result
│   │
│   └── abort(404) if invalid
│
├── User Information Extraction
│   ├── token.userinfo JSON parsing
│   ├── user profile data extraction
│   └── group membership processing
│
├── Certificate Generation
│   ├── generate_key_and_csr()
│   │   ├── [Same as API routes]
│   │   └── user-specific common name
│   │
│   ├── Client IP Processing
│   │   ├── [Same as API routes]
│   │   └── geolocation preparation
│   │
│   ├── Rich Metadata Preparation
│   │   ├── user_agent_detection.detect_user_agent()
│   │   │   ├── request.headers.get('User-Agent')
│   │   │   ├── user_agents.parse()
│   │   │   ├── browser/version extraction
│   │   │   └── metadata dictionary
│   │   │
│   │   ├── user_agent_detection.detect_os()
│   │   │   ├── OS family detection
│   │   │   ├── version extraction
│   │   │   └── OS metadata
│   │   │
│   │   ├── template_set from URL parameters
│   │   ├── option processing (TCP/UDP)
│   │   └── request metadata compilation
│   │
│   └── request_signed_certificate()
│       ├── [Same signing service call]
│       └── rich metadata inclusion
│
├── Certificate Request Tracking
│   ├── CertificateRequest.create_from_request()
│   │   ├── [Same as API routes]
│   │   ├── user information inclusion
│   │   ├── template_set tracking
│   │   └── request_source='web'
│   │
│   ├── signing success/failure tracking
│   └── database persistence
│
├── Template Selection and Processing
│   ├── user_group_memberships extraction
│   │   ├── userinfo['groups'] processing
│   │   ├── list normalization
│   │   └── group name extraction
│   │
│   ├── find_best_template_match()
│   │   ├── [Same as computer bundle]
│   │   ├── group-based template matching
│   │   ├── priority-based selection
│   │   └── template content retrieval
│   │
│   └── render_config_template()
│       ├── [Same rendering process]
│       ├── user-specific context
│       ├── certificate embedding
│       └── configuration generation
│
├── Token Cleanup
│   ├── db.session.delete(token)
│   ├── db.session.commit()
│   └── one-time use enforcement
│
├── Response Generation
│   ├── download filename construction
│   ├── Response() with OVPN mimetype
│   └── Content-Disposition header
│
└── Error Handling
    ├── [Same signing service error handling]
    ├── template rendering errors
    ├── database operation errors
    └── fallback error responses
```

## CLI Tool Command Chains

### **get_openvpn_profile.py**

#### Command: `get_openvpn_profile.py [options]`
```
Entry Point: main()
│
├── Configuration Resolution
│   ├── Config() initialization
│   │   ├── Path() object creation for config files
│   │   ├── _load_config_file() for user config
│   │   │   ├── path.is_file() existence check
│   │   │   ├── yaml.safe_load() parsing
│   │   │   └── error handling
│   │   │
│   │   ├── _load_config_file() for system config
│   │   ├── _resolve() for server_url
│   │   │   ├── CLI argument priority
│   │   │   ├── environment variable check
│   │   │   ├── user config lookup
│   │   │   └── system config fallback
│   │   │
│   │   ├── _resolve_output_path()
│   │   │   ├── [Same resolution pattern]
│   │   │   ├── user_downloads_path() fallback
│   │   │   └── Path.home() final fallback
│   │   │
│   │   ├── _resolve_overwrite_flag()
│   │   │   ├── boolean string parsing
│   │   │   └── default false
│   │   │
│   │   └── options processing
│   │
│   └── configuration validation
│
├── Pre-flight Checks
│   ├── config.server_url validation
│   ├── config.output_path.exists() check
│   ├── config.overwrite flag processing
│   └── ClickException on validation failure
│
├── Server Connectivity Test
│   ├── click.echo() progress message
│   ├── requests.get() health endpoint
│   │   ├── f"{config.server_url}/health" URL
│   │   ├── timeout=5 configuration
│   │   └── response.raise_for_status()
│   │
│   └── ClickException on connection failure
│
├── OIDC Authentication Flow
│   ├── click.echo() flow start message
│   ├── get_profile_with_oidc()
│   │   ├── _find_free_port()
│   │   │   ├── socket.socket() creation
│   │   │   ├── s.bind(('', 0)) random port
│   │   │   └── s.getsockname()[1] extraction
│   │   │
│   │   ├── HTTPServer Setup
│   │   │   ├── HTTPServer(('127.0.0.1', port), _CallbackHandler)
│   │   │   ├── server_thread creation
│   │   │   ├── thread.daemon = True
│   │   │   └── thread.start()
│   │   │
│   │   ├── Login URL Construction
│   │   │   ├── f"{config.server_url}/auth/login"
│   │   │   ├── cli_port parameter
│   │   │   ├── optionset parameter
│   │   │   └── URL encoding
│   │   │
│   │   ├── Browser Interaction
│   │   │   ├── output_auth_url processing
│   │   │   ├── webbrowser.open() [if not test mode]
│   │   │   ├── click.echo() to stderr [if test mode]
│   │   │   └── file writing [if file output]
│   │   │
│   │   ├── Token Waiting Loop
│   │   │   ├── timeout = time.time() + 120
│   │   │   ├── while not _RECEIVED_TOKEN loop
│   │   │   ├── time.sleep(1) intervals
│   │   │   ├── timeout check
│   │   │   └── ClickException on timeout
│   │   │
│   │   ├── Token Processing
│   │   │   ├── httpd.shutdown()
│   │   │   ├── token = _RECEIVED_TOKEN.pop(0)
│   │   │   └── token validation
│   │   │
│   │   ├── Profile Download
│   │   │   ├── download_url construction
│   │   │   ├── requests.get() with token
│   │   │   ├── timeout=30 configuration
│   │   │   ├── response.raise_for_status()
│   │   │   └── response.content return
│   │   │
│   │   └── error handling throughout
│   │
│   └── profile_content extraction
│
├── File Writing
│   ├── open() with binary mode
│   ├── f.write(profile_content)
│   └── file closure
│
├── Success Reporting
│   ├── click.secho() success message
│   ├── fg="green" color formatting
│   └── output path display
│
└── Error Handling
    ├── Exception catching
    ├── ClickException re-raising
    └── error message formatting
```

#### OIDC Callback Handler
```
Class: _CallbackHandler(BaseHTTPRequestHandler)
Method: do_GET()
│
├── HTTP Response Setup
│   ├── self.send_response(200)
│   ├── self.send_header() content type
│   ├── self.end_headers()
│   └── HTML response writing
│
├── URL Parameter Processing
│   ├── urlparse(self.path) parsing
│   ├── parse_qs() query extraction
│   └── token parameter extraction
│
├── Token Storage
│   ├── _RECEIVED_TOKEN.append(token)
│   └── inter-thread communication
│
└── Response Completion
    └── browser auto-close script
```

### **get_openvpn_server_config.py**

#### Command: `get_openvpn_server_config.py [options]`
```
Entry Point: main()
│
├── Configuration Resolution
│   ├── Config() initialization
│   │   ├── [Similar to profile tool]
│   │   └── simplified config options
│   │
│   └── server_url validation
│
├── PSK Profile Retrieval
│   ├── get_profile_with_psk()
│   │   ├── endpoint_url = f"{config.server_url}/api/v1/server/bundle"
│   │   ├── headers = {'Authorization': f'Bearer {psk}'}
│   │   ├── requests.post() call
│   │   │   ├── timeout=30 configuration
│   │   │   ├── headers authentication
│   │   │   └── error handling
│   │   │
│   │   ├── response.raise_for_status()
│   │   ├── content type validation
│   │   └── response.content return
│   │
│   └── tar_content extraction
│
├── File Extraction
│   ├── extract_server_files()
│   │   ├── target_dir = Path(target_dir)
│   │   ├── target_dir.mkdir() creation
│   │   │   ├── parents=True for path creation
│   │   │   ├── exist_ok=True for idempotency
│   │   │   └── permission handling
│   │   │
│   │   ├── tarfile.open() with BytesIO
│   │   │   ├── fileobj=io.BytesIO(tar_content)
│   │   │   ├── mode='r:gz' for gzip
│   │   │   └── tar context manager
│   │   │
│   │   ├── Member Processing Loop
│   │   │   ├── tar.getmembers() iteration
│   │   │   ├── member.isfile() filtering
│   │   │   ├── security validation
│   │   │   └── file type classification
│   │   │
│   │   ├── File Classification
│   │   │   ├── Certificate files (.crt, .pem)
│   │   │   ├── Private key files (.key)
│   │   │   ├── Configuration files (.ovpn)
│   │   │   └── TLS files (tls-*)
│   │   │
│   │   ├── File Writing Loop
│   │   │   ├── target_path construction
│   │   │   ├── path traversal prevention
│   │   │   ├── tar.extractfile() content extraction
│   │   │   ├── file.read() content reading
│   │   │   ├── target file writing
│   │   │   └── permission setting
│   │   │
│   │   ├── Statistics Collection
│   │   │   ├── file count tracking
│   │   │   ├── file type counting
│   │   │   └── size statistics
│   │   │
│   │   └── Summary Reporting
│   │       ├── click.echo() file counts
│   │       ├── success confirmation
│   │       └── file listing
│   │
│   └── extraction result
│
├── Success Reporting
│   ├── click.secho() completion message
│   ├── file count reporting
│   └── target directory display
│
└── Error Handling
    ├── Network errors
    ├── Authentication failures
    ├── File system errors
    └── TAR extraction errors
```

### **get_openvpn_computer_config.py**

#### Command: `get_openvpn_computer_config.py [options]`
```
Entry Point: main()
│
├── [Configuration Resolution - Similar to server tool]
│
├── Computer Profile Retrieval
│   ├── get_computer_profile_with_psk()
│   │   ├── endpoint_url = f"{config.server_url}/api/v1/computer/bundle"
│   │   ├── [Similar PSK authentication as server tool]
│   │   └── single OVPN file response
│   │
│   └── profile_content extraction
│
├── [File Writing - Similar to profile tool]
│
├── [Success Reporting - Similar to other tools]
│
└── [Error Handling - Similar patterns]
```

### **generate_pki.py**

#### Command: `generate_pki.py generate-root [options]`
```
Entry Point: generate_root()
│
├── Parameter Processing
│   ├── click option extraction
│   ├── path validation
│   └── lifespan validation
│
├── Directory Setup
│   ├── Path(out_dir) creation
│   ├── directory.mkdir() with parents
│   ├── overwrite protection
│   └── permission setting
│
├── Root CA Subject Prompting
│   ├── prompt_for_subject_fields()
│   │   ├── click.prompt() for each field
│   │   ├── default value handling
│   │   ├── input validation
│   │   └── subject dict construction
│   │
│   └── subject validation
│
├── Root CA Key Generation
│   ├── create_private_key()
│   │   ├── validate_entropy_for_key_generation()
│   │   │   ├── EntropyValidator() instantiation
│   │   │   ├── validator.check_system_entropy()
│   │   │   │   ├── /proc/sys/kernel/random/entropy_avail reading
│   │   │   │   ├── entropy threshold checking
│   │   │   │   ├── entropy quality testing
│   │   │   │   └── recommendation generation
│   │   │   │
│   │   │   ├── interactive prompting [if insufficient]
│   │   │   ├── validator.wait_for_entropy() [if requested]
│   │   │   └── boolean result
│   │   │
│   │   ├── Key Type Selection
│   │   │   ├── 'ed25519': ed25519.Ed25519PrivateKey.generate()
│   │   │   ├── 'rsa2048': rsa.generate_private_key(65537, 2048)
│   │   │   ├── 'rsa4096': rsa.generate_private_key(65537, 4096)
│   │   │   └── ValueError for unknown types
│   │   │
│   │   ├── Passphrase Handling
│   │   │   ├── click.prompt() with hide_input=True
│   │   │   ├── passphrase confirmation
│   │   │   ├── matching validation
│   │   │   └── encoding to bytes
│   │   │
│   │   ├── Key Serialization
│   │   │   ├── serialization.Encoding.PEM
│   │   │   ├── serialization.PrivateFormat.PKCS8
│   │   │   ├── serialization.BestAvailableEncryption(passphrase)
│   │   │   └── private_bytes() output
│   │   │
│   │   └── File Writing
│   │       ├── Path(key_path) creation
│   │       ├── write_bytes() operation
│   │       ├── chmod(0o600) permission setting
│   │       └── click.echo() confirmation
│   │
│   └── private_key object return
│
├── Root CA Certificate Creation
│   ├── build_subject_name()
│   │   ├── x509.NameBuilder()
│   │   ├── field iteration and addition
│   │   │   ├── x509.oid.NameOID mapping
│   │   │   ├── x509.NameAttribute() creation
│   │   │   └── builder.add_attribute()
│   │   │
│   │   └── builder.build() name object
│   │
│   ├── Certificate Builder Setup
│   │   ├── x509.CertificateBuilder()
│   │   ├── subject_name() and issuer_name() [same for root]
│   │   ├── public_key() from private key
│   │   ├── serial_number() random generation
│   │   ├── not_valid_before() current time
│   │   ├── not_valid_after() + lifespan
│   │   └── extension additions
│   │
│   ├── CA Extensions
│   │   ├── x509.BasicConstraints(ca=True, path_length=1)
│   │   ├── x509.KeyUsage() for CA operations
│   │   ├── x509.SubjectKeyIdentifier.from_public_key()
│   │   └── extension critical flags
│   │
│   ├── Certificate Signing
│   │   ├── get_signing_algorithm()
│   │   │   ├── key type detection
│   │   │   ├── hashes.SHA256() for RSA/ECDSA
│   │   │   └── None for Ed25519/Ed448
│   │   │
│   │   └── builder.sign() with private key
│   │
│   └── Certificate Writing
│   │   ├── serialization.Encoding.PEM
│   │   ├── certificate.public_bytes()
│   │   ├── file writing
│   │   └── success confirmation
│
├── Intermediate CA Generation
│   ├── _generate_intermediate()
│   │   ├── [Similar key generation process]
│   │   ├── [Similar certificate creation]
│   │   ├── Different subject prompting
│   │   ├── parent certificate loading
│   │   ├── issuer_name() from root certificate
│   │   ├── CA constraints (ca=True, path_length=0)
│   │   └── signing with root private key
│   │
│   └── intermediate file writing
│
├── Success Reporting
│   ├── click.secho() success messages
│   ├── file path reporting
│   ├── certificate validity reporting
│   └── usage instructions
│
└── Error Handling
    ├── entropy validation failures
    ├── file system errors
    ├── cryptographic errors
    └── user input validation
```

## Cross-Service Communication Chains

### **Frontend → Signing Service Communication**

#### Certificate Signing Request Flow
```
Frontend Function: request_signed_certificate()
│
├── Configuration Retrieval
│   ├── current_app.config.get('SIGNING_SERVICE_URL')
│   ├── current_app.config.get('SIGNING_SERVICE_API_SECRET')
│   └── endpoint URL construction
│
├── Payload Construction
│   ├── {'csr': csr_pem, 'certificate_type': certificate_type}
│   ├── user_id inclusion [if provided]
│   ├── client_ip inclusion [if provided]
│   ├── request_metadata inclusion [if provided]
│   └── JSON serialization
│
├── HTTP Request
│   ├── requests.post() call
│   ├── headers = {'Authorization': f'Bearer {api_secret}'}
│   ├── json=payload parameter
│   ├── timeout=5 configuration
│   └── connection establishment
│
├── Signing Service Processing
│   ├── @frontend_api_secret_required decorator
│   │   ├── request.headers.get('Authorization')
│   │   ├── Bearer token extraction
│   │   ├── secret comparison
│   │   └── authentication validation
│   │
│   ├── Request Validation
│   │   ├── request.get_json() parsing
│   │   ├── 'csr' field validation
│   │   ├── 'certificate_type' validation
│   │   └── input sanitization
│   │
│   ├── CSR Processing
│   │   ├── x509.load_pem_x509_csr() parsing
│   │   ├── CSR validation
│   │   ├── subject extraction
│   │   └── public key validation
│   │
│   ├── CA Operations
│   │   ├── load_intermediate_ca()
│   │   │   ├── config file reading
│   │   │   ├── secure_key_context() setup
│   │   │   ├── certificate loading
│   │   │   ├── private key loading with passphrase
│   │   │   └── key validation
│   │   │
│   │   ├── sign_csr()
│   │   │   ├── certificate builder setup
│   │   │   ├── validity period calculation
│   │   │   ├── serial number generation
│   │   │   ├── extension processing
│   │   │   └── certificate signing
│   │   │
│   │   └── certificate serialization
│   │
│   ├── Certificate Transparency Logging
│   │   ├── log_certificate_to_ct()
│   │   │   ├── get_ct_client() initialization
│   │   │   ├── metadata preparation
│   │   │   ├── CT service API call
│   │   │   └── logging confirmation
│   │   │
│   │   └── audit trail creation
│   │
│   └── Response Generation
│       ├── {'certificate': cert_pem} construction
│       ├── jsonify() serialization
│       └── HTTP 200 response
│
├── Response Processing
│   ├── response.raise_for_status() validation
│   ├── response.json() parsing
│   ├── 'certificate' field extraction
│   └── certificate PEM return
│
└── Error Handling
    ├── requests.exceptions.RequestException
    ├── KeyError/ValueError for malformed responses
    ├── SigningServiceError wrapping
    └── error propagation
```

### **Signing Service → Certificate Transparency Service Communication**

#### Certificate Logging Flow
```
Signing Service Function: log_certificate_to_ct()
│
├── CT Client Setup
│   ├── get_ct_client()
│   │   ├── CTLogClient() instantiation
│   │   ├── service URL configuration
│   │   ├── API secret loading
│   │   └── client initialization
│   │
│   └── client validation
│
├── Certificate Metadata Preparation
│   ├── certificate parsing and validation
│   ├── subject/issuer extraction
│   ├── validity period extraction
│   ├── fingerprint calculation
│   ├── client IP processing
│   └── metadata dictionary construction
│
├── CT Service API Call
│   ├── requests.post() to CT service
│   ├── endpoint: /api/log-certificate
│   ├── Authorization header with secret
│   ├── JSON payload with certificate data
│   ├── timeout configuration
│   └── response processing
│
├── CT Service Processing
│   ├── @certtransparency_api_secret_required validation
│   ├── request data validation
│   ├── certificate validation
│   ├── GeoIP lookup for client IP
│   ├── CertificateLog database entry creation
│   ├── database persistence
│   └── success response
│
└── Response Handling
    ├── success confirmation
    ├── error handling and retry logic
    ├── logging and monitoring
    └── result return
```

## Summary

This comprehensive route-to-function mapping provides complete traceability from user interactions (web requests, CLI commands) through all intermediate processing layers down to leaf functions performing core operations. Key insights:

### **Execution Depth Analysis**
- **Shallow routes**: Health checks, static pages (3-5 function calls)
- **Medium routes**: Authentication, simple queries (8-12 function calls)
- **Deep routes**: Certificate generation, profile rendering (15-25+ function calls)

### **Cross-Cutting Concerns**
- **Authentication/Authorization**: Present in all protected routes
- **Logging/Tracing**: Embedded throughout execution chains
- **Error Handling**: Multi-layer approach with specific exception types
- **Database Operations**: Transaction management and rollback handling

### **Performance Hotspots**
- Certificate generation (cryptographic operations)
- Template rendering (file I/O and Jinja2 processing)
- Cross-service communication (network latency)
- Database queries (especially CT service queries)

### **Security Checkpoints**
- Input validation at route entry points
- Authentication/authorization decorators
- PSK verification with constant-time comparison
- Path traversal prevention in file operations
- API secret verification for service communication

This mapping serves as a foundation for performance optimization, security analysis, debugging, and architectural understanding of the OpenVPN Manager system.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Explore directory structure of services/ and tools/", "status": "completed", "activeForm": "Exploring directory structure of services/ and tools/"}, {"content": "Scan all Python files for docstring analysis", "status": "completed", "activeForm": "Scanning all Python files for docstring analysis"}, {"content": "Analyze function and class docstrings for quality", "status": "completed", "activeForm": "Analyzing function and class docstrings for quality"}, {"content": "Map function calls and dependencies across codebase", "status": "completed", "activeForm": "Mapping function calls and dependencies across codebase"}, {"content": "Create docstring audit report", "status": "completed", "activeForm": "Creating docstring audit report"}, {"content": "Create function call mapping documentation", "status": "completed", "activeForm": "Creating function call mapping documentation"}, {"content": "Create route to function chains mapping", "status": "completed", "activeForm": "Creating route to function chains mapping"}]