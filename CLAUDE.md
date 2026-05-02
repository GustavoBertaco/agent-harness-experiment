# Agent Harness — Conventions & Workflow

This repo is a local lab for experimenting with data technologies using a **Spec-Driven Development (SDD)** agentic workflow. The idea: humans author intent, agents compile structured specs, and parallel agents in isolated git worktrees execute the implementation.

Inspired by Nubank's "Donkey-Kong" agentic harness (April 2026) — 1 week actual execution vs 6–8 week estimate.

---

## The 9-Step Workflow

```
1. Human writes Light PRD (free-form, ~1 page)
2. Human + agent compile PS-NNN Product Spec  →  specs/PS-NNN-<name>.md
3. Agent writes Architecture doc              →  specs/architecture.md
4. Agent writes Engineering Specs            →  specs/eng/ENG-NN-<task>.md (one per task)
5. Human reviews specs, resolves open questions
6. /build-wave [N]  →  parallel agents implement each ENG spec in isolated worktrees
7. Automatic code review (reviewer agent per branch)
8. QA testing (happy path + guardrail scenarios)
9. Merge + release notes
```

Steps 1–5 are spec development. Steps 6–9 are execution. The spec is the primary input to every agent — never vague prompts.

---

## Directory Structure

```
agent-harness-experiment/
├── specs/
│   ├── PS-NNN-<name>.md         ← AI-compiled product specs
│   ├── architecture.md          ← system design for the current experiment
│   └── eng/
│       ├── ENG-01-<task>.md     ← engineering specs (one per agent task)
│       └── ENG-02-<task>.md
├── experiments/
│   └── <experiment-name>/       ← all code for an experiment lives here
│       ├── README.md
│       └── ...
└── .claude/
    ├── agents/                  ← specialized sub-agent configs
    └── commands/                ← custom slash commands
```

---

## Product Spec Format (PS-NNN)

File: `specs/PS-NNN-<name>.md`

```markdown
# PS-NNN: <Title>

**Status:** Draft | In Review | Approved
**Author:** <name>
**Date:** YYYY-MM-DD

## Intent
One paragraph: what is this and why does it matter?

## Problem
What pain or gap does this address?

## Goals
- Bullet list of success conditions

## Non-goals
- Explicitly out of scope

## Expected Behavior
Narrative description of how the system should behave.

## Acceptance Criteria
- AC-1: Given X, when Y, then Z
- AC-2: ...

## Constraints & Assumptions
- Tech, time, or business constraints

## Open Questions
| # | Question | Owner | Milestone |
|---|----------|-------|-----------|
| 1 | ...      | ...   | ...       |

## Dependencies
- Other specs or external systems this relies on

## Milestones
| Milestone | Description |
|-----------|-------------|
| M1        | ...         |
```

---

## Engineering Spec Format (ENG-NN)

File: `specs/eng/ENG-NN-<task>.md`

```markdown
# ENG-NN: <Title>

**Wave:** N
**Depends on:** ENG-XX (if any)

## Overview
One paragraph: what this spec builds and why.

## Tech Choices
- Language, libraries, tools

## Implementation Steps
1. Step one
2. Step two
3. ...

## Test Plan
Concrete, runnable acceptance checks:
- `pytest tests/test_foo.py::test_bar` → passes
- `python -c "import x; assert x.run() == expected"`

## Acceptance Criteria
- AC-1: ...
- AC-2: ...

## Notes
Edge cases, gotchas, restrictions.
```

---

## Available Commands

### `/build-wave [N]`
Spawns parallel implementation agents for engineering specs.

- `/build-wave` — runs all specs in `specs/eng/`
- `/build-wave 1` — runs only specs prefixed `ENG-01-*`

Each agent works in an isolated git worktree and opens a branch named `wave-N/ENG-NN-<slug>`.

---

## Tech Conventions

- **Experiment code** lives in `experiments/<name>/`, never at the repo root.
- **Language/stack** is per-experiment — choose whatever fits the data tech being tested.
- **Tests** run with `pytest` by default; override in the ENG spec if different.
- **Each experiment** has its own `README.md` with setup and run instructions.
- **Specs are immutable** once an agent starts implementing — resolve open questions first.

---

## Shared Engineering Context (always loaded by coding agents)

- Write tests before implementation (TDD).
- Branch naming: `wave-N/ENG-NN-<slug>` (e.g., `wave-1/ENG-02-ingestion`).
- Commit messages reference the spec ID: `ENG-02: implement ingestion pipeline`.
- Never skip tests or acceptance criteria — if a criterion can't be met, surface it as a blocker.
- Code lives under `experiments/<name>/`; do not write files outside that directory unless the spec explicitly says so.
