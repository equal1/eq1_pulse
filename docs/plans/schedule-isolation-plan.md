# Plan: isolate `Schedule`, unify on `OpSequence`, add the opaque `ExternalBlock`

**Status:** accepted — see [schedule-isolation-tasks.md](schedule-isolation-tasks.md) for the execution breakdown
**Date:** 2026-08-20
**Background:** [../research/openpulse-alignment-assessment.md](../research/openpulse-alignment-assessment.md)

---

## 0. Scope and framing decisions

These were settled before this plan and constrain everything below.

| Decision                                    | Consequence                                                                                                                     |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Direction is *consume* OpenPulse, not produce it.** | We must be able to *represent everything OpenPulse can say*. We do not need to be a subset of it, and constructs with no OpenPulse counterpart (`Store`, `CompensateDC`, `time_of_flight`, physical amplitude units) are fine as supersets. |
| **`Schedule` becomes disconnected and unused.** | Moved to an experimental module, dropped from the public `models` and `builder` namespaces, warned on, and moved to an `experimental` tag in the generated schema and a separate docs page. Not deleted yet. |
| **Schedule and sequence models must not mix.** | No container of one kind may hold the other; the builder may not nest one inside the other; the flat `eq1_pulse.models` namespace stops re-exporting schedule names. |
| **A `Channel` is a `(port, clock)` pair carrying its own frame implicitly.** | The flat-channel gaps in the research assessment are answered by *declaring more channels*, not by adding a frame object. A channel-mapping representation that resolves channels onto shared ports is **future work**. |
| **All clocks are NCOs synchronised to one global clock.** | Every channel is mutually phase-coherent. Phase relationships never need explicit modelling; `SetPhase`/`ShiftPhase` are per-channel and well-defined. |
| **Virtual channels absorb baseband and gate-virtualisation mappings.** | Primary use case: capacitive-coupling compensation. A virtual channel fans out to physical outputs through a mapping that lives in the (future) channel-mapping representation, not in the program IR. |
| **Add a timed/flex `ExternalBlock` with opaque contents.** | An external-program reference plus the set of channels it claims. This is the seed of OpenQASM `box` and the thing that makes OpenPulse `box` consumable at all. |

### What "consume, not produce" changes about the assessment

Several findings in the research assessment were framed as export problems. Re-read in the
consume direction:

| Assessment finding                                             | Re-read for consumption                                                                                                  |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `Store`, `CompensateDC`, `Record.time_of_flight` have no OpenPulse counterpart | **Non-issue.** Purely additive. Nothing to lower.                                                                    |
| Physical amplitude units vs normalised envelopes               | **Non-issue.** Physical units are a staple of the representation and stay. A hardware profile is an assumed precondition of the target, not a missing artefact; importing an OpenPulse `gaussian(0.2, ...)` consults it to turn `0.2` into volts. |
| Ramped square / chirped sine have no OpenPulse template        | **Reversed.** The question becomes: can we *absorb* `gaussian`, `drag`, `sech`, `gaussian_square`? Yes — `ExternalPulse(function=..., params=...)` is exactly that. Confirm coverage in Phase 4. |
| No `box` / `stretch` / `durationof` in eq1_pulse               | **Now blocking.** A `Schedule` cannot consume an OpenPulse program at all. `OpSequence` can consume `play`/`capture`/`delay`/`barrier` today; `box` is the first thing it cannot. Hence §3. |
| `Wait` multi-channel semantics "conflict"                      | **Dissolved.** `delay[d] a, b;` imports as `barrier(a, b); wait(a, b, d)` — equivalent, because after the barrier both cursors are equal. Exporting `wait(a, b, d)` emits one `delay` per channel. `Wait` is the more primitive operation; OpenQASM's multi-resource `delay` is the composite. Documentation only — see §4. |

---

## 1. Current coupling to be broken

Measured on `hp-peti/builder-interface`:

