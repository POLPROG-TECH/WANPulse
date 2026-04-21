# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | ✅ Current release |

## Reporting a Vulnerability

If you discover a security vulnerability in WANPulse, please report it responsibly.

**Do not open a public issue.**

Instead, please email **contact@polprog.pl** with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge your report within **48 hours** and aim to provide a fix or mitigation within **7 days** for critical issues.

## Scope

Security concerns relevant to WANPulse include:

- **Outbound probe abuse** - unintended traffic patterns toward third parties
- **Sensitive data leakage** - targets, tokens, or config values exposed in logs, diagnostics, or the UI
- **Config flow input validation** - host/URL parsing that may trigger unsafe behavior in Home Assistant
- **Dependency vulnerabilities** in third-party packages bundled with Home Assistant that WANPulse relies on

### Out of Scope

- Issues in Home Assistant core itself (report to [home-assistant/core](https://github.com/home-assistant/core))
- Network-layer issues on the user's own infrastructure
- Denial of service against probe targets operated by the user

## Disclosure Policy

We follow coordinated disclosure:

1. Report the issue privately via the contact above.
2. We confirm receipt and begin investigation.
3. Once a fix is released, we publicly acknowledge the reporter (with their consent).
