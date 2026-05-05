---
id: ADR-001
date: 2026-05-04
status: Accepted
---

# ADR-001: Security Reports Go to `.security/` (Gitignored) and BLOCKED Verdict is Mandatory

## Context

Two non-obvious design decisions were made when building the security-checker agent that future maintainers might be tempted to "clean up" without understanding the risk.

## Decision 1 — Reports in `.security/`, not repo root

Security reports are written to `.security/SECURITY-REPORT-<ENG-NN>.md`, a gitignored directory, rather than the repo root.

**Why:** A report at the repo root can be accidentally staged with `git add .` and committed. This would publicly publish a map of the repo's own vulnerabilities — worse than not having a report at all. The `.security/` directory is gitignored so this cannot happen even carelessly.

## Decision 2 — BLOCKED verdict stops the merge; it is not advisory

A single CRITICAL security finding issues a BLOCKED verdict, and the `build-wave` workflow explicitly forbids merging a BLOCKED branch. There is no override path for the agent.

**Why:** A warning-only model puts the decision on the developer, who — especially when less experienced — will often rationalize skipping it ("I'll fix it later"). Making BLOCKED a hard stop forces the fix to happen at the moment of lowest cost, not after the branch is merged and the context is gone. The friction is intentional.

## Consequences

- Developers cannot accidentally commit security reports
- BLOCKED branches accumulate until fixed — there is no "merge with known issues" escape hatch
- Running `/build-wave` on a branch with a CRITICAL finding will always require a fix cycle before proceeding
