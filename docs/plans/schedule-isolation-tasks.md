# Execution breakdown: `Schedule` isolation + `ExternalBlock`

Companion to [schedule-isolation-plan.md](schedule-isolation-plan.md). Ten independently
executable tasks, each sized for a single clean Sonnet (or Haiku) session.

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
> aligned pipes in markdown tables.
>
> **Verify.** `./qa/run_all_qa.sh` (pyright + mypy + pytest with coverage). It must pass before you
> report done. If it passed before your change and fails after, you are not done.
>
> **Context.** Read `docs/plans/schedule-isolation-plan.md` — the section named in your task — before
> starting. Do not re-litigate decisions recorded there; §9 lists the ones already closed.
>
> **Scope.** Do only what your task says. Each task lists an explicit *out of scope* set. If you
> believe a listed exclusion is wrong, say so in your final message rather than acting on it.

---

## Dependency graph

```text
1 ─┬─> 3 ──> 4 ──> 5 ──┬──> 8 ──> 9 ──> 10
2 ─┘                   │
                       │
6 ──> 7 ───────────────┘
```

Tasks 6 and 7 touch only models and are independent of the builder split; they are placed after 5
purely so that task 8 has everything it needs. If you want fewer sessions, the safe merges are
**6 + 7** and **9 + 10**.

| #  | Task                                              | Size | Touches                                      |
| -- | ------------------------------------------------- | ---- | -------------------------------------------- |
| 1  | Extract shared builder infrastructure             | M    | `builder/`                                   |
| 2  | Move schedule models to `experimental`            | S    | `models/`, `utilities/`                      |
| 3  | Create the experimental schedule builder          | L    | `builder/experimental/`                      |
| 4  | Make `builder/core.py` sequence-only              | L    | `builder/core.py`, `builder/__init__.py`     |
| 5  | Seal and test the boundary                        | M    | `builder/`, `tests/`                         |
| 6  | `ExternalParamValue`; widen `ExternalPulse.params`| S    | `models/pulse_types.py`, `tests/`            |
| 7  | `ExternalBlock` model                             | M    | `models/`, `tests/`                          |
| 8  | `external_block()` builder                        | M    | `builder/core.py`, `tests/`                  |
| 9  | Relocate schedule tests                           | M    | `tests/`                                     |
| 10 | Relocate examples and docs; docstring notes       | M    | `examples/`, `docs/`, `models/`              |

---

## Task 1 — Extract shared builder infrastructure

**Read:** plan §2 ("Target layout").
**Goal:** split the context-free and state-management halves out of `builder/core.py` so that a
second builder can reuse them. **Pure move. No behaviour change. No test changes.**

### Steps

1. Create `src/eq1_pulse/builder/_state.py` and move these from `core.py` **unchanged**:
   - the type aliases `SequenceContext`, `ScheduleContext`, `BuilderContext`
   - the constants `_SEQUENCE_CONTEXT_TYPES`, `_SCHEDULE_CONTEXT_TYPES`
   - the predicates `_in_sequence`, `_in_schedule`
   - `BuilderState`, the `_state` `ContextVar`, `_get_state`
   - `_generate_op_name`, `_push_context`, `_pop_context`, `_current_context`
   - `_register_variable`, `_is_variable_declared`, `_check_variable_declared`

   Give the module a docstring saying that it is **deliberately** the one module aware of both
   context semantics, because that is what lets each builder reject the other's contexts (plan §2,
   "The shared context stack is the enforcement point"). This pure-move task may retain the
   existing concrete type tuples temporarily; task 5 replaces runtime concrete-class imports with
   context-kind markers. Keep `BuilderState.unconsumed_blocks` where it is (plan §9).

2. Create `src/eq1_pulse/builder/_factories.py` and move these from `core.py` **unchanged**:
   - `phase`, `square_pulse`, `sine_pulse`, `external_pulse`, `arbitrary_pulse`
   - `full_integration`, `demod_integration`
   - `var`, `channel`, `pulse_ref`
   - `_validate_or_pass_through`, `_validate_explicit_variable_ref`, `_validate_variable_ref`
   - `_convert_range_to_model`

   `var()` calls `_check_variable_declared`, so `_factories` imports from `_state`. Never the
   reverse.

