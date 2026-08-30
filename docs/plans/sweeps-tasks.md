# Execution breakdown: parameter sweeps

Companion to [sweeps-plan.md](sweeps-plan.md). Eight implementation tasks and one research task,
each sized for a single clean session. Every decision is closed; the ones taken while drafting are
recorded at the end.

**Revised 2026-08-26** alongside plan §17, which made a sweep an operand of the ordinary expression
grammar instead of the argument of an affine model. The breakdown changed more than the plan did:
the reference-type task is gone, the expression task became the load-bearing one, the affine fold
was deleted and its slot reused for the `affine_form()` recogniser, and the two builder tasks
collapsed into one. Tasks are renumbered; see *Closed since drafting*, D-4.

**Requires #3 (expressions) and #6 (symbols) to have landed** — both have. This plan adds three
nodes to #3's grammar and one rank rule over it; run before either and the work is done twice.

**Run the implementation tasks in numeric order** unless the dependency graph says two are
independent. Each assumes every task it depends on is complete and committed, and each leaves the
tree green.

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
> **Verify.** `./qa/run_all_qa.sh` (pyright + mypy + pytest with coverage). It must pass before you
> report done. If it passed before your change and fails after, you are not done.
>
> **Context.** Read the sections of `docs/plans/sweeps-plan.md` your task names, and **§15 in full
> regardless of task** — it is normative and several tasks are judged against it. Do not read the
> whole plan; the section list in your task is the budget. §17 is one page and worth reading
> whatever your task, because it says which parts of the plan were rewritten and which were not.
>
> **Scope.** Do only what your task says. Each task lists an explicit *out of scope* set. If you
> believe a listed exclusion is wrong, say so in your final message rather than acting on it.
>
> **Closed decisions.** Plan §9 lists twenty-four. Do not re-open them. In particular: a sweep is
> read with `sweep()` and never `var()`; arithmetic over sweeps is the ordinary grammar with no
> curated operator list; every sweep in one expression must be lock-step; `__len__` is not bound;
> there are no categorical sweeps; there is no `SweepRef`; and sweep values are always
> caller-supplied.

---

## Traps with known locations

Carried over from the #3 and #6 executions, plus the ones this plan introduces. None is a decision
to re-open; each is a place where correct-looking code is wrong.

