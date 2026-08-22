# Execution breakdown: expression support

Companion to [expressions-plan.md](expressions-plan.md) (issue #3). Five independently executable
tasks, each sized for a single clean session.

**Requires #6 to have landed** — it has. Its plan is not in the tree; the decisions behind the
`SymbolRef` alias and the notes on what the implementation added to the design are on the issue:
[design record](https://github.com/equal1/eq1_pulse/issues/6#issuecomment-5371855226). Task 2's sweep is a one-line alias change at the aliased read sites
*because* #6 already routed them through `SymbolRef`. Run before that and every widening has to be
done twice.

**[#10 — one wire form per type](https://github.com/equal1/eq1_pulse/issues/10) has also landed,
after this breakdown was first written**, and it moved ground several tasks stand on. The plan's
"Revision" section at the top lists what changed and where; the table below the preamble carries the
same material as traps. The short version: `"10us"` and bare identifiers are no longer wire forms,
`SymbolValue` was rewritten and lost the complex-voltage dimension, `builder/_coerce.py` is now the
only place authoring grammars are read, and `test_schema_symmetry.py` holds a tree-wide invariant the
new models must satisfy. Task 1 grew as a result; task 5 shrank.

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
> Discriminated unions via `Annotated[..., Discriminator("field")]`.
>
> **Verify.** `./qa/run_all_qa.sh` (pyright + mypy + pytest with coverage). It must pass before you
> report done. If it passed before your change and fails after, you are not done.
>
> **Context.** Read `docs/plans/expressions-plan.md` — its "Revision — what #10 changed here"
> section in every case, and the sections named in your task — before
> starting. For what #6 left you, read the code rather than a plan: `SymbolRef` and `ExternalRef` in
> `models/reference_types.py` (whose docstrings carry the wire-format rule and why it is the one
> asymmetry in the hierarchy), and `git grep -l SymbolRef src/` for the fields already widened. The
> decisions behind them are on [issue #6](https://github.com/equal1/eq1_pulse/issues/6#issuecomment-5371855226). Do not re-litigate them; §1 and §8 of the
> expressions plan list this plan's own closed ones.
>
> **Scope.** Do only what your task says. Each task lists an explicit *out of scope* set. If you
> believe a listed exclusion is wrong, say so in your final message rather than acting on it.

---

## What #6 learned that this plan will hit again

Carried over from the #6 execution, because tasks 2 and 4 repeat the same shapes one alias wider.
None of these are decisions to re-open; they are traps with known locations.

| Trap                                                                                                              | Where it bites                                    |
| ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| **A widened field is only half the edit.** The builder function exposing it needs the same widening, or the field is unreachable through the public API. #6 shipped four such gaps (`if_`, `play`, `record`, `demod_integration`) and caught them in review, not in QA — a narrow parameter hint is not a type error. Check "does every widened field's builder parameter share the field's type?", do not grep for the old alias. | Task 2 → task 4                                  |
| **The `TYPE_CHECKING`-only `__init__` overrides do not live with their fields.** `ConditionalBase.var` and `RepetitionBase.count` are declared in `control_flow.py`, but `Conditional`'s and `Repetition`'s constructor overrides are in `sequence.py`. Widen both or pyright reports the constructor, not the field. | Task 2                                            |
| **Widening a shared helper's return type ripples into every call site's parameter hint.** #6 widened `_validate_or_pass_through` / `_validate_explicit_variable_ref` to return `T \| SymbolRef` and had to widen eleven call-site signatures in `_factories.py` and `core.py` before pyright accepted the value being assigned back. Budget for it. | Task 4                                            |
| **`builder/experimental/schedule.py` mirrors the same functions over shared `_factories.py`.** It needs the identical type-hint widening to stay green even when a task otherwise leaves it alone. That is a type-hint fix, not a functional addition to a module scheduled for removal ([#8](https://github.com/equal1/eq1_pulse/issues/8)). | Task 4                                            |
| **Re-exporting through `core.py` needs the `from ._factories import X as X` idiom**, or an importer of `builder.core` gets a pyright error on the implicit re-export. | Task 4                                            |
| **`LeanModel` default elision is perturbed by a widened annotation.** Any field with a non-`None` default that gains a union member needs an explicit "still elided" test; `_default_value_of` is where it goes wrong. | Task 2                                            |
| **`tests/test_examples.py` discovers `examples/**/*.py` by `rglob`.** A new example file is picked up with no list to update. | Task 5                                            |
| **`ruff`'s configured rule set does not select `A` (flake8-builtins).** A parameter named `min`/`max` needs no `noqa`; adding one is removed again by the pre-commit hook as unused (`RUF100`). | Task 3, task 4                                    |
| **The docs build emits pre-existing autoapi "more than one target found for cross-reference" warnings** for names re-exported from `models/` (`Amplitude`, `DataOp`, …). They are on `main` too. Compare against a baseline build rather than treating any warning as new. | Task 5                                            |

---

## What #10 changed under this plan

Same purpose as the table above, one predecessor newer. These are measured against the landed tree,
not inferred; each has a plan section that argues it.

| Trap                                                                                                              | Where it bites                                    | Plan |
| ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- | ------ |
| **`SymbolValue` cannot hold an `Amplitude`.** `Amplitude` derives from `ComplexVoltage`, which is not a `Voltage` subclass and is in no dimension registry, so both `SymbolValue` and `ExternalParamValue` reject it *and* its own `model_dump` output `{"mV": (1.0, 2.0)}`. `LiteralExpr.value` inherits the hole. Fixing it has its own trap: `ComplexVoltage` must not go into `_DIMENSION_TAGS`, which also builds the unit-key map, where `V`/`mV` would then collide. | Task 1                                            | §2.4 |
| **`"10us"` and bare identifiers are rejected by the models.** They are builder authoring sugar now, read only through `builder/_coerce.py`. Any acceptance criterion or test that expects `SquarePulse.model_validate({"duration": "10us"})` to work is describing the pre-#10 tree. | Task 2 → task 3                                  | §3.3 |
| **`builder/_coerce.py` is the one place the string/dict/zero grammars are read.** `expr("10us")` works only if `expr()` routes strings through `as_symbol_value`. Re-reading the grammar inside `_expressions.py` puts a second copy of it in the tree. | Task 3                                            | §4.1 |
| **`test_schema_symmetry.py` asserts validation-schema == serialization-schema for every model `get_all_pydantic_models()` finds** — and that reads `openapi_generator.model_modules`. Listing `"expressions"` there is what turns the invariant on for the new nodes, so it belongs with the module, not with the schema task. | Task 1 (moved from task 5)                        | §3.4, §7 |
| **`UnaryExpr.op` is a single-valued `Literal`, so a default elides it from the wire.** Measured: `op: Literal["-"] = "-"` serializes without `op` at all. Not the discriminator rule — plain `LeanModel` default elision. No `op` or `function` field carries a default. | Task 1                                            | §2.1 |
| **`ExternalParamValue` is a hand-tagged union, not an alias.** Admitting `Expression` there is a `Tag` entry plus a branch in `_external_param_value_tag`, and it is deliberately *not* part of the mechanical sweep. | Task 2                                            | §3, §8 Q10 |

---

## Dependency graph

```text
1 ──> 2 ──┬──────────────> 5
     └──> 3 ──> 4 ────────┘
```

Safe merge: **3 + 4** (one builder feature split only by size). Do not merge 1 into anything — a
recursive discriminated union is the task most likely to need a second pass, and it is the one every
other task depends on.

| #  | Task                                                  | Size | Model     | Reasoning | Context     | Touches                                    |
| -- | ------------------------------------------------------- | ---- | --------- | --------- | ----------- | -------------------------------------------- |
| 1 ✅ | `models/expressions.py` — the node set, plus the `SymbolValue` fix | L    | Opus 5    | high      | 200k / ~75k | `models/expressions.py`, `models/basic_types.py`, `models/data_ops.py`, `models/pulse_types.py`, `utilities/openapi_generator.py`, `tests/` |
| 2 ✅ | Widen operations to `ValueRef`; rebuild sweep         | M    | Sonnet 5  | high      | 200k / ~60k | `models/`, `tests/`                          |
| 3 ✅ | Builder: `Expr` and its operators                     | M    | Sonnet 5  | high      | 200k / ~45k | `builder/_expressions.py`, `tests/`          |
| 4 ✅ | Builder: leaf checking, acceptance, exports           | M    | Sonnet 5  | medium    | 200k / ~50k | `builder/`, `tests/`                         |
| 5  | Schema tag, docs, example                             | S    | Haiku 4.5 | medium    | 200k / ~30k | `utilities/`, `docs/`, `examples/`, `tests/` |

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

**Why these assignments.** Task 1 is a mutually recursive discriminated union with forward references
and `model_rebuild()` ordering — the failure mode is a union silently degrading to `dict`, surfacing
far from its cause, and nothing in the tree does this yet. That is the Opus case exactly, and #10
added a second Opus-shaped piece to it: the `SymbolValue` fix edits a union that seventeen fields
resolve through, where the wrong tag rule silently reclassifies existing data rather than failing.
Task 2 is `high` for the same reason one level down: it adds a third branch at every pulse parameter
and a tag to a hand-written discriminator, and the regression is a value that quietly picks the wrong
member. Task 5 is checklist work — more so now that the `model_modules` entry moved to task 1. Task
2's working set is large because it spans six model modules at once, not because any one file is
big.

---

## Task 1 — `models/expressions.py`, and the value union it needs — **done**

**Status:** done, 2026-08-22. QA green (pyright 0, mypy clean, 933 tests). As built, with one
deviation from the acceptance criteria, noted below.

**Read:** plan §2 in full (including §2.4), §3.4, §7, and §8 Q3/Q4/Q7/Q8.
**Goal:** the expression tree exists, validates, round-trips, and is covered by the tree-wide schema
invariant. Nothing uses it yet.

> **As built.** The shape test is `is_complex_voltage_spelling` plus `dimension_tag_of_unit_mapping`
> in `basic_types.py`, which both tag functions now call for the mapping branch; the instance branch
> is a `ComplexVoltage` carve-out at the top of `dimension_tag_of`. `_DIMENSION_TAGS` is untouched,
> as the trap requires.
>
> **One existing test had to change rather than gain a case**, which the acceptance criteria asks be
> reported: `test_pulse_types.py::test_external_param_value_amplitude_is_rejected` asserted the
> exact gap §2.4 closes ("an `Amplitude` instance is rejected by `ExternalParamValue`"), citing a
> since-superseded scope decision. It is replaced by
> `test_external_param_value_amplitude_instance_survives_as_amplitude`. Nothing else changed; the
> `SymbolValue` and `ExternalParamValue` tests only gained cases.
>
> Depth is enforced by a `model_validator(mode="after")` on `ExprBase` over an iterative
> breadth-first walk (`_expression_depth`), which reads operands off field values rather than a
> per-class list, so a node type added later is walked without registering it. Recursion is
> deliberately avoided there: the validator runs on trees that have not yet been depth-checked.
>
> `ExpressionFunction` (the closed `Literal` of function names) is a module-level alias rather than
> an inline literal, so `CallExpr.function` and the arity validator name the same thing. It is not
> in `__all__` — step 9's list is unchanged.
>
> **Left for task 2, flagged here:** `expressions.py` imports `SymbolValue` from `data_ops.py` at
> module level, as step 4 directs. Task 2 widens `data_ops`'s own fields to `ValueRef`, which lives
> here — so task 2 inherits a `data_ops` ↔ `expressions` import cycle to break (a bottom-of-module
> import plus `model_rebuild()` in `data_ops` is the obvious shape). It is not a defect in this
> task; it is the first thing task 2 will hit.

Two pieces, in this order. The second is the one the plan is about; the first is a defect in the
value union it builds on, and building on it first only means fixing it twice.

### Steps

1. **Make `SymbolValue` able to carry a complex voltage** (plan §2.4). As the tree stands,
   `SymbolValue` and `ExternalParamValue` both reject an `Amplitude` *and* its own `model_dump`
   output `{"mV": (1.0, 2.0)}`, because `Amplitude` derives from `ComplexVoltage`, which is not a
   `Voltage` subclass and appears in no dimension registry.

   - The rule: within a voltage unit key, a real number is a `Voltage` and a `(real, imag)` pair is a
     `ComplexVoltage`. Two distinct wire shapes, so #10's invariant holds.
   - The shape test goes in `basic_types.py`, beside `dimension_tag_of` and
     `dimension_unit_tag_map()` — the two helpers `_symbol_value_tag` (`data_ops.py`) and
     `_external_param_value_tag` (`pulse_types.py`) share. One edit, both unions.
   - Add a `complex_voltage`-tagged `ComplexVoltage` member to each union, and widen
     `SymbolValueLike` / `ExternalParamValueLike` to match.
   - **Do not add `ComplexVoltage` to `_DIMENSION_TAGS`.** That dict also builds the unit-key →
     dimension map, and `ComplexVolts`/`ComplexMillivolts` carry the same `V`/`mV` keys as
     `Volts`/`Millivolts`; adding it there makes every voltage key resolve to whichever was iterated
     last. The unit-key map stays keyed on the real dimensions.
   - Correct the docstrings on both unions, which currently name `Amplitude` among the refinements
     said to be covered by their base dimension.

   Tests, in `tests/eq1lab_pulse/models/test_data_ops.py` and `test_pulse_types.py`: an `Amplitude`
   instance survives as an `Amplitude`; `{"mV": [1, 2]}` validates to a `ComplexVoltage` and dumps
   back to the same document; a real `{"mV": 100}` is still a `Voltage`; `{"usec": 3}` still produces
   exactly one `union_tag_invalid`. The accepted consequence — a real-valued `Amplitude(mV=100)`
   dumps `{"mV": 100}` and revalidates as `Voltage`, the same narrowing `Duration` → `Time` already
   gets — is worth its own test so it reads as intended rather than as a bug.

2. Create `src/eq1_pulse/models/expressions.py` with the seven node types from plan §2.1:
   `ExprBase(LeanModel)`, `LiteralExpr`, `SymbolExpr`, `UnaryExpr`, `BinaryExpr`, `CompareExpr`,
   `LogicalExpr`, `CallExpr`, and the `Expression` discriminated union on `expr_type`. (`ExprBase` is
   the base, not one of the seven.)

   `expr_type` is declared **first** in every class — `LeanModel` treats the first single-valued
   `Literal` field as the discriminator and always serializes it.

3. **No `op` or `function` field carries a default.** `op` is multi-valued on four of the five nodes
   and so is an ordinary field, which is what is wanted — but `UnaryExpr.op` is `Literal["-"]`,
   single-valued, and `LeanModel`'s ordinary default elision then drops it from the wire entirely:
   measured, `op: Literal["-"] = "-"` serializes as `{"expr_type": "unary", "operand": …}`. Declare
   it without a default and test that `model_dump()` contains `op`.

4. `LiteralExpr.value` is `SymbolValue`, imported from `data_ops.py` where #6 put it and step 1 fixed
   it. `SymbolExpr.symbol` is `SymbolRef` from `reference_types.py`. Do not redefine either.

5. `UnaryExpr.op` is `Literal["-"]` **only**. `abs` is a `CallExpr` function, not a unary op
   (plan §8 Q3). `LogicalExpr` carries `operands: list[Expression]` and `op: Literal["and", "or", "not"]`.

6. Validators — these three and no others:
   - `CallExpr`: `min`/`max` take ≥ 2 args, every other function takes exactly 1.
   - `LogicalExpr`: `not` takes exactly 1 operand, `and`/`or` take ≥ 2.
   - depth: a module constant `MAX_EXPRESSION_DEPTH = 32` and a validator that raises a
     `ValueError` naming the limit. Note what the cap is *for* (plan §2.3): pydantic-core already
     turns a deep validation into a `ValidationError`, so do not write the test as "a
     `RecursionError` became a `ValidationError`" — it was already one. The cap exists because the
     serializer has no such guard. Test that depth 33 raises `ValidationError`, and that no tree
     which serializes can exceed the cap.

   **No type inference, no unit checking, no simplification.** Plan §0 and §1 say why; a reviewer
   will look for these having crept in.

7. Add `type ValueRef = SymbolRef | Expression` **in this module** (plan §8 Q5 — putting it in
   `reference_types.py` creates an import cycle) and a `ValueRefLike` beside it. A plain `|` union,
   not a callable-discriminator one; §8 Q9 closed that.

8. Handle the recursion: `from __future__ import annotations`, forward references, and an explicit
   `model_rebuild()` per node class at the bottom of the module. Verify by validating a
   depth-3 tree from a plain dict — if a rebuild is missing, that is where it shows.

9. `__all__`, sorted, exporting the seven node types, `ExprBase`, `Expression`, `ValueRef`,
   `ValueRefLike` and `MAX_EXPRESSION_DEPTH`.

10. **Wire the module into model discovery** (plan §3.4, §7): `"expressions"` into
    `openapi_generator.model_modules` and `"ExprBase"` into `excluded_base_classes`, in this task
    rather than task 5. `model_modules` is what `get_all_pydantic_models()` reads, so it is what
    decides whether `test_schema_symmetry.py` sees these models at all; and without the exclusion a
    field-less base class appears in the schema the moment the module is listed. The tag-list entry
    and the generator's own test stay in task 5.

11. Tests in `tests/eq1lab_pulse/models/test_expressions.py` (new):
    - each node type constructs and round-trips through `model_dump` → `model_validate`;
    - the `Expression` union discriminates each `expr_type` correctly;
    - a depth-3 nested tree round-trips from a plain dict;
    - `CallExpr` and `LogicalExpr` arity validators accept and reject;
    - `UnaryExpr.model_dump()` contains `op` (step 3);
    - depth 33 raises `ValidationError`;
    - a `SymbolExpr` wrapping an `ExternalRef` round-trips with the `{"ext": ...}` form intact;
    - a `LiteralExpr` holding an `Amplitude` round-trips (step 1's consumer).

    And in `tests/eq1lab_pulse/models/test_schema_symmetry.py`: add one expression node to
    `_canonical_round_trip_instances()`. The two module-wide tests there pick the rest up on their
    own once step 10 lands.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `test_schema_symmetry.py` passes **with the new models in scope** — confirm they are, by checking
  they appear in `get_all_pydantic_models()`, not by trusting the test to be covering them.
- No existing test changed, **except** the `SymbolValue` / `ExternalParamValue` tests step 1 extends.
  If an existing one has to change rather than gain a case, say so in your final message: it means
  the fix altered a resolution that was previously relied on.
- `models/expressions.py` imports nothing from `channel_ops`, `pulse_types`, `sequence` or
  `control_flow` — dependencies point one way.

### Out of scope

Using `Expression` in any operation model, including `ExternalParamValue` — step 1 fixes that union's
*value* members only; task 2 adds its expression member. Any builder change. The `openapi_generator`
tag-list entry and its test (task 5).

---

## Task 2 — Widen operations to `ValueRef`; the rebuild sweep — **done**

**Status:** done, 2026-08-22. QA green (pyright 0, mypy clean, 950 tests). As built, matching the
acceptance criteria, with one addition noted below.

> **As built.** `expressions.py`'s own `from .data_ops import SymbolValue` moved to the bottom of
> that module (after `Expression`/`ValueRef` are defined) to break the cycle task 1 flagged; every
> other widened module (`data_ops`, `pulse_types`, `channel_ops`, `control_flow`, `external_block`)
> keeps the `*Like` alias under `TYPE_CHECKING` only and adds a deferred
> `from .expressions import ValueRef` plus a `model_rebuild()` sweep at its own bottom.
> `control_flow.py` was missing `from __future__ import annotations`, required by the pattern; added
> it. `models/experimental/schedule.py`'s `SchedRepetition`/`SchedConditional` needed their
> `TYPE_CHECKING`-only `__init__` overrides widened too (not called out by name in the steps, but the
> same trap the table above already names for `sequence.py`) — no separate `model_rebuild()` for
> them, since they inherit the already-rebuilt fields from their generic base.

**Read:** plan §3 in full, and §2 of the #6 plan for the read-site inventory.
**Goal:** an `Expression` is accepted wherever a `SymbolRef` is.

### Steps

1. Replace `SymbolRef` with `ValueRef` (and `SymbolRefLike` with `ValueRefLike`) at every site
   listed in the #6 plan's §2 tables — **both** tables, including the concrete-only fields task 4
   of #6 widened. Same list, same files, no new judgement about what counts as a read site.

2. **`ExternalParamValue` is not one of those sites and needs its own edit** (plan §3, §8 Q10). #10
   spelled its members out with explicit `Tag`s over a hand-written `_external_param_value_tag`, so
   admitting an `Expression` is a `Tag` entry plus a branch in the tag function — routing a mapping
   that carries `expr_type`. Test that an expression survives there and that every existing member
   still resolves as it did.

3. `ConditionalBase.var` is typed `ValueRef` like the rest, plus a model validator restricting it to
   a predicate: a `SymbolRef`, a `CompareExpr`, or a `LogicalExpr`. Arithmetic nodes are rejected
   with a message naming what was passed. Plan §3 consequence 1 and §8 Q2.

4. Run the `model_rebuild()` sweep: every model whose fields now transitively mention `Expression`
   needs rebuilding. That is `pulse_types`, `channel_ops`, `data_ops`, `external_block`,
   `control_flow`, `sequence`, and `experimental/schedule`. Add a test that imports the package
   fresh and validates one model of each family from a plain dict containing an expression — a
   missed rebuild degrades the union to `dict` silently and this is what catches it.

5. Tests:
   - `test_channel_ops.py` / `test_pulse_types.py` — one widened field per family accepts an
     `Expression`;
   - `test_control_flow.py` — `Conditional` accepts `CompareExpr`, `LogicalExpr` and a bare
     `SymbolRef`; rejects `BinaryExpr` and `LiteralExpr`;
   - `test_sequence.py` — a sequence containing expressions round-trips through **JSON** (not just
     `model_dump`).

### Acceptance

- `./qa/run_all_qa.sh` passes.
- **The existing coercion tests in `test_pulse_types.py` and `test_authoring_forms.py` pass
  unchanged.** Adding a third branch at every typed read site is the highest regression risk in this
  plan, and those files are the guard. What they assert, on the landed tree — do not "fix" any of it:

  | input at a typed read site | resolves to                                                        |
  | ---------------------------- | -------------------------------------------------------------------- |
  | `{"ns": 100}`              | `Duration`                                                         |
  | `{"var": "d"}`             | `VariableRef`                                                      |
  | `{"ext": "q0.t"}`          | `ExternalRef`                                                      |
  | `"10us"`                   | **rejected** — a unit-suffixed string left the wire in #10          |
  | `"my_dur"`                 | **rejected** — a bare identifier is a string, never a reference     |

  In `ExternalParamValue`, arbitrary strings still stay `str`, and every reference retains its
  tagged JSON form.
- `test_schema_symmetry.py` still passes: the widened fields must not give any model an input-only
  wire form.

### Out of scope

Any builder change. Simplification, evaluation, or type checking of expressions.

---

## Task 3 — Builder: `Expr` and its operators — **done**

**Status:** done, 2026-08-22. QA green (pyright 0, mypy clean, 987 tests). As built, matching the
acceptance criteria.

**Read:** plan §4.1 (including the `_coerce` paragraph), §4.2, and §8 Q1/Q6.
**Goal:** Python operators build an `Expression` tree. Nothing consumes it yet.

### Steps

1. Create `src/eq1_pulse/builder/_expressions.py` with the `Expr` wrapper class and the `expr()`
   entry point. `expr(x)` accepts an `Expr` (identity), a `SymbolRef`, a raw `SymbolValue`, or a
   bare `Expression`, normalizing to `SymbolExpr` / `LiteralExpr` as appropriate.

   **The raw-value branch calls `as_symbol_value` from `builder/_coerce.py`** — a module added by
   #10, after this breakdown was written, and now the single place the string / dict / zero
   authoring grammars are read. `"10us"` and `"80mV"` are not wire forms any more; they reach a
   model only through a constructor or through `_coerce`. So `expr("10us")` works if and only if
   `expr()` delegates there, and reading the grammar again inside `_expressions.py` puts a second
   copy of it in the tree.

2. Operators per plan §4.2: `+ - * / %` with their reflected `r`-variants, unary `-`, `abs()`,
   `< <= > >=`, and the methods `.eq()`, `.ne()`, `.and_()`, `.or_()`, `.not_()`, plus `.unwrap()`.

3. **Do not overload `__eq__` or `__ne__`.** `Reference.__eq__` already means value comparison and
   is tested; pydantic relies on it. `and`/`or`/`not` cannot be overloaded in Python at all — they
   coerce to `bool`. Set `__hash__ = None` explicitly.

   The class docstring must state the asymmetry — `<` works, `==` does not — and why, so a user
   hitting it finds the answer where they are already looking.

4. `Expr` is **not** a pydantic model. It is a plain class that holds an `Expression` and returns
   new `Expr` instances from its operators.

5. `abs()` maps to `CallExpr(function="abs")`, matching the model.

6. Tests in `tests/eq1lab_pulse/test_builder_expressions.py` (new):
   - each operator produces the right node with the right `op`;
   - `expr("10us")` and `expr("80mV")` produce the `LiteralExpr` the same string produces through
     `as_symbol_value` — and the authoring-form case goes in
     `tests/eq1lab_pulse/models/test_authoring_forms.py`, the ledger #10 added for exactly this;
   - `expr(Amplitude("80mV"))` produces a `LiteralExpr`, which task 1's `SymbolValue` fix is what
     makes possible;
   - reflected forms: `2 * expr(var("a"))` and `expr(var("a")) * 2` differ only in operand order;
   - `.eq()` / `.ne()` / `.and_()` / `.or_()` / `.not_()`;
   - `expr(expr(x))` is `expr(x)`;
   - `Expr` is unhashable;
   - `expr(var("a")) == expr(var("a"))` does **not** return a `CompareExpr` — assert the actual
     behaviour so a future change to `__eq__` is caught.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `_expressions.py` does not import from `core.py` — dependencies among builder modules point one
  way, as `_state.py` and `_factories.py` already establish.

### Out of scope

Wiring `Expr` into the operation builders (task 4). Exporting `expr` (task 4).

---

## Task 4 — Builder: leaf checking, acceptance, exports — **done**

**Status:** done, 2026-08-22. QA green (pyright 0, mypy clean, 1003 tests). As built, with a few
additions beyond the letter of the plan, noted below.

> **As built.** `_check_expression_leaves` and the `Expr`/bare-`Expression` branches on
> `_validate_or_pass_through` / `_coerce_or_ref` / `_validate_explicit_variable_ref` landed exactly
> as specced. Beyond that:
>
> - **Every `SymbolRefLike`-typed parameter in `builder/core.py` was widened to
>   `SymbolRefLike | ExprLike`**, not only the ones pyright flagged (`repeat`, `if_`, `play`,
>   `wait`, `set_frequency`/`shift_frequency`, `set_phase`/`shift_phase`, `record`, `discriminate`,
>   `external_block`). The unflagged ones type-checked silently only because their model-construction
>   call already carried a stale `# type: ignore[assignment]`/`[arg-type]` from before this task —
>   the parameter's *declared* type, not the narrower inferred one, is what a caller sees. Widening
>   only the flagged sites would have left `set_frequency(ch, expr(...))` accepted at runtime but
>   rejected by a caller's own type checker. `ExprLike = Expr | Expression`, added to
>   `builder/_expressions.py` and exported from it (plan didn't name where this alias should live).
> - Four model-construction call sites (`SetFrequency`, `ShiftFrequency`, `SetPhase`, `ShiftPhase`)
>   needed their own new `# type: ignore[arg-type]`, matching the pattern `_factories.py`'s pulse
>   constructors already used — `Expr` itself (the builder wrapper, not `Expression`) is never a
>   valid model field value, so the widened parameter type doesn't match the model's `ValueRefLike`.
> - `builder/experimental/schedule.py` needed the type-hint-only widening the trap table predicts,
>   on `play()`'s `scale_amp` — no functional `expr` support, per the out-of-scope note.
> - The plan's own §5 snippet does not run as printed: `measure(..., amplitude="50mV")` omits the
>   required `integration=` keyword, and `result_var="iq"` is never `var_decl`-ed. Both are
>   independent of this task's changes (verified against `main` before this branch). Confirmed the
>   snippet runs end to end with `integration=full_integration()` and a preceding
>   `var_decl("iq", "complex")` added; task 5 owns making `examples/expression_ramsey.py` itself
>   runnable and should carry this fix forward.

**Read:** plan §4.3.
**Goal:** builder functions accept an `Expr` and check its leaves.

### Steps

1. In `builder/_factories.py`, add a tree walker that visits every `SymbolExpr` in an `Expression`
   and calls `_check_variable_declared` or `_check_external_declared` per leaf. It belongs next to
   the existing validation helpers, and it is the only new traversal in this plan.

2. Extend `_validate_or_pass_through` and `_validate_explicit_variable_ref` with two branches: an
   `Expr` (unwrap, walk the leaves, return the `Expression`) and a bare `Expression` model (walk,
   return unchanged). A user deserializing a fragment should not have to re-wrap it.

   Both return `T | SymbolRef` today; they now return `T | ValueRef`. That is the ripple the trap
   table warns about — #6 had to widen eleven call-site signatures in `_factories.py` and `core.py`
   before pyright accepted the value being assigned back, and this is the same edit one alias
   wider.

   **`_coerce_or_ref` is a third function in that chain and the easy one to miss.** Every pulse
   factory reaches `_validate_or_pass_through` through it, and it decides what to do with the result
   by `isinstance(resolved, VariableRef | ExternalRef)` — anything else is handed to an `as_*`
   coercion. An `Expression` falling through there reaches `as_amplitude()`, which is not a type
   error and not a test failure until someone writes the call. Add `Expression` to that check and
   widen its return to `T | ValueRef | None`. `square_pulse(amplitude=expr(var("s")) * Amplitude("80mV"))`
   — the plan's §5 example — is the case that exercises it, so make sure a test covers a pulse
   factory and not only the operation builders.

3. Export `expr` from `builder/core.py` and from `builder/__init__.py`'s import list and `__all__`,
   both kept sorted.

4. `if_()` accepts an `Expr` whose unwrapped node is a predicate, delegating the predicate check to
   the model validator from task 2 rather than duplicating it. Update its docstring and add an
   expression example.

5. Tests, in `test_builder_expressions.py` and `test_validate_or_pass_through.py`:
   - an expression in a pulse parameter, a `wait` duration, a `set_frequency`;
   - an undeclared variable **or** external symbol anywhere in a tree raises, including nested three
     levels deep — that is what the walker is for;
   - `if_(expr(var("a")) > 5)` builds; `if_(expr(var("a")) + 1)` raises;
   - a bare `Expression` model passed directly is accepted.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `builder.__all__` is sorted and contains `expr`.
- The plan's §5 example runs end to end.
- The experimental schedule builder still imports and its tests pass — it shares `_factories`.

### Out of scope

Docs and the example file (task 5). Adding `expr` to `builder/experimental/`.

---

## Task 5 — Schema tag, docs, example

**Read:** plan §6, §7.
**Goal:** expressions are visible in the generated schema and documented.

**Two of this task's original three generator edits moved to task 1.** `"expressions"` in
`model_modules` and `"ExprBase"` in `excluded_base_classes` are what put the new models under
`test_schema_symmetry.py`, so they belong with the module rather than with its documentation
(plan §3.4, §7). Expect to find them already there; if they are not, task 1 is incomplete — say so
rather than adding them here.

### Steps

1. `utilities/openapi_generator.py` — one edit: an `{"name": "expressions", "description": ...}`
   entry in the tag list.

2. `tests/test_openapi_generator.py` — the seven expression models are present; `ExprBase` is
   absent.

3. `examples/expression_ramsey.py` — the plan's §5 example, made runnable. It imports `Amplitude`
   from `eq1_pulse.models` (the builder does not export it) and uses it in the `amplitude=`
   expression, which is the example's point: that literal is what task 1's `SymbolValue` fix
   unblocked. Check how `tests/test_examples.py` discovers examples before assuming it picks the
   file up.

4. `docs/source/user_guide/builder_guide.rst` — an "Expressions" section: `expr()` is required (bare
   `var("a") * 2` does not work, and why); `<`/`>` work but `==` does not, use `.eq()`; expressions
   are recorded, never evaluated or dimension-checked by eq1_pulse. Mention that `expr()` reads the
   same authoring forms the rest of the builder does — `expr("10us")` works, though `"10us"` is not
   a wire form — and keep that consistent with what #10 already wrote in this guide about strings
   and quantities.

5. Build the docs (`cd docs && ./generate_html.sh`) and confirm no new Sphinx warnings.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `python -m eq1_pulse.utilities.openapi_generator` runs and the seven models appear.
- Docs build clean.

### Out of scope

Any model or builder change. If something is missing, report it rather than adding it here.