3. `core.py` imports what it needs from both and **re-exports the public names it previously
   exported**, so `core.__all__` is unchanged and `from eq1_pulse.builder import square_pulse`
   still resolves.

### Acceptance

- `core.__all__` and `builder.__all__` are byte-identical to before.
- `./qa/run_all_qa.sh` passes with **zero** changes under `tests/`, `examples/`, or `docs/`.
- `python -c "from eq1_pulse.builder import *; print(len(__all__ if 0 else dir()))"` runs clean.

### Out of scope

Deleting anything; renaming anything; touching `models/`; changing any signature.

---

## Task 2 — Move schedule models to `experimental`

**Read:** plan §5 Phase 2.
**Goal:** `Schedule` and friends stop being part of the public model namespace.

### Steps

1. Create `src/eq1_pulse/models/experimental/__init__.py`. Module docstring must state that the
   contents are unused, experimental, and scheduled for removal. Do **not** star-import from it in
   `models/__init__.py`.

2. Move `src/eq1_pulse/models/schedule.py` → `src/eq1_pulse/models/experimental/schedule.py`,
   content unchanged apart from import paths (`.base_models` → `..base_models`, etc.). It may keep
   importing the shared leaves (`channel_ops`, `data_ops`, `control_flow` bases) — that is allowed
   (plan §1, "Where the boundary goes").

3. Leave a shim at `src/eq1_pulse/models/schedule.py` that re-exports from the new location and
   emits a `DeprecationWarning` **on import**:

   ```python
   warnings.warn(
       "eq1_pulse.models.schedule has moved to eq1_pulse.models.experimental.schedule "
       "and is no longer part of the supported model set.",
       DeprecationWarning,
       stacklevel=2,
   )
   ```

4. In `src/eq1_pulse/models/__init__.py`: remove `from . import schedule as _schedule`, remove
   `from .schedule import *`, and remove `_schedule.__all__` from the aggregate `__all__`.

5. In `src/eq1_pulse/utilities/openapi_generator.py`:
   - in `model_modules`, replace `"schedule"` with `"experimental.schedule"`. Both
     `importlib.import_module(f"eq1_pulse.models.{module_name}")` and the
     `obj.__module__.startswith("eq1_pulse.models")` filter work unchanged.
   - add a tag `{"name": "experimental", "description": "Unused / experimental models, subject to removal"}`.
    - use the key map returned by `models_json_schema()` to attach `"tags": ["experimental"]` to
       every component generated from `eq1_pulse.models.experimental`, including separate
       `-Input`/`-Output` components when present.
   - change the `sequences` tag description from `"Operation sequences and schedules"` to
     `"Operation sequences"`.

6. Update any import of `eq1_pulse.models.schedule` or `from eq1_pulse.models import Schedule`
   under `tests/`, `examples/`, and `docs/source/_generator/` to the new path. Do **not**
   restructure those files — that is task 9 and task 10. Minimal import fix only.

### Acceptance

- `from eq1_pulse.models import Schedule` raises `ImportError`.
- `from eq1_pulse.models.experimental.schedule import Schedule` works.
- `import eq1_pulse.models.schedule` works and emits one `DeprecationWarning`.
- The generated OpenAPI still contains `Schedule`, `ScheduledOperation`, `RefPt`, `RelTime`,
   `SchedRepetition`, `SchedIteration`, `SchedConditional`; every component generated from those
   experimental models carries the `experimental` tag, while supported components do not.
- `./qa/run_all_qa.sh` passes.

### Out of scope

Touching `builder/`; moving or rewriting tests; deleting the schedule models.

---

## Task 3 — Create the experimental schedule builder

