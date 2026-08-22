# Execution breakdown: operator-keyed expression serialization

A follow-up refactor to [expressions-plan.md](expressions-plan.md) / [expressions-tasks.md](expressions-tasks.md)
(issue #3, all five tasks landed). It changes **only the wire form** of the expression nodes: no node
is added or removed, no validator changes, no builder API changes.

**The problem.** Every node carries `expr_type` *and* an operator, and the two say the same thing
twice. On a tree of any depth the redundancy dominates the document:

```jsonc
// today
{"expr_type": "binary", "op": "*",
 "left":  {"expr_type": "symbol",  "symbol": {"var": "scale"}},
 "right": {"expr_type": "literal", "value":  {"mV": 80}}}
```

**The fix.** Delete `expr_type` and let each node be keyed on a field it already needs -- the
operator for the four operator nodes, and the single payload field for the other three:

```jsonc
// after
{"binary_op": "*",
 "left":  {"symbol": {"var": "scale"}},
 "right": {"value":  {"mV": 80}}}
```

Half the keys, and the one key that survives is the one a reader was looking for anyway.

---

## The design -- closed decisions

### Node to key

| Node          | Key          | Field change                 | Wire form                                    |
| ------------- | ------------ | ---------------------------- | -------------------------------------------- |
| `LiteralExpr` | `value`      | none -- drop `expr_type`     | `{"value": {"ns": 100}}`                     |
| `SymbolExpr`  | `symbol`     | none -- drop `expr_type`     | `{"symbol": {"var": "x"}}`                   |
| `UnaryExpr`   | `unary_op`   | `op` becomes `unary_op`      | `{"unary_op": "-", "operand": ...}`          |
| `BinaryExpr`  | `binary_op`  | `op` becomes `binary_op`     | `{"binary_op": "+", "left": ..., "right": ...}`  |
| `CompareExpr` | `compare_op` | `op` becomes `compare_op`    | `{"compare_op": "<", "left": ..., "right": ...}` |
| `LogicalExpr` | `logical_op` | `op` becomes `logical_op`    | `{"logical_op": "and", "operands": [...]}`   |
| `CallExpr`    | `function`   | none -- drop `expr_type`     | `{"function": "abs", "args": [...]}`         |

Three nodes need no field change at all: `value`, `symbol` and `function` are already unique across
the node set and already say what the node is. Only the four operator nodes rename `op`, and they
rename it because `op` alone cannot discriminate -- `"-"` is both a unary and a binary operator,
which is exactly why the operator has to be qualified by arity rather than left bare.

### The union

`Discriminator("expr_type")` becomes a **callable** `Discriminator` over per-member `Tag`s -- the
same shape `ExternalParamValue` in `pulse_types.py` already uses, for the same reason: the
discriminating key is not the same key on every member. Read the tag off the mapping's keys (or off
the instance's type), and the seven keys are mutually exclusive by construction.

### No aliases

A serialization alias is not an option and is not to be reintroduced. `test_schema_symmetry.py`
asserts `model_json_schema(mode="validation") == model_json_schema(mode="serialization")` for every
discovered model, so an alias applying to one mode fails it; and an alias with
`populate_by_name=True` applies to both but then admits **two** wire spellings of one type, which is
the invariant #10 exists to hold. The rename is a real rename.

### `expr_type` is deleted, not kept as a property

`ExprBase` loses its `expr_type: Any` field and gains nothing back. "Is this a predicate?" is
answerable from the wire key alone (`compare_op` / `logical_op` versus `binary_op`), which is
strictly better than what the #3 plan §2.1 argued for `expr_type`; and in Python it is already
answered by `isinstance` -- `control_flow.py`'s `_validate_predicate` does exactly that today and
does not change.

---

## Measured, not assumed

Prototyped against the landed tree before this breakdown was written. Do not re-derive these; do
lock them down with the tests task 2 adds.

| Fact                                                                                                                                                    | Consequence                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| A mixed depth-3 tree validates from a plain dict, and `model_dump()` / `model_dump_json()` reproduce it exactly, under `warnings.simplefilter("error")`. | The callable discriminator's serializer is exact. No silent member mismatch. |
| `BinaryExpr` and `CompareExpr` differ **only** in their operator key -- same `left`/`right` otherwise -- and each still serializes as itself when nested inside the other. | The one shape that could have collided does not.                   |
| Validation-mode and serialization-mode JSON schemas are still equal.                                                                                    | `test_schema_symmetry.py` stays green with no edit.                |
| The union's JSON schema becomes a bare `oneOf` of `$ref`s with **no** `discriminator`/`mapping` keyword -- that is what a callable `Discriminator` generates. Members stay decidable: every node is `additionalProperties: false` and its key is `required`. | Expected, not a regression. `ExternalParamValue` already generates this. |
| `unary_op: Literal["-"]` is now the **first** field, so `LeanModel`'s discriminator rule serializes it always -- measured identical with and without a default. | The #3 plan §2.1 trap is *inverted*. Declare it without a default anyway, for symmetry with the other three operator fields. |
| `ExprBase` becomes field-less. `ExprBase().model_dump()` is `{}`. `ExprBase._non_discriminator_fields()` raises `StopIteration` on a field-less model, but `LeanModel._wrap_serializer` never reaches it for one -- its field loop is empty. | Reachable only by calling the private classmethod directly. Nothing does; do not add a guard. |
| `ValueRef` (`SymbolRef` or `Expression`) still resolves `{"var": "x"}` to `VariableRef` and `{"binary_op": ...}` to `BinaryExpr`.                        | The plain union needs no change.                                   |

---

## Traps

| Trap                                                                                                                                              | Where it bites |
| --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| **`.op` is overwhelmingly `ScheduleItem.op`, not an expression's.** `tests/eq1lab_pulse/experimental/test_builder.py` alone reads `.op` on schedule items roughly forty times. A blind `.op` rename destroys it. The **only** expression `.op` reads in the tree are `expressions.py`'s `LogicalExpr._validate_operand_count` (two lines). | Task 1         |
| **Three `op=` arguments sit on their own line** and are missed by a `ClassName(op=` pattern: `test_control_flow.py:39`, `test_expressions.py:53`, `test_schema_symmetry.py:75`. All three belong to the enclosing `LogicalExpr`/`BinaryExpr` constructor. | Task 1         |
| **`_external_param_value_tag` sniffs `"expr_type" in value`** for the mapping branch (`pulse_types.py:247`). Its instance branch (`isinstance(value, ExprBase)`) needs no change. The round-trip half of `test_external_param_value_expression` goes through the mapping branch, so a missed edit is a test failure rather than a silent hole -- but only because that test exists. | Task 1         |
| **`op=` also appears with a non-literal value**: `LogicalExpr(op=op, ...)` in the parametrized arity tests (`test_expressions.py:163,171`). The pytest parameter is named `op` too; rename the keyword, and rename the parameter with it or the test reads as if nothing changed. | Task 1         |
| **`output/eq1_pulse_openapi.{json,yaml}` are committed but already stale** -- last regenerated in #10, before expressions existed (`grep -c BinaryExpr` gives 0). Nothing in the repo regenerates them, and `python -m eq1_pulse.utilities.openapi_generator` writes `openapi.{json,yaml}` into the *cwd*, not there. Leave them alone; refreshing them is a separate change and would bury this diff. | Task 3         |
| **`docs/source/user_guide/builder_guide.rst` never shows a serialized expression.** Its only model-level mention is `CallExpr(function="abs")`, which is unchanged. The doc work is an addition, not a correction. | Task 3         |

---

## Dependency graph

```text
1 ──┬──> 2
    └──> 3
```

Safe merge: **2 + 3** (both small, disjoint files). Task 1 is not mergeable into either -- it is the
whole functional change and must land green on its own.

| #  | Task                                                   | Size | Model     | Reasoning | Context     | Touches                                                                                   |
| -- | ------------------------------------------------------ | ---- | --------- | --------- | ----------- | ----------------------------------------------------------------------------------------- |
| 1  | Key each node on its own field; callable discriminator | M    | Sonnet 5  | medium    | 200k / ~55k | `models/expressions.py`, `models/pulse_types.py`, `builder/_expressions.py`, 10 test files |
| 2  | Lock the new wire form                                 | S    | Haiku 4.5 | medium    | 200k / ~25k | `tests/eq1lab_pulse/models/test_expressions.py`, `test_pulse_types.py`                     |
| 3  | Docs and plan records                                  | S    | Haiku 4.5 | medium    | 200k / ~25k | `docs/source/user_guide/builder_guide.rst`, `docs/plans/`                                  |

The columns mean what [expressions-tasks.md](expressions-tasks.md)'s legend says they mean.

**Why `medium` reasoning throughout,** where #3's equivalent tasks were `high`: the failure mode that
made them `high` -- a union silently resolving to the wrong member, or degrading to `dict` -- has
been measured away in the table above, and every remaining mistake is loud. `extra="forbid"` turns a
missed `op=` into a `ValidationError`, pyright reports the unknown keyword, and `test_expressions.py`
already asserts exact `model_dump()` documents. Task 1 is large by file count and mechanical by
content.

---

## Common preamble -- paste into every session

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
> report done. It passes at the branch point; if it fails after your change, you are not done.
>
> **Context.** Read this file's "The design", "Measured, not assumed" and "Traps" sections before
> starting. They are measurements, not proposals -- do not re-derive them and do not reopen them.
> `docs/plans/expressions-plan.md` describes the *old* wire form throughout; read it for the node
> set and the validators, not for the serialization.
>
> **Scope.** Do only what your task says. Each task lists an explicit *out of scope* set. If you
> believe a listed exclusion is wrong, say so in your final message rather than acting on it.

---

## Task 1 -- Key each node on its own field

**Goal:** `expr_type` is gone from the wire and from the models; every node is discriminated by the
field it already carried. The tree is green.

**Read:** this file's design / measured / trap sections; `src/eq1_pulse/models/expressions.py` in
full; `_external_param_value_tag` in `src/eq1_pulse/models/pulse_types.py`.

### Steps

1. **`models/expressions.py` -- the node classes.**

   - Delete `ExprBase.expr_type` entirely, and any import it leaves unused. Keep `ExprBase` itself:
     `isinstance(x, ExprBase)` is load-bearing in `pulse_types.py` and `builder/_factories.py`, and
     `ExprBase` is already in `openapi_generator.excluded_base_classes`.
   - Delete the `expr_type` field from all seven node classes.
   - Rename `op` on the four operator nodes to `unary_op`, `binary_op`, `compare_op`, `logical_op`.
     Each keeps its existing `Literal[...]` values and stays **first** in its class. **No default**
     on any of them -- per the measured table `unary_op` would serialize either way; keep the four
     uniform.
   - `LogicalExpr._validate_operand_count` reads `self.op` twice -- both become `self.logical_op`,
     including the one inside the error message's f-string.

2. **`models/expressions.py` -- the tag machinery.** Add this above the `Expression` alias, with
   full ReST docstrings on both members in the house style:

   ```python
   _EXPRESSION_TAGS: Final[dict[type[ExprBase], str]] = {
       LiteralExpr: "value",
       SymbolExpr: "symbol",
       UnaryExpr: "unary_op",
       BinaryExpr: "binary_op",
       CompareExpr: "compare_op",
       LogicalExpr: "logical_op",
       CallExpr: "function",
   }


   def expression_tag_of(value: Any) -> str | None:
       if isinstance(value, Mapping):
           return next((tag for tag in _EXPRESSION_TAGS.values() if tag in value), None)
       for node_type, tag in _EXPRESSION_TAGS.items():
           if isinstance(value, node_type):
               return tag
       return None
   ```

   `expression_tag_of` is public-named without being in `__all__`, matching `dimension_tag_of` in
   `basic_types.py` -- it is imported by `pulse_types.py` and by nothing outside the package.
   `__all__` is otherwise **unchanged**: this task adds and removes no exported name.

3. **`models/expressions.py` -- the union.** Replace the string discriminator with the tagged form:

   ```python
   type Expression = Annotated[
       Annotated[LiteralExpr, Tag("value")]
       | Annotated[SymbolExpr, Tag("symbol")]
       | Annotated[UnaryExpr, Tag("unary_op")]
       | Annotated[BinaryExpr, Tag("binary_op")]
       | Annotated[CompareExpr, Tag("compare_op")]
       | Annotated[LogicalExpr, Tag("logical_op")]
       | Annotated[CallExpr, Tag("function")],
       Discriminator(expression_tag_of),
   ]
   ```

   Member order is `_EXPRESSION_TAGS`'s declaration order; keep the two lists in the same order so a
   reader can check them against each other. The `model_rebuild()` calls at the bottom of the module
   are unchanged.

4. **Docstrings in `models/expressions.py`.** Four say `expr_type` and are now wrong:

   - the **module** docstring's last paragraph ("answerable from `expr_type` alone without
     inspecting `op`") -- rewrite it for the new scheme: the wire key *is* the operator, and
     `compare_op` / `logical_op` versus `binary_op` answers "is this a predicate?" on the wire as
     well as in Python;
   - `ExprBase`'s class docstring, which describes the deleted field;
   - `UnaryExpr.op`'s docstring, whose whole subject is the no-default trap -- replace it with the
     inverted fact from the measured table: it is the discriminator now, and is always serialized;
   - `ValueRef`'s ("an expression carries `expr_type`") -- an expression now carries one of the
     seven node keys.

5. **`models/pulse_types.py` -- one functional line.** In `_external_param_value_tag`, replace the
   mapping-branch check `if "expr_type" in value:` with `if expression_tag_of(value) is not None:`,
   importing `expression_tag_of` alongside `ExprBase, Expression, ValueRef` in the deferred
   bottom-of-module import. Leave the branch's position, the `isinstance(value, ExprBase)` instance
   branch, and everything else in that function alone.

   Then correct the two docstrings naming `expr_type`: `_EXTERNAL_PARAM_EXPR_TAG`'s, and the
   `ExternalParamValue` paragraph reading "tagged the same way, on its own `expr_type` key".

6. **`builder/_expressions.py` -- mechanical.** Twenty constructor calls, all single-line:
   `BinaryExpr(op=` becomes `BinaryExpr(binary_op=`, and likewise for `UnaryExpr`, `CompareExpr` and
   `LogicalExpr`. Nothing else changes: `Expr`'s public surface, `expr()`, and every operator method
   keep their signatures and behaviour.

7. **Tests -- mechanical renames.** The same four constructor substitutions, plus the three own-line
   `op=` sites and the two parametrized `op=op` sites the trap table names. Files:

   `tests/eq1lab_pulse/models/` -- `test_expressions.py`, `test_valueref_rebuild_sweep.py`,
   `test_channel_ops.py`, `test_control_flow.py`, `test_data_ops.py`, `test_external_block.py`,
   `test_pulse_types.py`, `test_schema_symmetry.py`, `test_sequence.py`;
   `tests/eq1lab_pulse/test_builder_expressions.py`.

   Finish with `git grep -n 'Expr(op=\|^\s*op=' src tests` returning nothing.

8. **Tests -- the wire documents.** Every dict literal spelling an expression loses its
   `"expr_type"` key and renames its `"op"` key. They are in `test_expressions.py` (the
   discrimination parametrize, the depth-3 tree, and the `model_dump()` assertions around lines 134,
   177, 195, 201 and 217) and `test_valueref_rebuild_sweep.py` (two module-level documents).

   `test_union_discriminates_on_expr_type` is now about node keys rather than an `expr_type` value:
   rename it and its parametrize ids, drop the `assert node.expr_type == expr_type` line in favour
   of `assert isinstance(node, node_type)`, and build each case from the "Node to key" table above.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `git grep -n expr_type src tests` is empty.
- `git grep -n '\.op\b' src` matches nothing in `models/expressions.py`, and the schedule-item `.op`
  reads in `tests/eq1lab_pulse/experimental/test_builder.py` are untouched.
- No test is deleted and no test's *subject* changes. Renaming a test and rewriting the documents it
  asserts is expected; if you find yourself weakening an assertion to make it pass, stop and say so
  in your final message.
- `builder/_expressions.py`'s public API is unchanged apart from the four keyword renames.

### Out of scope

Any change to the node set, the validators, `MAX_EXPRESSION_DEPTH`, or the builder's public surface.
New tests (task 2). Docs (task 3). `output/eq1_pulse_openapi.*`.

---

## Task 2 -- Lock the new wire form

**Goal:** the properties task 1 relies on are asserted, not assumed. Purely additive.

**Read:** this file's "Measured, not assumed" table; `tests/eq1lab_pulse/models/test_expressions.py`
as task 1 left it.

### Steps

Add these to `tests/eq1lab_pulse/models/test_expressions.py`. Each corresponds to one row of the
measured table, and each must fail if that row stops holding.

1. **Exact serialization, warnings as errors.** Build one mixed tree containing all seven node types
   -- a `CompareExpr` over a `BinaryExpr` over a `SymbolExpr` and a `LiteralExpr`, against a
   `CallExpr`, with a `UnaryExpr` and a `LogicalExpr` somewhere in it. Inside
   `warnings.catch_warnings()` with `warnings.simplefilter("error")`: validate it from a plain dict,
   assert `model_dump()` equals that same dict, and assert `json.loads(model_dump_json())` does too.

   The `simplefilter("error")` is the point of the test -- a union serializer that picks the wrong
   member emits `PydanticSerializationUnexpectedValue` as a *warning* and produces output anyway.

2. **`BinaryExpr` and `CompareExpr` do not collide.** They differ only in their operator key. Nest
   each inside the other and assert both survive a `model_dump` / `model_validate` round trip as
   their own type.

3. **Every node is reachable from a mapping.** Parametrize over the seven (key, document, type)
   triples: `expression_tag_of(document)` returns the expected key, and the union validates the
   document to the expected type. Also assert `expression_tag_of` returns `None` for `{"var": "x"}`,
   for `{}`, and for a non-mapping such as `5`.

4. **`ValueRef` still disambiguates.** `TypeAdapter(ValueRef)` resolves `{"var": "x"}` to
   `VariableRef`, `{"ext": "q0.f01"}` to `ExternalRef`, and `{"binary_op": "+", ...}` to
   `BinaryExpr`.

5. **`unary_op` is always serialized.** `UnaryExpr(unary_op="-", operand=...).model_dump()` contains
   `unary_op`. `test_expressions.py` has this assertion today for `op` and task 1 renamed it -- if
   what is already there is adequate, say so and skip this step rather than duplicating it.

6. **No `expr_type` survives in a dumped tree.** Dump the step-1 tree and assert the string
   `"expr_type"` does not appear in its JSON.

Then in `tests/eq1lab_pulse/models/test_pulse_types.py`, extend
`test_external_param_value_expression` -- do not add a second test -- with one case per *other* node
type reaching `ExternalParamValue` as a **mapping**. That is the branch task 1 edited, and today only
`BinaryExpr` exercises it.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- Each new test fails when the property it names is broken. Check at least steps 1 and 3 that way --
  locally break one of task 1's tag entries, watch the test fail, restore it. Report that you did.
- No existing test is modified except the one extension named above.

### Out of scope

Any change to `src/`. If a test cannot be made to pass without one, task 1 is incomplete -- report it
rather than fixing it here.

---

## Task 3 -- Docs and plan records

**Goal:** the new wire form is documented where a reader looks for it, and the plan documents no
longer present the old one as current.

**Read:** this file's "Node to key" table; `docs/source/user_guide/builder_guide.rst` from the
"Building computed values with expressions" heading to the end of that section.

### Steps

1. **`docs/source/user_guide/builder_guide.rst`.** Add a short **"What an expression looks like on
   the wire"** subsection at the end of the expressions section. It has one job: show the serialized
   form of `expr(var("scale")) * Amplitude("80mV")` as a `.. code-block:: json`, and state the rule
   in one sentence -- each node carries exactly one key naming what it is, and for the operator
   nodes that key is the operator qualified by arity (`unary_op`, `binary_op`, `compare_op`,
   `logical_op`).

   Show only the new form. The old one is not something a reader should learn. The surrounding
   section needs no correction -- its only model-level reference is `CallExpr(function="abs")`,
   which did not change. Do not restructure it.

2. **`docs/plans/expressions-plan.md`.** Add a `**Revision -- operator-keyed serialization**` note at
   the top of §2.1, in the voice of that file's existing "Revision" notes: `expr_type` was removed
   and each node is keyed on its own field; point at this file. Then annotate the two paragraphs
   §2.1 ends with -- the `LeanModel` convention paragraph and the `UnaryExpr.op` trap paragraph --
   since both are now false as written. Annotate the §2.1 diagram rather than rewriting it.

   Everything else in that plan -- the node set, §2.2's function set, §2.3's depth cap, §2.4's
   `SymbolValue` fix -- is unaffected and must not be touched.

3. **`docs/plans/expressions-tasks.md`.** Two edits: mark task 5 **done** (it landed in `bce72e1`;
   the file still shows it open), and add a one-line pointer under the preamble to this breakdown as
   the successor that changed the wire form.

4. **Build the docs** -- `cd docs && ./generate_html.sh` -- and confirm no new Sphinx warnings
   against a baseline build. The autoapi "more than one target found for cross-reference" warnings
   for names re-exported from `models/` are pre-existing and on `main`; compare, do not count.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- The docs build produces no warning a baseline build does not.
- The JSON in step 1 is *correct* -- produce it by running that builder expression through
  `model_dump_json()`, not by hand.

### Out of scope

Any change to `src/` or `tests/`. Regenerating `output/eq1_pulse_openapi.{json,yaml}`: they are
already stale by two issues (see the trap table), and refreshing them belongs to its own change.
