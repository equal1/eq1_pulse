# Execution breakdown: expression support

Companion to [expressions-plan.md](expressions-plan.md) (issue #3). Five independently executable
tasks, each sized for a single clean session.

**Requires #6 to have landed** — it has. Its plan is not in the tree; the decisions behind the
`SymbolRef` alias and the notes on what the implementation added to the design are on the issue:
[design record](https://github.com/equal1/eq1_pulse/issues/6#issuecomment-5371855226). Task 2 below is a one-line alias change *because* #6 already routed every
read site through `SymbolRef`. Run before that and every widening has to be done twice.

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
> **Context.** Read `docs/plans/expressions-plan.md` — the sections named in your task — before
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
| 1  | `models/expressions.py` — the node set                | L    | Opus 5    | high      | 200k / ~60k | `models/expressions.py`, `tests/`            |
| 2  | Widen operations to `ValueRef`; rebuild sweep         | M    | Sonnet 5  | high      | 200k / ~60k | `models/`, `tests/`                          |
| 3  | Builder: `Expr` and its operators                     | M    | Sonnet 5  | high      | 200k / ~45k | `builder/_expressions.py`, `tests/`          |
| 4  | Builder: leaf checking, acceptance, exports           | M    | Sonnet 5  | medium    | 200k / ~50k | `builder/`, `tests/`                         |
| 5  | Schema, docs, example                                 | S    | Haiku 4.5 | medium    | 200k / ~30k | `utilities/`, `docs/`, `examples/`, `tests/` |

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
far from its cause, and nothing in the tree does this yet. That is the Opus case exactly. Task 2 is
`high` for the same reason one level down: it turns a four-way smart union into a six-way one at
every pulse parameter, and the regression is a coercion that quietly picks the wrong member. Task 5
is checklist work. Task 2's working set is large because it spans six model modules at once, not
because any one file is big.

---

## Task 1 — `models/expressions.py`

**Read:** plan §2 in full, and §8 Q3/Q4/Q7.
**Goal:** the expression tree exists, validates, and round-trips. Nothing uses it yet.

### Steps

1. Create `src/eq1_pulse/models/expressions.py` with the seven node types from plan §2.1:
   `ExprBase(LeanModel)`, `LiteralExpr`, `SymbolExpr`, `UnaryExpr`, `BinaryExpr`, `CompareExpr`,
   `LogicalExpr`, `CallExpr`, and the `Expression` discriminated union on `expr_type`.

   `expr_type` is declared **first** in every class — `LeanModel` treats the first single-valued
   `Literal` field as the discriminator and always serializes it. `op` is multi-valued and is
   therefore an ordinary field, which is what is wanted.

2. `LiteralExpr.value` is `SymbolValue`, imported from `data_ops.py` where #6 put it.
   `SymbolExpr.symbol` is `SymbolRef` from `reference_types.py`. Do not redefine either.

3. `UnaryExpr.op` is `Literal["-"]` **only**. `abs` is a `CallExpr` function, not a unary op
   (plan §8 Q3). `LogicalExpr` carries `operands: list[Expression]` and `op: Literal["and", "or", "not"]`.

4. Validators — these three and no others:
   - `CallExpr`: `min`/`max` take ≥ 2 args, every other function takes exactly 1.
   - `LogicalExpr`: `not` takes exactly 1 operand, `and`/`or` take ≥ 2.
   - depth: a module constant `MAX_EXPRESSION_DEPTH = 32` and a validator that raises a
     `ValueError` naming the limit. It must turn what would be a `RecursionError` into a
     `ValidationError` — test that, do not just assert the constant exists.

   **No type inference, no unit checking, no simplification.** Plan §0 and §1 say why; a reviewer
   will look for these having crept in.

5. Add `type ValueRef = SymbolRef | Expression` **in this module** (plan §8 Q5 — putting it in
   `reference_types.py` creates an import cycle) and a `ValueRefLike` beside it.

6. Handle the recursion: `from __future__ import annotations`, forward references, and an explicit
   `model_rebuild()` per node class at the bottom of the module. Verify by validating a
   depth-3 tree from a plain dict — if a rebuild is missing, that is where it shows.

7. `__all__`, sorted, exporting the seven node types, `Expression`, `ValueRef`, `ValueRefLike` and
   `MAX_EXPRESSION_DEPTH`.

8. Tests in `tests/eq1lab_pulse/models/test_expressions.py` (new):
   - each node type constructs and round-trips through `model_dump` → `model_validate`;
   - the `Expression` union discriminates each `expr_type` correctly;
   - a depth-3 nested tree round-trips from a plain dict;
   - `CallExpr` and `LogicalExpr` arity validators accept and reject;
   - depth 33 raises `ValidationError`, **not** `RecursionError`;
   - a `SymbolExpr` wrapping an `ExternalRef` round-trips with the `{"ext": ...}` form intact.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- No existing test changed.
- `models/expressions.py` imports nothing from `channel_ops`, `pulse_types`, `sequence` or
  `control_flow` — dependencies point one way.

### Out of scope

Using `Expression` in any operation model. Any builder change. Adding the module to
`openapi_generator` (task 5).

---

## Task 2 — Widen operations to `ValueRef`; the rebuild sweep

**Read:** plan §3 in full, and §2 of the #6 plan for the read-site inventory.
**Goal:** an `Expression` is accepted wherever a `SymbolRef` is.

### Steps

1. Replace `SymbolRef` with `ValueRef` (and `SymbolRefLike` with `ValueRefLike`) at every site
   listed in the #6 plan's §2 tables — **both** tables, including the concrete-only fields task 4
   of #6 widened. Same list, same files, no new judgement about what counts as a read site.

2. `ConditionalBase.var` is typed `ValueRef` like the rest, plus a model validator restricting it to
   a predicate: a `SymbolRef`, a `CompareExpr`, or a `LogicalExpr`. Arithmetic nodes are rejected
   with a message naming what was passed. Plan §3 consequence 1 and §8 Q2.

3. Run the `model_rebuild()` sweep: every model whose fields now transitively mention `Expression`
   needs rebuilding. That is `pulse_types`, `channel_ops`, `data_ops`, `external_block`,
   `control_flow`, `sequence`, and `experimental/schedule`. Add a test that imports the package
   fresh and validates one model of each family from a plain dict containing an expression — a
   missed rebuild degrades the union to `dict` silently and this is what catches it.

4. Tests:
   - `test_channel_ops.py` / `test_pulse_types.py` — one widened field per family accepts an
     `Expression`;
   - `test_control_flow.py` — `Conditional` accepts `CompareExpr`, `LogicalExpr` and a bare
     `SymbolRef`; rejects `BinaryExpr` and `LiteralExpr`;
   - `test_sequence.py` — a sequence containing expressions round-trips through **JSON** (not just
     `model_dump`).

### Acceptance

- `./qa/run_all_qa.sh` passes.
- **The existing coercion tests in `test_pulse_types.py` pass unchanged.** At ordinary typed read
   sites, `"10us"` is still a `Duration`, `{"ns": 100}` is still a `Duration`, a bare identifier is
   still a `VariableRef`, and `{"ext": ...}` is still an `ExternalRef`. In `ExternalParamValue`,
   unit-suffixed strings are pre-coerced, arbitrary strings stay `str`, and references retain their
   tagged/wrapped JSON forms. The widened unions are the highest regression risk in this plan and
   these tests are the guard.

### Out of scope

Any builder change. Simplification, evaluation, or type checking of expressions.

---

## Task 3 — Builder: `Expr` and its operators

**Read:** plan §4.1, §4.2, and §8 Q1/Q6.
**Goal:** Python operators build an `Expression` tree. Nothing consumes it yet.

### Steps

1. Create `src/eq1_pulse/builder/_expressions.py` with the `Expr` wrapper class and the `expr()`
   entry point. `expr(x)` accepts an `Expr` (identity), a `SymbolRef`, a raw `SymbolValue`, or a
   bare `Expression`, normalizing to `SymbolExpr` / `LiteralExpr` as appropriate.

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

## Task 4 — Builder: leaf checking, acceptance, exports

**Read:** plan §4.3.
**Goal:** builder functions accept an `Expr` and check its leaves.

### Steps

1. In `builder/_factories.py`, add a tree walker that visits every `SymbolExpr` in an `Expression`
   and calls `_check_variable_declared` or `_check_external_declared` per leaf. It belongs next to
   the existing validation helpers, and it is the only new traversal in this plan.

2. Extend `_validate_or_pass_through` and `_validate_explicit_variable_ref` with two branches: an
   `Expr` (unwrap, walk the leaves, return the `Expression`) and a bare `Expression` model (walk,
   return unchanged). A user deserializing a fragment should not have to re-wrap it.

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

## Task 5 — Schema, docs, example

**Read:** plan §6, §7.
**Goal:** expressions are visible in the generated schema and documented.

### Steps

1. `utilities/openapi_generator.py` — three explicit edits: `"expressions"` into `model_modules`,
   `"ExprBase"` into `excluded_base_classes`, and an `{"name": "expressions", "description": ...}`
   entry in the tag list.

2. `tests/test_openapi_generator.py` — the seven expression models are present; `ExprBase` is
   absent.

3. `examples/expression_ramsey.py` — the plan's §5 example, made runnable. Check how
   `tests/test_examples.py` discovers examples before assuming it picks the file up.

4. `docs/source/user_guide/builder_guide.rst` — an "Expressions" section: `expr()` is required (bare
   `var("a") * 2` does not work, and why); `<`/`>` work but `==` does not, use `.eq()`; expressions
   are recorded, never evaluated or dimension-checked by eq1_pulse.

5. Build the docs (`cd docs && ./generate_html.sh`) and confirm no new Sphinx warnings.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `python -m eq1_pulse.utilities.openapi_generator` runs and the seven models appear.
- Docs build clean.

### Out of scope

Any model or builder change. If something is missing, report it rather than adding it here.