**Read:** plan §2 and §5 Phase 3.
**Goal:** stand up a complete, self-contained schedule-building API under
`builder/experimental/`. **Additive only — `builder/core.py` keeps working exactly as it does
today.** Both APIs coexist at the end of this task; task 4 removes the duplication from `core.py`.

### Steps

1. Move `src/eq1_pulse/builder/utils.py` → `src/eq1_pulse/builder/experimental/utils.py`
   (`OperationToken`, `ScheduleParams`, `SCHEDULE_PARAM_NAMES`, `resolve_schedule_params`). Update
   `core.py`'s import to the new path so the tree stays green. Delete the original file.

2. Create `src/eq1_pulse/builder/experimental/schedule.py` containing the schedule-side API,
   derived from the schedule branches currently in `core.py`:

   - context managers: `build_schedule`, `sub_schedule`, `_sub_schedule_with_token`
   - control flow: `repeat`, `for_`, `if_` — **schedule branch only**, no sequence branch, no
     `_in_sequence` fallback
   - operations: `play`, `wait`, `barrier`, `set_frequency`, `shift_frequency`, `set_phase`,
     `shift_phase`, `record`, `discriminate`, `store`, `measure`, `var_decl`, `pulse_decl`
   - decorators / blocks: `ScheduleBlock`, `nested_schedule`, `add_block`
   - helpers: `_add_to_schedule`, `_reject_unconsumed_blocks`

   Every operation function takes `**schedule_params: Unpack[ScheduleParams]` and returns
   `OperationToken` (not `OperationToken | None` — in this module there is no sequence case). Each
   raises if `_current_context()` is not a schedule context.

   Import the context stack from `.._state` and the context-free helpers from `.._factories`.
   Do **not** copy `phase`, `square_pulse`, `sine_pulse`, `external_pulse`, `arbitrary_pulse`,
   `full_integration`, `demod_integration`, `var`, `channel`, `pulse_ref`, or any `_validate_*`
   helper — import and re-export them.

   `_reject_schedule_params` is a sequence-side concern; it does **not** belong here.

   Each schedule context manager owns one `unconsumed_blocks` scope. On normal exit,
   `build_schedule`, `sub_schedule`, `repeat`, `for_`, and `if_` must capture that scope, restore the
   context stack, then call `_reject_unconsumed_blocks`. On exceptional exit they restore the stack
   and re-raise without masking the original exception.

3. Create `src/eq1_pulse/builder/experimental/__init__.py` re-exporting the above plus the shared
   factories, so `from eq1_pulse.builder.experimental import *` gives a complete working API.
   Module docstring must state that this API is unused and scheduled for removal, and point at
   `eq1_pulse.builder` for sequences.

4. Add `tests/eq1lab_pulse/experimental/test_experimental_builder_smoke.py`: build a schedule end
   to end via `eq1_pulse.builder.experimental` only — nested `sub_schedule`, a `ref_op`/`ref_pt`
   relation, a `repeat`, a `measure` — and assert the resulting `Schedule` model.

### Acceptance

- `from eq1_pulse.builder.experimental import *` then a full schedule build works with no import
  from `eq1_pulse.builder.core`.
- The existing schedule tests still pass unchanged against `eq1_pulse.builder` (task 4 migrates them).
- `./qa/run_all_qa.sh` passes.

### Out of scope

Removing anything from `core.py` beyond the `utils.py` import path; changing `builder/__init__.py`;
migrating existing tests; adding warnings.

---

## Task 4 — Make `builder/core.py` sequence-only

**Read:** plan §5 Phase 3.
**Goal:** delete every schedule concept from the sequence builder.

### Steps

1. In `src/eq1_pulse/builder/core.py`, delete:
   - `_add_to_schedule`, `_reject_schedule_params`, `_reject_unconsumed_blocks`,
     `_sub_schedule_with_token`
   - `build_schedule`, `sub_schedule`, `add_block`, `ScheduleBlock`, `nested_schedule`
   - the schedule branch of `repeat`, `for_`, and `if_`
   - all imports from `models/experimental/schedule.py` and from `experimental/utils.py`