| Site                                       | Coupling                                                                                                       |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| `models/__init__.py`                       | `from .schedule import *`, and `_schedule.__all__` is first in the aggregate `__all__`.                        |
| `models/schedule.py`                       | Imports `ChannelOp`, `DataOp`, and the `control_flow` bases. Defines `RefPt`, `RelTime`, `ScheduledOperation`, `Schedule`, `SchedRepetition`, `SchedIteration`, `SchedConditional`. |
| `builder/core.py`                          | ~300 schedule references. `BuilderContext = SequenceContext \| ScheduleContext`; every public operation takes `**schedule_params` and returns `OperationToken \| None`; `_in_schedule` / `_in_sequence` dispatch appears in every one. |
| `builder/utils.py`                         | `OperationToken`, `ScheduleParams`, `SCHEDULE_PARAM_NAMES`, `resolve_schedule_params` — entirely schedule-side. |
| `builder/__init__.py`                      | Re-exports `build_schedule`, `sub_schedule`, `nested_schedule`, `add_block`, `ScheduleBlock`, `ScheduleParams`, `OperationToken`, `resolve_schedule_params`. |
| `utilities/openapi_generator.py`           | `"schedule"` in `model_modules`; the `sequences` tag description reads "Operation sequences and schedules".    |
| `BuilderState.unconsumed_blocks`           | Exists solely for `@nested_schedule` / `add_block`. Sequence builds carry the bookkeeping for nothing.          |
| Tests                                      | `models/test_schedule.py` (78 refs), `test_builder.py` (165), `test_schedule_params_validation.py` (60), `test_builder_context_matrix.py` (34), `test_builder_state_isolation.py` (15), `test_variable_tracking.py` (8), `test_builder_variable_verification.py` (7). |
| Examples / docs                            | `examples/sub_schedule_example.py`, `examples/nested_decorator_example.py`, `docs/source/examples/sub_schedule_examples.rst`, `docs/source/_generator/{schedule,schedule_refop,nested_schedule}_diagram.py`, `builder_guide.rst`, `introduction.rst`, `index.rst`. |

### Where the boundary goes

Not everything shared is "mixing". The split is:

| Layer                                                                             | Shared?    | Rationale                                                                     |
| --------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------- |
| `base_models`, `basic_types`, `units`, `nd_array`, `complex`, `arithmetic`, `identifier_str`, `reference_types`, `pulse_types` | **shared** | No timing semantics. Duplicating them would be strictly worse.                |
| Leaf operations: `channel_ops` (`Play`, `Wait`, `Barrier`, …), `data_ops`          | **shared** | Timing-free. A `Play` is a `Play` in either world.                            |
| `control_flow` abstract bases (`SequenceBase`, `RepetitionBase`, `IterationBase`, `ConditionalBase`) | **shared** | Generic over the body type; that is the entire point of the parameterisation. |
| Containers, unions, control-flow concretisations, timing types                     | **split**  | `OpSequence`/`Repetition`/`Iteration`/`Conditional`/`ExternalBlock` stay; `Schedule`/`ScheduledOperation`/`RefPt`/`RelTime`/`Sched*` move out. |
| Builder public API                                                                 | **split**  | Two independent function sets over one shared context stack.                   |
| Builder context-free helpers (pulse factories, `phase()`, `var()`, validation)      | **shared** | They never touch the context stack.                                            |

The experimental schedule module may import shared leaves downward. Nothing in the sequence
world may import from the experimental module. Enforced by a test (§6, gate G3).

---

## 2. Target layout

```text
src/eq1_pulse/
  models/
    __init__.py              # sequence world only; schedule names NOT re-exported
    base_models.py           # unchanged (shared)
    basic_types.py           # unchanged (shared)
    channel_ops.py           # shared leaves; Wait docstring note only (§4)
    control_flow.py          # shared abstract bases
    data_ops.py              # unchanged (shared)
    pulse_types.py           # unchanged (shared)
    reference_types.py       # unchanged (shared)
    sequence.py              # OpSequence, Repetition, Iteration, Conditional
    external_block.py        # NEW: ExternalBlock (§3)
    experimental/
      __init__.py            # warns on import; not re-exported by models
      schedule.py            # Schedule, ScheduledOperation, RefPt, RelTime, Sched*

  builder/
    __init__.py              # sequence builder only
    _state.py                # BuilderState, context stack, variable tracking, op counter
    _factories.py            # context-free: pulse factories, phase(), var(), channel(),
                             # pulse_ref(), integrations, validation helpers, range conversion
    core.py                  # sequence-only public API; no ScheduleParams, no OperationToken
    experimental/
      __init__.py            # warns on import
      schedule.py            # build_schedule, sub_schedule, repeat/for_/if_, play/wait/...,
                             # ScheduleBlock, nested_schedule, add_block
      utils.py               # OperationToken, ScheduleParams, resolve_schedule_params
```

