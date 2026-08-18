# Security and production-use warning

> [!CAUTION]
> **This repository is demonstration and example software. It is not a
> production-ready application.**

The demo uses delegated user authentication and does not intentionally store
access tokens or passwords. Fabric permissions remain authoritative for data
access.

Before adapting this project for production, design and validate at least:

- A confidential-client or managed-identity authentication architecture.
- Secure server-side token caching and session management.
- Centralized secret storage such as Azure Key Vault.
- Private networking and supported network-isolation patterns.
- CSRF, replay, rate-limit, abuse, and denial-of-service controls.
- Role and group lifecycle management.
- Data classification, residency, retention, deletion, and audit requirements.
- Encryption, backup, restore, high availability, and disaster recovery.
- Structured logging, tracing, monitoring, alerts, and incident response.
- Prompt-injection, indirect-injection, and data-exfiltration controls.
- Dependency, container, infrastructure, and software-supply-chain scanning.
- Formal threat modeling, penetration testing, privacy review, and compliance
  approval.

Do not publish `.env`, `config/*.local.json`, credentials, access tokens,
connection strings, tenant identifiers, workspace identifiers, or data-agent
identifiers.

Report vulnerabilities privately through GitHub's security-advisory feature
rather than opening a public issue.