2. From every remaining public function — `play`, `wait`, `barrier`, `set_frequency`,
   `shift_frequency`, `set_phase`, `shift_phase`, `record`, `discriminate`, `store`, `measure`,
   `var_decl`, `pulse_decl` — remove the `**schedule_params: Unpack[ScheduleParams]` parameter,
   change the return annotation from `OperationToken | None` to `None`, and delete the
   `if _in_schedule(context): ...` branch. `_add_to_sequence` loses its `schedule_params` argument.

3. Update every affected docstring: drop the `:param schedule_params:` line, drop the "Token if in
   schedule context" return text, and remove schedule examples from the `Examples` blocks.

4. Rewrite `src/eq1_pulse/builder/__init__.py`: remove `ScheduleBlock`, `ScheduleParams`,
   `OperationToken`, `build_schedule`, `sub_schedule`, `nested_schedule`, `add_block`,
   `resolve_schedule_params` from both the imports and `__all__`. Rewrite the module docstring so
   every example is a sequence, and add one line pointing at `eq1_pulse.builder.experimental` for
   the retired schedule API.

5. Migrate the tests that exercise the schedule API through `eq1_pulse.builder` so they import from
   `eq1_pulse.builder.experimental` instead. Move them wholesale for now; task 9 relocates the
   files. The affected files are `tests/eq1lab_pulse/test_builder.py`,
   `test_builder_context_matrix.py`, `test_schedule_params_validation.py`,
   `test_builder_state_isolation.py`, `test_variable_tracking.py`,
   `test_builder_variable_verification.py`. Likewise for `examples/sub_schedule_example.py` and
   `examples/nested_decorator_example.py`.

### Acceptance

- `from eq1_pulse.builder import build_schedule` raises `ImportError`.
- No public function in `core.py` accepts `**schedule_params` or returns `OperationToken`:
  `grep -n "schedule_params\|OperationToken" src/eq1_pulse/builder/core.py` returns nothing.
- `./qa/run_all_qa.sh` passes; coverage does not regress.

### Out of scope

Reciprocal-rejection error messages and the `FutureWarning` (task 5); relocating test files
(task 9); `ExternalBlock`.

---

## Task 5 — Seal and test the boundary

**Read:** plan §2 ("The shared context stack is the enforcement point") and §6 (gates G3, G4).
**Goal:** make mixing the two worlds impossible, and prove it.

### Steps

1. Sequence side (`builder/core.py`): every operation and context manager must raise a clear
   `RuntimeError` when the current context is a schedule context. Message pattern:

   ```text
   play() requires a build_sequence() context. Schedules are built with
   eq1_pulse.builder.experimental and cannot contain sequence operations.
   ```

2. Schedule side (`builder/experimental/schedule.py`): the mirror image, pointing at
   `eq1_pulse.builder`.

3. `build_sequence()` must raise if a schedule context is already on the stack;
   `build_schedule()` must raise if a sequence context is already on the stack.

   Add `_context_kind: ClassVar[Literal["sequence"]]` to every sequence context model and the
   corresponding `"schedule"` marker to every schedule context model. `_in_sequence()` and
   `_in_schedule()` inspect this marker; concrete model imports in `_state.py` are under
   `TYPE_CHECKING` only, so importing the supported builder does not import the experimental tree.

4. `build_schedule()` emits exactly **one** `FutureWarning` on context entry — not per operation:

   ```python
   warnings.warn(
       "build_schedule() and the Schedule representation are unused and will be removed. "
       "Use eq1_pulse.builder.build_sequence().",
       FutureWarning,
       stacklevel=3,
   )
   ```