| Trap                                                                                                                                                                                                                                                              | Where it bites |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| **The rank walk must stop at `IndexExpr` and `LenExpr`.** Both take a sweep and return a scalar, so `sweep_names_in()` must **not** descend into their `operand`. Get this wrong and `amplitude=sweep("vg")[var("i")]` — plan §6's index-iteration form, one of the two loop spellings the feature exists for — is rejected as rank-1, while every other test still passes. | Task 1         |
| **A missed `model_rebuild()` does not raise.** It degrades a union member to a plain `dict`, surfacing far from its cause. `IterableSequence` and `Expression` both gain members this plan. `tests/eq1lab_pulse/models/test_valueref_rebuild_sweep.py` is the shape to copy — validate from a plain dict and assert the field is the model, not a dict standing in for one. | Tasks 1, 3     |
| **`ValueRef` is edited, and it is used by nearly every model in the tree.** Narrowing it to `SymbolRef \| ScalarExpression` is one line whose blast radius is every read site in the IR. Every existing expression is rank-0 and must keep validating; if any existing test breaks, the walk is wrong, not the test. | Task 1         |
| **`ValueRef` is not the only value site.** `pulse_types.ExternalParamValue` offers `Expression` as a tagged member of its own union — the type of `ExternalPulse.params` and `ExternalBlock.params` — so narrowing `ValueRef` leaves it wide. It needs the same edit, and nothing tells you: the miss type-checks, passes every test, and lets `{"sweep": "vg"}` reach an external program. Found in review of T1, not by QA. | Task 1         |
| **A widened field is only half the edit.** The builder function exposing it needs the same widening or the field is unreachable through the public API. #6 shipped four such gaps and caught them in review, not QA — a narrow parameter hint is not a type error. | Task 4         |
| **`LeanModel` treats the first single-valued `Literal` field as the discriminator** and always serializes it. `SweepDecl(SweepSpec, DataOpBase)` must declare `op_type` **first**, or the wire form in §15 is wrong in a way no type checker catches.               | Task 2         |
| **`OpBase` lifts every operation to `{op_type: payload}` unconditionally.** This is why `SweepGroup.sweeps` is `list[SweepSpec]` and not `list[SweepDecl]`. Typing it the obvious way produces valid, ugly YAML that passes every test except §15's.             | Task 2         |
| **`SweepSpec` cannot inherit `SymbolDeclBase`** — that class is an `OpBase` descendant. Its three shared fields (`dtype`, `shape`, `unit`) are restated, not reused. Trying to reuse them is the first thing to fail.                                              | Task 2         |
| **A transform is a value, not a declaration.** There is no transform operation, no name to bind, and no model for one — it is an `Expression`. If you find yourself adding a declaration op, a `dtype` for a transform, or anything resembling `AffineSweep`, re-read plan §4.2 and §9 Q13/Q22. | Tasks 2, 4     |
| **`SweepSource` is a discriminated union nested in a plain `\|` union** at `IterableSequence`. It resolves — the keys do not collide — but a malformed item reports against eleven expression members. If the errors are unreadable, the fix is a `Discriminator` reusing `expression_tag_of`, not a narrower `items` type. | Task 3         |
| **`builder/experimental/schedule.py` mirrors the same functions over shared `_factories.py`.** It needs identical type-hint widening to stay green even when a task otherwise leaves it alone. That is a type-hint fix, not a feature addition to a module scheduled for removal ([#8](https://github.com/equal1/eq1_pulse/issues/8)). | Task 4         |
| **Re-exporting through `core.py` needs the `from ._sweeps import X as X` idiom**, or an importer of `builder.core` gets a pyright error on the implicit re-export.                                                                                                | Task 4         |
| **`tests/test_examples.py` discovers `examples/**/*.py` by `rglob`.** A new example file is picked up with no list to update.                                                                                                                                     | Task 6         |
| **The docs build emits pre-existing autoapi "more than one target found for cross-reference" warnings** for names re-exported from `models/`. They are on `main` too. Compare against a baseline build rather than treating any warning as new.                     | Task 6         |
| **Removing `list[str]` from `IterableSequence` is a breaking schema change.** It also deletes a special case in `IterationBase._validate_vars_vs_items`. The zipped and broadcast cases must still pass without it — they are what that validator is actually for. | Task 3         |

---

## Dependency graph

```text
T1 ─┬─ T3 ─ T4 ─┬─ T6
    │           └─ T8
    └─ T5 ──────── T6

T2 ─┬─ T3
    └─ T7 ───────── T8

R-1 ....... informational; gates nothing
```

**T1 and T2 are independent** and may run in parallel or merge — different files, no shared symbol.
Do not merge T1 into anything else: the rank walk is the one piece of this plan with a silent
failure mode that no existing test covers.

T3 needs both. T5 (`affine_form()`) needs only T1 and may run any time after it, in parallel with
T3 and T4. T7 needs only T2. T8 needs T4 and T7.

| #   | Task                                                            | Size | Model     | Reasoning | Context     | Touches                                          |
| ----- | ----------------------------------------------------------------- | ------ | ----------- | ----------- | ------------- | -------------------------------------------------- |
| T1  | `models/expressions.py` — the sweep leaf, two nodes, the rank rule | M    | Opus 5    | high      | 200k / ~55k | `models/expressions.py`, `tests/`                |
| T2  | `models/sweeps.py` — the declarations                           | M    | Opus 5    | high      | 200k / ~50k | `models/sweeps.py`, `tests/`                     |
| T3  | `Indices`, `IterableSequence`, `SweepOp`, rebuild sweep          | M    | Sonnet 5  | high      | 200k / ~50k | `models/control_flow.py`, `models/sequence.py`, `tests/` |
| T4  | Builder: `sweep()`, indexing, declarations, `for_`, checks        | M    | Sonnet 5  | high      | 200k / ~55k | `builder/`, `tests/`                             |
| T5  | `utilities/affine_form.py` — the compactness recogniser          | M    | Sonnet 5  | high      | 200k / ~40k | `utilities/affine_form.py`, `tests/`             |
| T6  | Schema, docs, example                                            | S    | Haiku 4.5 | medium    | 200k / ~30k | `utilities/`, `docs/`, `examples/`, `tests/`     |
| T7  | `models/arguments.py` — the invocation payload                  | S    | Sonnet 5  | high      | 200k / ~35k | `models/arguments.py`, `tests/`                  |
| T8  | `check_arguments()` — units and nesting                          | M    | Sonnet 5  | high      | 200k / ~45k | `utilities/check_arguments.py`, `tests/`         |
| R-1 | Research: how eq1lab would consume this                          | S    | Sonnet 5  | medium    | 200k / ~25k | `docs/research/` (new file), no source           |

### Legend

The four columns are chosen **independently**. Size does not imply reasoning level: a small task
with a silent failure mode gets `high`, a large mechanical one gets `medium`.

| Column        | Value      | Means                                                                                                              |
| --------------- | ------------ | -------------------------------------------------------------------------------------------------------------------- |
| **Size**      | S          | One or two source files plus their tests. A shape already in the tree to copy from.                                |
|               | M          | Three to six files including tests, or one file plus a change that ripples through its callers.                    |
|               | L          | A new module, or an edit spanning most of `models/`. Expect to want a second pass over your own output before QA is green. |
| **Reasoning** | medium     | Mistakes are **loud** — wrong code fails pyright, mypy, or an existing test immediately.                            |
|               | high       | Mistakes are **silent** — wrong code type-checks and passes the existing tests while being subtly wrong: a union resolving to the wrong member, a serializer dropping a field, a model degraded to `dict`. |
| **Model**     | Haiku 4.5  | The acceptance criteria are a checklist. Nothing to design.                                                        |
|               | Sonnet 5   | Ordinary model or builder work, with an in-tree pattern to follow.                                                 |
|               | Opus 5     | Silent failure mode **and** no in-tree precedent to copy.                                                          |
| **Context**   | `w / s`    | `w` is the window to run with; `s` is roughly what should be resident — the named plan sections, the files listed, their tests. A session approaching its `s` figure has loaded files it was not asked to touch. |

**Why these assignments.** T1 and T2 are the Opus tasks, for opposite reasons. T1 edits the union
every read site in the IR depends on and introduces a walk whose one stop condition is invisible to
every existing test; nothing in the tree does rank this way. T2 is `SweepDecl(SweepSpec, DataOpBase)`
— multiple inheritance across two model hierarchies with a discriminator-ordering rule and a wire
form that is wrong-but-valid if either is missed. T5 is `high` because a recogniser is arithmetic
that type-checks whatever it computes: a wrong `affine_form()` returns plausible terms and a
consumer uploads the wrong scan. T4 and T6 have loud failures.

---

## T1 — `models/expressions.py`: the sweep leaf, two nodes, and the rank rule

**Landed** as `bb6dea6`, with the review fixes in steps 2, 5 and 5a folded in afterwards.

**Read:** plan §3, §5, §15 (expressions and transforms).
**Depends on:** nothing.
**Goal:** a sweep is an expression operand; a tree knows whether it reads one; the value sites say
no and the sweep sites say yes.

This is the plan's load-bearing task. Everything else consumes what it defines.

### Steps

1. `SweepExpr(ExprBase)` with a single `sweep: IdentifierStr` field. **Flat** — leave the three
   `_wire_*` class vars unset, exactly as `LiteralExpr` and `SymbolExpr` do, so the wire form is
   `{"sweep": "vg"}`. Read `SymbolExpr` and the class docstring of `ExprBase` first.

2. `IndexExpr` and `LenExpr` as plan §5 sketches. **Copy `NotExpr`'s three class vars** —
   `_wire_tag_from_ = "name"`, `_wire_payload_key_ = None` — and its single-valued `Literal` tag
   field. Read `NotExpr` and its docstring first; it explains why the tag comes from the field name.
   `IndexExpr.indices` is `list[ScalarExpression]`, not `list[Expression]`: an index is a position,
   never a sweep. Give it `Field(min_length=1)` — `a[]` names no item, and `CallExpr` already
   establishes that arity is checked in this module.

3. Register all three in `_EXPRESSION_TAGS` (`sweep`, `index_op`, `len_op`) and add
   `Annotated[..., Tag(...)]` members to the `Expression` union. `expression_tag_of` needs no edit —
   it reads the registry.

4. `sweep_names_in(expression) -> frozenset[str]`, walking with the existing `_operands_of`
   iterator so a node type added later is walked without registering it. Two things it must do that
   a naive walk does not:
   - read the **name** off a `SweepExpr`, whose `sweep` field is a `str` and therefore invisible to
     `_operands_of`;
   - **stop at `IndexExpr` and `LenExpr`** — do not descend into their `operand`. Both return
     scalars whatever they read. This is the trap named in the table above; write the test for it
     before the walk.

   Walk iteratively, on `_expression_depth`'s pattern: the depth cap is validated first, so the walk
   is bounded, but the reason `_expression_depth` avoids recursion applies here too.

5. Two annotated aliases and one edited one:

   ```python
   type ScalarExpression = Annotated[Expression, AfterValidator(_reject_sweeps)]
   type SweepSource = Annotated[Expression, AfterValidator(_require_sweep)]
   type ValueRef = SymbolRef | ScalarExpression        # was: SymbolRef | Expression
   ```

   `_reject_sweeps` raises a message **naming the offending sweeps**, because the author needs to
   know which one leaked into a value. `_require_sweep` has none to name — their absence is the
   fault — so it names **the node it got instead**, via `expression_tag_of`; a bare "this is not a
   sweep" is unactionable, and the usual way to land here by accident is an `IndexExpr` or `LenExpr`
   that is rank-0 however deep the sweep under it sits. Leave `ValueRefLike` alone: it hints
   authoring input, and the field's own type does the checking.

6. **Narrow `ExternalParamValue` too.** In `models/pulse_types.py`, its expression member becomes
   `Annotated[ScalarExpression, Tag(_EXTERNAL_PARAM_EXPR_TAG)]`. It is the one value site in the IR
   that does not go through `ValueRef` — see the trap table — and it types `ExternalPulse.params`
   and `ExternalBlock.params`. Add `ScalarExpression` to the deferred import at the bottom of the
   module. `ExternalParamValueLike` keeps its plain `Expression`, for the reason `ValueRefLike`
   does.

7. `model_rebuild()` for the three new nodes at the bottom of the module, beside the existing eight.

8. **Do not** add `"len"` to `ExpressionFunction`. Plan §9 Q3 closed that; `CallExpr` stays a set of
   mathematical functions, which over a sweep are applied elementwise.

9. **Do not** curate which operators may take a sweep. A node is rank-1 exactly when an operand is,
   uniformly — comparisons included. Plan §9 Q21.

10. `__all__` updated and sorted; the module docstring gains a paragraph on rank, in the terms it
    already uses for result kind.

11. Tests in `tests/eq1lab_pulse/models/test_expressions.py`:
    - all three nodes round-trip, and their wire forms match §15 **literally**;
    - **the stop condition**: `sweep_names_in` returns empty for a `LenExpr` and an `IndexExpr`
      however deep the sweep sits, and `{"index_op": …}` **validates** at a `ValueRef` field;
    - a bare `{"sweep": "vg"}` is **rejected** at a `ValueRef` field, and so is a sweep nested four
      levels down under one — same error, and it names `vg`;
    - a rank-0 tree is **rejected** at a `SweepSource` field;
    - every operator over a sweep builds and round-trips: `+ - * / %`, unary `-`, `abs`, a
      `CallExpr`, and a comparison;
    - `expression_tag_of` returns the three new tags and the existing eight are unchanged;
    - an `IndexExpr` nested inside a `BinaryExpr` round-trips **through JSON**, not just
      `model_dump`;
    - the depth validator counts the new nodes like any other;
    - `indices=[]` is rejected;
    - `_require_sweep`'s message names the node it got.

12. Tests in `tests/eq1lab_pulse/models/test_pulse_types.py` for step 6: a bare `{"sweep": "vg"}`
    and a tree over one are both rejected at `ExternalParamValue`, an `index_op` and a `len_op` are
    both accepted there, and the rejection reaches `ExternalPulse.params` and not just the alias.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- **No existing expression or model test is modified.** Every expression in the tree today is
  rank-0; if one now fails, the walk is wrong.
- `git grep -n "SweepRef" src/` returns nothing. Plan §9 Q24.
- `git grep -n "Annotated\[Expression" src/` returns exactly the two alias definitions in
  `expressions.py` and nothing else — no other field or union still admits a rank-1 tree at a value
  site.

### Out of scope

`models/sweeps.py` (T2). `IterableSequence` (T3). Any builder change. `affine_form()` (T5).

---

## T2 — `models/sweeps.py`: the declarations

**Landed** as `be20b19`, including the `nd_array` fix step 2 now describes.

**Read:** plan §2, §4.1, §4.3, §15 (declarations).
**Depends on:** nothing.
**Goal:** the sweep declarations exist, validate, and serialize exactly as §15 says.

### Steps

1. Create `src/eq1_pulse/models/sweeps.py`. It imports `basic_types`, `data_ops` and `expressions`,
   and nothing imports it back — keep it a leaf, with no deferred import at the bottom of the
   module. The sweep **expression** nodes are not here; they are in `expressions.py` (T1), which is
   what keeps this module a leaf and `control_flow.py` free of any import of it.

2. `type SweepValue = LinSpace | Range | NumpyIntArray1D | NumpyFloatArray1D | NumpyComplexArray1D`.
   `LinSpace` and `Range` come from `basic_types` unchanged. The three arrays come from `nd_array`
   and are **restated, not imported as `NumpyIterableArray`** — that alias lives in `control_flow`,
   which is an operation module, and importing it would break this module's leaf property, which is
   step 1 and an acceptance criterion. Members are decidable by wire shape; do not add a tag.

   Expect to fix `nd_array.np_int_1d_array_validate` on the way: it returned a real-dtype array
   before checking `ndim`, so an `(N, 2)` real array — the authoring form of a 1-D *complex* one —
   was accepted by the integer member and won the smart union ahead of the complex member. Move the
   dimension check first. A complex `default` cannot round-trip until you do, and no existing test
   covers it because `IterableSequence` never exercised that path.

3. `SweepSpec(LeanModel)` with `name`, `dtype`, `shape`, `unit`, `default`, `limits`. **It cannot
   inherit `SymbolDeclBase`** — that is an `OpBase` descendant and would make every group member an
   operation. Restate the three shared fields, with a comment saying why.

4. `SweepDecl(SweepSpec, DataOpBase)` adding `op_type: Literal["sweep_decl"]`, **declared first**.
   Verify the wire form is `{"sweep_decl": {...}}` with a real assertion, not by inspection.

5. `SweepGroup(OpBase)` with `op_type` and `sweeps: list[SweepSpec]` (min length 2).

6. `type SweepOp = Annotated[SweepDecl | SweepGroup, OperationDiscriminator()]` — two operations,
   and there is no third. **There is no model for a transform**: it is an `Expression`. If you are
   writing a class with `terms` and an `offset`, stop and read plan §4.2 and §17.

7. Validators — these and no others: `SweepGroup.sweeps` has at least two members and, **where every
   member's `default` is concrete**, equal lengths. Lock-step membership is not checkable here; it
   needs declaration scope and belongs in T4. Plan §9 Q23.

8. `__all__`, sorted.

9. Tests in `tests/eq1lab_pulse/models/test_sweeps.py` (new):
   - every model round-trips through `model_dump` → `model_validate` **and** through JSON;
   - the §15 declaration YAML block asserted **literally** against `model_dump()` — this is the
     acceptance criterion for steps 3–5 and the only thing that catches the `list[SweepDecl]`
     mistake;
   - `SweepOp` discriminates both operations by their sole key;
   - a `SweepGroup` with mismatched concrete lengths raises; one with unsupplied defaults does not;
   - `LeanModel` elision: `shape`, `limits` and an absent `default` do not appear.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `models/sweeps.py` imports nothing from `channel_ops`, `pulse_types`, `sequence` or
  `control_flow`, and defines no expression node.
- The §15 declaration block is asserted literally, not paraphrased.

### Out of scope

Wiring `SweepOp` into `DiscriminableOp` (T3). Any expression node (T1). Any builder change.
Lock-step validation (T4).

---

## T3 — `Indices`, `IterableSequence`, `SweepOp`, and the rebuild sweep

**Read:** plan §6, §7, §15 (loops).
**Depends on:** T1, T2.
**Goal:** a loop can iterate a sweep or a transform of one; a sequence can carry a sweep operation.

### Steps

1. In `models/control_flow.py`, add `Indices(LeanModel)` with `count: int | ValueRef`.

2. Widen `IterableSequence` to `LinSpace | Range | NumpyIterableArray | SweepSource | Indices`, and
   **remove `list[str]`**. Both additions are decidable by wire shape — every expression is a
   sole-key object naming its node, and none of those keys is `start`, `count`, `num` or `step` —
   so no discriminator change. A bare `{"sweep": "vg"}` needs no member of its own: it is a one-node
   expression, and `SweepSource` already admits it.

3. Delete the `list[str]` special case from `IterationBase._validate_vars_vs_items`. Read that
   validator carefully first: it uses `all(isinstance(item, str) ...)` to tell "one iterable of
   strings" from "a list of iterables", and removing the member simplifies but does not delete the
   validator. **The zipped and broadcast cases must still pass.**

4. In `models/sequence.py`, add `SweepOp` to `DiscriminableOp`. This is also the first thing that
   imports `models/sweeps.py` at all — T2 left it a leaf nothing reaches — so a rebuild that was
   never exercised now is. Check what `models/__init__.py` re-exports while you are there: it lists
   nine modules and `expressions` and `sweeps` are not among them, so `Expression`, `ValueRef`,
   `SweepDecl` and the rest are not importable from `eq1_pulse.models`. That predates this plan;
   decide it deliberately rather than by omission, and say which way you went.

5. **Optional, and this is the task to do it in:** `control_flow.NumpyIterableArray` and the three
   array members `sweeps.SweepValue` restates are the same set written twice (plan §2.1). Moving
   the alias down into `nd_array` and importing it from both removes the duplication without
   costing `sweeps.py` its leaf property. You are editing that line anyway.

6. Run the rebuild sweep. Every model transitively mentioning the new union members needs
   `model_rebuild()`. Add `tests/eq1lab_pulse/models/test_sweep_rebuild.py` on the model of
   `test_valueref_rebuild_sweep.py` — validate one representative model per family from a plain
   dict containing a sweep expression and assert the field deserialized to the model, not a dict.
   This is the task's highest-value test; a missed rebuild is silent.

7. Tests:
   - `test_control_flow.py` — `Iteration` accepts a bare `{"sweep": …}`, a `binary_op` tree over
     one, and `Indices`; a rank-0 tree and a `list[str]` are both now **rejected**; zipped and
     broadcast forms unchanged;
   - `test_sequence.py` — a sequence containing both sweep operations round-trips through **JSON**,
     and matches §15's loop blocks literally;
   - `test_schema_symmetry.py` — whatever it asserts about unions still holds.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- The `list[str]` removal is the only intentional breaking change beyond T1's `ValueRef` narrowing;
  note it in the commit message.
- No model anywhere validates a sweep expression into a plain `dict`.

### Out of scope

Any builder change. The declaration-scope checks in plan §7 and §8.3 (T4).

---

## T4 — Builder: `sweep()`, indexing, declarations, `for_`, checks, exports

**Read:** plan §7, §8.
**Depends on:** T3.
**Goal:** the plan's §13 examples A–H build.

This was two tasks before the revision. The affine fold that made up half of one of them no longer
exists — `Expr`'s operators already do the arithmetic — so what is left fits in one session.

### Steps

1. Create `src/eq1_pulse/builder/_sweeps.py`. It does not import `core.py`, matching the one-way
   rule `_state.py`, `_factories.py` and `_expressions.py` already establish.

2. `sweep(name) -> Expr` returning `Expr(SweepExpr(sweep=name))`. **That is the whole constructor.**
   There is no `Sweep` wrapper class, no fold, no term canonicalisation and no `unwrap()` that
   returns two different types — `Expr` already is the wrapper, and its operators already build the
   trees. If you are writing `__mul__`, you are writing the wrong file.

3. In `_expressions.py`, add `Expr.__getitem__` returning an `Expr` wrapping an `IndexExpr`; a tuple
   index becomes multiple `indices`. Add the free function `len_(x)` wrapping a `LenExpr`. Both
   **raise `TypeError` at the calling line** when the operand reads no sweep — call
   `sweep_names_in()` and check — rather than letting `IndexExpr` raise a `ValidationError` two
   frames later.

4. **Do not bind `__len__`.** Plan §9 Q4: `len()` runs `__index__` on the result and rejects
   anything that is not a non-negative `int`. Add a test asserting `len(sweep("a"))` raises.

5. `sweep_decl()` and `sweep_group()` — **two** declaration functions. A transform is anonymous
   (plan §4.2), so there is nothing to declare it with. `sweep_group()` is a context manager
   collecting the `sweep_decl()` calls in its body into one `SweepGroup`, following
   `sub_sequence()`'s shape in `core.py`.

6. Extend `_state.py`'s declaration tracking to sweeps, alongside variables and externals. It backs
   the three checks below.

7. Three build-time checks, all local, none a traversal:
   - **undeclared sweep** — `sweep("x")` with no `sweep_decl` in scope, wherever in a tree it
     appears;
   - **at most one consuming `for_`** per sweep (plan §7) — a loop consumes every sweep its `items`
     trees read, so this is `sweep_names_in()` over each item, unioned; a second consumer raises,
     naming the first;
   - **lock-step** (plan §4.2) — every sweep a *single* expression reads must be the same sweep or a
     member of one `SweepGroup`. A cross-level combination raises naming both sweeps, and the
     message points at plan §10's in-body alternative.

   There is **no** cycle check to write: an expression tree is finite and acyclic, and a transform
   has no name for another to reference. Plan §9 Q8.

8. `for_` accepts an `Expr` and calls `unwrap()`. Its `items` parameter hint widens to match
   `IterableSequence` — the "widened field is only half the edit" trap. Check
   `builder/experimental/schedule.py` for the same signature.

9. Export `sweep`, `sweep_decl`, `sweep_group`, `indices` and `len_` from `core.py` (using the
   `from ._sweeps import X as X` idiom) and from `builder/__init__.py`'s import list and `__all__`,
   both kept sorted.

10. Tests in `tests/eq1lab_pulse/test_builder_sweeps.py` (new):
    - each of plan §13's examples A–H builds and its dump matches expectation;
    - **example H specifically** — `sweep("amp") * sweep("scale")` builds a `BinaryExpr`. It raised
      `TypeError` under the first design, so a test asserting it now *works* is what stops the
      restriction being reintroduced;
    - an inline transform in `for_` items dumps as the expression tree §15 shows, and a bare
      reference dumps as `{"sweep": …}`;
    - all three checks in step 7 raise, each with a message naming the offending sweep;
    - example G's cross-level mirror — the same two sweeps declared nested rather than grouped —
      raises, under `*` as well as under `+`;
    - a sweep consumed by two `for_` blocks raises;
    - `expr(var("i"))[0]` and `len_(expr(var("i")))` raise `TypeError`, not `ValidationError`.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `builder.__all__` is sorted and contains all five new names.
- Plan §13 examples A–H all run.
- `_sweeps.py` does not import `core.py`, and contains no arithmetic.
- The experimental schedule builder still imports and its tests pass.

### Out of scope

Docs, the example file and the schema (T6). `affine_form()` (T5).

---

## T5 — `utilities/affine_form.py`

**Read:** plan §2.2, §4.4, §9 Q22.
**Depends on:** T1.
**Goal:** a consumer can ask whether a sweep expression is affine, and get the terms if it is.

This is where the deleted `AffineSweep` model went. It is the difference between uploading three
numbers and uploading twenty thousand floats, and it is **advisory** — nothing in `models/` or
`builder/` calls it. May run any time after T1, in parallel with T3 and T4.

### Steps

1. Create `src/eq1_pulse/utilities/affine_form.py`. It imports `models/expressions.py` and nothing
   from `builder/`.

2. `AffineForm` — a plain frozen dataclass (**not** a pydantic model; it never touches the wire)
   with `terms: dict[str, Expression]` and `offset: Expression`.

3. `affine_form(expression) -> AffineForm | None`. Returns the decomposition when the tree is
   `sum(scale_i * sweep_i) + offset` with every `scale_i` and the `offset` rank-0, and `None`
   otherwise. `None` is a normal answer, not a failure: it means *evaluate this elementwise*.

4. The recognisable set, and nothing beyond it:
   - a bare `SweepExpr` — one term, scale literal `1`, offset literal `0`;
   - `+` and `-` of two recognisable operands, or of one and a rank-0 tree;
   - `*` of a recognisable operand and a **rank-0** tree, either way round;
   - `/` of a recognisable operand by a rank-0 tree — never the reverse;
   - unary `-`.

   Everything else returns `None`: `*` and `/` between two sweep-bearing operands, `%`, every
   `CallExpr`, every comparison, and `IndexExpr` / `LenExpr` (which are rank-0 anyway and belong in
   the *offset*, not in the terms).

5. **Canonicalise terms by sweep name, summing scales.** `sweep("a") + sweep("a")` is one term of
   scale `2`. This is the canonicalisation the builder used to do at authoring time; it moved here
   with the rest of the algebra.

6. Scales and offsets are combined as **`Expression` trees, not floats** — a scale may be
   `ext("vg.m11")`, which has no value until invocation. Building `BinaryExpr(op="*", …)` is the
   whole of "multiplying" two scales. Do not evaluate anything; plan §1's *declare, never enforce*
   applies here too.

7. Do not fold literal arithmetic either. `2 * 3` stays a tree. A consumer that wants numbers
   evaluates; this function decomposes.

8. `__all__`, sorted. The module docstring states plainly that a `None` result is correct and common,
   and what a consumer should do with it.

9. Tests in `tests/eq1lab_pulse/test_affine_form.py` (new):
   - a bare sweep, `s * 2`, `2 * s`, `s / 2`, `-s`, `s + 5`, `5 - s`, `s1 - s2`, and
     `s * ext("m11") + ext("o1")` — each recognised, with the exact terms and offset asserted;
   - `sweep("a") + sweep("a")` is **one** term of scale `2`;
   - `sweep("a") * sweep("b")`, `1 / sweep("a")`, `abs(sweep("a"))`, `sweep("a") % 3` and
     `sweep("a") > 0` each return `None`;
   - a scale that is itself an expression over externals survives as a tree, unevaluated;
   - plan §13 example C's two transforms are both recognised — the case the whole utility exists
     for.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `affine_form.py` imports nothing from `builder/` and evaluates nothing.
- Every case in step 4's list is tested, in both the recognised and the `None` direction.

### Out of scope

Calling it from anywhere. Any model change. Any builder change. Evaluating a sweep.

---

## T6 — Schema, docs, example

**Read:** plan §12, §15, §17.
**Depends on:** T4, T5.
**Goal:** sweeps are in the generated schema and documented.

### Steps

1. `utilities/openapi_generator.py` — `"sweeps"` **and `"arguments"`** into `model_modules`, and an
   `{"name": ..., "description": ...}` entry in the tag list for each. `excluded_base_classes` is
   **not** touched: `SweepSpec` and `ProgramArguments` are `LeanModel`s that appear on the wire, not
   base classes. `SweepExpr`, `IndexExpr` and `LenExpr` ride in on `expressions`, which is already
   listed.

   If T7 has not landed yet, do the `"sweeps"` half and say so — do not skip it silently.

2. `tests/test_openapi_generator.py` — `SweepSpec`, `SweepDecl`, `SweepGroup`, `ProgramArguments`
   and `QualifiedSweepValue` are present; `SweepExpr`, `IndexExpr` and `LenExpr` are present. There
   is **no** `AffineSweep` and no `SweepRef`; if you find yourself looking for either, read plan
   §17.

   **Do not look for the rank rule in the schema, and do not assert it is there.** `ScalarExpression`
   and `SweepSource` are `AfterValidator`s, which emit no JSON Schema, so all three aliases publish
   the same thing and a schema validator accepts `{"sweep": "vg"}` under an amplitude. Plan §3.3
   says so; if the docs section in step 4 claims the schema enforces rank, that is the sentence to
   fix, not the schema.

3. `examples/swept_gate_scan.py` — plan §13 example C, made runnable, dumping the program twice
   with different supplied ranges to show §0's point. `tests/test_examples.py` discovers examples by
   `rglob`, so there is no list to update.

4. `docs/source/user_guide/builder_guide.rst` — a "Sweeps" section covering: what a sweep is and is
   not (a list, items may repeat); why `sweep()` is not `var()`; the three operations; that
   arithmetic over a sweep is the arithmetic already documented one section up, applied elementwise;
   the lock-step rule and what to write instead when it bites (plan §10); and plan §4.4's table on
   where the arithmetic runs.

5. A short subsection on `affine_form()`, beside the one on `check_arguments()`. Both are advisory
   and nothing calls them, so a reader who does not learn they exist never benefits — and for
   `affine_form()` that costs a float per point of every scan. Lead with that.

6. Build the docs (`cd docs && ./generate_html.sh`) and confirm no new Sphinx warnings against a
   baseline build of `main`.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `python -m eq1_pulse.utilities.openapi_generator` runs and the new models appear.
- Docs build clean against baseline.

### Out of scope

Any model or builder change. If something is missing, report it rather than adding it here.

---

## T7 — `models/arguments.py`

**Read:** plan §16 (the `ProgramArguments` subsection), §9 Q15/Q17/Q18.
**Depends on:** T2.
**Goal:** an invocation is a validated, schema-published artifact.

Unchanged by the 2026-08-26 revision — the payload supplies *values* for declared sweeps, and
transforms were anonymous before and after.

### Steps

1. Create `src/eq1_pulse/models/arguments.py`. It imports `basic_types`, `data_ops` and `sweeps`,
   and nothing imports it back — another leaf, like `sweeps.py`.

2. `QualifiedSweepValue(RootModel[dict[UnitKey, SweepValue]])` — the `{"mV": {...}}` form. Validate
   **exactly one key** and that it is a known unit, reusing `dimension_tag_of_unit_mapping` from
   `basic_types` rather than writing a second unit reader.

3. `type SweepArgument = SweepValue | QualifiedSweepValue` and
   `type SweepLevel = dict[IdentifierStr, SweepArgument]`.

4. `ProgramArguments(LeanModel)` with `parameters: dict[IdentifierStr, SymbolValue]` and
   **`sweeps: list[SweepLevel]`**, both defaulting to empty.

5. **`sweeps` is a list of levels, outermost first — not a flat mapping.** A level with one entry is
   a single sweep; a level with several is a group. Plan §16 and §9 Q19. This is the shape that lets
   the payload assert the nesting; getting it flat defeats T8's check 3 entirely.

6. **Keep `parameters` and `sweeps` apart.** Plan §16 says why: `{"mV": [1, 2]}` is a
   `ComplexVoltage` under `SymbolValue` and a two-item array sweep under `SweepArgument`, and one
   combined field cannot tell them apart without a declaration to consult. Merging them is the
   mistake to avoid.

7. Validators: every level is non-empty; no name appears in two levels, or twice overall. **Do not**
   check anything against a program — this model does not have one. That is T8.

8. No `externals` mapping — those are resolved by the framework, not supplied. Plan §9's remaining
   open note.

9. `__all__`, sorted.

10. Tests in `tests/eq1lab_pulse/models/test_arguments.py` (new):
    - the §16 YAML block round-trips **literally**, including the two-entry level staying one list
      item with two keys;
    - `{"mV": {"start": 0, "stop": 1, "num": 5}}` validates as a `QualifiedSweepValue`; a two-key
      mapping and an unknown unit key both raise;
    - `{"mV": [1, 2]}` resolves to `ComplexVoltage` under `parameters` and to an array sweep under
      `sweeps` — the ambiguity the split exists to remove, asserted from both sides;
    - an empty level raises; a name repeated across two levels raises;
    - an empty `ProgramArguments` validates;
    - a bare `SweepValue` with no unit key is accepted inside a level.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `models/arguments.py` imports nothing from `builder/` or `utilities/`.
- The §16 YAML is asserted literally, not paraphrased.

### Out of scope

Checking arguments against a program (T8). Any change to a declaration model. Resolved externals.

---

## T8 — `check_arguments()`

**Read:** plan §16 in full, §7, §9 Q15/Q16.
**Depends on:** T4, T7.
**Goal:** a program plus a `ProgramArguments` can be checked before invoking.

This is the task that makes §0's promise safe: a stored program invoked with the wrong ranges is
still a valid program, so nothing else in this plan catches an mV-for-V substitution.

### Steps

1. Create `src/eq1_pulse/utilities/check_arguments.py`. It lives in `utilities/`, **not**
   `models/`: the payload is data the IR owns (T7), but matching one against a particular program is
   analysis no field validator can perform. Plan §9 Q16/Q18.

2. It takes a program and a **`ProgramArguments`** from T7 — do not redefine the shape here, and do
   not accept a loose dict. Whatever T7 already validates is not this function's problem: a
   malformed unit key or a two-key wrapper never reaches it.

3. Walk the program's declarations, gathering scope the way the builder does. Implement the five
   checks in plan §16 in order: name coverage, unit agreement, nesting agreement, group agreement,
   shape and limits.

4. **Report every finding, do not raise on the first.** Return a list of findings, each naming the
   declaration and what is wrong. An empty list means the arguments fit. A user with three mistakes
   should learn all three in one run.

5. **Compare units as strings. Never convert, never rescale.** `"mV" != "V"` is a finding; deciding
   they are 1000 apart is not this function's business and contradicts #6. An argument that states
   no unit is accepted as being in the declared one — that is not a finding.

6. Transforms are anonymous, so they never appear in arguments at all — there is no
   "supplied a computed sweep" case to check for. What a loop's `items` tree *does* tell you is
   which sweeps that loop consumes: `sweep_names_in()` over each item, which is the same call the
   builder makes in T4 and the input to check 3.

7. **Nesting agreement is the other headline check.** Derive the program's structure per plan §7 —
   unconsumed sweeps in declaration order, then consumed sweeps in `for_` nesting order — and
   compare it to `arguments.sweeps` position by position: same level count, same order, same members
   per level. This is the one check needing a body traversal; everything else is local to the
   declarations.

   Findings here name **both sides**: what the payload asserted and what the program actually says.
   That is the whole value — it is how a stored invocation catches a program that has drifted since
   it was written.

8. Tests in `tests/eq1lab_pulse/test_check_arguments.py` (new):
   - plan §16's example arguments against a program with that exact structure — no findings;
   - **`unit: V` supplied for a `unit: mV` declaration is a finding** — the headline case;
   - a stated unit matching, and an omitted unit, both produce no finding;
   - a missing sweep and an unknown name are each a finding;
   - **drift cases**, one per shape: two levels swapped; a sweep moved from its own level into a
     group; a group split across two levels; one level too many. Each is a finding, and its message
     names both the asserted and the actual structure;
   - a loop whose `items` is a **transform** consumes its bases correctly — a program built like
     plan §13 example C is checked against a single-level payload naming `detuning`, with no
     findings;
   - a level whose entries have unequal lengths is a finding;
   - a program with three distinct problems returns three findings in one call;
   - `shape` and `limits` violations are findings.

### Acceptance

- `./qa/run_all_qa.sh` passes.
- `check_arguments.py` imports nothing from `builder/`.
- No unit conversion anywhere in the module — a reviewer will grep for arithmetic on unit strings.
- Nothing calls it automatically; it is advisory.

### Out of scope

Defining the argument shape — that is T7. Any change to a declaration model. Enforcing anything at
build time. Resolved externals.

---

## R-1 — Research: how eq1lab would consume this

**Type:** research. Produces a document, touches no source.
**Depends on:** nothing. Can run at any time; gates nothing.
**Output:** `docs/research/sweeps-eq1lab-integration.md`, listed in `docs/research/README.md`'s
assessments table.

### Questions to answer

Read the eq1lab checkout beside this one (`../eq1lab`) — it is the source, not the web.

1. **Where do scan ranges live today?** Are they literals in experiment scripts, or resolved from a
   config / calibration store per device? `eq1lab_core/sweep_types.py`,
   `eq1lab_core/sweep/param_expr.py`, `eq1lab/framework/_nd_sweep.py` and the examples under
   `examples/01_framework_features/` are the places to look. Informational now that D-2 is closed
   (always caller-supplied) — but if the answer is "mostly config", say so loudly, because it would
   be evidence to reopen plan §9 Q17.
2. **What would consume a `SweepDecl`?** Trace how `do_nd_inner_loop` and `nd_sweep` currently
   receive sweep specifications, and identify the seam where an eq1_pulse program's declarations
   would be read instead.
3. **Does anything need `TogetherSweep` semantics that `SweepGroup` does not cover?** In
   particular `SweepPlaceholder` and the `wrapped_nd_inner_loop` / QDAC-trigger path.
4. **How are values supplied to a program today?** D-3 is closed — `ProgramArguments` is a model
   (T7) — so the question is now compatibility: does eq1lab have an established payload shape that
   T7's `parameters` / `sweeps` split would fight with?
5. **What in `normalize_sweep_argument`'s nine input forms would eq1lab still need** after adopting
   `SweepValue`, and which are qcodes-compatibility shims that can be dropped at the boundary.
6. **How far does `ParameterExpr` reach?** New with the 2026-08-26 revision, and the most useful
   question of the six. `ParameterExpr` accepts arbitrary arithmetic over parameters; so, now, does
   this. Enumerate the expressions eq1lab actually builds with it and check each against plan §5's
   grammar and §4.2's lock-step rule. Anything that needs two independent-length sweeps in one
   expression is the interesting finding — plan §10 rejects it deliberately, and evidence that
   eq1lab needs it is evidence to reopen that.

### Format

Follow `docs/research/openpulse-alignment-assessment.md`: a findings summary, then a section per
question, then an explicit "what this means for the sweeps plan" section naming any decision in plan
§9 it would reopen. If it reopens none, say so — that is the useful answer.

### Out of scope

Changing anything in this repo. Proposing eq1lab changes. This is a survey.

---

## Deferred — file as issues once this plan closes

Found while reviewing T1 and T2. Neither blocks a task here, and neither should be picked up while
tasks are still landing on the same files.

**D-A — the expression walks are exponential on a shared-operand DAG.** `_expression_depth` and
`sweep_names_in` both walk structure rather than distinct objects, so a tree that reuses one operand
instance at both sides of a node — `n = BinaryExpr(lhs=n, rhs=n)`, repeated — doubles its expansion
per level. Pydantic never copies submodels, so an author can build one in Python; it becomes
unusably slow around 21 levels, under `MAX_EXPRESSION_DEPTH`. It is **not reachable from a document**:
JSON has no sharing, so a deserialized tree is a real tree. Predates this plan (`_expression_depth`
came with #3); T1 inherited the shape rather than introducing it, and the note lives on
`_expression_depth`'s docstring.

The fix is memoizing on `id()` in both walks, and the reason not to do it now is that it changes what
"depth" means for a shared subtree — a real decision, and `MAX_EXPRESSION_DEPTH` is a wire-format
constraint that T3's and T6's schema work is measured against. Investigate after T8.

**D-B — `models/__init__.py` re-exports neither `expressions` nor `sweeps`.** It lists nine modules;
`Expression`, `ValueRef`, `SweepDecl`, `SweepSpec` and `sweep_names_in` are therefore not importable
from `eq1_pulse.models`, only from their own modules. Also predates this plan. T3 step 4 asks the
task that first imports `sweeps.py` to settle it rather than leave it to omission; if T3 defers it
too, it belongs here.

---

## Closed since drafting

**D-1 — the public names.** Closed: **accepted as written.** `sweep()` references, `sweep_decl()`
declares a supplied sweep, `sweep_group()` declares a lock-step group. Rejected along the way:
`axis()` (contradicts "items may repeat"), `derived_sweep()` and `parallel_sweep()` (both broke the
`sweep*` prefix), `together_sweep()` and `sweep_ref()` (near-misses). `sweep_expr()` was in the
accepted set until transforms were made anonymous — with no name to bind there is no function to
name. The `SweepExpr` name it collided with is now taken by the expression leaf node (T1), which is
a model rather than a builder function, so the collision is gone. Plan §9 Q12/Q13.

**D-2 — sweep provenance.** Closed: **always caller-supplied.** No `ExternalDecl`-style
resolve-by-name, no provenance field. Plan §9 Q17.

**D-3 — the arguments payload.** Closed: **promote it into `models/`** (T7) while the checker stays
a utility (T8). Plan §9 Q16/Q18.

**D-4 — sweeps as ordinary expressions.** Closed 2026-08-26: **adopted**, and the breakdown is
renumbered around it. Plan §17 carries the argument. What moved:

| Was                                             | Is                                                                |
| ------------------------------------------------- | ------------------------------------------------------------------- |
| T1 — `SweepRef`, `SweepName`                    | **gone.** `models/reference_types.py` is untouched. Plan §9 Q24.  |
| T3 — `IndexExpr`, `LenExpr`                     | **T1**, grown to hold `SweepExpr`, the rank walk and the two aliases |
| T2 — `models/sweeps.py`                         | **T2**, minus `AffineSweep` and `SweepSource`                     |
| T4 — `Indices`, `IterableSequence`, rebuild     | **T3**                                                            |
| T5 — the affine fold                            | **gone.** `Expr`'s operators already do it.                       |
| T6 — builder declarations, `for_`, checks       | **T4**, absorbing what remained of T5                             |
| —                                               | **T5** — `utilities/affine_form.py`, new; where the affine algebra went |
| T7 — schema, docs, example                      | **T6**                                                            |
| T8 — `models/arguments.py`                      | **T7**, unchanged in substance                                    |
| T9 — `check_arguments()`                        | **T8**, plus one test for a transform-driven loop                 |

The net is one task fewer and one file fewer in `models/`, against one new file in `utilities/`.

D-1 to D-3 were open when this breakdown was first written; R-1 was to inform them. It no longer
gates anything and is kept because questions 2, 3, 5 and the new 6 are still worth answering before
eq1lab adopts this.
