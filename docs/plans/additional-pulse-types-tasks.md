# Execution breakdown: step pulse, digital trigger pulse, wait-for-trigger

Companion to [additional-pulse-types-plan.md](additional-pulse-types-plan.md) (issue #5). Four
independently executable tasks, each sized for a single clean session.

**Run last**, after [symbols-and-parameters-tasks.md](symbols-and-parameters-tasks.md) (#6) and
[expressions-tasks.md](expressions-tasks.md) (#3). There is no logical dependency in either
direction — only a merge-conflict one, since all three plans edit `pulse_types.py` and
`channel_ops.py`. Running this last means `StepPulse.amplitude` is declared once, with the alias
that is current by then, instead of being widened afterwards. Plan §1.

**Run them in numeric order.** Each task assumes every lower-numbered task is complete and
committed. Each leaves the tree green.

---

## Common preamble — paste into every session

> **Environment.** `conda activate eq1_pulse-dev` before running anything. If the prompt does not
> show `(eq1_pulse-dev)`, activation did not happen.
>
> **Conventions.** Follow `.github/copilot-instructions.md`. Load-bearing points: ReST docstrings
> (`:param:` / `:return:` / `:raises:`, no `:type:` where the annotation says it); blank lines must
> be **completely** empty; no trailing whitespace anywhere; max 2 consecutive blank lines at top
> level, 1 inside a function; 120-column lines; `X | Y` inside `isinstance()`, never a tuple;
> aligned pipes in markdown tables. Models inherit from the bases in `models/base_models.py`.
>
> **Alias check.** Before declaring any new field, look at what the neighbouring fields in the same
> file use — `ValueRef` if #3 has landed, `SymbolRef` if only #6 has, `VariableRef` if neither.
> Match them. Do not introduce a fourth spelling.
>
> **Verify.** `./qa/run_all_qa.sh` (pyright + mypy + pytest with coverage). It must pass before you
> report done. If it passed before your change and fails after, you are not done.
>
> **Context.** Read `docs/plans/additional-pulse-types-plan.md` — the sections named in your task —
> before starting. Do not re-litigate decisions recorded there; §2 and §7 list the closed ones.
>
> **Scope.** Do only what your task says. Each task lists an explicit *out of scope* set. If you
> believe a listed exclusion is wrong, say so in your final message rather than acting on it.

---

## Dependency graph

```text
1 ──> 2 ──> 3 ──> 4
```

Strictly sequential, but small. Safe merges if you want fewer sessions: **1 + 2** and **3 + 4**. The
whole plan fits in two sessions that way.

| #  | Task                                              | Size | Model     | Reasoning | Context     | Touches                                    |
| -- | --------------------------------------------------- | ---- | --------- | --------- | ----------- | -------------------------------------------- |
| 1  | Pulse base refactor; `StepPulse`; trigger pulse   | M    | Sonnet 5  | high      | 200k / ~45k | `models/pulse_types.py`, `tests/`            |
| 2  | `WaitForTrigger`                                  | S    | Sonnet 5  | medium    | 200k / ~30k | `models/channel_ops.py`, `tests/`            |
| 3  | Builder: three new functions                      | S    | Sonnet 5  | medium    | 200k / ~35k | `builder/`, `tests/`                         |
| 4  | Schema, docs, example                             | S    | Haiku 4.5 | medium    | 200k / ~25k | `utilities/`, `docs/`, `examples/`, `tests/` |

### Legend

The four columns are chosen **independently**. In particular, size does not imply reasoning level: a
small task with a silent failure mode gets `high`, a large mechanical one gets `medium`.

| Column        | Value      | Means                                                                                                              |
| --------------- | ------------ | -------------------------------------------------------------------------------------------------------------------- |
| **Size**      | S          | One or two source files plus their tests. A shape already in the tree to copy from.                                |
|               | M          | Three to six files including tests, or one file plus a change that ripples through its callers.                    |
|               | L          | A new module, or an edit spanning most of `models/`. Expect to want a second pass over your own output before QA is green. |
| **Reasoning** | medium     | Mistakes are **loud** — wrong code fails pyright, mypy, or an existing test immediately.                           |
|               | high       | Mistakes are **silent** — wrong code type-checks and passes the existing tests while being subtly wrong: a smart union resolving to the wrong member, a serializer quietly dropping a field, a model that degraded to `dict`. |
| **Model**     | Haiku 4.5  | The acceptance criteria are a checklist. Nothing to design.                                                        |
|               | Sonnet 5   | Ordinary model or builder work, with an in-tree pattern to follow.                                                 |
|               | Opus 5     | Silent failure mode **and** no in-tree precedent to copy.                                                          |
| **Context**   | `w / s`    | `w` is the window to run with; `s` is roughly what should be resident — the named plan sections, the files listed, their tests. If a session approaches its `s` figure, it has loaded files it was not asked to touch. |

Size is a budget, not a schedule. It says how much of a session the task consumes, so that two `S`
tasks can reasonably be merged and an `L` one should not be.

**Why these assignments.** Task 1 is the clearest case of size and reasoning diverging: it moves one
required field between base classes, which is a handful of lines, but getting it wrong makes
`amplitude` optional on four existing models — still type-checks, still passes most tests. Hence `M`
with `high`. There is an in-tree pattern for everything it does, so Sonnet rather than Opus. Task 4
is checklist work. Everything here fits the 200k standard window with room to spare.

---

## Task 1 — Pulse base refactor, `StepPulse`, `DigitalTriggerPulse`

**Read:** plan §3.1, §3.2, §3.3, §3.4, and §7 Q1.
**Goal:** two new pulse types exist and the four existing ones are provably unchanged.

### Steps

1. **Before touching anything**, grep for `.amplitude` across `src/`, `tests/`, `examples/` and
   `docs/`. Any site that takes a `PulseBase` and reads `.amplitude` will still type-check but is
   now unsound. This is the one silent breakage the refactor can cause; report what you find even if
   nothing needs changing.

2. In `models/pulse_types.py`, split `PulseBase`: it keeps `duration`, and a new
   `AnalogPulseBase(PulseBase)` carries `amplitude`. Re-parent `SquarePulse`, `SinePulse`,
   `ExternalPulse` and `ArbitrarySampledPulse` onto `AnalogPulseBase`.

   **Nothing about those four changes on the wire or in their constructor signatures.** Their
   `TYPE_CHECKING` `__init__` overloads already spell out full signatures and need no edit.

3. Add `StepPulse(AnalogPulseBase)` with `pulse_type: Literal["step"] = "step"` and **no new
   fields**. Its docstring is the whole model — plan §3.2 lists the three things it must say, and
   the ASCII diagram there is worth reproducing:

   - the amplitude is reached instantaneously at the start, no ramp;
   - the level **persists** past the pulse and becomes the channel's new base level;
   - `duration` is how long the step **occupies the channel**, not how long the level lasts — it
     exists so the next operation on the channel is ordered after it. This is what distinguishes a
     step from a `SquarePulse` with the same duration and amplitude, and a reader cannot infer it.

4. Add `DigitalTriggerPulse(PulseBase)` with `pulse_type: Literal["trigger"] = "trigger"`. `duration`
   inherited, no amplitude. Docstring: the line is high for `duration` and returns low afterwards.

5. Extend the `PulseType` union with both, and `pulse_types.__all__` (sorted) with both plus
   `AnalogPulseBase`.

6. Add `"AnalogPulseBase"` to `excluded_base_classes` in `utilities/openapi_generator.py`.

7. Tests in `tests/eq1lab_pulse/models/test_pulse_types.py`:
   - both new pulses construct, round-trip, and discriminate on `pulse_type`;
   - `DigitalTriggerPulse(duration="100ns", amplitude="1V")` **raises** — `extra="forbid"` gives
     this for free, so assert it rather than assuming it;
   - `SquarePulse` still requires `amplitude` (assert the `ValidationError` when it is omitted);
   - all four existing pulses serialize byte-identically to before — write this as explicit literal
     comparisons, not round trips.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- The four "unchanged serialization" assertions are present and passing.
- The `.amplitude` grep result is reported in your final message.

### Out of scope

`WaitForTrigger` (task 2). Any builder change. Any channel-op change.

---

## Task 2 — `WaitForTrigger`

**Read:** plan §3.5, §2, and §7 Q2/Q3.
**Goal:** the operation exists in the model and the `ChannelOp` union.

### Steps

1. In `models/channel_ops.py`, add `WaitForTrigger(ChannelOpBase)` with
   `op_type: Literal["wait_for_trigger"] = "wait_for_trigger"` and **no fields of its own** —
   `channel` is inherited and *is* the trigger line.

2. The docstring must cover:
   - the channel must be a digital input line (nothing in the IR enforces that; the target's
     hardware configuration does);
   - the operation blocks **its own channel's** timeline until the line goes high. It is **not** a
     barrier — other channels continue independently;
   - to make several channels wait on one trigger: `barrier(...)` then `wait_for_trigger(...)` on
     each. Mirror the phrasing `Wait` already uses for the `delay` decomposition — that docstring is
     the house style for this kind of note.

3. Extend the `ChannelOp` union and `channel_ops.__all__` (sorted).

4. Tests in `tests/eq1lab_pulse/models/test_channel_ops.py`: constructs from a channel string and a
   `ChannelRef`; round-trips; discriminates inside `ChannelOp`. Plus one in
   `tests/eq1lab_pulse/models/test_sequence.py`: a sequence containing a step pulse, a trigger pulse
   and a `WaitForTrigger` round-trips through JSON.

### Acceptance

- `./qa/run_all_qa.sh` passes.

### Out of scope

A `timeout` field. An `edge` field. Both were considered and declined — plan §2 and §7 Q6.

---

## Task 3 — Builder: `step_pulse`, `trigger_pulse`, `wait_for_trigger`

**Read:** plan §4.
**Goal:** the three operations are reachable from the builder.

### Steps

1. In `builder/_factories.py`, add `step_pulse(*, duration, amplitude)` and
   `trigger_pulse(*, duration)`, modelled on `square_pulse` — same `_validate_or_pass_through`
   plumbing, same docstring shape including an `Examples` block.

2. In `builder/core.py`, add `wait_for_trigger(channel)`, modelled on `barrier` — the
   `_current_context` / `_in_sequence` / `_add_to_sequence` dance, no schedule params.

3. Export all three from `builder/__init__.py` (import list and `__all__`, sorted). `step_pulse` and
   `trigger_pulse` are context-free factories and are therefore visible to the experimental schedule
   builder for free; **do not** add `wait_for_trigger` to `builder/experimental/`.

4. Tests in `tests/eq1lab_pulse/test_builder.py`: each function's happy path; `wait_for_trigger`
   outside a sequence context raises `RuntimeError`; `trigger_pulse` rejects an `amplitude` keyword.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `builder.__all__` is sorted and contains `step_pulse`, `trigger_pulse`, `wait_for_trigger`.
- The plan's §5 example runs end to end.

### Out of scope

Docs and the example file (task 4).

---

## Task 4 — Schema, docs, example

**Read:** plan §5, §6.
**Goal:** the three additions are visible in the generated schema and documented.

### Steps

1. `tests/test_openapi_generator.py` — `StepPulse`, `DigitalTriggerPulse` and `WaitForTrigger` are
   in `components.schemas`; `AnalogPulseBase` is not.

2. `examples/trigger_and_step.py` — the plan's §5 example, made runnable. Check how
   `tests/test_examples.py` discovers examples before assuming it picks the file up.

3. `docs/source/user_guide/builder_guide.rst` — extend the pulse-types material with the step pulse
   (emphasising the persistent level) and the digital trigger pulse / wait-for-trigger pair. Keep it
   to the same depth as the surrounding pulse documentation.

4. Build the docs (`cd docs && ./generate_html.sh`) and confirm no new Sphinx warnings.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `python -m eq1_pulse.utilities.openapi_generator` runs and the three models appear.
- Docs build clean.

### Out of scope

Any model or builder change. If something is missing, report it rather than adding it here.