5. Add `tests/eq1lab_pulse/test_module_boundaries.py`:
   - **G3, import direction.** Walk the AST of every `.py` under `src/eq1_pulse/`. Assert that no
     module outside an `experimental` package contains an import naming `experimental`. Cover both
     `import` and `from ... import`, and both absolute (`eq1_pulse.models.experimental...`) and
   relative (`from .experimental import ...`) forms. Ignore imports guarded by `if TYPE_CHECKING:`;
   they create no runtime dependency. The `models/schedule.py` shim is the only runtime exception
   — allowlist it by path.
   - **G4, mixing rejection.** Parametrised: `build_schedule()` inside `build_sequence()` raises;
     `build_sequence()` inside `build_schedule()` raises; sequence `play()` inside a schedule
     context raises; experimental `play()` inside a sequence context raises. Assert on message
     content, not just the exception type.
   - **G6, warning count.** A 20-operation schedule build emits exactly one `FutureWarning`.

6. Ensure the rest of the suite does not fail on the new warning — add a `filterwarnings` entry in
   `pyproject.toml` or per-test markers as appropriate, but **do not** globally silence
   `FutureWarning`.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `tests/eq1lab_pulse/test_module_boundaries.py` fails if you temporarily add
  `from .experimental import schedule` to `builder/core.py`. Verify this by hand, then revert.

### Out of scope

`ExternalBlock`; moving test files; docs.

---

## Task 6 — `ExternalParamValue`; widen `ExternalPulse.params`

**Read:** plan §3 "Parameters", subsection 3.
**Goal:** one shared parameter value type for externally defined entities.

### Steps

1. In `src/eq1_pulse/models/pulse_types.py`, define:

   ```python
   type ExternalParamScalarValue = bool | float | int | complex_from_tuple | str
   type ExternalParamValue = Annotated[
       Amplitude | Duration | Frequency | Phase | Magnitude
      | _TaggedVariableRef | _TaggedPulseRef | PulseType
      | ExternalParamScalarValue,
      BeforeValidator(_coerce_dimensional_string),
   ]
   ```

   with an input alias `ExternalParamValueLike` accepting the corresponding `*Like` forms
   (`AmplitudeLike`, `DurationLike`, `FrequencyLike`, `PhaseLike`, `MagnitudeLike`, `VariableRef`,
   `VarRefDict`, `PulseRefLike`, `PulseType`, scalars). Watch for a circular reference: `PulseType`
   is defined at the bottom of this module, so the alias must be declared after it or guarded under
   `TYPE_CHECKING`. The tagged aliases serialize references as `{"var_ref": ...}` and
   `{"pulse_ref": ...}`; `complex_from_tuple` accepts a pair and serializes it as
   `[real, imaginary]` in JSON.

2. Retain `PulseParamValue` / `PulseParamValueLike` / `PulseParamScalarValue` as aliases of the new
   types for backwards compatibility, with a docstring noting the widening.

3. Point `ExternalPulse.params` at `dict[str, ExternalParamValue] | None`, and the `TYPE_CHECKING`
   `__init__` overload at `dict[str, ExternalParamValueLike] | None`.

4. **Pin down the bare-`str` case.** `ExternalParamValue` must pre-coerce unit-suffixed strings
   before smart-union resolution; otherwise the exact `str` branch wins. Document that `"10us"`
   becomes a `Duration` while `"foo"` stays a `str`, and add tests asserting both outcomes, plus
   `"100mV"` → `Amplitude` and `"5GHz"` → `Frequency`.

5. Extend `tests/eq1lab_pulse/models/test_pulse_types.py` with JSON round-trip coverage for each new
   member of the union, especially tagged references and the complex pair encoding.

### Acceptance

- Every existing `ExternalPulse` test passes unchanged.
- New tests cover each union member and the four string-coercion cases.
- `./qa/run_all_qa.sh` passes.

### Out of scope

`ExternalBlock`; the builder.

---

## Task 7 — `ExternalBlock` model

**Read:** plan §3 in full.
**Goal:** the model, its semantics docstring, and its validation.

### Steps

