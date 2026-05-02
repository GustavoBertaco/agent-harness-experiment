# agent-harness-experiment

A local lab for experimenting with data technologies using a **Spec-Driven Development (SDD)** agentic workflow.

## How it works

1. Write a Light PRD describing what you want to build
2. Compile it into a structured Product Spec (`specs/PS-NNN-*.md`)
3. Generate Engineering Specs (`specs/eng/ENG-NN-*.md`) — one per implementation task
4. Run `/build-wave` to spawn parallel Claude agents that implement each spec in isolated git worktrees
5. Review, QA, and merge

See `CLAUDE.md` for the full workflow, spec formats, and conventions.

## Getting started

```bash
git clone <repo>
cd agent-harness-experiment
# Open in Claude Code
code .
```

Start by writing a Light PRD in a scratch file, then ask Claude to compile it into a Product Spec.
