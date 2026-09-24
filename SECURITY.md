# Security Policy

## Supported Versions

Currently, only the latest version of the **Raspberry Pi IDE Simulator** on the `master` branch is supported with security updates.

| Version | Supported |
| ------- | --------- |
| Latest  | ✅        |
| Older   | ❌        |

## Reporting a Vulnerability

We take the security and isolation of the IDE execution engine very seriously. 

If you discover a security vulnerability within this project, **please DO NOT open a public issue.**

Instead, please privately report the issue to the repository maintainer, or use [GitHub's private vulnerability reporting feature](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability) if it is enabled on this repository.

We will investigate all legitimate reports and do our best to quickly patch any confirmed vulnerabilities.

## Scope

**In Scope:**
- Sandbox escapes or isolation failures in the `CodeExecutor`.
- Arbitrary code execution vulnerabilities (outside of the intended user-script simulation context).
- Path traversal vulnerabilities in the IDE's file management (Open/Save dialogs).
- Command injection vulnerabilities.

**Out of Scope:**
- Vulnerabilities in 3rd-party dependencies (e.g., `uv`, `pygame`, `tkinter`), unless the vulnerability is caused by how this project improperly integrates them.
- Denial of Service (DoS) caused by deliberately writing infinite loops in the simulation environment.