1. Create `src/eq1_pulse/models/external_block.py` with the model exactly as sketched in plan §3:
   `op_type: Literal["external_block"]`, `program: FullyQualifiedIdentifier | None`,
   `channels: dict[str, ChannelRef]`, `params: dict[str, ExternalParamValue] | None`,
   `results: dict[str, VariableRef] | None`, `duration: Duration | VariableRef | None`.

2. Write plan §3's semantics rules **1 through 6 verbatim** into the class docstring — reservation,
   synchronisation, non-interference, opacity/optimisation barrier, timed vs flex, and the empty-
   `program` reservation case. Also record rule §3-Parameters-4 (flex duration combined with a
   runtime-variable parameter is unresolvable) and §3-Parameters-5 (no signature checking).

3. Add a model validator rejecting `duration=None` when any value in `params` is a `VariableRef`,
   with a message naming the offending parameter and stating both fixes (supply an explicit
   `duration`, or pass a compile-time value).

4. Add `ExternalBlock` to `DiscriminableOp` in `src/eq1_pulse/models/sequence.py`, and export it
   from `src/eq1_pulse/models/__init__.py`. Do **not** add it to anything under
   `models/experimental/` (plan §9).

5. Add `tests/eq1lab_pulse/models/test_external_block.py` covering: serialisation round-trip;
   discriminated-union dispatch on `op_type`; timed vs flex; `program=None` pure reservation;
   role-keyed channels; each `params` value type; `results` binding; and the flex-plus-runtime-
   variable rejection.

### Acceptance

- An `ExternalBlock` nested inside an `OpSequence` round-trips through
  `model_dump()` / `model_validate()` and dispatches correctly by `op_type`.
- `./qa/run_all_qa.sh` passes.

### Out of scope

The builder function (task 8); examples and docs (task 10).

---

## Task 8 — `external_block()` builder function

**Read:** plan §3 "Builder surface" and "Parameters".
**Goal:** expose `ExternalBlock` through the sequence builder.

### Steps

1. Add `external_block()` to `src/eq1_pulse/builder/core.py`, accepting both forms:

   ```python
   external_block(program=..., channels={"drive": "q0", "readout": "q0_ro"},
                  params={...}, results={...}, duration=...)
   external_block("q0", "q1", program="eq1.cal.cz")     # positional, roles do not matter
   ```

   For the positional form, generate placeholder role keys deterministically (`"0"`, `"1"`, … —
   pick one scheme and document it). Reject supplying both positional channels and a `channels=`
   mapping.

2. Validate `results` variables with the existing `_validate_variable_ref` /
   `_check_variable_declared` machinery, exactly as `record()` does for its `var`. A `VariableRef`
   in `params` is a *read* and gets the same treatment as any other read.

3. Export `external_block` from `builder/core.__all__` and `builder/__init__.__all__`. Do **not**
   add it to `builder/experimental/`.

4. Add builder tests: inside `build_sequence`, inside `repeat` / `for_` / `if_` / `sub_sequence`;
   both call forms; positional-plus-`channels=` rejection; undeclared `results` variable rejection;
   rejection inside a schedule context.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `grep -n external_block src/eq1_pulse/builder/experimental/` returns nothing.

### Out of scope

Examples and docs (task 10).

---

## Task 9 — Relocate schedule tests

**Read:** plan §5 Phase 5.
**Goal:** schedule tests live under an `experimental` tree; sequence test files contain no schedule
material.

### Steps

1. Create `tests/eq1lab_pulse/experimental/` (with `__init__.py` if the sibling packages have one).

2. Move wholesale: `tests/eq1lab_pulse/models/test_schedule.py` and
   `tests/eq1lab_pulse/test_schedule_params_validation.py`.

3. Split, moving only the schedule-exercising tests: `test_builder.py`,
   `test_builder_context_matrix.py`, `test_builder_state_isolation.py`, `test_variable_tracking.py`,
   `test_builder_variable_verification.py`. The sequence halves stay where they are. Preserve test
   names so history stays greppable.

4. Check `tests/eq1lab_pulse/models/test_comparison_invariants.py` for its single schedule
   reference and route it appropriately.

