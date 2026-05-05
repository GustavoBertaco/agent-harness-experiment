# Agent Harness — Conventions & Workflow

This repo is a local lab for experimenting with data technologies using a **Spec-Driven Development (SDD)** agentic workflow. The idea: humans author intent, agents compile structured specs, and parallel agents in isolated git worktrees execute the implementation.

---

## Non-Negotiable Principles

These two principles apply to every agent in every workflow step. No exceptions.

### Spec-Driven Development (SDD)
- **No implementation without an approved spec.** Before any code is written, a Product Spec (PS-NNN) and Engineering Specs (ENG-NN) must exist and have no unresolved Open Questions.
- **The spec is the source of truth.** Agents must implement what the spec says, not what seems reasonable. Ambiguities go back to the human as blockers — never resolved with assumptions.
- **Specs are immutable once implementation starts.** Changes to requirements require updating the spec first, then re-implementing.

### Test-Driven Development (TDD)
- **Tests are written before implementation code.** The sequence is always: write a failing test → write the minimum code to pass it → refactor.
- **No production code exists without a corresponding test.** If a test cannot be written for a behavior, that behavior is not implemented.
- **All tests must pass before a task is considered done.** A partial implementation with passing tests is acceptable; untested code is not.

Violating either principle is a blocker, not a judgment call.

---

## The 9-Step Workflow

```
1. Human writes Light PRD (free-form, ~1 page)
2. Human + agent compile PS-NNN Product Spec  →  specs/ps/PS-NNN-<name>.md
3. Agent writes Architecture doc              →  specs/architecture.md
4. Agent writes Engineering Specs            →  specs/eng/ENG-NN-<task>.md (one per task)
5. Human reviews specs, resolves open questions
6. /build-wave [N]  →  parallel agents implement each ENG spec in isolated worktrees
              └─ security-checker runs automatically after each branch is built
                 BLOCKED verdict = must fix before proceeding; see .security/SECURITY-REPORT-ENG-NN.md
                 Reports go to .security/ (gitignored) — never commit them
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
│   ├── ps/
│   │   └── PS-NNN-<name>.md     ← AI-compiled product specs
│   ├── architecture.md          ← system design for the current experiment
│   └── eng/
│       ├── ENG-01-<task>.md     ← engineering specs (one per agent task)
│       └── ENG-02-<task>.md
├── experiments/
│   └── <experiment-name>/       ← all code for an experiment lives here
│       ├── README.md
│       └── ...
├── .security/                   ← security reports (gitignored — never commit)
│   └── SECURITY-REPORT-ENG-NN.md
├── references/                  ← research and external references by topic
│   └── security/
│       └── owasp-secure-coding-2025.md
├── docs/
│   └── decisions/               ← Architecture Decision Records (ADRs)
│       └── ADR-NNN-<title>.md   ← why a harness design decision was made
└── .claude/
    ├── agents/                  ← specialized sub-agent configs
    └── commands/                ← custom slash commands
```

---

## Spec Templates

- Product Spec (PS-NNN): `specs/ps/` — template at `specs/LIGHT-PRD-TEMPLATE.md`
- Engineering Spec (ENG-NN): `specs/eng/ENG-NN-TEMPLATE.md`

---

## Architecture Decision Records (ADRs)

Significant harness design decisions are logged in `docs/decisions/ADR-NNN-<title>.md`. Each ADR captures:
- **Context** — what problem or gap prompted the decision
- **Decision** — what was chosen and why
- **Consequences** — trade-offs and expected friction

When a harness convention changes (agent behavior, workflow step, gitignore policy, etc.), write an ADR. Code tells you *what*; ADRs tell you *why*.

---

## Reference Material

External research and standards used to inform harness decisions live in `references/<topic>/`. Add a new file when you gather material from external sources — future agents and humans can trace decisions back to their evidence base.

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