`builder/utils.py` is emptied and removed; its contents move to `builder/experimental/utils.py`.

### The shared context stack is the enforcement point

Both builders use `builder/_state.py`. That is deliberate: a single stack lets each builder
*reject* the other's contexts with a clear error rather than silently producing a mixed model.
Context-kind detection uses a `ClassVar` marker (`_context_kind = "sequence"` or `"schedule"`)
rather than runtime `isinstance` checks against concrete schedule classes. `_state.py` can therefore
understand both semantics without importing the experimental model tree or triggering its warning;
concrete context imports are permitted only under `TYPE_CHECKING`.

```python
# in builder/core.py (sequence side)
context = _current_context("play()")
if not _in_sequence(context):
    raise RuntimeError(
        "play() from eq1_pulse.builder requires a build_sequence() context. "
        "Schedules use eq1_pulse.builder.experimental."
    )
```

and symmetrically on the schedule side. `build_schedule()` inside a live sequence context, or
`build_sequence()` inside a live schedule context, raises.

---

## 3. New model: the timed/flex `ExternalBlock`

### Purpose

A single operation that reserves a set of channels for a contiguous span whose contents the IR
does not describe. It is simultaneously:

- the way to reference an externally defined program (a calibrated gate, a vendor routine, a
  hand-written OpenPulse `defcal`);
- the scoping construct needed to *consume* OpenQASM `box`;
- the mechanism that makes a multi-channel operation atomic against the surrounding scheduler
  (the seed of a proper `measure`).

### Sketch

```python
class ExternalBlock(OpBase):
    """An opaque, channel-reserving block of externally defined contents."""

    op_type: Literal["external_block"] = "external_block"

    program: FullyQualifiedIdentifier | None = None
    """Reference to an externally defined program supplying the contents.

    Spelled as a fully-qualified identifier for consistency with
    :attr:`ExternalPulse.function`."""

    channels: dict[str, ChannelRef]
    """Channels claimed by the block, keyed by the role each plays in the
    referenced program. The reservation set is exactly ``channels.values()``."""

    params: dict[str, ExternalParamValue] | None = None
    """Input arguments passed to the referenced program."""

    results: dict[str, VariableRef] | None = None
    """Output bindings: variables the referenced program writes into."""

    duration: Duration | VariableRef | None = None
    """Total duration. :obj:`None` means *flex*: the duration is whatever the
    referenced program naturally takes, and must be resolved before execution."""
```

### Semantics (to be written into the model docstring verbatim)

1. **Reservation.** The block occupies every channel in `channels` for its whole extent. No
   operation elsewhere in the program may be scheduled on any of those channels within that
   extent.
2. **Synchronisation.** Entry and exit are synchronisation points across `channels`: the block
   starts at the latest availability of all of them and all of them become free simultaneously
   at its end. (Same rule as OpenQASM `box` resource participation and `defcal` entry alignment.)
3. **Non-interference.** Channels *not* listed are unaffected and may be driven concurrently.
4. **Opacity / optimisation barrier.** Contents are not described by this IR. Operations may not
   be moved into or out of the block. Nothing may be assumed about what happens on the reserved
   channels inside it.
5. **Timed vs flex.**
   - `duration=D` — hard total-duration constraint. It is an error if the referenced program's
     natural duration exceeds `D`. Slack placement inside the block is the program's business.
   - `duration=None` — flex. Duration is the referenced program's natural duration, resolved by
     whatever holds the program definitions. Directly analogous to OpenQASM's untimed `box` and
     to `durationof`.
6. **Empty `program`.** `program=None` with a `duration` is a pure reservation — "these channels
   are busy for this long, do not touch them." Useful for modelling externally driven intervals.

### Parameters

`ExternalPulse` already takes `params: dict[str, PulseParamValue] | None`, so passing values into
an external entity is an established pattern. `ExternalBlock` needs three things that pattern does
not currently cover.

#### 1. Channel roles, not just a reservation set

A flat `channels: list[ChannelRef]` says *which* channels are busy but not *what each is for*. An
external `measure` program needs to know which of its two channels is the drive and which is the
readout. Two ways to express it:

