---
description: Spawn parallel implementation agents for engineering specs in a wave
argument-hint: [wave-number]
---

# /build-wave — Parallel Spec Implementation

Orchestrates parallel Claude agents to implement engineering specs, each in an isolated git worktree.

## Behavior

### Step 1: Resolve specs to run

Parse `$ARGUMENTS`:
- If a number N is given (e.g., `/build-wave 1`): glob `specs/eng/ENG-0N-*.md` (zero-padded to 2 digits)
- If no argument: glob all `specs/eng/ENG-*.md`
- If no specs are found: print a clear error and stop

Print the list of specs found before proceeding.

### Step 2: Validate

For each spec file:
- Confirm it exists and is readable
- Confirm the `specs/eng/` directory exists

If the repo has uncommitted changes, warn the user but proceed unless they cancel.

### Step 3: Spawn parallel agents

For each spec file, spawn one Agent with `isolation: "worktree"`. Each agent's prompt must:

```
You are a spec-implementer agent. Your task is to implement the engineering spec at: <spec-file-path>

Follow the instructions in .claude/agents/spec-implementer.md exactly.

Spec file: <spec-file-path>
Wave: <N or "all">
```

Spawn all agents in a single message (parallel). Do NOT run them sequentially.

### Step 4: Collect results

Wait for all agents to complete. For each, capture:
- Spec ID and title
- Branch name created
- Tests written / passing
- Any blockers

### Step 5: Print summary table

```
## Build Wave N — Results

| Spec         | Branch                        | Tests | Status   |
|--------------|-------------------------------|-------|----------|
| ENG-01-foo   | wave-1/ENG-01-foo             | 5/5   | DONE     |
| ENG-02-bar   | wave-1/ENG-02-bar             | 3/4   | BLOCKED  |

Blockers:
- ENG-02: <blocker description>

Next steps:
- Review branches with /review-wave N (manual)
- Fix blockers by asking the debugger agent
```

## Important notes

- Each agent works in its own git worktree — they cannot interfere with each other or with the main working tree.
- This command does not merge anything. Merging is a human step after review.
- If a spec has dependencies on another spec (listed in "Depends on"), warn if the dependency spec hasn't been implemented yet (check if its branch exists via `git branch --list`).
- Wave number in branch names uses the spec's own wave field, not the CLI argument.
