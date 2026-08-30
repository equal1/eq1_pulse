# Execution Breakdown Template: [Feature Name]

Companion to `[plan-name].md`. [Number] implementation tasks and [Number] research task(s), each sized for a single clean session.

**Requires:** [list dependencies, e.g., "#3 (expressions) and #6 (symbols) to have landed"]

**Run the implementation tasks in numeric order** unless the dependency graph says two are independent. Each assumes every task it depends on is complete and committed, and each leaves the tree green.

---

## Common preamble — paste into every session

> **Environment.** [Setup instructions, e.g., `conda activate project-dev`]
>
> **Conventions.** Follow [relevant style guide]. Load-bearing points: [list 3-5 critical conventions]
>
> **Verify.** `./qa/run_all_qa.sh` (or project-specific QA command). It must pass before you report done.
>
> **Context.** Read the sections of `[plan-name].md` your task names, and **§[key section] in full regardless of task** — it is normative. Do not read the whole plan; the section list in your task is the budget.
>
> **Scope.** Do only what your task says. Each task lists an explicit *out of scope* set. If you believe a listed exclusion is wrong, say so in your final message rather than acting on it.

---

## Traps with known locations

| Trap | Where it bites |
|------|----------------|
| **[Trap 1 — description]** | Task [N] |
| **[Trap 2 — description]** | Tasks [N], [M] |

---

## Dependency graph

```text
T1 ─┬─ T2 ─ T3
    └─────── T4

R-1 ....... informational; gates nothing
```

**[Explanation of dependencies and which tasks can run in parallel]**

---

## Task schedule

| # | Task | Size | Model | Context | Touches |
|---|------|------|-------|---------|---------|
| T1 | [Name] | [S/M/L] | [Haiku/Sonnet/Opus] | [context in tokens] | [files] |
| T2 | [Name] | [S/M/L] | [Haiku/Sonnet/Opus] | [context in tokens] | [files] |
| R-1 | Research: [question] | [S/M/L] | [Haiku/Sonnet/Opus] | [context in tokens] | [files] |

### Legend

| Column | Value | Means |
|--------|-------|-------|
| **Size** | S | One or two source files plus tests. A shape already in the tree. |
| | M | Three to six files including tests, or one file with changes rippling through callers. |
| | L | A new module, or edits spanning most of a major directory. Expect a second review pass. |
| **Model** | Haiku 4.5 | Acceptance criteria are a checklist; nothing to design. |
| | Sonnet 5 | Ordinary model/builder work with in-tree pattern to follow. |
| | Opus 5 | Silent failure mode AND no in-tree precedent. |
| **Reasoning** | medium | Mistakes are **loud** — wrong code fails type checks or existing tests immediately. |
| | high | Mistakes are **silent** — code type-checks and passes tests while being subtly wrong. |

---

## T1 — [Task name]

**Read:** [plan sections, e.g., §3, §5, §15]
**Depends on:** [T0 or nothing]
**Goal:** [one sentence on what success looks like]

### Steps

1. [Step 1 with expected outcome]
2. [Step 2 with expected outcome]
3. [Step 3 with expected outcome]

### Acceptance

- `./qa/run_all_qa.sh` passes
- [Specific acceptance criterion 1]
- [Specific acceptance criterion 2]

### Out of scope

[List what is explicitly NOT part of this task]

---

## T2 — [Task name]

**Read:** [plan sections]
**Depends on:** [T1]
**Goal:** [one sentence]

[Same structure as T1]

---

## R-1 — Research: [Research question]

**Type:** research. Produces a document, touches no source.
**Depends on:** nothing. Can run at any time; gates nothing.
**Output:** `docs/research/[research-topic].md`

### Questions to answer

1. [Research question 1]
2. [Research question 2]
3. [Research question 3]

### Format

Follow [existing research format]. Include: findings summary, then a section per question, then "what this means for [project]" section.

### Out of scope

[Anything not in scope for this research]

---

## Closed decisions

**D-1 — [Decision name].** Closed: **[choice].** [Rationale.] [Plan section reference.]

**D-2 — [Decision name].** Closed: **[choice].** [Rationale.] [Plan section reference.]

---

## Deferred — file as issues once this plan closes

Found while reviewing [task]. Neither blocks a task here.

**D-A — [Issue to track separately]** [Explanation and suggestion for when to address it.]

**D-B — [Issue to track separately]** [Explanation and suggestion for when to address it.]
