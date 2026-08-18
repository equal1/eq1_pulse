# Code Review — `hp-peti/builder-interface` vs `main`

**Reviewed:** 2026-08-18 · **Range:** `main...hp-peti/builder-interface` (11 commits, 63 files, +15471/−342)

## Status

All findings below have been **fixed** except one ([D7](#d7)) — see
[What was deliberately left alone](#what-was-deliberately-left-alone) at the end.
QA after the fixes: `pyright src tests` clean, `mypy src tests` clean,
`ruff check` clean, `pytest` **698 passed** (was 425), coverage 92% (was 89%),
`sphinx -b html` builds with 0 errors (was 2).

Four regression guards were added so these classes of defect cannot return silently:

| Test | Guards |
|:---|:---|
| [tests/eq1lab_pulse/test_builder_context_matrix.py](../../tests/eq1lab_pulse/test_builder_context_matrix.py) | every operation × every sequence and schedule context ([B1](#b1), [B3](#b3)) |
| [tests/eq1lab_pulse/test_builder_state_isolation.py](../../tests/eq1lab_pulse/test_builder_state_isolation.py) | state cleanup after failed builds, name determinism ([B4](#b4), [D6](#d6)) |
| [tests/eq1lab_pulse/models/test_comparison_invariants.py](../../tests/eq1lab_pulse/models/test_comparison_invariants.py) | `a == b implies hash(a) == hash(b)`, NaN ordering ([B7](#b7), [B8](#b8)) |
| [tests/test_documentation_examples.py](../../tests/test_documentation_examples.py) and [tests/test_examples.py](../../tests/test_examples.py) | every doc/docstring snippet binds against the real signature; every example runs ([P2](#p2--documentation-defects)) |

## Scope

The branch adds three largely independent things:

1. **A new builder DSL** — [`src/eq1_pulse/builder/`](../../src/eq1_pulse/builder/) (`core.py` ~2270 lines, `utils.py`, `__init__.py`).
2. **Model-layer rework** — zero-value handling in [`base_models.py`](../../src/eq1_pulse/models/base_models.py) (`register_unit_of_zero`) and a new comparison/ordering system in [`basic_types.py`](../../src/eq1_pulse/models/basic_types.py) (`register_comparison_unit`, `ComparableWrappedValueOrZeroModel`).
3. **Documentation and examples** — 15 matplotlib diagram generators, ~2900 lines of RST, 11 runnable example scripts.

### What I verified

| Check | Result |
|:---|:---|
| `pytest tests` | **425 passed**, 89% total coverage (`builder/core.py` at 88%) |
| `ruff check src tests examples docs` | clean |
| `pyright src` | 0 errors |
| `mypy src` | **2 errors** (see [T1](#t1)) |
| All 11 `examples/*.py` executed | all exit 0 |
| Targeted probe scripts for the findings below | reproduced as described |

The overall design is sound and the test suite is genuinely good. The findings
below are concentrated in two places: **context-type dispatch inside schedules**,
and **documented API surface that does not match the implemented signatures**.

---

## P0 — Correctness bugs

### B1. Most operations are unusable inside `repeat` / `for_` / `if_` in a schedule  *[Fixed]*

Eight builder functions test the current context with `isinstance(context, Schedule)`
only, instead of `Schedule | SchedRepetition | SchedIteration | SchedConditional`
as `play()` and `wait()` correctly do:

`set_frequency` ([core.py:1899](../../src/eq1_pulse/builder/core.py#L1899)),
`shift_frequency` ([:1934](../../src/eq1_pulse/builder/core.py#L1934)),
`set_phase` ([:1969](../../src/eq1_pulse/builder/core.py#L1969)),
`shift_phase` ([:2004](../../src/eq1_pulse/builder/core.py#L2004)),
`record` ([:2056](../../src/eq1_pulse/builder/core.py#L2056)),
`discriminate` ([:2117](../../src/eq1_pulse/builder/core.py#L2117)),
`store` ([:2175](../../src/eq1_pulse/builder/core.py#L2175)),
and `barrier` ([:1861](../../src/eq1_pulse/builder/core.py#L1861)).

Inside a schedule-side control-flow block the context is a `SchedRepetition`,
so these fall through to `_add_to_sequence()`, which then raises:

```python
with build_schedule():
    with repeat(3):
        set_frequency("q", "5GHz")
# RuntimeError: Cannot add sequence operation to SchedRepetition context
```

Same for `record`, `store`, `discriminate`, `set_phase`, `shift_phase`,
`shift_frequency`. `play()` in the same position works, which makes the failure
look arbitrary to a user. `barrier()` is a special case: it *should* be rejected
in schedules, but currently emits the confusing `Cannot add sequence operation to
SchedRepetition context` instead of its own explanatory message.

**Fix:** introduce a single predicate and use it everywhere.

```python
_SCHEDULE_CONTEXTS = (Schedule, SchedRepetition, SchedIteration, SchedConditional)
_SEQUENCE_CONTEXTS = (OpSequence, Repetition, Iteration, Conditional)

def _in_schedule(context: Any) -> bool:
    return isinstance(context, _SCHEDULE_CONTEXTS)
```

There are 12 `isinstance(context, Schedule)`-family checks in the file with three
different spellings; consolidating them is the actual repair, not patching each site.

### B2. `measure()` in a schedule emits two operations with the same name  *[Fixed]*

[core.py:2236-2262](../../src/eq1_pulse/builder/core.py#L2236-L2262) — `record_params = schedule_params.copy()` carries the caller's `op_name`
through to the `record` operation, which the `play` operation already consumed:

```python
with build_schedule() as s:
    var_decl("r", "complex")
    measure("q", result_var="r", duration="1us", amplitude="1mV",
            integration=full_integration(), op_name="meas")
[i.name for i in s.items]   # ['op_1', 'meas', 'meas']   <-- duplicate
```

Duplicate names silently break `ref_op` resolution downstream — any later
operation referencing `"meas"` is ambiguous.

**Fix:** pop `op_name` from `record_params` and derive a distinct name
(e.g. `f"{play_token.name}_record"`), or generate one.

### B3. `add_block()` / `sub_schedule()` cannot nest inside schedule control flow  *[Fixed]*

[`add_block`](../../src/eq1_pulse/builder/core.py#L1571) and
[`sub_schedule`](../../src/eq1_pulse/builder/core.py#L664) both require the
context to be exactly `Schedule`:

```python
with build_schedule():
    with repeat(2):
        with sub_schedule():        # RuntimeError: sub_schedule can only be
            play(...)               # used within a build_schedule() context
```

Same root cause as B1. Additionally `add_block` reads `context.items[-1]` to
recover the token — that only works because it assumes a flat `Schedule`.
Have `sub_schedule` return the token it already computes (see [D1](#d1)) and
`add_block` can use it directly instead of reaching into `.items`.

### B4. `unconsumed_blocks` leaks entries keyed by `id()`, causing cross-build false errors  *[Fixed]*

[`ScheduleBlock.__init__`](../../src/eq1_pulse/builder/core.py#L1518-L1522)
registers under `id(_current_context())`. Cleanup only happens in the `finally`
of `build_schedule`/`sub_schedule`, keyed by the *schedule's* id. A block
registered against any other context — or a block whose `add_block()` call raised
(B3) — is never removed:

```python
try:
    with build_schedule():
        with repeat(2):
            add_block(blk("q"))     # raises; block stays registered
except RuntimeError:
    pass
# state.unconsumed_blocks == {123715320516912: [<ScheduleBlock ...>]}
```

That entry survives for the process lifetime. Because CPython reuses `id()`
values after collection, a *later unrelated* `build_schedule()` can allocate a
`Schedule` at the same address and fail on exit with
`Schedule context closed with 1 unconsumed ScheduleBlock(s)` plus a traceback
pointing into code that has nothing to do with it. I hit this accidentally while
probing, before I understood the mechanism — it will be extremely hard to debug
in the field.

**Fix:** stop keying state on `id()`. Either

- attach the tracking to the context object itself (a `WeakKeyDictionary`, or a
  parallel stack of per-frame records pushed/popped alongside `context_stack`), or
- track blocks on a single stack in `BuilderState` scoped to the innermost
  builder frame, cleaned up unconditionally in the `finally`.

The same `id()`-keying is used for `declared_variables`. That one currently
self-heals because `_cleanup_context_variables` runs on every exit path, but it
carries the same latent hazard and should move with it.

### B5. `_validate_or_pass_through` rejects legitimate identifier-shaped string literals  *[Fixed]*

[core.py:378-431](../../src/eq1_pulse/builder/core.py#L378-L431) treats *any*
string that satisfies `str.isidentifier()` as a variable reference, and raises if
it is not declared. `external_pulse()` applies this to every value in `params`:

```python
external_pulse("lib.gauss", duration="10ns", amplitude="1mV",
               params={"window": "hann"})
# RuntimeError: Parameter 'params['window']' in external_pulse() references
# undeclared variable 'hann'.
```

`"hann"`, `"linear"`, `"cubic"`, `"gaussian"` — every plain enum-ish string a
pulse function might take — is now unusable, and the error blames the user for
not declaring a variable. This is the most likely finding to bite a real user.

**Fix (pick one, in order of preference):**

1. Require explicit `var("x")` / `VariableRef` for variable references in
   `params` and other free-form dicts; drop the identifier-string heuristic there.
2. Keep the heuristic for typed scalar parameters (`duration`, `amplitude`,
   `frequency`, `phase`) where a bare identifier is unambiguous, but *pass
   through* rather than raise when the name is undeclared, so the model's own
   validator produces the error.

At minimum, `external_pulse(params=...)` should not run the heuristic.

### B6. Six operations report the wrong function name in their error messages  *[Fixed]*

Copy-paste: `_add_to_sequence(context, op, schedule_params, "set_frequency")` in
`shift_frequency` ([:1937](../../src/eq1_pulse/builder/core.py#L1937)),
`set_phase` ([:1972](../../src/eq1_pulse/builder/core.py#L1972)),
`shift_phase` ([:2007](../../src/eq1_pulse/builder/core.py#L2007)),
`record` ([:2059](../../src/eq1_pulse/builder/core.py#L2059)),
`discriminate` ([:2120](../../src/eq1_pulse/builder/core.py#L2120)),
`store` ([:2178](../../src/eq1_pulse/builder/core.py#L2178)).

```python
with build_sequence():
    set_phase("q", "90deg", rel_time="10ns")
# RuntimeError: Schedule parameters ('rel_time') not allowed in sequence
# context for 'set_frequency'.        <-- wrong operation
```

This directly undoes commit `bd19b62` ("specify operation names in
context-related error messages"). The same six functions also call bare
`_current_context()` instead of `_current_context("<name>()")`, losing the
improved message from that commit on the no-context path too.

### B7. `Duration(us=1) == Duration(ns=1000)` is `True` but their hashes differ  *[Fixed]*

`ComparableWrappedValueOrZeroModel.__eq__`
([basic_types.py:220](../../src/eq1_pulse/models/basic_types.py#L220)) compares
across units, but no matching `__hash__` was added, so pydantic's
field-value-based hash is inherited unchanged:

```python
Duration(us=1) == Duration(ns=1000)          # True
hash(Duration(us=1)) == hash(Duration(ns=1000))   # False
{Duration(us=10), Duration(ns=10000)}        # two elements, both "equal"
{Duration(us=1): "a"}[Duration(ns=1000)]     # KeyError
```

This violates the `__eq__`/`__hash__` invariant. Any set/dict/`in`/`Counter`
use of these types is now silently wrong, and it will not show up in the existing
tests because they compare with `==` directly.

**Fix:** define `__hash__` on `ComparableWrappedValueOrZeroModel` over the same
normalized quantity `__eq__` compares on. The registry already holds everything
needed — the equality-compatible `types` set is the natural hash bucket:

```python
def __hash__(self) -> int:
    info = _find_registered_equality_comparison_type_info(type(self))
    if info is None:
        return super().__hash__()
    # hash the normalized magnitude only; Python's numeric hash is already
    # consistent across int/float/complex, so 1, 1.0 and 1+0j collide correctly
    return hash(getattr(self.value, info.unit))
```

Note this deliberately does *not* include the type in the hash — `__eq__` treats
`Voltage` and `ComplexVoltage` as compatible, so they must hash alike. Add a
property test asserting `a == b implies hash(a) == hash(b)` across every
registered pair.

### B8. `__gt__` / `__ge__` are wrong for NaN  *[Fixed]*

[basic_types.py](../../src/eq1_pulse/models/basic_types.py) defines
`__gt__` as `not __le__` and `__ge__` as `not __lt__`. With a NaN payload both
directions report "greater":

```python
d = Duration(s=float("nan"))
d >= 0   # True
d > 0    # True
d < 0    # False
```

**Fix:** implement `__gt__`/`__ge__` directly against the comparison unit,
mirroring `__lt__`/`__le__`, so NaN propagates `False` in both directions.
`functools.total_ordering` is *not* a substitute here — it derives them the same
incorrect way.

---

## P1 — API design

<a id="d1"></a>
### D1. `sub_schedule()` cannot return its token  *[Fixed]*

[core.py:697-699](../../src/eq1_pulse/builder/core.py#L697-L699):

```python
    # Return the token so it can be used for further references
    return token  # type: ignore[return-value]
```

This is inside a `@contextmanager` generator. The value becomes
`StopIteration.value` and `contextlib` discards it — `with sub_schedule() as x`
binds the `Schedule`, never the token. Verified: `type(x).__name__ == 'Schedule'`.
The `type: ignore` is suppressing the very error that would have caught this.

The token is the only handle for `ref_op`, so users must currently pass
`op_name=` and refer to it by string. Either `yield token` (breaking, but the
useful object), or yield a small named tuple `(schedule, token)`, or add a
`.token` attribute to the yielded object. Whichever you choose, delete the dead
`return` and the `type: ignore`.

### D2. `name=` is accepted, silently ignored, and documented as the correct spelling  *[Fixed]*

`ScheduleParams` declares `op_name`, but `_add_to_schedule`
([core.py:245-251](../../src/eq1_pulse/builder/core.py#L245-L251)) does:

```python
sched_params = {**resolved_params}
sched_params["name"] = sched_params.pop("op_name")
```

A caller-supplied `name="init"` lands in `resolved_params`, then gets
**overwritten** by the auto-generated `op_name`. No error, no warning:

```python
with build_schedule() as s:
    play("q", pulse, name="myop")
s.items[0].name   # 'op_7'
```

`name=` is what the docs tell people to use — [builder_guide.rst:999](../../docs/source/user_guide/builder_guide.rst#L999),
[:1057](../../docs/source/user_guide/builder_guide.rst#L1057),
[:1075](../../docs/source/user_guide/builder_guide.rst#L1075),
[:1246](../../docs/source/user_guide/builder_guide.rst#L1246),
[:1267](../../docs/source/user_guide/builder_guide.rst#L1267),
[:1274](../../docs/source/user_guide/builder_guide.rst#L1274) — and the
`add_block` and `nested_schedule` docstrings ([core.py:1565](../../src/eq1_pulse/builder/core.py#L1565),
[:1692](../../src/eq1_pulse/builder/core.py#L1692)). The `sub_schedule`,
`repeat`, `for_` and `if_` docstrings all describe the parameter set as
"(name, ref_op, ref_pt, ...)".

**Fix:** decide on one spelling. Given `ScheduledOperation.name` is the model
field, accepting `name=` as an alias would be kindest; failing that, reject
unknown keys explicitly rather than dropping them, and correct all six doc sites.

### D3. `Duration(5)` now silently means five **seconds**  *[Fixed]*

The rewritten `WrappedValueModel.__init__`
([base_models.py](../../src/eq1_pulse/models/base_models.py)) routes *any* lone
positional argument into the registered zero-unit field:

```python
if args and len(args) == 1 and not kwargs:
    super().__init__(**{get_unit_of_zero(self.__class__): args[0]})
```

Previously the single-positional form was reserved for the literal `0`
(`_apply_default_zero_args_to_init_data` raised `ValueError` otherwise). Now:

```python
Duration(5)      # Duration(s=5.0)     — 5 seconds
Amplitude(1)     # Amplitude(V=1)      — 1 Volt
Phase(90)        # Phase(deg=90)
```

For a pulse library where the working scale is ns and mV, `Duration(5)` meaning
5 seconds and `Amplitude(1)` meaning 1 V is a dangerous default. The old code
forced the unit to be explicit; this quietly did not.

**Resolved:** restored the literal-`0` restriction in
[`WrappedValueModel.__init__`](../../src/eq1_pulse/models/base_models.py#L74-L102).
A single positional argument is now accepted only for `0`; any other value raises
`ValueError` naming the class and suggesting the matching keyword (e.g.
`Duration(5)` → *"5 is not a valid positional argument for Duration(); ... use
Duration(s=5)"*). This restores exactly the behavior each concrete class enforced
individually on `main` (`_apply_default_zero_args_to_init_data`), but centralized in
the base class the way this branch had already, rather than reverting the
one-`__init__`-for-all-subclasses simplification. Pinned by
[tests/eq1lab_pulse/models/test_wrapped_value_positional_args.py](../../tests/eq1lab_pulse/models/test_wrapped_value_positional_args.py).

The related poor error for the *string* form was left as-is — it is a smaller,
separate issue, and the fix above already stops the dangerous case (a bare number
silently choosing a unit). It reads as the natural thing to write:

```python
Duration("10us")   # ValidationError: 7 validation errors ... unable to parse
                   # string as a number
Phase("90deg")     # ValidationError: 8 validation errors
```

(The builder's `phase("90deg")` helper works, because it routes to
`model_validate` — the inconsistency between `phase()` and `Phase()` is itself
worth resolving.) Route non-numeric positionals to `model_validate`, or raise a
clear `TypeError` naming the supported forms.

### D4. `for_(["i", "j"], range(10))` is documented as supported but always fails  *[Fixed]*

[core.py:924-928](../../src/eq1_pulse/builder/core.py#L924-L928):

```python
if not isinstance(items, list):
    # Single iterable provided for multiple variables - wrap in list
    # This allows for_(["i", "j"], range(10)) to iterate same range for both
    validated_items = [_convert_range_to_model(items)]
```

Wrapping one iterable in a one-element list against two variables always trips
the model's length check:

```
ValidationError: Both 'var' and 'items' must have the same length.
```

Either broadcast properly (`[converted] * len(validated_vars)`) or drop the
branch and raise a clear `ValueError` at the builder level. As written the
comment promises behavior the code cannot deliver.

### D5. `_convert_range_to_model` silently swallows degenerate ranges  *[Fixed]*

[core.py:780](../../src/eq1_pulse/builder/core.py#L780) maps an empty Python
range to `[]`, so `for_("i", range(10, 0, 2))` builds a loop that never executes,
with no diagnostic. Given the function already documents that Python `range` and
the `Range` model differ in three ways (inclusive stop, step-sign handling,
divisibility), a wrong-direction step is far more likely a typo than an
intention. Recommend raising `ValueError` for the empty case, and keeping the
silent fallback only for the "step doesn't divide evenly" path.

### D6. `op_counter` is global and never reset  *[Fixed]*

`BuilderState.op_counter` persists across `build_schedule()` calls, so building
the same program twice in one process yields `op_1…` then `op_11…`. That makes
serialized output non-reproducible and golden-file comparison awkward. Reset the
counter in `build_schedule()`/`build_sequence()` when the context stack is empty.

### D7. `measure()` in sequence context is not a measurement  *[Not fixed]*

[core.py:2265-2271](../../src/eq1_pulse/builder/core.py#L2265-L2271) — the
comment concedes it:

```python
# Note: In a true measurement, play and record should be simultaneous
# This requires the backend to handle the timing correctly
play(drive_channel, meas_pulse)
record(readout_channel, result_var, ...)
```

The module docstring for `sequence.py` explicitly carves out "a Play and its
corresponding Record" as the one same-channel-same-time exception, so the IR
does have a notion of this pairing — but nothing in the emitted sequence marks
these two operations as that pair. A backend seeing two independent ops will
serialize them. Either emit a marker the backend can key on, or promote the
caveat from an inline comment into the public docstring so users know the
sequence form is approximate.

---

## P2 — Documentation defects

The RST and docstrings were clearly written alongside an earlier signature set.
Every example below raises immediately:

| Location | Written | Problem |
|:---|:---|:---|
| [builder/__init__.py:23](../../src/eq1_pulse/builder/__init__.py#L23), [core.py:20](../../src/eq1_pulse/builder/core.py#L20), [core.py:508](../../src/eq1_pulse/builder/core.py#L508) | `wait("ch1", "5us")` | `duration` is keyword-only → `TypeError` |
| [core.py:2165](../../src/eq1_pulse/builder/core.py#L2165) (`store` docstring) | `with repeat(range(100)):` | `count` must be `int` → `ValidationError` |
| [builder_guide.rst:913](../../docs/source/user_guide/builder_guide.rst#L913), [:994](../../docs/source/user_guide/builder_guide.rst#L994), [:1331](../../docs/source/user_guide/builder_guide.rst#L1331) | `record(ch, var=v, duration="1us")` | `integration` is required → `TypeError` |
| [builder_guide.rst:1316](../../docs/source/user_guide/builder_guide.rst#L1316) | `integration="full"` | must be `full_integration()` → `ValidationError` |
| [builder/__init__.py:36](../../src/eq1_pulse/builder/__init__.py#L36) | `measure(..., duration="1us", amplitude="50mV")` | `integration` is required → `TypeError` |
| 6 sites (see [D2](#d2)) | `add_block(..., name="init")` | silently ignored |

**Root cause and the real fix:** none of this documentation is executed. The
examples in `examples/` all run (I checked), but the RST snippets and the
`.. code-block:: python` docstrings are inert text. Two cheap mitigations, in
order of value:

1. Convert the docstring examples to **doctests** and add `--doctest-modules`
   for `src/eq1_pulse/builder/` to the pytest config. Every table row above would
   have been caught at commit time.
2. Add a test that imports and executes each `examples/*.py` (they already all
   pass), so the working reference material stays working.

Also worth noting: the docstring examples are `.. code-block:: python`, so
Sphinx does not check them either — `sphinx.ext.doctest` on the RST would close
the remaining gap.

### Docs housekeeping

- **Two unused generator modules.** `docs/source/_generator/rabi_duration_diagram.py`
  and `schedule_diagram.py` are not imported by any `.. plot::` block.
  `rabi_duration_diagram.py` also overlaps almost entirely with
  `duration_rabi_diagram.py` — near-identical name, same subject. Delete the dead
  pair or wire them in; the name collision alone will cause future confusion.
- **Contradictory conf.py comment.** [conf.py](../../docs/source/conf.py) —
  `# Show only SVG in HTML output (True to show all formats)` immediately above
  `plot_html_show_formats = True`. The comment says the opposite of the value.
- **`matplotlib` is now a hard docs dependency** (`plot_directive` un-commented,
  `matplotlib` added to the `doc` extra) — correct, just flagging that doc builds
  now execute arbitrary generator code at build time. `plot_working_directory`
  and `plot_basedir` both point at `_generator`, so a generator that opens a
  figure without closing it will accumulate across the build; the generators
  return `fig` and only call `plt.show()` under `__main__`, which is right, but
  none call `plt.close()`.
- **`.gitignore`.** `*.pdf` was added globally; `docs/source/.gitignore`
  re-allows `_static/*.pdf`. That works, but the global `*.svg`/`*.pdf` ignores
  mean any future contributor adding an asset outside `_static/` will silently
  lose it. Consider narrowing the global patterns to the build output paths.

---

## P3 — Tooling and process

<a id="t1"></a>
### T1. `mypy src` fails — the QA gate is red  *[Fixed]*

```
src/eq1_pulse/models/basic_types.py:430: error: Returning Any from function declared to return "Amplitude"  [no-any-return]
src/eq1_pulse/models/basic_types.py:440: error: Returning Any from function declared to return "Amplitude"  [no-any-return]
```

Both in the new `Phase.__matmul__` / `__rmatmul__`
([basic_types.py:423-441](../../src/eq1_pulse/models/basic_types.py#L423-L441)) —
`self.complex_rotation * rhs` is `Any` because `ArithmeticFrozenWrappedValueModel.__mul__`
is untyped at that position. `qa/run_all_qa.sh` runs mypy, so this must be green
before merge. Annotate the intermediate, or type `__mul__`'s return properly.

Related: the `__as_amplitude` helper returns `NotImplemented` behind
`# type: ignore`, and callers check `rhs is NotImplemented`. That works, but the
declared return type `-> Amplitude` is a lie that is causing the two mypy errors
downstream. Declare it `-> Amplitude | type(NotImplemented)`-equivalent
(practically: `-> Any` with a comment, or restructure so `__matmul__` does the
`isinstance` dispatch itself and returns `NotImplemented` directly).

### T2. Suppressed type errors are hiding real bugs  *[Partly fixed]*

There were ~20 `# type: ignore[...]` comments in `builder/core.py`. One of them
([D1](#d1), `sub_schedule`'s `return token`) was suppressing a genuine defect; that
one is gone along with the dead code it hid.

17 remain. They fall into two groups, and only the second is worth further work:

- **Load-bearing** — `yield` inside the `@contextmanager` overloads (`[misc]`, 4 sites)
  and the `**sched_params` splats into pydantic constructors (`[arg-type]`). These
  reflect real limits of typing `contextlib` and `Unpack`, and are fine as they are.
- **Worth revisiting** — the `[arg-type]` suppressions on model construction
  (`Wait`, `Record`, `Store`, `Discriminate`, `DemodIntegration`, `ExternalPulse`)
  exist because the builder accepts `…Like` union types that the model `__init__`
  overloads do not declare. Widening those model signatures would remove six
  suppressions and make the accepted input types visible to callers, rather than
  asserted away at the call site.

### T3. Test coverage gaps align with the bugs  *[Fixed]*

`builder/core.py` was at 88%, and the uncovered lines were exactly the risky ones:
`682-699` (the `sub_schedule` unconsumed-block path and the dead `return token`),
`946-959` / `1014-1027` (the schedule-context branches of `for_` and `if_`),
`1900` / `1935` / `1970` / `2005` (the schedule branches of the four
frequency/phase setters — i.e. [B1](#b1) was uncovered precisely because no test put
them in a schedule).

`builder/core.py` is now at **95%**, and the branches that hid B1, B3, B4 and D6 are
covered by the four new test modules listed under [Status](#status). The context matrix
was checked against the original bug: reverting `set_frequency` alone to its narrow
`isinstance(context, Schedule)` check fails three of its cases.

What remains uncovered is the error-reporting arms of `_add_to_sequence` /
`_add_to_schedule` and a few `RuntimeError` guards for context types the public API
cannot actually produce — reachable only by calling the private helpers directly.

---

## Things that are right

Worth saying explicitly, since the list above is long:

- `BuilderState` in a `ContextVar` (commit `f4d2dcf`) is the correct call for
  thread/async safety and is a real improvement over module globals.
- `ScheduleBlock` capturing its creation traceback so the "unconsumed block"
  error can point at the offending call site is a genuinely thoughtful touch.
- The `register_unit_of_zero` / `register_comparison_unit` decorators replace a
  large amount of duplicated `model_validate*` override boilerplate in
  `base_models.py` with a declarative registry — a clear net simplification.
- `_reject_schedule_params` giving an explicit "use `build_schedule()` instead"
  message is exactly the right level of hand-holding for a DSL.
- The examples are all runnable and cover the API broadly.

---

## What was deliberately left alone

Two items in this review were **not** applied, because they are decisions rather
than defects. (D3 was originally in this section too — it has since been fixed on
request; see [D3](#d3) above.)

### D7 — `measure()` in a sequence emits two unlinked operations

Left as-is. Marking the play/record pair in the emitted IR is a format question that
touches the model layer and whatever consumes it, not a builder-local fix. The caveat
was promoted from an inline comment into the public docstring so the approximation is
at least visible to callers.

### Two dead diagram generators

`docs/source/_generator/rabi_duration_diagram.py` and `schedule_diagram.py` are still
unreferenced by any `.. plot::` block, and `rabi_duration_diagram.py` still overlaps
almost entirely with `duration_rabi_diagram.py`. They are not deleted here: they may be
work in progress, and that call belongs to whoever wrote them.

One item from the original review turned out to be a **non-issue**: the generators do
not need `plt.close()`. Matplotlib's `plot_directive` calls `plt.close("all")` between
blocks itself, so figures do not accumulate across the build.

### Note on the two API changes that did land

[D1](#d1) and [D2](#d2) change public behavior and are worth calling out before this
interface is announced:

- `sub_schedule()` now yields an `OperationToken` rather than the `Schedule`. Nothing
  in the repository used the yielded value, and the token is what the (previously dead)
  `return token` was reaching for.
- `name=` is now **rejected** with `TypeError: Use 'op_name' to name a scheduled
  operation, not 'name'.` rather than silently ignored. Accepting it as an alias was
  the first instinct, but `var_decl(name=...)` and `pulse_decl(name=...)` already bind
  that keyword to a parameter of their own, so an alias would work for `play` and not
  for those two. One spelling with a pointed error beats an alias that is only
  sometimes available. All doc sites were updated to `op_name`.