5. Add a session-scoped `filterwarnings` fixture or a `pytest.ini` marker so the experimental tree
   does not drown in the task-5 `FutureWarning`. Do not suppress it outside that tree.

### Acceptance

- `grep -rn "Schedule\|Sched\|schedule" tests/eq1lab_pulse --include=*.py` matches only files under
  `tests/eq1lab_pulse/experimental/`, plus the boundary test from task 5.
- `./qa/run_all_qa.sh` passes; total test count is unchanged; coverage does not regress.

### Out of scope

Examples and docs (task 10); deleting tests.

---

## Task 10 — Relocate examples and docs; write the docstring notes

**Read:** plan §0, §4, §5 Phase 5.
**Goal:** the supported docs describe sequences only; the assumptions the IR rests on are written
down.

### Steps

1. **Examples.** Move `examples/sub_schedule_example.py` and the schedule half of
   `examples/nested_decorator_example.py` to `examples/experimental/`, each with a header comment
   stating it exercises an unused API. Confirm `tests/test_examples.py` and
   `tests/test_documentation_examples.py` still discover them; adjust the discovery globs if needed.

2. **Docs.** Move `docs/source/examples/sub_schedule_examples.rst` and the schedule sections of
   `docs/source/user_guide/builder_guide.rst`, `introduction.rst`, and `index.rst` into a single
   `docs/source/experimental/schedule.rst`, labelled unused at the top. Move the generators
   `docs/source/_generator/{schedule,schedule_refop,nested_schedule}_diagram.py` with it and fix
   their imports.

3. **Channel model assumptions.** Write plan §0's five channel assumptions into
   `docs/source/user_guide/introduction.rst` — a channel *is* a `(port, clock)` pair carrying its
   own frame implicitly; all clocks are NCOs on one global clock, so all channels are mutually
   phase-coherent; multiple channels may resolve onto one physical port; virtual channels absorb
   baseband and gate-virtualisation mappings, primarily for capacitive-coupling compensation; the
   channel-mapping representation is future work. These are currently unstated anywhere and are
   load-bearing for anyone reading the IR.

4. **`Wait` ↔ `delay` correspondence.** Add plan §4's two identities to the `Wait` docstring in
   `src/eq1_pulse/models/channel_ops.py` and to the `src/eq1_pulse/models/sequence.py` module
   docstring:

   ```text
   import:   delay[d] a, b;   ->   barrier(a, b) ; wait(a, b, d)
   export:   wait(a, b, d)    ->   delay[d] a;  delay[d] b;
   ```

   State why: after the barrier both cursors are equal, so an independent per-channel wait lands
   both ends at `max(...) + d`. `Wait` is the more primitive operation; OpenQASM's multi-resource
   `delay` is the composite. **Do not change any behaviour.**

5. **`ExternalBlock` docs.** Add `examples/external_block_example.py` and a docs page covering both
   call forms, timed vs flex, the pure-reservation case, and `results` binding.

### Acceptance

- `cd docs && ./generate_html.sh` builds clean, no new warnings.
- `grep -rn "build_schedule" docs/source/user_guide/` returns nothing.
- `./qa/run_all_qa.sh` passes.

### Out of scope

Deleting the experimental modules — that happens after one release cycle (plan §8).

---

## Final state

After task 10:

- `eq1_pulse.models` and `eq1_pulse.builder` are sequence-only, with `ExternalBlock`.
- `eq1_pulse.models.experimental` and `eq1_pulse.builder.experimental` hold a complete but unused
  schedule API that warns on entry and cannot be mixed with sequences.
- The generated OpenAPI still carries the schedule schemas, tagged `experimental`.
- Import direction and mixing rejection are enforced by tests, not convention.
- The channel model assumptions and the `Wait` ↔ `delay` correspondence are documented.

Remaining follow-on work is in plan §8 ("Explicitly deferred") — the channel-mapping
representation is the largest item and gates the amplitude-unit conversion.
