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
You are an implementation agent working in an isolated worktree. Your task is to implement the feature described in: <spec-file-path>

Follow the speckit-implement workflow:
1. Read the spec at <spec-file-path> as your feature specification
2. Read any available plan.md and tasks.md in the same directory
3. Execute all tasks in tasks.md in dependency order, TDD-first
4. Commit after each completed phase using conventional commit messages

Feature spec: <spec-file-path>
```

Spawn all agents in a single message (parallel). Do NOT run them sequentially.

### Step 4: Collect results

Wait for all agents to complete. For each, capture:
- Spec ID and title
- Branch name created
- Tests written / passing
- Any blockers

### Step 4.5: Run security checks

For every branch that completed without a BLOCKED status in Step 4, spawn one security-checker agent **in parallel** (single message, all at once). Each agent's prompt must be:

```
You are a security-checker agent. Scan the implementation branch for security vulnerabilities.

Follow the instructions in .claude/agents/security-checker.md exactly.

Branch: <branch-name>
Spec file: <spec-file-path>
ENG ID: <ENG-NN>
```

Wait for all security-checker agents to complete. For each, record:
- The verdict: CLEAR, WARNINGS, or BLOCKED
- Any CRITICAL findings (one-line summary each)

Branches with a BLOCKED security verdict must be listed in the Blockers section of the summary and must NOT be merged.

### Step 5: Print summary table

```
## Build Wave N — Results

| Spec         | Branch                        | Tests | Impl Status | Security    |
|--------------|-------------------------------|-------|-------------|-------------|
| ENG-01-foo   | wave-1/ENG-01-foo             | 5/5   | DONE        | CLEAR       |
| ENG-02-bar   | wave-1/ENG-02-bar             | 3/4   | BLOCKED     | (skipped)   |
| ENG-03-baz   | wave-1/ENG-03-baz             | 4/4   | DONE        | WARNINGS    |

Blockers:
- ENG-02 (impl): <blocker description>
- ENG-03 (security): see SECURITY-REPORT-ENG-03.md for details

Next steps:
- Review branches with /review-wave N (manual)
- Fix impl blockers by asking the debugger agent
- Fix security blockers by asking the security-checker agent to re-scan after changes
- For WARNINGS: read the .security/SECURITY-REPORT-*.md files and decide whether to fix or acknowledge
```

## Important notes

- Each agent works in its own git worktree — they cannot interfere with each other or with the main working tree.
- This command does not merge anything. Merging is a human step after review.
- If a spec has dependencies on another spec (listed in "Depends on"), warn if the dependency spec hasn't been implemented yet (check if its branch exists via `git branch --list`).
- Wave number in branch names uses the spec's own wave field, not the CLI argument.
