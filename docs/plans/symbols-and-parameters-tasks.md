# Execution breakdown: external constants and parameter variables

Companion to [symbols-and-parameters-plan.md](symbols-and-parameters-plan.md) (issue #6). Seven
independently executable tasks, each sized for a single clean session.

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
> `*Like` aliases accompany every new model type. `TYPE_CHECKING` imports to break cycles.
>
> **Verify.** `./qa/run_all_qa.sh` (pyright + mypy + pytest with coverage). It must pass before you
> report done. If it passed before your change and fails after, you are not done.
>
> **Context.** Read `docs/plans/symbols-and-parameters-plan.md` — the sections named in your task —
> before starting. Do not re-litigate decisions recorded there; §1 and §9 list the ones already
> closed.
>
> **Scope.** Do only what your task says. Each task lists an explicit *out of scope* set. If you
> believe a listed exclusion is wrong, say so in your final message rather than acting on it.

---

## Dependency graph

```text
1 ──┬──> 2 ──────────┬──> 5 ──> 6 ──> 7
    └──> 3 ──> 4 ────┘
```

Safe merges if you want fewer sessions: **3 + 4** (both are the same widening edit over different
field sets) and **6 + 7**. Do not merge 1 into anything — it is the task most likely to need a
second pass.

| #  | Task                                                | Size | Model      | Reasoning | Context     | Touches                                     |
| -- | ----------------------------------------------------- | ---- | ---------- | --------- | ----------- | --------------------------------------------- |
| 1  | `ExternalSymbolStr`, `ExternalRef`, `SymbolRef`     | M    | Opus 5     | high      | 200k / ~45k | `models/`, `tests/`                         |
| 2  | Declarations: limits, params, externals             | M    | Sonnet 5   | high      | 200k / ~40k | `models/data_ops.py`, `tests/`               |
| 3  | Widen the existing `VariableRef` read sites         | M    | Sonnet 5   | medium    | 200k / ~55k | `models/`, `tests/`                         |
| 4  | Widen the concrete-only read sites                  | M    | Sonnet 5   | high      | 200k / ~45k | `models/`, `builder/core.py`, `tests/`       |
| 5  | Builder: `ext()`, external namespace, validation    | M    | Sonnet 5   | high      | 200k / ~50k | `builder/`, `tests/`                        |
| 6  | Builder: `param_decl()`, `extern_decl()`, exports   | S    | Sonnet 5   | medium    | 200k / ~35k | `builder/`, `tests/`                        |
| 7  | Schema checks, docs, example                        | S    | Haiku 4.5  | medium    | 200k / ~30k | `utilities/`, `docs/`, `examples/`, `tests/` |

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

**Why these assignments.** Task 1 overrides pydantic's serializer and JSON-schema machinery, where a
mistake produces a model that works everywhere except the one union that matters — silent, and no
precedent in the tree for overriding those two methods together. Task 7 is checklist work. Tasks 3
and 6 are `medium` despite their size because they are mechanical edits against an explicit field
inventory; tasks 4 and 5 are `high` because both perturb `LeanModel` default elision and smart-union
resolution, which fail quietly. No task here needs more than the 200k standard window.

---

## Task 1 — `ExternalSymbolStr`, `ExternalRef`, `SymbolRef` ✅ done

**Status:** done, 2026-08-21. One addition beyond the steps below: `Reference._wrap_serializer`
gained a `_serializes_bare` guard. Without it the `SymbolRef` smart union serialized an
`ExternalRef` bare — a plain `@model_serializer` is called without an instance check, so the
`VariableRef` member accepted the value and won. See
`test_symbol_ref_union_serialization_is_unambiguous`.

The wrapped wire form is therefore a three-part contract: `_serializes_bare = False`, an overridden
`_wrap_serializer`, and an overridden `model_json_schema`. `Reference.__pydantic_init_subclass__`
rejects any subclass that declares one without the others, or that defines other than exactly one
field, so a future reference class cannot silently reintroduce the bug or ship a schema that
disagrees with its serializer.

**Read:** plan §3.1, §3.2, and the §9 Q1/Q2 rows.
**Goal:** an external symbol can be spelled, validated, and round-tripped. Nothing uses it yet.

### Steps

1. In `models/identifier_str.py`, add `str_is_external_symbol` and
   `type ExternalSymbolStr = Annotated[str, AfterValidator(str_is_external_symbol)]`, next to and in
   the style of the existing `str_is_fully_qualified_identifier`. Grammar:

   ```text
   external_symbol ::= segment ( "." segment )*
   segment         ::= identifier ( "[" integer "]" )?
   ```

   Accept: `q0`, `q0[1]`, `q0.f01`, `q0[1].amp`, `chip.q0[3].readout.threshold`.
   Reject: `1q`, `q0[]`, `q0.`, `q0[a]`, `q0["aux"]`, `q0[-1]`, `""`, `q0..f01`.

2. In `models/reference_types.py`, add `ExternalRef(Reference)` with the single field
   `ext: ExternalSymbolStr`.

   **It must not serialize bare.** Override `_wrap_serializer` to return `{"ext": self.ext}` and
   `model_json_schema` to return the object schema rather than the unwrapped field schema — the
   base class does the opposite of both. Validation still accepts a bare string via the inherited
   `_wrap_validator`, so `ExternalRef("q0.f01")` works.

   The class docstring must say *why* this class breaks the hierarchy's uniformity, in those words:
   a bare `"q0"` would be ambiguous with a `VariableRef` because the leading identifier is the only
   mandatory part of the grammar. Without that sentence someone will "fix" it.

3. Add `ExtRefDict` (a `TypedDict` with `ext: str`) and the aliases:

   ```python
   type SymbolRef = VariableRef | ExternalRef
   type SymbolRefLike = VariableRefLike | ExternalRef | ExtRefDict
   ```

   `VariableRef` is listed **first** so pydantic smart mode resolves a bare string to it.

4. Add `ExternalRef`, `SymbolRef`, `SymbolRefLike`, `ExtRefDict` to `reference_types.__all__`
   (kept sorted).

5. Tests in `tests/eq1lab_pulse/models/test_reference_types.py`:
   - the grammar accept/reject table from step 1, parametrized;
   - `ExternalRef("q0[1].amp").model_dump() == {"ext": "q0[1].amp"}`;
   - JSON round trip through `model_validate`;
   - `TypeAdapter(SymbolRef).validate_python("amp")` is a `VariableRef`, and
     `...validate_python({"ext": "q0.f01"})` is an `ExternalRef`;
   - `ExternalRef.model_json_schema()` has `"properties"`, i.e. it is not a bare string schema.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- No existing test changed.
- `VariableRef` serialization is untouched — assert it explicitly in the new tests.

### Out of scope

Any use of `ExternalRef` in an operation model. Declarations. Any builder change.

---

## Task 2 — Declarations: limits, parameters, external symbols

**Read:** plan §3.3, §3.4, and the §9 Q3/Q4/Q6/Q7 rows.
**Goal:** the three declaration kinds exist and carry unit, default and limits.

### Steps

1. In `models/data_ops.py`, add

   ```python
   type SymbolValue = Amplitude | Duration | Frequency | Phase | Magnitude | Voltage | Threshold | bool | int | float | complex
   ```

   plus a `SymbolValueLike`, following the pattern `ExternalParamValue` / `ExternalParamValueLike`
   already sets in `pulse_types.py` — including its smart-union note about bare strings, which
   applies here for the same reason.

2. Add `ValueLimits(LeanModel)` with `minimum`, `maximum`, `allowed`, all optional, all
   `SymbolValue`-typed (`allowed` is `list[SymbolValue] | None`). Docstring: these are **declared
   and never enforced** by eq1_pulse; plan §1 says why.

3. Refactor `VariableDecl` into `SymbolDeclBase(DataOpBase)` carrying `dtype`, `shape`, `unit`, with
   `VariableDecl(SymbolDeclBase)` keeping `op_type="var_decl"` and its `name: IdentifierStr`.
   **`VariableDecl` gains nothing and its serialization must be byte-identical.**

4. Add `ParameterDecl(SymbolDeclBase)` — `op_type="param_decl"`, `name: IdentifierStr`,
   `default: SymbolValue | None = None`, `limits: ValueLimits | None = None`.

5. Add `ExternalDecl(SymbolDeclBase)` — `op_type="extern_decl"`, `name: ExternalSymbolStr`, same
   `default` and `limits`.

6. Extend the `DataOp` union to
   `VariableDecl | ParameterDecl | ExternalDecl | PulseDecl | Discriminate | Store`, and
   `data_ops.__all__` with the four new names.

7. Add `"SymbolDeclBase"` to `excluded_base_classes` in `utilities/openapi_generator.py`.

8. Tests in `tests/eq1lab_pulse/models/test_data_ops.py`:
   - each declaration constructs with and without the optional fields;
   - `ValueLimits` accepts dimensional and scalar bounds;
   - a `ParameterDecl` with `default` and `limits` round-trips;
   - **`VariableDecl(name="x", dtype="float", unit="mV").model_dump()` is unchanged** — write this
     as an explicit literal comparison, not a round trip;
   - `LeanModel` default elision still drops `shape=None` / `unit=None` / `limits=None`;
   - each new `op_type` discriminates correctly inside the `DataOp` union.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- The `VariableDecl` serialization test is present and passing.

### Out of scope

Builder functions. Widening any operation field. `ExternalRef` use anywhere.

---

## Task 3 — Widen the existing `VariableRef` read sites

**Read:** plan §2 (the first table and the write-site table).
**Goal:** every field that accepts a `VariableRef` today also accepts an `ExternalRef`.

### Steps

1. Replace `VariableRef` with `SymbolRef` (and `VariableRefLike` with `SymbolRefLike` in the
   `TYPE_CHECKING` `__init__` overloads) at **exactly** the fields in the plan's §2 first table:
   `pulse_types.py`, `channel_ops.py`, `control_flow.py` (`ConditionalBase.var` only),
   `external_block.py`.

2. Add `ExternalRef` to the `ExternalParamValue` union and `ExtRefDict` to `ExternalParamValueLike`,
   in `pulse_types.py`.

3. **Do not touch the write sites.** `IterationBase.var`, `Record.var`, `Trace.var`,
   `Discriminate.target`, `Discriminate.source`, `Store.source`, `ExternalBlock.results` keep
   `VariableRef`. The plan's second §2 table is the authority; work from it rather than from grep.

4. Tests: one widened field per operation family accepts an `ExternalRef`, in
   `tests/eq1lab_pulse/models/test_channel_ops.py` and `test_pulse_types.py`. Plus **negative**
   tests — `Iteration(var=ExternalRef("q0"), ...)`, `Record(..., var=ExternalRef("q0"))` and
   `Discriminate(target=ExternalRef("q0"), ...)` must each raise `ValidationError`.

5. A sequence containing an `ExternalRef` in a pulse parameter round-trips through JSON —
   `tests/eq1lab_pulse/models/test_sequence.py`.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- The existing coercion tests in `test_pulse_types.py` pass **unchanged**: `"10us"` is still a
  `Duration`, `{"ns": 100}` is still a `Duration`, a bare identifier string is still a
  `VariableRef`. Widening a smart union is exactly the change that breaks these.

### Out of scope

The concrete-only fields (task 4). Any builder change.

---

## Task 4 — Widen the concrete-only read sites

**Read:** plan §2 ("Also widened — concrete-only today") and §9 Q5.
**Goal:** the nine fields that accept only a literal today also accept a `SymbolRef`.

### Steps

1. Widen exactly the seven rows of the plan's "Also widened" table:
   `RepetitionBase.count`, `Discriminate.threshold`, `Discriminate.rotation`,
   `Record.time_of_flight`, `Trace.time_of_flight`, `CompensateDC.max_amp`,
   `DemodIntegration.phase`, `DemodIntegration.scale_cos`, `DemodIntegration.scale_sin`.

2. `RepetitionBase.count` keeps `Field(ge=0)` on its literal branch. There is nothing to constrain
   on the symbol branch — that is the "declare, never enforce" split, not an oversight. Express it
   so pyright and mypy both accept it, and say so in the field docstring.

3. `builder.core.repeat()` widens its `count: int` parameter to `int | SymbolRefLike` and routes it
   through `_validate_or_pass_through`. Update its docstring and add an example with a parameter.

4. `DemodIntegration.scale_cos` / `scale_sin` default to `1`, not `None`. Confirm `LeanModel`'s
   default-elision serializer still drops them when they equal `1` after the widening — add an
   explicit test, because a widened annotation is exactly what perturbs `_default_value_of`.

5. Tests: each widened field accepts a `VariableRef` and an `ExternalRef` and still accepts its
   literal form. `repeat(var("n"))` inside a sequence produces `Repetition(count=VariableRef("n"))`.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- The `scale_cos`/`scale_sin` elision test is present.
- `repeat(10)` still works everywhere it is used in `examples/` and `tests/`.

### Out of scope

`ext()` and the declaration builders (tasks 5 and 6). The write sites, still.

---

## Task 5 — Builder: `ext()`, the external namespace, validation plumbing

**Read:** plan §5.2, §5.3, §5.4.
**Goal:** external references can be built and are checked for declaration.

### Steps

1. `builder/_state.py`: add `declared_externals: list[set[str]]` to `BuilderState`, pushed and
   popped in `_push_context` / `_pop_context` alongside `declared_variables` and
   `unconsumed_blocks`. Add `_register_external`, `_is_external_declared`,
   `_check_external_declared`, mirroring the variable trio including their error messages.

2. `builder/_factories.py`: add `ext(name: str) -> ExternalRef`, the sibling of `var()`. It calls
   `_check_external_declared` and returns `ExternalRef(ext=name)`. Docstring in the same shape as
   `var()`'s, including an `Examples` block.

3. Extend `_validate_or_pass_through` and `_validate_explicit_variable_ref` with two branches each:
   an `ExternalRef` instance (check declared, pass through) and a dict with an `"ext"` key (build,
   check, pass through).

   **An identifier-like string is still a variable, never an external symbol.** There is no path
   from a bare `str` to an `ExternalRef`. Add this to both functions' docstrings — they already
   document their string handling in detail and the new rule belongs next to it.

4. Export `ext` from `builder/core.py` (it re-exports the `_factories` names) and from
   `builder/__init__.py`'s import list and `__all__`, both kept sorted.

5. Tests:
   - `tests/eq1lab_pulse/test_validate_or_pass_through.py` — the two new branches on both
     functions, plus a case asserting `"q0_f01"` stays a variable lookup;
   - `tests/eq1lab_pulse/test_builder_variable_verification.py` — `ext()` on an undeclared symbol
     raises `RuntimeError` with a message naming the symbol;
   - `tests/eq1lab_pulse/test_builder_state_isolation.py` — `declared_externals` is pushed and
     popped in step with the context stack, and does not leak between builds.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- The experimental schedule builder still imports and its tests pass — it shares `_factories` and
  `_state` and must not have been broken by either change.

### Out of scope

`param_decl` / `extern_decl` (task 6). Adding anything to `builder/experimental/`.

---

## Task 6 — Builder: `param_decl()`, `extern_decl()`, exports

**Read:** plan §5.1, §5.2, §5.4.
**Goal:** the two declaration builders exist, in `core.py`, next to `var_decl`.

### Steps

1. Add to `builder/core.py`, modelled closely on `var_decl`:

   ```python
   def param_decl(name, dtype, *, shape=None, unit=None, default=None, min=None, max=None, allowed=None) -> None
   def extern_decl(name, dtype, *, shape=None, unit=None, default=None, min=None, max=None, allowed=None) -> None
   ```

   Each assembles a `ValueLimits` from `min`/`max`/`allowed` and passes `limits=None` when all three
   are `None`. Each does the `_current_context` / `_in_sequence` / `_add_to_sequence` dance
   `var_decl` does.

2. `param_decl` registers into the **variable** namespace via the existing `_register_variable`, so
   a `var_decl` of the same name afterwards is a redeclaration error. `extern_decl` registers via
   `_register_external`.

3. `min` and `max` shadow builtins. That is the right name here — it reads as the domain concept and
   neither builtin is used in the function body. Add the `# noqa: A002` the linter will want, or
   whatever `ruff` is configured to raise; do not rename the parameters to work around it without
   saying so.

4. Export both from `builder/__init__.py` (import list and `__all__`, sorted). Do **not** add them
   to `builder/experimental/`.

5. Tests in `tests/eq1lab_pulse/test_builder.py`: both happy paths; limits assembled correctly from
   the flat keywords; `limits` is `None` when no bound is given; `param_decl("x")` then
   `var_decl("x")` raises; declarations outside a sequence context raise.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `builder.__all__` is sorted and contains `ext`, `extern_decl`, `param_decl`.
- The plan's §6 example runs end to end.

### Out of scope

Docs and the example file (task 7).

---

## Task 7 — Schema checks, docs, example

**Read:** plan §4, §6, §8.
**Goal:** the feature is visible in the generated schema and documented.

### Steps

1. `tests/test_openapi_generator.py` — add the four §4 checks:
   - `ExternalRef` is an object schema with an `ext` property, **not** a bare string;
   - `ValueLimits`, `ParameterDecl`, `ExternalDecl` are in `components.schemas`;
   - `SymbolDeclBase` is **not**;
   - the `VariableDecl` schema entry is unchanged.

2. `examples/calibrated_rabi.py` — the plan's §6 example, made runnable. Check how
   `tests/test_examples.py` discovers examples before assuming it picks the file up automatically;
   if it uses an explicit list, add it there.

3. `docs/source/user_guide/builder_guide.rst` — a "Late-bound values" section covering both
   declaration kinds, when to reach for which (a parameter is supplied per submission by the caller;
   an external constant is looked up per submission by name), and that units and limits are declared
   but never enforced by eq1_pulse.

4. Build the docs (`cd docs && ./generate_html.sh`) and confirm no new Sphinx warnings.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `python -m eq1_pulse.utilities.openapi_generator` runs and the new models appear.
- Docs build clean.

### Out of scope

Any model or builder change. If something is missing, report it rather than adding it here.
