# Plan: step pulse, digital trigger pulse, wait-for-trigger

**Issue:** [#5 — Additional pulse types in the model.](https://github.com/equal1/eq1_pulse/issues/5)
**Status:** accepted — all open questions closed (§7); see
[additional-pulse-types-tasks.md](additional-pulse-types-tasks.md) for the execution breakdown
**Date:** 2026-08-21
**Predecessors:** independent of [symbols-and-parameters-plan.md](symbols-and-parameters-plan.md) (#6)
and [expressions-plan.md](expressions-plan.md) (#3) in substance, but if run after them its new
fields must use the widened `ValueRef` alias rather than `VariableRef`. See §1.

---

## 0. What the issue asks for

| # | Requirement                                                                                                              |
| - | -------------------------------------------------------------------------------------------------------------------------- |
| 1 | **Step pulse** (amplitude, duration): amplitude changes instantaneously at the start and *changes the base level for subsequent pulses* |
| 2 | **Digital trigger pulse** (duration): sets a digital trigger line high for the duration                                     |
| 3 | **Wait for trigger** (trigger_line): pauses the sequence until a digital trigger line goes high                             |

Small in surface area, but requirement 2 does not fit the existing pulse hierarchy (§3.1) and
requirement 1 leaves the meaning of `duration` open (§7 Q1, now closed).

---

## 1. Ordering against #6 and #3

This plan touches `pulse_types.py` and `channel_ops.py` — the same files #6 widens. There is no
logical dependency in either direction, only a merge-conflict one.

**Run it last.** Then `StepPulse.amplitude` and `WaitForTrigger`'s fields are declared with whatever
alias is current (`ValueRef` after #3, `SymbolRef` after #6, `VariableRef` if run first), and no
field has to be revisited. If it is run first instead, its new fields join the §2 read-site
inventory in the #6 plan and are widened along with everything else — also fine, just more edits.

The `PulseBase` refactor in §3.1 is the one piece that genuinely conflicts: it moves `amplitude`
between classes, and #6 widens `amplitude`. Doing that once, after #6, is strictly less work.

---

## 2. Scope and framing decisions

| Decision                                                                     | Consequence                                                                                                                        |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| **A trigger line is a `ChannelRef`.**                                        | The schedule-isolation plan settled that "a channel is a `(port, clock)` pair"; a digital output line is such a pair with a trivial clock. Introducing a parallel `TriggerLineRef` namespace would need its own declaration, its own builder factory, and its own resolution rules for no gain. Consequence: `DigitalTriggerPulse` is played with `play()` on the trigger channel, and `WaitForTrigger` derives from `ChannelOpBase`. |
| **`PulseBase` loses `amplitude`; a new `AnalogPulseBase` gains it.**          | A digital trigger pulse has no amplitude. Making `amplitude` optional on `PulseBase` instead would make it optional on `SquarePulse` too, weakening four existing models to accommodate one new one. See §3.1. |
| **`StepPulse` is a pulse, not a `SetAmplitude` channel op.**                 | The issue says "pulse types … added to the pulse model", and a step has a duration, so it occupies the channel like any other pulse. Its persistence is documented semantics, not a different model kind. |
| **No `timeout` on `WaitForTrigger`.**                                        | Not asked for. A trigger that never arrives hangs the sequence; that is the operation's nature and the backend's problem. |
| **A `StepPulse` occupies its channel for `duration`; the level persists past it.** | `duration` is the reservation, not the lifetime of the level. Following operations on the channel are ordered after it and are relative to the *new* base level. §3.2. |
| **`WaitForTrigger`'s channel field is spelled `channel`.**                   | Inherited from `ChannelOpBase` like nine other channel ops. Consistency beats matching the issue's prose word `trigger_line`; the docstring carries the meaning. |

---

## 3. Model changes

### 3.1 Restructuring the pulse base

Today:

```text
PulseBase(_LeanModel)              duration, amplitude
├── SquarePulse
├── SinePulse
├── ExternalPulse
└── ArbitrarySampledPulse
```

After:

```text
PulseBase(_LeanModel)              duration
├── AnalogPulseBase                + amplitude
│   ├── SquarePulse                (unchanged fields)
│   ├── SinePulse                  (unchanged fields)
│   ├── ExternalPulse              (unchanged fields)
│   ├── ArbitrarySampledPulse      (unchanged fields)
│   └── StepPulse                  pulse_type="step"
└── DigitalTriggerPulse            pulse_type="trigger"
```

**Nothing about the four existing pulses changes on the wire or in their constructor signatures.**
`amplitude` is still required on each of them; it is simply inherited from one level further down.
The `TYPE_CHECKING` `__init__` overloads on each concrete class already spell out their full
signatures, so they need no edit at all.

`AnalogPulseBase` is added to `openapi_generator.excluded_base_classes` next to `PulseBase`.

An `isinstance(p, PulseBase)` check anywhere in the codebase keeps working; an
`isinstance(p, PulseBase)` that *assumes* `.amplitude` does not. Grep for `.amplitude` before
starting — this is the one silent breakage the refactor can cause.

### 3.2 `StepPulse`

```python
class StepPulse(AnalogPulseBase):
    pulse_type: Literal["step"] = "step"
```

No new fields — `duration` and `amplitude` are inherited and are exactly what the issue specifies.
The entire content of this model is its docstring, which must state:

- The amplitude is reached instantaneously at the start (no ramp).
- The level **persists** past the pulse: it becomes the channel's new base level, which subsequent
  pulses on that channel are relative to.
- `duration` is how long the step **occupies the channel**, not how long the level lasts. The level
  outlives the pulse; the duration exists so that the next operation on the channel is correctly
  ordered after it. Spell this out — it is the one thing a reader cannot infer, and it is what
  distinguishes a step from a square pulse of the same duration and amplitude.

```text
amp
     ┌──────────────────────────────
     │
─────┘
     |<-dur->|
             ^ next operation starts here, relative to the new base level
```

### 3.3 `DigitalTriggerPulse`

```python
class DigitalTriggerPulse(PulseBase):
    pulse_type: Literal["trigger"] = "trigger"
```

`duration` inherited; no amplitude. Played on a channel that is a digital output line. The docstring
states that the line is high for `duration` and returns low afterwards.

### 3.4 `PulseType` union

```python
type PulseType = Annotated[
    SquarePulse | SinePulse | ExternalPulse | ArbitrarySampledPulse | StepPulse | DigitalTriggerPulse,
    Discriminator("pulse_type"),
]
```

### 3.5 `WaitForTrigger`

```python
class WaitForTrigger(ChannelOpBase):
    op_type: Literal["wait_for_trigger"] = "wait_for_trigger"
```

`channel` is inherited from `ChannelOpBase` and *is* the trigger line. The issue names the field
`trigger_line`; §2 makes it a channel, so it is spelled `channel` like every other channel op — the
docstring says that the channel must be a digital input line. A pydantic alias exposing it as
`trigger_line` was considered and rejected: it would make this the only channel op whose channel is
spelled differently, in the model, the schema and the builder.

Added to the `ChannelOp` union.

**Semantics to document:** the operation blocks *its own channel's* timeline until the line goes
high. It is not a barrier — other channels continue independently. If several channels must wait for
one trigger, that is `barrier(...)` followed by `wait_for_trigger(...)` on each, mirroring the
`delay` decomposition already documented on `Wait`.

---

## 4. Builder

| Function                                    | Module          | Notes                                                       |
| --------------------------------------------- | ----------------- | ------------------------------------------------------------- |
| `step_pulse(*, duration, amplitude)`        | `_factories.py` | Sibling of `square_pulse`. Same validation plumbing.        |
| `trigger_pulse(*, duration)`                | `_factories.py` | Sibling of `square_pulse`, no amplitude.                    |
| `wait_for_trigger(channel)`                 | `core.py`       | Sibling of `barrier`. Sequence-context check, add to sequence. |

All three added to `builder/__init__.py`'s import list and `__all__`, kept sorted. `step_pulse` and
`trigger_pulse` are context-free factories and are therefore also visible to the experimental
schedule builder for free; `wait_for_trigger` is a `core.py` operation and is **not** added to the
experimental builder, consistent with how #6 treats its new operations.

---

## 5. Example

```python
from eq1_pulse.builder import *

with build_sequence() as seq:
    # Move the DC bias to a new operating point and leave it there.
    play("plunger", step_pulse(duration="1us", amplitude="150mV"))

    # Tell external instrumentation to start, then block until it acknowledges.
    play("trig_out", trigger_pulse(duration="100ns"))
    wait_for_trigger("trig_in")

    play("q0_drive", square_pulse(duration="25ns", amplitude="80mV"))
```

---

## 6. Tests

| File                                              | Add                                                                                     |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `tests/eq1lab_pulse/models/test_pulse_types.py`   | `StepPulse` / `DigitalTriggerPulse` construct, round-trip, discriminate by `pulse_type`; `DigitalTriggerPulse` **rejects** `amplitude` (`extra="forbid"` makes this automatic — assert it); all four existing pulses unchanged |
| `tests/eq1lab_pulse/models/test_channel_ops.py`   | `WaitForTrigger` constructs and round-trips; appears in the `ChannelOp` union             |
| `tests/eq1lab_pulse/models/test_sequence.py`      | a sequence containing all three round-trips                                               |
| `tests/eq1lab_pulse/test_builder.py`              | the three new builder functions; `wait_for_trigger` outside a sequence context raises      |
| `tests/test_openapi_generator.py`                 | the three new models present; `AnalogPulseBase` absent                                    |

---

## 7. Decisions closed

| #  | Question                                                        | Decision                                                                                                                                              |
| -- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q1 | What does `duration` mean on a `StepPulse`?                     | **It occupies the channel for `duration`; the level persists past the end.** Consistent with both halves of the issue text. Rejected: `duration` as a settle/ramp time (contradicts "instantaneously"); a level that returns to baseline afterwards (contradicts "changes the base level for subsequent pulses", and is what `SquarePulse` already does). |
| Q2 | `WaitForTrigger.channel` or `.trigger_line`?                    | **`channel`,** inherited from `ChannelOpBase`. The docstring says it must be a digital input line.                                                     |
| Q3 | Is a trigger line really a `ChannelRef`?                        | **Yes.** A channel is a `(port, clock)` pair (schedule-isolation plan §0); a digital line is one with a trivial clock. A parallel reference kind would need its own declaration, factory and resolution rules for no gain. Revisit only if trigger lines need attributes channels lack. |
| Q4 | Does `StepPulse` need a "return to zero" counterpart?           | **No.** `step_pulse(duration=..., amplitude=0)` is the return to zero.                                                                                 |
| Q5 | Should `DigitalTriggerPulse` be a pulse or a `SetDigital` op?   | **A pulse,** as the issue asks. A duration-carrying thing played on a channel is a pulse in this IR.                                                    |
| Q6 | Does `wait_for_trigger` need edge/level selection?              | **No.** The issue says "until … goes high". Add `edge: Literal["rising", "falling"]` only when hardware needs it — an added optional field breaks nothing. |

### Deliberately not decided here

- **How a channel is marked digital.** Nothing in the IR distinguishes a digital line from an analog
  one; that lives in the target's hardware configuration, same as every other channel property.
  Playing a `SquarePulse` on a trigger line is not rejected by this plan.