| Option                                                                | Assessment                                                                                              |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `channels: list[ChannelRef]` for reservation, plus `ChannelRef` allowed inside `params` for roles | Two sources of truth. Nothing stops a channel being passed as a parameter without being reserved. |
| **`channels: dict[str, ChannelRef]`** — keys are roles, values are the reservation set | **Recommended.** One source of truth; an unreserved channel argument becomes unrepresentable. |

The builder should still accept the positional form when roles do not matter, generating
placeholder keys, so the simple case stays terse.

#### 2. Inputs versus outputs

A block can write results. `Record`, `Discriminate`, and `Store` all name their target variable in
a dedicated field precisely so the write is visible to the builder's declared-variable tracking and
to any later dependency analysis. Burying a written variable inside a generic `params` dict would
hide it from exactly that machinery.

Hence the split: `params` for inputs, `results` for outputs. A `VariableRef` appearing in `params`
is read; a `VariableRef` in `results` is written and must be declared in an enclosing scope, under
the same rule `record()` already enforces.

`ExternalPulse` needs no `results` — a pulse produces a waveform, not data.

#### 3. One shared parameter value type

A block plausibly wants to pass things a pulse does not: a `Phase`, a `Magnitude`/`Threshold`, a
`bool`, a `PulseRef` or an inline `PulseType` (a gate block parameterised by its drive pulse).
The implemented shared type is conceptually:

```python
type ExternalParamScalarValue = bool | float | int | complex_from_tuple | str
type ExternalParamValue = Annotated[
  Amplitude | Duration | Frequency | Phase | Magnitude
  | _TaggedVariableRef | _TaggedPulseRef | PulseType
  | ExternalParamScalarValue,
  BeforeValidator(_coerce_dimensional_string),
]
```

`ExternalPulse.params` and `ExternalBlock.params` both use the full `ExternalParamValue` type.
`PulseParamValue`, `PulseParamValueLike`, and `PulseParamScalarValue` remain deprecated aliases for
backwards compatibility.

The pre-validator is required because Pydantic's smart-union resolution would otherwise prefer the
exact `str` branch: `"10us"` becomes a `Duration`, while `"foo"` stays a `str`. Explicit
`VariableRef` and `PulseRef` values serialize as `{"var_ref": ...}` and `{"pulse_ref": ...}` so
they survive a JSON round-trip through a union that also accepts arbitrary strings. Complex values
use the JSON-safe `[real, imaginary]` representation. These forms are part of the wire contract and
are covered by round-trip tests.

#### 4. Interaction with flex duration

If `duration=None` (flex) **and** any `params` value is a `VariableRef` whose value is only known
at run time, the block's duration is not resolvable at compile time. OpenQASM has the same rule for
`defcal`: the body must have a definite duration *regardless of its parameters*. Either the
external program guarantees a parameter-independent duration, or the block must carry an explicit
`duration`. Make this a validation rule with a clear error, not a runtime surprise.

#### 5. No signature checking

The IR does not know the referenced program's signature — opacity is the point. Arity and type
checking of `params`/`results`/`channels` belongs to whatever resolves `program`. The IR validates
only what it can see: that `results` variables are declared, that `channels` values are valid
channel references, and rule 4 above.

### Placement

`ExternalBlock` joins the sequence-side unions:

```python
type DiscriminableOp = Annotated[
    ChannelOp | DataOp | ExternalBlock | Repetition | Iteration | Conditional, Discriminator("op_type")
]
```

It is deliberately **not** added to the experimental schedule unions. The schedule world is frozen.

### Builder surface

```python
with build_sequence() as seq:
    var_decl("m", "complex", unit="mV")

    # named channel roles, input params, output binding
    external_block(
        program="eq1.cal.measure",
        channels={"drive": "q0", "readout": "q0_ro"},
        params={"amp": "50mV", "tau": var("t")},
        results={"iq": var("m")},
    )

    # positional form when roles do not matter
    external_block("q0", "q1", program="eq1.cal.cz")       # flex duration

    # pure reservation
    external_block("q1", duration="1us")
```

### Deferred

Inline (non-opaque) block contents, `stretch`, alignment policies, and `durationof` are **out of
scope for this plan**. `ExternalBlock` is the minimum that unblocks OpenPulse consumption; the
assessment's §5 vocabulary is the follow-on.

One consequence of the name: if inline contents arrive later, they belong in a **sibling** model
(`Block`, carrying a body instead of a `program`) rather than as a mutation of this one, since an
`ExternalBlock` with inline contents would be a contradiction. Both would share the reservation
and timing semantics above.

