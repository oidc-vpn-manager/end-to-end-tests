# OpenVPN Manager

OpenVPN Manager is a comprehensive system for automated certificate management and OpenVPN profile generation. It provides a complete solution for organizations that need to manage OpenVPN access at scale while maintaining security controls and audit trails.

## 🚀 What Problem Does This Solve?

Traditional OpenVPN deployments often suffer from several critical issues:

- **Manual certificate management** leading to security vulnerabilities and operational overhead
- **Lack of audit trails** for issued certificates and access grants
- **Poor user experience** with complex manual configuration processes
- **Security risks** from shared certificates or weak key management
- **Operational complexity** in managing certificates across multiple users and devices

OpenVPN Manager addresses these challenges by providing:

- **Automated certificate lifecycle management** with secure key isolation
- **Complete audit trail** through Certificate Transparency logging
- **Self-service user portal** with OIDC authentication
- **API-driven automation** for server and client deployments
- **Microservice architecture** with clear separation of concerns

## 🏗️ Architecture Overview

The system consists of three core microservices that work together to provide secure, auditable OpenVPN certificate management:

### Core Services
- **[Frontend Service](Architecture.md#frontend-service)** - Web UI and REST API for users and administrators
- **[Signing Service](Architecture.md#signing-service)** - Isolated certificate signing service  
- **[Certificate Transparency Service](Architecture.md#certificate-transparency-service)** - Immutable audit log of all issued certificates

### Supporting Tools
- **[PKI Tool](Architecture.md#pki-tool)** - Offline root and intermediate CA generation
- **[OpenVPN Config Tool](Architecture.md#openvpn-config-tool)** - Client CLI for profile retrieval and management

## 📚 Documentation

### Getting Started
- **[Architecture Overview](Architecture.md)** - Detailed system design and component interactions
- **[Deployment Guide](Deployment.md)** - Production deployment with Docker Compose and Kubernetes

### User Guides
- **[Using the Service](Using-The-Service.md)** - End-user guide for generating OpenVPN profiles
- **[Administrator Guide](Using-The-Service-As-An-Administrator.md)** - Admin workflows for PSK management and certificate review

### Technical References
- **[API Documentation](../services/frontend/app/assets/swagger/v1.yaml)** - Complete REST API specification
- **[Docker Deployment](../deploy/docker/README.md)** - Production Docker Compose setup
- **[Kubernetes Deployment](../deploy/helm/README.md)** - Production Kubernetes Helm charts

## 🔐 Security Features

- **Microservice architecture** with service isolation and defined interfaces
- **Service separation patterns** for user/admin service isolation and scaling
- **Certificate Transparency logging** for complete audit trail
- **OIDC integration** with enterprise identity providers
- **Modern cryptography** with Ed25519 and RSA key support
- **Network segmentation** between frontend, signing, and database tiers
- **API authentication** with secure token-based access control

## 🚦 Quick Start

1. **Generate PKI materials**: Use the [PKI tool](https://github.com/openvpn-manager/pki_tool) to create root and intermediate CAs
2. **Deploy services**: Follow the [Docker deployment guide](https://github.com/openvpn-manager/deploy-with-docker/blob/main/README.md) for a quick start
3. **Configure OIDC**: Set up authentication with your identity provider
4. **Create server certificates**: Use the admin interface to generate server configurations
5. **Issue user certificates**: Users can self-service through the web portal

## 🛠️ Development

### Prerequisites
- Python 3.9+
- Docker and Docker Compose
- PostgreSQL (for production) or SQLite (for development)
- OIDC-compatible identity provider

### Running Tests
```bash
make test
```

All services maintain 100% test coverage with comprehensive unit, integration, and end-to-end testing.

### Development Environment
```bash
# Clone the repository
git clone https://github.com/openvpn-manager/end-to-end-tests openvpn-manager --recurse-submodules
cd openvpn-manager

# Start development environment
cd tests
docker-compose up -d

# Run integration tests
make test
```

## 🤝 Contributing

Contributions are welcome! Since this is Free Software:

- No copyright assignment needed, but will be gratefully received
- **Feature requests and improvements are gratefully received**, however they may not be implemented due to time constraints or if they don't align with the developer's vision for the project
- Please ensure all tests pass and maintain 100% code coverage
- Follow the existing code style and architectural patterns

### Development Standards
- All code must pass linting and security checks
- 100% test coverage requirement for all new code
- Security-first design principles
- Comprehensive documentation for all user-facing features

## 📄 License

This software is released under the [GNU Affero General Public License version 3](LICENSE).

The AGPL v3 license ensures that any modifications to this software, including those used to provide network services, must be made available under the same license terms. This promotes collaborative development while preventing proprietary capture of the codebase.

## 🤖 AI Assistance Disclosure

This code was developed with assistance from AI tools. While released under a permissive license that allows unrestricted reuse, we acknowledge that portions of the implementation may have been influenced by AI training data. Should any copyright assertions or claims arise regarding uncredited imported code, the affected portions will be rewritten to remove or properly credit any unlicensed or uncredited work.

## 🆘 Support

- **Documentation**: Start with this README and explore the linked guides
- **Issues**: Report bugs and feature requests through the project issue tracker
- **Security**: Report security vulnerabilities to jon+openvpnmanagersecurity@sprig.gs

---

**Built with security, scalability, and user experience in mind. Deploy with confidence.**