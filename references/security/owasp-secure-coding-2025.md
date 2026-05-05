---
topic: Secure Coding Practices
gathered: 2026-05-04
relevance: Informed security-checker agent improvements
---

# OWASP Secure Coding Practices — 2025/2026 Reference

## Key Sources

- [OWASP Secure Coding Practices Quick Reference Guide](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)
- [OWASP Top 10 2025 — What Every Developer Must Know](https://seccomply.net/resources/blog/owasp-top-10-2025)
- [OWASP Secure Coding Practices Guide 2026](https://www.appsecmaster.net/blog/owasp-secure-coding-practices-guide/)
- [Secure Coding Checklist 2026](https://www.securityjourney.com/post/secure-coding-checklist)

## OWASP Top 10 — 2025 Edition Notable Changes

- **A10 — SSRF (Server-Side Request Forgery)** elevated to its own top-10 category (was previously part of A10 "Insufficient Logging")
- **A06 — Vulnerable and Outdated Components** now requires SBOM (Software Bill of Materials)
- **New: AI-generated code risk** — OWASP 2025 explicitly calls out LLM-generated code as an elevated risk category; it frequently contains injection patterns and cryptographic weaknesses due to being trained on pre-2020 codebases

## Core Checklist (every commit)

1. Input validation — strict allow-lists, not block-lists
2. Output encoding — all dynamic data encoded before rendering
3. Secrets check — no literals in code, use environment variables
4. Dependency scan — known CVEs + pinned versions
5. Unit tests for auth logic

---

# GitHub Repository Secrets Exposure — Reference

## Key Sources

- [GitHub: Best Practices for Preventing Data Leaks](https://docs.github.com/en/code-security/getting-started/best-practices-for-preventing-data-leaks-in-your-organization)
- [Exposed Git Repos: The Overlooked Threat to DevOps Security](https://pentera.io/blog/git-repo-security-exposed-secrets/)
- [21 Security Best Practices for GitHub — Check Point](https://www.checkpoint.com/cyber-hub/cloud-security/what-is-developer-security/21-security-best-practices-for-github/)
- [GitHub Secret Protection](https://github.com/security/advanced-security/secret-protection)

## Key Statistics

- GitHub 2024: **39 million leaked secrets** — 67% increase year-over-year
- Most common cause: `.env` files or config files committed accidentally

## Prevention Checklist

- `.env` in `.gitignore` before the first commit (not after)
- `.env.example` as a template committed instead
- `git-secrets`, `truffleHog`, or `gitleaks` in pre-commit hooks
- Secret rotation immediately on any suspected exposure (history is permanent)

## Incident Response

If a secret is exposed in git history:
1. Immediately rotate/revoke the secret
2. Remove from history: `git filter-repo` or BFG Repo-Cleaner
3. Force-push (coordinate with team)
4. Audit all access logs for the exposed credential

---

# Python Supply Chain Security — Reference

## Key Sources

- [Defense in Depth: Securing the Python Supply Chain](https://bernat.tech/posts/securing-python-supply-chain/)
- [PyPI Supply Chain Attacks of 2025 — What Python Engineers Should Learn](https://medium.com/@joyichiro/the-pypi-supply-chain-attacks-of-2025-what-every-python-backend-engineer-should-learn-from-the-875ba4568d10)
- [12 Best Practices to Prevent Software Supply Chain Attacks 2026](https://bastion.tech/blog/software-supply-chain-attack-prevention-best-practices/)
- [7 Software Supply Chain Security Best Practices 2026 — Sysdig](https://www.sysdig.com/learn-cloud-native/software-supply-chain-security-best-practices)

## 2025 Attack Timeline (context)

- **PyPI phishing campaign (July 2025)**: Targeted maintainers with spoofed emails + credential harvester proxy
- **GhostAction (September 2025)**: Injected code into GitHub Actions workflows across 570+ repos, stole 3,300+ secrets
- **Shai-Hulud worm (November 2025)**: npm-origin worm that also hit PyPI via monorepo credential sharing

## Prevention Checklist

- Pin all dependencies to exact versions (`requests==2.31.0`, not `requests>=2.0`)
- Add hash verification: `pip install --require-hashes -r requirements.txt`
- Run `pip-audit` in CI on every PR
- Use Trusted Publishing on PyPI (if publishing packages)
- Audit GitHub Actions workflows — avoid `pull_request_target` with write permissions