---

## 4. `Wait` vs `delay` — documentation only

Not a semantic conflict. eq1_pulse's `Wait` is the *more primitive* operation; OpenQASM's
multi-resource `delay` conflates a barrier with a delay, and the composite decomposes exactly:

```text
import:   delay[d] a, b;   ->   barrier(a, b) ; wait(a, b, d)
export:   wait(a, b, d)    ->   delay[d] a;  delay[d] b;
```

The import identity holds because after `barrier(a, b)` we have `cursor(a) == cursor(b) == max(...)`,
so an independent per-channel wait lands both ends at `max(...) + d` — precisely the OpenQASM
semantics. The export identity holds because a single-resource `delay` advances only its own cursor.

**No model or behaviour change.** The task is a docstring note on `Wait` and in the `sequence.py`
module docstring recording both rules, so the difference in granularity is not rediscovered as a
bug later. Fold this into Phase 4 or Phase 5 rather than giving it a phase of its own.

---

## 5. Phases

Each phase is independently mergeable and leaves the tree green.

### Phase 1 — extract shared builder infrastructure (no behaviour change)

- Create `builder/_state.py`: move `BuilderState`, `_state`, `_get_state`, `_generate_op_name`,
  `_push_context`, `_pop_context`, `_current_context`, `_register_variable`,
  `_is_variable_declared`, `_check_variable_declared`.
- Create `builder/_factories.py`: move `phase`, `square_pulse`, `sine_pulse`, `external_pulse`,
  `arbitrary_pulse`, `full_integration`, `demod_integration`, `var`, `channel`, `pulse_ref`,
  `_validate_or_pass_through`, `_validate_explicit_variable_ref`, `_validate_variable_ref`,
  `_convert_range_to_model`.
- `core.py` imports from both. Public API byte-identical.
- **Gate:** full QA suite passes with zero test changes.

### Phase 2 — move the schedule models

- Create `models/experimental/` with `__init__.py` and `schedule.py`.
- Move `models/schedule.py` there unchanged, except: `SchedRepetition`/`SchedIteration`/
  `SchedConditional` keep using the shared `control_flow` bases (allowed, see §1).
- Remove `schedule` from `models/__init__.py` imports, star-imports, and `__all__`.
- Add a module-level warning banner to `models/experimental/__init__.py`.
- Leave a shim at `models/schedule.py` that re-exports from the new location with a
  `DeprecationWarning` on import, for one release.
- In `openapi_generator.py`, retarget rather than remove: `"schedule"` → `"experimental.schedule"` in
  `model_modules` (`importlib.import_module(f"eq1_pulse.models.{module_name}")` and the
  `obj.__module__.startswith("eq1_pulse.models")` filter both still work unchanged). Add an
  `{"name": "experimental", "description": "Unused / experimental models, subject to removal"}`
  tag, and drop "and schedules" from the `sequences` tag description.
- **Gate:** `from eq1_pulse.models import Schedule` fails;
  `from eq1_pulse.models.experimental.schedule import Schedule` works; the generated OpenAPI still
  contains the schedule schemas, and every component mapped from an experimental model carries
  `"tags": ["experimental"]` (including `-Input`/`-Output` variants when generated).

### Phase 3 — split the builder

- Create `builder/experimental/schedule.py` with the schedule-side public API: `build_schedule`,
  `sub_schedule`, `_sub_schedule_with_token`, `add_block`, `ScheduleBlock`, `nested_schedule`,
  schedule-flavoured `repeat`/`for_`/`if_`, and schedule-flavoured `play`/`wait`/`barrier`/
  `set_frequency`/`shift_frequency`/`set_phase`/`shift_phase`/`record`/`discriminate`/`store`/
  `var_decl`/`pulse_decl`/`measure`.
- Move `builder/utils.py` → `builder/experimental/utils.py`; delete the original.
- Strip `core.py`: remove `**schedule_params` from every signature, change return types from
  `OperationToken | None` to `None`, delete `_in_schedule`, `_add_to_schedule`,
  `_reject_schedule_params`, `ScheduleContext`, `_SCHEDULE_CONTEXT_TYPES`.
