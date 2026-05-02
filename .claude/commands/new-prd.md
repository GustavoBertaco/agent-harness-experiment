---
description: Socratic interview to create a Light PRD for a new data experiment
argument-hint: [experiment-name-or-idea]
---

# /new-prd — Light PRD Interview

Guide the user through a Socratic question process to capture everything needed for an agent-ready Light PRD. Ask questions in rounds, one round at a time. Build the PRD incrementally from the answers.

## How to run this

Work through 5 rounds of questions. After each round, summarize what you've captured so far and ask if anything needs correcting before moving to the next round. Do not ask all questions at once.

At the end, invoke the `prd-writer` agent with the full collected answers to produce the final `specs/PS-NNN-*.md` file.

---

## Round 1 — The Big Picture

Ask these questions together in one message:

> **Round 1 of 5 — Big Picture**
>
> 1. What are you building? (One sentence — pretend you're explaining it to a new colleague.)
> 2. What specific problem does it solve? Who feels this pain most? Be concrete — name the situation, not just "slow queries" or "bad DX".
> 3. Why experiment with this now? What's the trigger?

Wait for the user's answers. Summarize what you understood. Correct if needed. Then move to Round 2.

---

## Round 2 — Success & Scope

> **Round 2 of 5 — Success & Scope**
>
> 1. What does "this worked" look like? Give me one concrete thing you could measure or observe in week 1.
> 2. What is explicitly OUT of scope for this experiment? (Naming what you're NOT building is as important as naming what you are.)
> 3. What must you NOT break or change while building this? Any shared files, schemas, or systems that are off-limits?

Wait for answers. Summarize. Correct if needed. Then Round 3.

---

## Round 3 — Users & Behavior

> **Round 3 of 5 — Users & Behavior**
>
> 1. Who uses this? What's their goal when they interact with it?
> 2. Walk me through the happy path — what happens step by step from start to finish?
> 3. What are the top 2 edge cases or failure modes you're already thinking about?

Wait for answers. Summarize. Correct if needed. Then Round 4.

---

## Round 4 — Technical Reality

> **Round 4 of 5 — Technical Reality**
>
> 1. What data tech are you experimenting with? (Stack, libraries, versions if known.)
> 2. Any performance targets? Scale constraints? Data volumes?
> 3. Write me one concrete acceptance criterion — something I could run as a command or test assertion that would prove this works. (e.g., "pytest passes", "query returns in < 500ms", "file is created at path X")

Wait for answers. Summarize. Correct if needed. Then Round 5.

---

## Round 5 — Unknowns

> **Round 5 of 5 — Unknowns**
>
> 1. What's your biggest open question — something you don't know yet that could affect how this gets built?
> 2. Any external dependencies? (Datasets, APIs, other experiments this builds on?)
> 3. Anything else you want the implementing agent to know that we haven't covered?

Wait for answers. Summarize the full collected picture.

---

## Compilation

After Round 5, tell the user:

> "I have everything I need. Let me compile your Light PRD now."

Then invoke the `prd-writer` agent with a structured summary of all collected answers, organized by PRD section:

```
Compile a Light PRD from the following interview answers:

INTENT: [what they're building + why now]
PROBLEM: [specific pain + who feels it]
GOALS: [measurable success conditions from rounds 2 & 4]
NON-GOALS: [explicit out-of-scope items]
EXPECTED BEHAVIOR: [happy path from round 3]
EDGE CASES: [from round 3]
ACCEPTANCE CRITERIA: [from round 4]
TECH CONSTRAINTS: [stack, scale, perf from round 4]
BOUNDARIES:
  - Never: [off-limits items from round 2]
  - Ask: [anything ambiguous]
  - Always: [standard conventions from CLAUDE.md]
OPEN QUESTIONS: [from round 5]
DEPENDENCIES: [from round 5]
```

## Tone & style

- Ask one round at a time — never dump all 15 questions at once.
- Mirror the user's language back to them in summaries.
- If an answer is vague ("I want it to be fast"), probe: "How fast? What's the threshold that would make you say 'good enough'?"
- If the user skips a question, note it as an open question in the PRD rather than guessing.
- Keep each round conversational — this is an interview, not a form.
