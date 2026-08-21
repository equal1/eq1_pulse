# Plan: external constants and parameter variables

**Issue:** [#6 — Feature: external constants and pulse parameter variables](https://github.com/equal1/eq1_pulse/issues/6)
**Status:** accepted — all open questions closed (§9); see
[symbols-and-parameters-tasks.md](symbols-and-parameters-tasks.md) for the execution breakdown
**Date:** 2026-08-21
**Successors:** [expressions-plan.md](expressions-plan.md) (#3) builds directly on the `SymbolRef` alias introduced here.

---

## 0. What the issue asks for

| # | Requirement                                                                                | Where it lands                                  |
| - | ------------------------------------------------------------------------------------------ | ------------------------------------------------- |
| 1 | Refer to **external constants by name** wherever a variable or constant may appear           | new `ExternalRef` + widened read-site unions      |
| 2 | Names follow `identifier[index].attribute`; only the leading identifier is mandatory         | new `ExternalSymbolStr` validated string type     |
| 3 | Declare **parameter** variables (names are plain identifiers)                                | new `ParameterDecl` data op                       |
| 4 | Architectural place for **limits** on parameter/constant values                              | new `ValueLimits` model on both declarations      |
| 5 | Optional **default values** for parameters and external symbols                              | `default` field on both declarations              |
| 6 | **Units** are expressed in the declaration                                                   | `unit` field, reused from `VariableDecl`          |
| 7 | All of it available in **models, schema and builder**                                        | §3, §4, §5                                        |

### The motivating use case, restated

A calibration framework holds the current value of `q0.f01`, `q0[1].amp`, `readout.threshold`. A
pulse program refers to those *by name* and is submitted once. When calibration moves, the same
serialized program is re-submitted against fresh values — **the IR is never rebuilt**. That is the
whole point of `ExternalRef` and it is what distinguishes it from a `VariableRef`: a variable is
bound *inside* the program, an external constant is resolved *outside* it.

---

## 1. Scope and framing decisions

These are settled and constrain everything below.

| Decision                                                              | Consequence                                                                                                                                     |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Declare-only. eq1_pulse never enforces units or limits.**             | `unit`, `limits` and `default` are carried through the model and the schema and are otherwise inert. No dimensional analysis, no range checking. The issue is explicit: "any outside framework is responsible to convert the units if possible or reject them". |
| **A parameter is a variable with an external binding, not a new reference kind.** | `ParameterDecl` declares a name; that name is referenced with the ordinary `VariableRef`. Zero changes to any read-site union for parameters. Only the *declaration* is new. |
| **No "Parameterized sequence" container.**                             | The issue offers a declaration *or* a container. A declaration op composes with everything that already exists (nesting, sub-sequences, control flow, the schedule world) and adds one entry to `DataOp`. A container would require a new top-level model, a new builder entry point, a new union member in `OpSequenceItem`, and a rule for what happens when one is nested. Rejected as the larger change for no extra expressiveness — see §9 Q4. |
| **External symbols must be declared before use.**                      | Symmetric with variables, and it is the declaration that carries the unit — requirement 6 is meaningless without it. Enforced in the builder, not in the models (same split as `VariableRef` today). |
| **Read sites widen; write sites do not.**                              | An external constant is read-only by construction. `Iteration.var`, `Record.var`, `Trace.var`, `Discriminate.target`, `Store.source`, `ExternalBlock.results` keep `VariableRef`. See §2. |
| **No new model modules.**                                              | Everything lands in existing modules already listed in `openapi_generator.model_modules`, so schema generation needs one line changed, not a new entry. |
| **`ExternalRef` keeps a wrapped `{"ext": "..."}` wire form.**           | The one deliberate asymmetry in the `Reference` hierarchy. In ordinary reference unions a bare JSON string means `VariableRef`; in `ExternalParamValue`, arbitrary strings remain `str` and references use tagged objects. §3.2. |
| **Widening reaches every plausible read site, not only today's `VariableRef` sites.** | Nine fields that are concrete-only today also widen. §2.                                                                          |
| **External symbols use `dtype` + a free-form `unit` string, exactly like variables.** | One declaration shape across all three kinds. No dimensional types as dtypes.                                                     |
| **Indices are integers.**                                              | `q0[1].amp` yes, `q0["aux"].amp` no. String keys can be added later without invalidating any existing symbol.                                    |
| **Declarations are lexically scoped, exactly like variables.**          | One scoping rule in the language, and `_state.py` already implements it.                                                                        |

---

## 2. Read sites vs write sites

The single largest piece of mechanical work is widening the right unions and only those. This is
the complete inventory, measured on `main`.

### Read sites — widen `VariableRef` → `SymbolRef`

| Module                | Field                                                                            |
| ----------------------- | ---------------------------------------------------------------------------------- |
| `pulse_types.py`      | `PulseBase.duration`, `PulseBase.amplitude`                                        |
| `pulse_types.py`      | `SquarePulse.rise_time`, `SquarePulse.fall_time`                                    |
| `pulse_types.py`      | `SinePulse.frequency`, `SinePulse.to_frequency`                                     |
| `pulse_types.py`      | `ExternalPulse.duration`, `ExternalPulse.amplitude`                                 |
| `pulse_types.py`      | `ExternalParamValue` / `ExternalParamValueLike` (the `VariableRef` member)           |
| `channel_ops.py`      | `Play.scale_amp`, `Play.cond`                                                       |
| `channel_ops.py`      | `Wait.duration`                                                                     |
| `channel_ops.py`      | `SetFrequency.frequency`, `ShiftFrequency.frequency`                                |
| `channel_ops.py`      | `SetPhase.phase`, `ShiftPhase.phase`                                                |
| `channel_ops.py`      | `Record.duration`, `Trace.duration`                                                 |
| `channel_ops.py`      | `CompensateDC.duration`, `CompensateDC.rise_time`, `CompensateDC.fall_time`          |
| `control_flow.py`     | `ConditionalBase.var`                                                               |
| `external_block.py`   | `ExternalBlock.duration` (`params` widens via `ExternalParamValue`)                 |

#### Also widened — concrete-only today

These have no `VariableRef` alternative at present. Widening them makes them accept `SymbolRef`
where they accept only a literal now, so each is *both* an external-constant change and a
runtime-variability change. Decided in favour of widening: a calibration store that cannot supply a
readout threshold or a time-of-flight is not much of a calibration store.

| Module             | Field                                                        | Widened to                              |
| -------------------- | -------------------------------------------------------------- | ----------------------------------------- |
| `control_flow.py`  | `RepetitionBase.count`                                       | `int \| SymbolRef`                       |
| `data_ops.py`      | `Discriminate.threshold`                                     | `Threshold \| SymbolRef`                 |
| `data_ops.py`      | `Discriminate.rotation`                                      | `Phase \| SymbolRef`                     |
| `channel_ops.py`   | `Record.time_of_flight`, `Trace.time_of_flight`              | `Duration \| SymbolRef \| None`          |
| `channel_ops.py`   | `CompensateDC.max_amp`                                       | `Magnitude \| SymbolRef \| None`         |
| `channel_ops.py`   | `DemodIntegration.phase`                                     | `Phase \| SymbolRef \| None`             |
| `channel_ops.py`   | `DemodIntegration.scale_cos`, `DemodIntegration.scale_sin`   | `float \| SymbolRef`                     |

`RepetitionBase.count` also requires `builder.core.repeat()` to widen its `count: int` parameter and
route it through `_validate_or_pass_through`. `count` keeps its `ge=0` constraint for the literal
branch; there is no constraint to apply to the symbol branch, which is exactly the "declare, never
enforce" split.

`DemodIntegration.scale_cos` / `scale_sin` default to `1`. Widening a field that has a non-`None`
default is the one place `LeanModel`'s default-elision serializer can surprise: confirm the defaults
still elide after the change.

### Write sites — leave as `VariableRef`

| Module              | Field                                                             | Why                                              |
| --------------------- | ------------------------------------------------------------------- | -------------------------------------------------- |
| `control_flow.py`   | `IterationBase.var`                                                | loop binding target                              |
| `channel_ops.py`    | `Record.var`, `Trace.var`                                          | acquisition destination                          |
| `data_ops.py`       | `Discriminate.target`                                              | assignment destination                           |
| `external_block.py` | `ExternalBlock.results`                                            | output bindings                                  |
| `data_ops.py`       | `Store.source`                                                     | names a program variable to persist, not a value |

`Discriminate.source` is a genuine read site but reads a *run-time acquisition result*; an external
constant there is meaningless. Left as `VariableRef`.

---

## 3. Model changes

### 3.1 `identifier_str.py` — the external symbol grammar

```python
type ExternalSymbolStr = Annotated[str, AfterValidator(str_is_external_symbol)]
```

Grammar, as an EBNF, derived from the issue's `identifier[index].attribute`:

```text
external_symbol ::= segment ( "." segment )*
segment         ::= identifier ( "[" index "]" )?
index           ::= integer
```

So `q0`, `q0[1]`, `q0.f01`, `q0[1].amp`, `chip.q0[3].readout.threshold` are all valid; `1q`, `q0[]`,
`q0.` and `q0[a]` are not. The module already has `str_is_fully_qualified_identifier` doing the
dotted-identifier half of this; the new validator is that plus optional bracketed indices, and
should be written next to it and share its style.

The `index` production is integer-only by decision, not by accident — §9 Q2. String keys can be
added later without invalidating any symbol that is valid today.

### 3.2 `reference_types.py` — `ExternalRef` and the `SymbolRef` alias

```python
class ExternalRef(Reference):
    """Reference to a constant resolved outside the program."""

    ext: ExternalSymbolStr


type SymbolRef = VariableRef | ExternalRef
type SymbolRefLike = VariableRefLike | ExternalRef | ExtRefDict
```

**`ExternalRef` does not serialize bare.** Every other `Reference` unwraps to its single field's
value, so `VariableRef("amp")` serializes to `"amp"`. If `ExternalRef` did the same, `"q0"` on the
wire would be ambiguous between the two — the issue makes the leading identifier the only mandatory
part, so every bare variable name is also a well-formed external symbol. `ExternalRef` therefore
overrides `_wrap_serializer` and `model_json_schema` to keep the wrapped `{"ext": "q0[1].amp"}` form.
Validation still accepts the bare string, so `ExternalRef("q0.f01")` and
`ExternalRef.model_validate({"ext": "q0.f01"})` both work.

Consequences to hold onto:

- In the `SymbolRef` union, a bare JSON string is **always** a `VariableRef`. `VariableRef` is
  listed first so pydantic's smart mode resolves it that way even before the wrapped form is
  considered.
- Round-tripping any model containing an `ExternalRef` is lossless and unambiguous.
- This is the one place where the reference hierarchy is deliberately not uniform. The class
  docstring must say why, in those words, or someone will "fix" it.

A sigil prefix such as `"$q0.f01"` was the alternative; it was considered and rejected — §9 Q1.

### 3.3 `data_ops.py` — limits, defaults, and the two new declarations

```python
type SymbolValue = Amplitude | Duration | Frequency | Phase | Magnitude | Voltage | Threshold | bool | int | float | complex


class ValueLimits(LeanModel):
    """Declared bounds on a symbol's value. Carried, never enforced."""

    minimum: SymbolValue | None = None
    maximum: SymbolValue | None = None
    allowed: list[SymbolValue] | None = None
```

`ValueLimits` is deliberately three inert fields. It is the "architectural place to express limits"
the issue asks for and nothing more; the moment eq1_pulse tries to check one of them it has taken on
unit conversion, which §1 says it does not do.

`VariableDecl` grows a sibling structure. Factor the shared shape out rather than copying it:

```text
SymbolDeclBase(DataOpBase)          # dtype, shape, unit
├── VariableDecl                    # op_type="var_decl"      (unchanged on the wire)
├── ParameterDecl                   # op_type="param_decl"    + default, limits
└── ExternalDecl                    # op_type="extern_decl"   + default, limits, name is ExternalSymbolStr
```

- `VariableDecl` gains **nothing**. Its serialization is byte-identical to today. This must be
  asserted by a test — it is the compatibility guarantee for every already-serialized program.
- `ParameterDecl.name` is `IdentifierStr` (the issue: "parameter names are usually identifiers").
- `ExternalDecl.name` is `ExternalSymbolStr`.
- `default: SymbolValue | None = None` on both.
- `limits: ValueLimits | None = None` on both.
- `SymbolDeclBase` goes into `openapi_generator.excluded_base_classes`.
- `DataOp` becomes `VariableDecl | ParameterDecl | ExternalDecl | PulseDecl | Discriminate | Store`.

### 3.4 What a parameter *means*

`ParameterDecl` declares a name whose value is supplied when the program is submitted, rather than
computed inside it. Everything else about it is a variable: it is referenced with `var("amp")`, it
obeys the same lexical scoping, it may be read anywhere a variable may be read. `default` makes it
optional at submission time.

The distinction from `ExternalDecl` is *who resolves it*: a parameter is supplied per-submission by
the caller; an external constant is looked up per-submission in a calibration store by name. Both
are late-bound, neither is written by the program.

---

## 4. Schema

No generator change beyond adding `SymbolDeclBase` to `excluded_base_classes`. `ExternalRef`,
`ValueLimits`, `ParameterDecl` and `ExternalDecl` all live in modules already in `model_modules`
and are picked up by the existing `inspect.getmembers` sweep.

Verify after the change:

- `ExternalRef` appears as `{"type": "object", "properties": {"ext": {...}}}`, **not** as a bare
  string — this is the observable consequence of §3.2 and the thing most likely to regress.
- `ValueLimits`, `ParameterDecl`, `ExternalDecl` are present in `components.schemas`.
- `SymbolDeclBase` is absent.
- The `VariableDecl` entry is unchanged.

`tests/test_openapi_generator.py` already exists and is the place for these.

---

## 5. Builder

### 5.1 New public functions

| Function                                                              | Module          | Notes                                                                 |
| ----------------------------------------------------------------------- | ----------------- | ----------------------------------------------------------------------- |
| `ext(name) -> ExternalRef`                                            | `_factories.py` | Sibling of `var()`. Checks the symbol was declared.                   |
| `param_decl(name, dtype, *, shape=, unit=, default=, min=, max=, allowed=)` | `core.py`  | Sibling of `var_decl()`. Registers into the **variable** namespace.   |
| `extern_decl(name, dtype, *, shape=, unit=, default=, min=, max=, allowed=)` | `core.py` | Registers into the **external** namespace.                            |

Limits are passed as flat `min=` / `max=` / `allowed=` keywords and assembled into `ValueLimits`
internally; if all three are `None` the field stays `None`. No `limits()` factory function — three
keywords on two functions does not need a builder of its own.

All three names are added to `builder/__init__.py`'s import list and `__all__`, both of which are
kept sorted.

### 5.2 Builder state

`BuilderState` gains one parallel stack next to `declared_variables`:

```python
declared_externals: list[set[str]] = field(default_factory=list)
```

pushed and popped in `_push_context` / `_pop_context` alongside the others, with
`_register_external`, `_is_external_declared` and `_check_external_declared` mirroring the variable
functions. `_state.py`'s docstring already explains why this state lives here; no new rationale needed.

`param_decl` calls the existing `_register_variable` — parameters and variables share one namespace,
so `var_decl("x", ...)` after `param_decl("x", ...)` is a redeclaration error, which is correct.

### 5.3 Validation plumbing

`_validate_or_pass_through` and `_validate_explicit_variable_ref` in `_factories.py` are the choke
points every operation's parameters pass through. Both grow one branch:

- an `ExternalRef` instance → check declared, pass through;
- a dict with an `"ext"` key → build `ExternalRef`, check declared, pass through.

An identifier-like *string* continues to mean a variable, never an external symbol. A string is
promoted to `ExternalRef` **never** — external symbols must be spelled `ext("q0.f01")` or
`{"ext": "q0.f01"}`. This mirrors §3.2's wire-format rule and keeps one rule in the user's head
instead of two.

`tests/eq1lab_pulse/test_validate_or_pass_through.py` is the existing home for these cases.

### 5.4 The experimental schedule builder

`builder/experimental/schedule.py` has its own copies of the operation functions but shares
`_factories.py` and `_state.py`. It therefore inherits `ext()` and the widened validation for free.
`param_decl`/`extern_decl` are **not** added to the experimental builder — the module is documented
as unused and scheduled for removal, and `test_module_boundaries.py` exists to keep the sequence
world from depending on it.

---

## 6. Example

```python
from eq1_pulse.builder import *

with build_sequence() as seq:
    # Supplied at submission time, with a fallback.
    param_decl("n_shots", "int", default=1000, min=1, max=100_000)

    # Resolved from the calibration store at submission time.
    extern_decl("q0.f01", "float", unit="GHz")
    extern_decl("q0.pi_amp", "float", unit="mV")
    extern_decl("readout.threshold", "float", unit="mV")

    var_decl("iq", "complex", unit="mV")
    var_decl("state", "bool")

    set_frequency("q0_drive", ext("q0.f01"))

    with repeat(var("n_shots")):
        play("q0_drive", square_pulse(duration="25ns", amplitude=ext("q0.pi_amp")))
        record("q0_readout", var="iq", duration="1us", integration=full_integration())
        discriminate(target="state", source="iq", threshold=ext("readout.threshold"))
        store(key="p1", source="state", mode="average")
```

Note `repeat(var("n_shots"))` and `threshold=ext("readout.threshold")`: both are among the
concrete-only fields widened in §2. Neither works before this plan lands.

---

## 7. Tests

| File                                                        | Add                                                                                     |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `tests/eq1lab_pulse/models/test_reference_types.py`         | `ExternalSymbolStr` grammar accept/reject table; `ExternalRef` wrapped round trip; `SymbolRef` union disambiguation (bare string → `VariableRef`) |
| `tests/eq1lab_pulse/models/test_data_ops.py`                | `ParameterDecl` / `ExternalDecl` construction, defaults, limits; **`VariableDecl` serialization unchanged** |
| `tests/eq1lab_pulse/models/test_channel_ops.py`             | one widened field per operation family accepts an `ExternalRef`                          |
| `tests/eq1lab_pulse/models/test_pulse_types.py`             | pulse parameters accept `ExternalRef`                                                    |
| `tests/eq1lab_pulse/models/test_sequence.py`                | a sequence containing all three declaration kinds round-trips                            |
| `tests/eq1lab_pulse/test_builder.py`                        | `param_decl` / `extern_decl` / `ext` happy paths                                         |
| `tests/eq1lab_pulse/test_builder_variable_verification.py`  | `ext()` on an undeclared symbol raises; `param_decl` collides with `var_decl`             |
| `tests/eq1lab_pulse/test_validate_or_pass_through.py`       | `ExternalRef` and `{"ext": ...}` branches; identifier string still means variable         |
| `tests/test_openapi_generator.py`                           | the four checks in §4                                                                     |

Write-site negative tests matter as much as the positive ones: `Iteration(var=ExternalRef("q0"))`,
`Record(var=ExternalRef("q0"))` and `Discriminate(target=ExternalRef("q0"))` must all fail validation.

---

## 8. Docs

- `docs/source/user_guide/builder_guide.rst` — a section on late-bound values covering both kinds and,
  explicitly, when to reach for which.
- `examples/calibrated_rabi.py` — the §6 example, made runnable. `tests/test_examples.py` picks up
  `examples/` automatically; confirm the discovery mechanism before assuming it.
- Class docstrings carry the semantics (this codebase documents heavily in the models, per
  `external_block.py`); the plan text above is the source for them.

---

## 9. Decisions closed

Every question raised while drafting is answered. Recorded here so they are not re-litigated; the
reasoning is preserved so they *can* be reopened deliberately.

| #  | Question                                                                                     | Decision                                                                                                                              |
| -- | ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Q1 | Wire format for `ExternalRef`                                                                | **Wrapped `{"ext": "q0.f01"}`.** No escaping rule, no sigil in source, self-describing in the schema. Cost: one documented asymmetry in the `Reference` hierarchy. Rejected: a `"$q0.f01"` sigil; requiring two segments so a bare identifier is always a variable (contradicts the issue). |
| Q2 | Index type in the grammar                                                                    | **Integers only.** `q0[1].amp` yes, `q0["aux"].amp` no. Adding string keys later invalidates no existing symbol.                       |
| Q3 | Must external symbols be declared?                                                           | **Yes, required.** `ext()` on an undeclared symbol raises, exactly as `var()` does. Every external reference in a program then has a declared unit — which is what lets the outside framework convert or reject. Rejected: optional declaration; auto-declaring on first use (a builder call silently mutating the sequence is unlike anything else in the API, and the auto-declaration would carry no unit). |
| Q4 | `ParameterDecl` op vs a `ParameterizedSequence` container                                    | **The op.** Composes with nesting, control flow and sub-sequences for free; adds one `DataOp` union member instead of a new container, a new builder entry point and a nesting rule. A flat parameter list, if ever needed, is a tree walk — a utility, not a model change. |
| Q5 | How far "wherever variables or constants can appear" reaches                                 | **Everything plausible.** The nine concrete-only fields in §2 widen too. A calibration store that cannot supply a readout threshold or a time-of-flight is not much of a calibration store. |
| Q6 | How an external symbol's type is declared                                                    | **`dtype` + free-form `unit` string, identical to `VariableDecl`.** One declaration shape across all three kinds. Rejected: dimensional types (`Frequency`, `Amplitude`) as dtypes — a second way to say what a type is, while `VariableDecl` would still use the first. |
| Q7 | Are declarations scoped or global?                                                           | **Lexically scoped, like variables.** One rule in the language, and `_state.py` already implements it.                                 |

### Deliberately not decided here

- **Whether the outside framework rejects or converts a unit mismatch.** Out of scope by §1. This
  plan's job is to make the unit *present*.
- **How a calibration store is addressed or discovered.** `ExternalRef` names a symbol; who resolves
  it is a submission-time concern with no representation in the IR.