- Leave `BuilderState.unconsumed_blocks` in shared state; the sequence side never populates it.
  Every schedule context manager, including `repeat()`/`for_()`/`if_()`, rejects unconsumed nested
  `ScheduleBlock`s on normal exit after restoring the context stack.
- Add reciprocal rejection: sequence functions reject schedule contexts and vice versa;
  `build_schedule()` inside a live sequence context raises, and vice versa.
- Emit a single `FutureWarning` on `build_schedule()` entry — **not** per operation.
- Update `builder/__init__.py`: drop all schedule exports; rewrite the module docstring so it
  documents sequences only.
- **Gate:** `from eq1_pulse.builder import build_schedule` fails with a helpful message pointing
  at `eq1_pulse.builder.experimental`.

### Phase 4 — add `ExternalBlock`

- `models/external_block.py` with the model from §3 and the full semantics docstring.
- `ExternalParamValue` (and its `*Like` input alias) in `pulse_types.py`; use it for both
  `ExternalPulse.params` and `ExternalBlock.params`, retaining the old pulse aliases for
  compatibility. Pin down and test dimensional string pre-coercion, arbitrary strings, tagged
  references, and complex pairs.
- Add to `DiscriminableOp`; do **not** add to the schedule unions.
- `external_block(...)` builder function in `core.py`, named to pair with `external_pulse()`.
- Model tests: serialisation round-trip, discriminated-union dispatch, timed vs flex,
  `program=None` reservation, channel role mapping, `params` value-type coverage (including
  `"10us"`-becomes-`Duration` vs `"foo"`-stays-`str`), `results` binding.
- Validation tests: `results` variables must be declared in an enclosing scope; flex duration
  combined with a runtime-variable parameter is rejected with a clear message.
- Builder tests: nesting inside `repeat`/`for_`/`if_`/`sub_sequence`; rejection in a schedule
  context.
- New example + docs page.
- **Gate:** an OpenQASM `box[500ns] { ... }` on a known channel set has a faithful IR
  representation.

### Phase 5 — relocate tests, examples, docs

- `tests/eq1lab_pulse/models/test_schedule.py` → `tests/eq1lab_pulse/experimental/`.
- Split `test_builder.py`, `test_builder_context_matrix.py`, `test_schedule_params_validation.py`
  into sequence-side and experimental-side files. `test_schedule_params_validation.py` moves
  wholesale.
- Add a mixing-rejection test file (§6 G3, G4).
- `examples/sub_schedule_example.py` and the schedule half of `examples/nested_decorator_example.py`
  → `examples/experimental/`, with a header comment stating they exercise an unused API.
  `tests/test_examples.py` and `tests/test_documentation_examples.py` must still find them.
- `docs/source/examples/sub_schedule_examples.rst` and the schedule sections of
  `builder_guide.rst` / `introduction.rst` / `index.rst` → a single
  `docs/source/experimental/schedule.rst`, clearly labelled.
- `docs/source/_generator/{schedule,schedule_refop,nested_schedule}_diagram.py` move with it.
- Write the channel model assumptions (§0) into `docs/source/user_guide/introduction.rst` —
  they are currently unstated anywhere and are load-bearing for anyone reading the IR.
- Add the `Wait` <-> `delay` correspondence (§4) to the `Wait` and `sequence.py` docstrings.
- **Gate:** Sphinx builds clean; the main user guide contains no `build_schedule` reference.

---

## 6. Acceptance gates

| Gate  | Check                                                                                                                 |
| ----- | ----------------------------------------------------------------------------------------------------------------------- |
| **G1**| `eq1_pulse.models.__all__` contains no schedule name. `from eq1_pulse.models import Schedule` raises `ImportError`.    |
| **G2**| `eq1_pulse.builder.__all__` contains no schedule name — no `ScheduleParams`, `OperationToken`, `ScheduleBlock`, `build_schedule`, `sub_schedule`, `nested_schedule`, `add_block`, `resolve_schedule_params`. |
| **G3**| **Import-direction test:** no module under `models/` (excluding `models/experimental/`) or `builder/` (excluding `builder/experimental/`) imports from any `experimental` package. Implement by AST-walking the source tree. |
| **G4**| **Mixing-rejection test:** `build_schedule()` inside `build_sequence()` raises; `build_sequence()` inside `build_schedule()` raises; sequence `play()` inside a schedule context raises; experimental `play()` inside a sequence context raises. |
| **G5**| Generated OpenAPI still contains `Schedule`, `ScheduledOperation`, `RefPt`, `RelTime`, `Sched*`, now carrying the `experimental` tag; it also contains `ExternalBlock`. No schedule component is reachable from a non-experimental tag. |
| **G6**| Entering `build_schedule()` emits exactly one `FutureWarning`; a 20-operation schedule emits exactly one.              |
| **G7**| Coverage does not regress. `./qa/run_all_qa.sh` clean — pyright, mypy, pytest.                                        |
| **G8**| No public sequence-side signature retains `**schedule_params`; no sequence-side function returns `OperationToken`.     |

