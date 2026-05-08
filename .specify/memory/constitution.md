<!--
  SYNC IMPACT REPORT
  ==================
  Version change: [TEMPLATE] → 1.0.0
  
  Principles added:
    - I. Spec-Driven Development (SDD) — from CLAUDE.md "Non-Negotiable Principles"
    - II. Test-Driven Development (TDD) — from CLAUDE.md "Non-Negotiable Principles"
    - III. Agentic Parallel Execution — from CLAUDE.md multi-feature path + security gate
    - IV. Experiment Isolation — from CLAUDE.md "Tech Conventions"
  
  Sections added:
    - Quality Gates
    - Governance
  
  Template updates:
    ✅ .specify/templates/plan-template.md — "Constitution Check" section already present; gates align
    ✅ .specify/templates/spec-template.md — no constitution-specific references; no update needed
    ✅ .specify/templates/tasks-template.md — TDD task ordering (tests-first) aligns with Principle II
    ✅ No commands templates found in .specify/templates/commands/
  
  Boundary decision: CLAUDE.md retains all operational guidance (workflow steps, directory
  structure, branch naming, commit format, tech conventions, ADR process). The constitution
  owns the principles; CLAUDE.md references them. No CLAUDE.md changes required.
  
  Deferred TODOs: None.
-->

# Agent Harness Constitution

## Core Principles

### I. Spec-Driven Development (NON-NEGOTIABLE)

Before any code is written, a Product Spec (PS-NNN) and at least one Engineering Spec (ENG-NN)
MUST exist with zero unresolved Open Questions.

- The spec is the sole source of truth. Agents MUST implement what the spec says, not what
  seems reasonable or convenient.
- Ambiguities encountered during implementation MUST surface as blockers to the human; they
  MUST NOT be resolved by agent assumption.
- Specs are immutable once implementation starts. Requirement changes require updating the spec
  first, then re-implementing affected work.

Violating this principle is a blocker, not a judgment call.

### II. Test-Driven Development (NON-NEGOTIABLE)

Tests MUST be written before implementation code. The mandatory sequence is:

1. Write a failing test that captures the desired behavior.
2. Write the minimum code required to make it pass.
3. Refactor — only once the test is green.

- No production code may exist without a corresponding test.
- If a test cannot be written for a behavior, that behavior MUST NOT be implemented.
- All tests MUST pass before a task is considered done. A partial implementation with passing
  tests is acceptable; untested code is not.

Violating this principle is a blocker, not a judgment call.

### III. Agentic Parallel Execution

When running the multi-feature parallel path, each agent MUST operate in an isolated git
worktree on a dedicated branch following the `wave-N/ENG-NN-<slug>` naming convention.

- A security review MUST run automatically after each agent branch is built.
- A `BLOCKED` security verdict MUST be resolved before any merge proceeds; it is never optional.
- Security reports live in `.security/` (gitignored) and MUST NOT be committed.

### IV. Experiment Isolation

All experiment code MUST live under `experiments/<name>/`. No files may be written outside
that directory unless the Engineering Spec explicitly authorizes a different path.

- Each experiment MUST have its own `README.md` covering setup and run instructions.
- Language and stack are chosen per-experiment to fit the data technology under test.

## Quality Gates

The following conditions MUST be satisfied before any implementation task is marked complete:

- **Spec gate**: Corresponding PS-NNN and ENG-NN exist; no open questions remain.
- **Test gate**: All tests covering the task's acceptance criteria are written and passing.
- **Security gate**: If on a wave branch, security review returned no `BLOCKED` findings.
- **Isolation gate**: No files written outside the authorized experiment directory.

Failing any gate is a blocker. Agents MUST surface gate failures to the human rather than
working around them.

## Governance

This constitution supersedes all other project practices. When CLAUDE.md operational guidance
conflicts with a constitutional principle, the principle takes precedence.

**Amendment procedure**:
1. Identify the principle or section being changed and the motivation.
2. Update this file with a version bump per the versioning policy below.
3. Add an ADR in `docs/decisions/` capturing context, decision, and consequences.
4. Update CLAUDE.md if any operational guidance must change to reflect the amendment.
5. Inform all active agents of the amendment before they start new tasks.

**Versioning policy**:
- MAJOR: A principle is removed, redefined, or made incompatible with prior behavior.
- MINOR: A new principle or section is added, or existing guidance is materially expanded.
- PATCH: Clarifications, wording fixes, or non-semantic refinements.

**Compliance**: Every PR review MUST verify that the implementation complies with all four
core principles and passes all quality gates. Non-compliance is a merge blocker.

**Version**: 1.0.0 | **Ratified**: 2026-05-07 | **Last Amended**: 2026-05-07
