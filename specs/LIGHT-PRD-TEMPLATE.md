# PS-NNN: [Title — one concise noun phrase]

**Status:** Draft | In Review | Approved
**Author:** [name]
**Date:** YYYY-MM-DD
**Experiment:** [experiments/<name>/ — the directory this maps to]

---

## Intent

> One paragraph. What is this, why does it matter, and why now?
> Avoid vague language. If you removed this paragraph, could someone still understand what you're building? If yes, rewrite it.

---

## Problem

> What specific pain does this address? Who feels it most acutely?
> Bad: "Data pipelines are slow."
> Good: "Loading 1M rows from Parquet into DuckDB takes >30s on a laptop; analysts stop mid-exploration."

**Affected users / personas:**
- [Role]: [What they're trying to do, what friction they hit]

---

## Goals

Measurable conditions that define success. Every goal must be verifiable.

- [ ] [Goal 1 — quantified: e.g., "query latency ≤ 500ms on 1M rows"]
- [ ] [Goal 2]
- [ ] [Goal 3]

---

## Non-Goals

Explicitly out of scope. Being explicit here prevents scope creep in agent implementation.

- [Thing that sounds related but isn't in scope]
- [Thing to address in a future experiment]

---

## Expected Behavior

Narrative walkthrough of the happy path. Write this as a sequence of events, not a feature list.

> Example: "A user points the pipeline at a local CSV. Within 5 seconds, a DuckDB table is created with correct schema inference. The user runs an aggregation query and gets results in under 500ms."

**Edge cases to handle:**
- [Edge case 1]: [Expected behavior]
- [Edge case 2]: [Expected behavior]

---

## Acceptance Criteria

Machine-verifiable. Each criterion maps to a runnable test or command.

| ID   | Criterion | Verification |
|------|-----------|--------------|
| AC-1 | [What must be true] | `pytest tests/test_foo.py::test_bar` → passes |
| AC-2 | [What must be true] | `python -c "assert result == expected"` |
| AC-3 | [What must be true] | `time query.sh` → real < 0.5s |

---

## Technical Constraints

| Area | Constraint |
|------|------------|
| Language | [e.g., Python 3.12] |
| Libraries | [e.g., DuckDB 1.x, Polars ≥ 0.20] |
| Data scale | [e.g., ≤ 10M rows, files up to 2GB] |
| Platform | [e.g., local only, no cloud dependencies] |
| Performance | [e.g., pipeline completes in ≤ 60s] |
| Compliance | [e.g., no PII in test data] |

---

## Boundaries

Three-tier system — agents must follow this exactly.

**Always do:**
- [e.g., "Always write tests before implementation"]
- [e.g., "Always use type hints in Python"]

**Ask before doing:**
- [e.g., "Ask before modifying the shared schema file"]
- [e.g., "Ask before adding a new dependency"]

**Never do:**
- [e.g., "Never write files outside experiments/<name>/"]
- [e.g., "Never use mocked data where real data can be used"]

---

## Open Questions

| # | Question | Owner | Target Milestone |
|---|----------|-------|-----------------|
| 1 | [Question blocking spec finalization] | [name] | [M1] |
| 2 | | | |

> Resolve all open questions before running `/build-wave`. Agents cannot make judgment calls on ambiguous requirements.

---

## Dependencies

- [External dataset, API, or service this relies on]
- [Other experiment or spec this depends on]

---

## Milestones

| Milestone | Description | Done when |
|-----------|-------------|-----------|
| M1 | [Foundation] | [ENG specs written and reviewed] |
| M2 | [First working version] | [All AC-N pass] |
| M3 | [Stretch goal] | [...] |