---

## 7. Risks

| Risk                                                                 | Mitigation                                                                                            |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Duplicating ten operation functions across two builders               | Phase 1 extracts the context-free factories and validators first, so the duplication is the ~6-line dispatch tail only. Accepted: the experimental copy is frozen and deletable wholesale. |
| Schema consumers silently keep using schedule components                | Resolved by moving rather than removing: the components stay resolvable, but the `experimental` tag marks them. Wire compatibility is preserved; visibility is not. |
| Shared `BuilderState` is a hidden coupling that lets mixing recur     | G3 and G4 are tests, not conventions. Add them in the same commit as the split.                       |
| `ExternalBlock` semantics under-specified, then hard to change        | Write rules 1–6 into the model docstring in Phase 4, with the OpenQASM `box` correspondence spelled out. Ship the example alongside. |
| `Wait` granularity mistaken for a semantic conflict later             | Record both the import and export identities in the docstrings (§4). No code change to get wrong. |
| Channel-mapping work later invalidates the `(port, clock)` assumption | Write the assumption down now (Phase 5) so the invalidation is visible rather than archaeological.     |

---

## 8. Explicitly deferred

| Item                                                                            | Why deferred                                                             |
| ------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Standardised channel-mapping representation (channel → port + clock + virtual-channel mixing) | Independent of the isolation work; needed for amplitude-unit conversion on import and for capacitive-coupling compensation. |
| `stretch` / symbolic duration expressions                                        | Only needed once we author timing intent, not to consume resolved programs. |
| `durationof`                                                                     | Same.                                                                    |
| Alignment policies (left / right / sequential / equispaced / positions)          | The ergonomic replacement for reference points. Wanted, but not blocking. |
| Inline (non-opaque) block contents (a sibling `Block` model)                     | The external-reference form is sufficient to unblock consumption.        |
| `while` / `switch` / `else`                                                      | No current need.                                                         |
| `dt` duration unit                                                               | Needed for exact-sample fidelity on import. Small; slot in with the channel-mapping work. |
| Hardware/target profile representation                                           | Assumed to exist as a precondition. Formalising it belongs with the channel-mapping work, not here. |
| Making `measure` a real atomic compound operation                                | `ExternalBlock` gives us the mechanism; converting `measure` is a follow-on. |
| Deleting the experimental schedule modules                                       | After one full release cycle with the `FutureWarning` in place.          |

---

## 9. Decisions on the remaining questions

All closed. Recorded here so the task briefs do not have to re-argue them.

| Question                                                   | Decision                                                                                                                          |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `unconsumed_blocks` in shared `BuilderState`               | **Leave the field in place**; the sequence path simply never populates it. Hooking it out buys nothing and adds an indirection. `_state.py` recognizes both context-kind markers without runtime imports of experimental classes. |
| Does `ExternalPulse.params` widen to `ExternalParamValue`? | **Yes, widen.** One shared type is easier to document and to test than two near-identical unions, and it costs nothing at the schema level. `PulseParamValue` becomes an alias retained for backwards compatibility. |
| `ExternalBlock` in the experimental schedule unions        | **No.** The schedule world is frozen. Anyone still authoring schedules during the deprecation window does not get `ExternalBlock`; that is an incentive, not a defect. |
| `ExternalBlock` naming and `program` type                  | `ExternalBlock`, `op_type = "external_block"`, `program: FullyQualifiedIdentifier`, builder function `external_block()`. Pairs with `ExternalPulse` / `external_pulse()`. |
| Generated OpenAPI                                          | Schedule schemas stay present, and each generated schedule component carries the `experimental` tag. Wire compatibility preserved, visibility removed. |
| `Wait` semantics                                           | **No change.** Documentation only — see §4.                                                                                       |
