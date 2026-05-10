<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at `specs/001-k8s-cdc-event-generator/plan.md`
<!-- SPECKIT END -->

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

## Workflow

### Single-Feature Path (default — use spec-kit)

```
1. /speckit-specify <description>   →  specs/<###-name>/spec.md
2. /speckit-clarify                 →  resolve open questions in spec
3. /speckit-plan                    →  plan.md + design artifacts
4. /speckit-analyze                 →  cross-artifact consistency check
5. Human reviews, resolves blockers
6. /speckit-tasks                   →  tasks.md (dependency-ordered)
7. /speckit-implement               →  implementation, TDD-first
8. reviewer agent                   →  code review vs. spec AC
9. Merge + release notes
```

### Multi-Feature Parallel Path (for large experiments)

```
1–5. Same spec-kit steps per feature
6. /build-wave [N]                  →  parallel agents in isolated worktrees
              └─ security-checker runs automatically after each branch is built
                 BLOCKED verdict = must fix before proceeding; see .security/SECURITY-REPORT-ENG-NN.md
                 Reports go to .security/ (gitignored) — never commit them
7. reviewer agent per branch
8. Merge
```

Steps 1–5 are spec development. Steps 6–9 are execution. The spec is the primary input to every agent — never vague prompts.

---

## Directory Structure

```
agent-harness-experiment/
├── specs/
│   ├── <###-name>/              ← spec-kit feature specs (single-feature path)
│   │   ├── spec.md
│   │   ├── plan.md
│   │   └── tasks.md
│   ├── ps/
│   │   └── PS-NNN-<name>.md     ← AI-compiled product specs (multi-feature path)
│   ├── architecture.md          ← system design for the current experiment
│   └── eng/
│       ├── ENG-01-<task>.md     ← engineering specs (one per agent task)
│       └── ENG-02-<task>.md
├── experiments/
│   └── <experiment-name>/       ← all code for an experiment lives here
│       ├── README.md
│       └── ...
├── .specify/                    ← spec-kit framework files (do not edit)
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
    ├── skills/                  ← spec-kit skills
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

## Git Workflow (non-negotiable)

- **Every local change must be made on a new branch** — never commit directly to `main` or the current feature branch unless the branch was just created for that purpose.
- **All commits must be GPG-signed**: always use `git commit -S -m "message"`.
- **"Open a PR"** means: sign and commit all pending local changes, then open a pull request to the remote branch. If any permission is missing, stop and ask the user to perform that action.

---

## ClickUp Hooks

ClickUp task creation is handled automatically by Claude Code hooks — no action needed here.

- **Hook script**: `.claude/hooks/clickup-post-write.ps1`
- **Trigger**: fires after `Write` tool calls on `specs/*/spec.md` (post-specify) and `specs/*/plan.md` (post-plan)
- **Credentials**: copy `.env.clickup.example` → `.env.clickup` and fill in `CLICKUP_API_TOKEN` and `CLICKUP_LIST_ID`

Behavior:
- **Post-specify**: creates a parent task (`to do`, tags: `spec`, `pending-review`) + a `Discovery` subtask
- **Post-plan**: moves `Discovery` → `complete`, creates a `Refinement` subtask, moves parent → `planning`
- Both hooks are idempotent — they skip if a matching ClickUp task already exists or if `clickup_task_id` is in the spec frontmatter

---

## Shared Engineering Context (always loaded by coding agents)

- Write tests before implementation (TDD).
- Branch naming: `wave-N/ENG-NN-<slug>` (e.g., `wave-1/ENG-02-ingestion`).
- Commit messages reference the spec ID: `ENG-02: implement ingestion pipeline`.
- Never skip tests or acceptance criteria — if a criterion can't be met, surface it as a blocker.
- Code lives under `experiments/<name>/`; do not write files outside that directory unless the spec explicitly says so.
