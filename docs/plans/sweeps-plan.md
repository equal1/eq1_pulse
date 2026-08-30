# Plan: parameter sweeps

**Status:** accepted — all open questions closed (§9); see
[sweeps-tasks.md](sweeps-tasks.md) for the execution breakdown
**Date:** 2026-08-25, revised 2026-08-26 — §17 records what changed and why
**Predecessors:** [#6 — external constants and parameter variables](https://github.com/equal1/eq1_pulse/issues/6)
and [#3 — expression support](https://github.com/equal1/eq1_pulse/issues/3), both **landed**. This
plan adds three nodes to #3's expression grammar and one rank rule over it, and depends on both
being in the tree.

This plan closes #3's last deliberately-deferred item — *"element-wise operations on array
variables … nothing defines what it means either. Left open until something needs it."* Something
needs it. §3 and §9 Q2 define it — and the 2026-08-26 revision defines it *widely*: a sweep is
an operand of the ordinary expression grammar, not the argument of a special-purpose affine model.
See §17 for the revision in one page.

---

## 0. Purpose

Store an experiment **once**, as a pulse program, and invoke it again and again with different
sweep ranges.

That is the whole feature. Every decision below is what the purpose forces:

| Because                                          | Therefore                                                                                                                    |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| The values come from outside                     | The program cannot embed them, cannot know their length, and cannot unroll. It needs `len_()` and `[]` to work with the list symbolically. §5. |
| The values travel on **every** invocation        | Their encoding is a first-class concern. A linear sweep is three numbers, not ten thousand floats. §2.                        |
| The same stored program runs any number of points | Widening a scan or halving its resolution must not require rebuilding the IR — the property `ParameterDecl` already buys for scalars, one rank up. |
| The result is N-dimensional                      | The nesting structure must be readable off the declarations, without walking loop bodies. §7.                                 |

### A sweep is a list, not an axis

Items may repeat and need not be ordered. An interleaved calibration scan is
`[100, 0, 100, 50, 100, 25]`. "Setpoints" on an "axis" imports monotonicity and uniqueness that are
not there, so the model says **items** throughout — the word `Iteration` already uses.

> **Naming caution.** `tests/eq1lab_pulse/models/test_valueref_rebuild_sweep.py` uses "sweep" in the
> unrelated sense of *a sweep through the model modules calling `model_rebuild()`*. That file is not
> about this feature, and this feature's own rebuild work (tasks 1 and 3) is a second, separate one.

---

## 1. Scope and framing decisions

| Decision                                                        | Consequence                                                                                                                        |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **A sweep is rank-1; a value is rank-0.**                       | The distinction is a property of an expression *tree*, computed by a bounded walk, and enforced at exactly two boundaries: `ScalarExpression` rejects a tree containing a sweep, `SweepSource` requires one. §3. |
| **A sweep is a list, and the operations on one are the grammar's.** | Iterate it (`for_`), measure it (`LenExpr`), index it (`IndexExpr`), and compute with it — `+ - * / %`, unary `-`, and every `CallExpr` function, elementwise. The middle two return scalars; arithmetic returns a sweep. |
| **Transforms on sweeps are ordinary expressions.**              | `sweep("d") * ext("vg.m11") + ext("vg.o1")` is a `BinaryExpr` over a `SweepExpr` leaf — the same nodes, the same wire form, the same builder operators that scalars already use. §2.2, §5. |
| **Sweep values are supplied per invocation; `default` is a fallback.** | Named the way `ParameterDecl.default` and `ExternalDecl.default` already are. A program wanting fixed values sets a default and supplies nothing. |
| **Compact forms are first-class *as supplied values*.**         | `LinSpace` and `Range` are members of `SweepValue`, not an optimisation a consumer applies. Keeping a *transform* of one compact is a recognisable property of the tree, not a modelled constraint — `affine_form()` in §2.2. |
| **No categorical sweeps.**                                      | Sweeping a channel or pulse reference makes per-channel scheduling data-dependent. §10.                                            |
| **Nesting order has exactly one source per sweep.**             | A consumed sweep takes it from `for_` nesting; an unconsumed one from declaration order. Nothing to reconcile, so no check. §7.     |
| **No `placement` field.**                                       | Whether the host or the program drives a sweep is structural — a `for_` consumes it, or nothing does.                              |
| **eq1_pulse still declares and never enforces.**                | Bounds, units and lengths travel on the declaration. Nothing here evaluates a sweep, materialises one, or folds an expression over one. |
| **Units are compared, never converted.**                        | A supplied sweep may state its unit; if it does, it must equal the declared one *exactly*, as strings. That is not unit conversion — it is the check that catches mV supplied for a V declaration, which is the failure this plan most needs to prevent. §16. |
| **The wire form is read by humans.**                            | A stored experiment is a YAML file someone opens to see what it sweeps. Every new form is chosen for that, using the bare-name carve-out `VarName` already establishes rather than new machinery. §15 is the full reference and is normative. |

---

## 2. Sweep values and their representation

### 2.1 `SweepValue`

```python
# models/sweeps.py
type SweepValue = LinSpace | Range | NumpyIntArray1D | NumpyFloatArray1D | NumpyComplexArray1D
```

The list-valued counterpart of `data_ops.SymbolValue`. Members are decidable by wire shape with no
tag, exactly as `SymbolValue`'s are:

| Form       | Wire                     | Size   | For                                             |
| ------------ | -------------------------- | -------- | ------------------------------------------------- |
| `LinSpace` | `{start, stop, num}`     | O(1)   | the common case — an evenly spaced scan         |
| `Range`    | `{start, stop, step}`    | O(1)   | a scan specified by resolution rather than count |
| array      | `[…]`                    | O(n)   | irregular, measured, or repeating items         |

`LinSpace` and `Range` are reused from `basic_types` unchanged, including their existing
`LinSpaceLike` / `RangeLike` TypedDict authoring forms. Both are already explicitly unitless
(*"units should be specified in the variable declaration"*), which is what `SweepDecl.unit`
continues.

The array members are the same three `control_flow.NumpyIterableArray` is an alias for, **restated
over `nd_array` rather than imported from it**. `NumpyIterableArray` lives in `control_flow`, which
is an operation module, and `models/sweeps.py` takes no import from one — that is what keeps it a
leaf (§4.1's task acceptance). The duplication is three names and is deliberate; consolidating it
means moving the alias down into `nd_array` and re-exporting, which is a change to `control_flow`
and belongs to the task that edits `IterableSequence` anyway.

### 2.2 Compactness, and where it went

An affine transform of a `LinSpace` is a `LinSpace`:

```text
scale * LinSpace(start, stop, num) + offset
    == LinSpace(scale*start + offset, scale*stop + offset, num)
```

and so is a **linear combination** of `LinSpace`es of equal length:

```text
s1*LinSpace(a1, b1, n) + s2*LinSpace(a2, b2, n) + o
    == LinSpace(s1*a1 + s2*a2 + o, s1*b1 + s2*b2 + o, n)
```

Equal length is exactly what §4.3's sweep group guarantees, which is why the sweeps read by one
expression must be lock-step: the constraint that makes elementwise arithmetic meaningful is the
same one that keeps this identity true.

**Affineness is a property a consumer recognises, not a shape the IR imposes.** The first version of
this plan modelled it — an `AffineSweep` carrying `terms` and an `offset`, so that a transform of
compact bases was compact *by construction*. That bought compactness at the price of a second,
parallel arithmetic: its own model, its own operators, its own folding rules, and four operations
(`s * s2`, `s / s2`, `k / s`, `sqrt(s)`) that had to be spelled as *absent methods* because the
model had nowhere to put them. The revision drops the model and keeps the identity:

```python
# utilities/affine_form.py -- advisory, like check_arguments()
def affine_form(expression: Expression) -> AffineForm | None:
    """Recognise ``sum(scale_i * sweep_i) + offset``; None if the tree is not affine."""
```

`AffineForm` is a plain dataclass of `terms: dict[str, Expression]` and `offset: Expression` — the
fields the model used to carry, produced by a **recogniser** rather than enforced by a validator. A
generator that wants to upload three numbers instead of ten thousand calls it and takes the fast
path when it gets a result; one that does not, evaluates the tree elementwise and is correct either
way. Nothing in `models/` runs it, and nothing has to call it at all.

This is the revision's real cost, stated plainly: **compactness is no longer guaranteed by the
type.** What it buys is that non-affine transforms stop being a special case with a different
spelling and a different failure mode. `sweep("a") * sweep("b")` is now a tree a consumer evaluates
elementwise, exactly as `sweep("a") + sweep("b")` is — the two differ in whether `affine_form()`
returns something, not in whether they can be written at all.

Transforms that read *no* sweep are unchanged: they are rank-0 arithmetic over a `var()` inside the
loop body, and #3's grammar has always handled them.

---

## 3. Rank, and how it is enforced

The load-bearing decision.

A sweep is a list; a value is a scalar. Nothing about that changes when sweeps become expression
operands — what changes is *where the distinction is recorded*. It was union membership; it is now
a property of a tree, computed by a walk, checked at the two boundaries that care.

### 3.1 `SweepExpr` — the leaf

```python
# models/expressions.py
class SweepExpr(ExprBase):
    """A reference to a declared sweep appearing in an expression, spelled ``{"sweep": "vg"}``."""

    sweep: IdentifierStr
```

Flat, like `LiteralExpr` and `SymbolExpr` — one field, so there is nothing to wrap. It registers in
`_EXPRESSION_TAGS` under `"sweep"` and gains a `Tag("sweep")` member in the `Expression` union;
`expression_tag_of` then routes a sole-key `{"sweep": ...}` mapping to it with no other change.

**It is a leaf, and the only one that is rank-1.** Every other node's rank is its operands': a
`BinaryExpr` is rank-1 exactly when `lhs` or `rhs` is.

### 3.2 Rank is a tree property

```python
def sweep_names_in(expression: Expression) -> frozenset[str]:
    """The names of every sweep read anywhere in *expression*, empty for a scalar tree."""
```

Walked with the same `_operands_of` iterator `_expression_depth` already uses, so a node type added
later is walked without registering it anywhere. Bounded by `MAX_EXPRESSION_DEPTH`, which is
validated first — the walk cannot run long because a tree that deep never validates.

Two annotated aliases apply it, and they are the whole enforcement:

```python
type ScalarExpression = Annotated[Expression, AfterValidator(_reject_sweeps)]
"""An expression that reads no sweep. What every value site accepts."""

type SweepSource = Annotated[Expression, AfterValidator(_require_sweep)]
"""An expression that reads at least one. What every sweep site accepts."""

type ValueRef = SymbolRef | ScalarExpression        # the first of two edits to existing aliases
```

`ValueRef` is the alias nearly every read site in the IR already uses — `Play.amplitude`,
`Repetition.count`, `Delay.duration`, `ConditionalBase.var`, all of them. Guarding it once guards
every one of them.

**There is a second value site, and it is easy to miss.** `pulse_types.ExternalParamValue` — the
type of `ExternalPulse.params` and `ExternalBlock.params` — does not go through `ValueRef`. It
offers an expression as one tagged member of its own union, so it needs the same narrowing
independently:

```python
    | Annotated[ScalarExpression, Tag(_EXTERNAL_PARAM_EXPR_TAG)]     # was: Expression
```

Nothing warns you about this. A missed narrowing here type-checks, passes every test, and lets
`{"sweep": "vg"}` reach an external program as a parameter. Together the two aliases are the whole
of the rank guard on the value side; a value site added later has to pick one of them on purpose.

Inside a sweep-valued tree the operands stay plain `Expression`, which is what lets a sweep leaf sit
under a `BinaryExpr` at all. The guard applies at the boundary, not at every node.

### 3.3 What the type system catches

| Mistake                                                    | Caught by                                                     |
| ------------------------------------------------------------ | --------------------------------------------------------------- |
| `play(ch, square_pulse(amplitude=sweep("vg")))`             | `ScalarExpression` — a sweep leaf at a `ValueRef` field       |
| `play(ch, square_pulse(amplitude=sweep("vg") * 2))`         | `ScalarExpression` — the *tree* is rank-1, at any depth       |
| `if_(sweep("vg") > 0)`                                      | `ScalarExpression` — `ConditionalBase.var` is a `ValueRef`    |
| `for_("i", var("n"))` over a scalar                         | `SweepSource` — a rank-0 tree where a sweep is required       |
| `for_("i", ext("gain") * 2)`                                | `SweepSource` — same, and this one used to be unrepresentable |
| `external_pulse("gate", detuning=sweep("vg"))`              | `ScalarExpression` — via `ExternalParamValue`, §3.2          |

On the builder, on deserialization, and on a program emitted by another producer — wherever the
document passes through pydantic. The second and third rows are new: the first version of this plan
could not catch them at all, because a sweep-bearing *tree* had no way to exist and therefore no way
to be rejected.

**What the published schema does not carry.** This is the admitted cost of reading rank off the
tree instead of off union membership, and it is not obvious: an `AfterValidator` emits no JSON
Schema, so `ScalarExpression`, `SweepSource` and `Expression` all publish the *same* schema, and a
consumer validating a document against the OpenAPI spec alone accepts `{"sweep": "vg"}` under an
amplitude. The union-membership version would have shown the rule, because a type is a schema and a
walk is not. Rank is enforced by eq1_pulse and stated in the docs, not by the spec — which is the
same place `check_arguments()` and `affine_form()` sit, and the same *declare, never enforce* line
§1 draws everywhere else. A task publishing the schema (§12) should not assert otherwise.

**What this does not catch** is lock-step: whether the sweeps a tree reads are members of one group.
That needs declaration scope, which no field validator has. It was a build-time check in the first
version too — group membership of `AffineSweep.terms` was explicitly excluded from the models — so
nothing moved. §8.3.

### 3.4 There is no `SweepRef`

The first version added one, a `Reference` subclass in `models/reference_types.py`, kept out of
`SymbolRef` and `ValueRef` on purpose: union membership was how rank was recorded, so the rank
distinction *had* to be a type. With rank read off the tree instead, the reference type carries
nothing — `SweepExpr.sweep` is an `IdentifierStr`, `SweepDecl.name` is an `IdentifierStr`, and the
keys of `ProgramArguments.sweeps` are `IdentifierStr`s. There is no union in which a sweep name must
be told apart from anything else, and so no tag to add and no `SweepName` carve-out to write.

`models/reference_types.py` is therefore **untouched by this plan**, and the task that changed it
is gone (§17).

> The counter-argument, recorded rather than taken: a `SweepRef` would give consumers a typed handle
> and would make `sweep()` read like `var()` and `ext()` in the builder. It would also be a public
> type whose only wire appearance is as a bare string inside one field. `SweepExpr` is that handle —
> it is a model, it is in the schema, and `isinstance(node, SweepExpr)` is the test a consumer
> actually writes. §9 Q24.

---

## 4. The models

New module `models/sweeps.py`. It imports `basic_types`, `data_ops` and `expressions`, and nothing
imports it back except `sequence.py` — a leaf, with no deferred-import cycle of its own. It holds
declarations only: the sweep *expression* nodes live in `expressions.py` (§5), which is what keeps
this module a leaf and `control_flow.py` free of any import of it. `SweepOp` joins
`DiscriminableOp` in `sequence.py` rather than `DataOp` in `data_ops.py`, which is what keeps that
true.

### 4.1 `SweepDecl`

The list-valued sibling of `ParameterDecl`: same provenance, same lexical scoping, carrying `name`,
`dtype`, `shape`, `unit`, `default` and `limits`. It differs in being a list rather than a value,
and in counting as one level of nesting. `shape` pins an accepted length when the author wants one;
left `None`, any length is accepted, which is the point.

Its fields are declared on `SweepSpec` and `SweepDecl` is that plus `op_type` — a split forced by
`SweepGroup`'s wire form, defined together with it in §4.3.

### 4.2 There is no transform model

A derived sweep is an expression. `sweep("detuning") * ext("vg.m11") + ext("vg.o1")` is a
`BinaryExpr` over a `BinaryExpr` over a `SweepExpr` and two `SymbolExpr`s — nodes that already
exist, built by operators that already work, serialized by a serializer that already runs.

```python
type SweepSource = Annotated[Expression, AfterValidator(_require_sweep)]
"""An expression reading at least one sweep. Accepted wherever a sweep may be read."""
```

`SweepSource` survives from the first version by name and by meaning — *a sweep, named or
computed* — but it is now an alias over the expression union rather than a two-member union of its
own. Every site that took it still takes it: `Iteration.items` (§6), `IndexExpr.operand` and
`LenExpr.operand` (§5). A bare `{"sweep": "vg"}` is the identity case and needs no special member,
because a lone `SweepExpr` **is** an expression reading one sweep.

**A transform has no name and is never assigned.** That is unchanged and still load-bearing. There
is no declaration operation for one, no wire key, no `dtype` to infer, no scoping rule, no
name-collision check, and no cycle check — an expression tree cannot contain itself:

```python
with for_(["p1", "p2"], [
    sweep("detuning") * ext("vg.m11") + ext("vg.o1"),
    sweep("detuning") * ext("vg.m21") + ext("vg.o2"),
]):
    ...
```

`p1` and `p2` are ordinary variables, declared with `var_decl` when a unit is wanted, exactly as
loop variables already are.

Scales and offsets are ordinary operands, so a virtual-gate matrix element is `ext("vg.m11")` and
resolves against live calibration on every invocation. So is a literal, a `var()`, a `min()` of two
of them, or any expression over them — there is no separate "scale" position with its own type,
because there is no separate model to have one.

**Every sweep a single expression reads must be lock-step** — the same sweep, or members of one
`SweepGroup`. That is the elementwise rule: two lists of independent lengths have no elementwise sum
and no elementwise product. It is a build-time check with declaration scope behind it (§8.3), and it
is the *only* restriction on which trees may be sweep-valued. Combining sweeps from different
nesting levels is rejected; §10 says why and what to write instead.

#### What is now writable that was not

| Expression                          | First version                    | Now                              |
| ------------------------------------- | ---------------------------------- | ---------------------------------- |
| `sweep("d") * 2 + 5`                 | `AffineSweep`, folded            | `BinaryExpr` tree                |
| `sweep("d1") - sweep("d2")`          | `AffineSweep`, two terms         | `BinaryExpr` tree                |
| `sweep("i") * sweep("q")`            | `TypeError` — not affine         | `BinaryExpr`, elementwise        |
| `ext("v0") / sweep("d")`             | `TypeError` — not affine         | `BinaryExpr`, elementwise        |
| `abs(sweep("d"))`, `call_expr_("sqrt", …)` | `TypeError` — not affine     | `CallExpr`, elementwise          |
| `sweep("d") % ext("period")`         | no spelling at all               | `BinaryExpr`, elementwise        |

The first two rows lose their compact representation and gain `affine_form()` (§2.2). The last four
gain a spelling. That trade is the revision.

### 4.3 `SweepGroup`

```python
class SweepSpec(LeanModel):
    """The body of a sweep declaration: everything except its being an operation."""

    name: IdentifierStr
    dtype: VariableDTypeType
    shape: tuple[int, ...] | None = None
    unit: str | None = None
    default: SweepValue | None = None
    limits: ValueLimits | None = None


class SweepDecl(SweepSpec, DataOpBase):
    op_type: Literal["sweep_decl"] = "sweep_decl"     # declared first -- see below


class SweepGroup(OpBase):
    """Independent sweeps advanced in lock-step. Occupies one level of nesting."""

    op_type: Literal["sweep_group"] = "sweep_group"

    sweeps: list[SweepSpec] = Field(min_length=2)
```

eq1lab's `TogetherSweep`, flattened onto the declarations. It holds **full specifications, not
names**, because members keep their own `dtype`, `unit` and `limits` — a voltage and a frequency
routinely move together. A group is one object, so it occupies exactly one slot in declaration
order and §7's rule needs no special case.

**Why `SweepSpec` is split out of `SweepDecl`.** `OpBase` lifts every operation to
`{op_type: payload}` unconditionally, so `sweeps: list[SweepDecl]` would repeat `sweep_decl:` on
every member of a group whose container already says they are sweeps. Typing the list as the
non-operation `SweepSpec` removes it. §15 shows both.

This replaces §4.1's single class with a two-class split; `SweepDecl` is `SweepSpec` plus `op_type`
and nothing else, and it is the form used at top level. Two risks for the implementing task:
`op_type` must be **declared first** in `SweepDecl`, because `LeanModel` treats the first
single-valued `Literal` field as the discriminator; and `SweepSpec` cannot inherit `SymbolDeclBase`,
which is itself an `OpBase` descendant, so its three shared fields are restated rather than reused.

A transform is implicitly lock-step with the sweeps it reads, so `SweepGroup` is only for
independently declared sweeps that must advance together.

```python
type SweepOp = Annotated[SweepDecl | SweepGroup, OperationDiscriminator()]
```

### 4.4 Where the arithmetic runs

A derived sweep and an in-loop `assign` compute the same numbers. They are **not** redundant
spellings — they say different things about where the work happens, and both are kept deliberately:

| Spelling                                                        | Transform runs                                | Hardware sees                       |
| ----------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------- |
| `for_(["p1"], [sweep("d") * ext("m11") + ext("o1")])` — a transform in the loop's *items* | before the loop — host generator, or list upload | two lists advanced in lock-step     |
| `assign("p1", var("d") * ext("m11") + ext("o1"))` in the body   | per iteration, on the sequencer               | one list, plus real-time arithmetic |

A primitive transpiler may not support in-loop scalar arithmetic efficiently, or at all.
Materialising the second list is the cost of doing business there, and the declared form is what
lets a generator pay it. Where the hardware *can* compute per iteration, the in-loop form saves the
upload.

The first row's "list upload" now has two cases, which is what `affine_form()` (§2.2) exists to tell
apart: an affine transform of a compact base is three numbers, and everything else is one float per
item. Both are correct; only the cost differs, and only a generator that asks can tell.

---

## 5. Expression nodes

Three new nodes in `models/expressions.py`, plus one walk and two aliases over them. `SweepExpr` is
in §3.1; the other two are modelled on `NotExpr` — a single-valued `Literal` tag field,
`_wire_tag_from_ = "name"`, `_wire_payload_key_ = None`.

```python
class IndexExpr(ExprBase):
    """One item of a sweep, as a scalar."""

    _wire_tag_source_: ClassVar[str] = "index_op"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"
    _wire_payload_key_: ClassVar[str | None] = None

    index_op: Literal["[]"]
    operand: SweepSource
    indices: list[ScalarExpression]


class LenExpr(ExprBase):
    """The number of items in a sweep, as an int."""

    _wire_tag_source_: ClassVar[str] = "len_op"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"
    _wire_payload_key_: ClassVar[str | None] = None

    len_op: Literal["len"]
    operand: SweepSource
```

```yaml
{index_op: {operand: {sweep: vg}, indices: [{symbol: {var: i}}]}}
{len_op: {operand: {sweep: vg}}}
```

**These two are where rank comes back down.** `operand` is `SweepSource`, so it accepts any
sweep-valued tree — `len_(sweep("a") * sweep("b"))` and `(sweep("d") * 2)[0]` both parse — and each
node **produces a scalar**, which is what closes the grammar. `indices` is `ScalarExpression`: an
index is a position, and a sweep of positions would be a gather, which nothing here needs and
nothing downstream could schedule.

The rank walk treats them as the boundary they are:

```python
def sweep_names_in(expression: Expression) -> frozenset[str]:
    ...  # does NOT descend into IndexExpr.operand or LenExpr.operand
```

Without that stop, `play("g", step_pulse(amplitude=sweep("vg")[var("i")]))` — the whole point of
index iteration — would be rejected as rank-1 by the `ValueRef` guard. **This is the one subtlety
in the walk and the one thing a test must pin**: a `LenExpr` or `IndexExpr` is rank-0 *whatever*
its operand reads, exactly as `len()` of a list is an `int`.

`indices` is a list, so `a[i, j]` is representable without a second node. It is `min_length=1` —
`a[]` names no item, and arity is the one structural thing this module checks, as `CallExpr` already
does. Beyond arity the IR validates only depth: no bounds checking, no count checked against a
declaration's `shape`. Same *declare, never enforce* line `ValueLimits` sits on.

`LenExpr` gets its own node rather than joining `ExpressionFunction` on the precedent `CompareExpr`
sets: that split is by **result kind**, and `len` is the one operation returning an `int` from
something that is not a number. Keeping it out also leaves `CallExpr` honest — every remaining
member is a scalar mathematical function, and over a sweep it is that function applied elementwise.

All three register in `_EXPRESSION_TAGS` and gain a `Tag(...)` member in the `Expression` union.
None touches an existing node, so every program serialized today still validates — with one
exception, named here because it is the plan's only breaking change to an existing type:
`ValueRef` becomes `SymbolRef | ScalarExpression`, so a document that put a sweep under an
amplitude is now rejected. No such document can exist, since sweeps are new.

### Every operator, elementwise

There is no allow-list. A node is sweep-valued when an operand is, uniformly, and that includes
`CompareExpr`, `LogicalExpr` and `NotExpr` — `sweep("d") > 0` is a boolean sweep, and the IR
records it without comment.

Curating the list was considered and dropped. A boolean sweep has exactly two sites it can reach:
`Iteration.items`, where iterating a mask is odd but harmless, and `IndexExpr.operand`. It cannot
reach a condition, because `ConditionalBase.var` is a `ValueRef` and the scalar guard already
rejects it. So the allow-list would buy one rejected oddity in exchange for a curated set, a
validator to enforce it, and a rule with no principle behind it — against a plan that says
*declare, never enforce* eight times. §9 Q21.

---

## 6. Iteration

```python
# models/control_flow.py
class Indices(LeanModel):
    """Iterate ``0 .. count-1``."""

    count: int | ValueRef


type IterableSequence = LinSpace | Range | NumpyIterableArray | SweepSource | Indices
```

Two members added, one removed. Both additions are decidable on the wire with no discriminator
change: `SweepSource` is the `Expression` union, whose every member is a sole-key object naming a
node — `sweep`, `binary_op`, `unary_op`, `function`, `index_op` — and none of those keys is
`start`, `count` or an array; `{"count": …}` is likewise distinct from `LinSpace`'s `num` and
`Range`'s `step`.

A bare `{"sweep": "vg"}` needs no member of its own: it is a one-node expression, and the union
already admits every expression. The compact spelling and the general one are the same member.

> **A trap for the implementing task.** `SweepSource` is itself a discriminated union nested inside
> a plain `|` union. It resolves, because the keys do not collide — but a malformed item now reports
> against eleven expression members rather than one `SweepRef`. If the errors are unreadable, the
> fix is a `Discriminator` on `IterableSequence` keyed on "sole key names an expression node",
> reusing `expression_tag_of`; not a narrower `items` type.

`list[str]` is **removed**. Nothing can consume it — `Play.pulse` is `PulseType | PulseRef` and
`Play.channel` is `ChannelTarget`, neither admitting a `VariableRef` — and with §10 ruling out
categorical sweeps it never will. Removing it also deletes the `list[str]` special case in
`IterationBase._validate_vars_vs_items`, which exists only to tell "one iterable of strings" from "a
list of iterables". §9 Q7.

Two loop forms, both wanted:

```python
with for_("v", sweep("vg")):                   # bind each item; "v" is an ordinary var
    play("gate", step_pulse(amplitude=var("v")))

with for_("i", indices(len_(sweep("vg")))):    # bind each position
    play("gate", step_pulse(amplitude=sweep("vg")[var("i")]))

with for_("p", sweep("vg") * ext("gain")):     # inline transform, no declaration
    play("gate", step_pulse(amplitude=var("p")))
```

The second form is what §5's rank stop exists for: `sweep("vg")[var("i")]` sits under an amplitude,
which is a `ValueRef`, and it is legal there precisely because an `IndexExpr` is rank-0.

Element binding reads better and is what is wanted almost always. The position is needed when an
item and its own index appear in one expression, or to reach a fixed item — a reference point taken
from the scan itself, `sweep("vg")[0]`.

`Repetition.count` is *already* `int | ValueRef`, so `repeat(len_(sweep("vg")))` works with nothing
but `LenExpr`. It binds no index, which is why `Indices` exists: it is `repeat` that says where you
are.

The loop variable is a plain `var()`. That is the separation working — everything downstream of the
loop is the IR that exists today, unchanged.

---

## 7. Nesting order

Each sweep takes its position from **exactly one** source, so there is nothing to reconcile and no
check to write:

- A sweep **consumed** by a `for_` takes its position from that loop's nesting. Structural,
  unambiguous. A loop consumes every sweep its `items` trees read — `sweep_names_in()` over each
  item, unioned — so an inline transform consumes its bases exactly as a bare reference does.
- A sweep **no `for_` consumes** is driven by the host — one invocation per item — and takes its
  position from declaration order. Host loops necessarily wrap the whole submission, so these are
  always outer to every in-program loop.

The full order is therefore: unconsumed sweeps in declaration order, then consumed sweeps in `for_`
nesting order.

The one thing to enforce is local: **a sweep may be consumed by at most one `for_`**, or its
position is not well defined. That is a builder-side declaration-tracking check, not a traversal.

Counting dimensions: each `SweepDecl` outside a group contributes one, each `SweepGroup`
contributes one of the length its members share. A transform contributes none — it is not a
declaration, and the lock-step rule (§4.2) guarantees the sweeps it reads already share a level.
Lengths
within a group agree — checkable at build time where the defaults are concrete, otherwise at
invocation.

A zipped `for_` must name members of one group, or a base together with sweeps derived from it.

---

## 8. Builder

New module `builder/_sweeps.py`. It does not import `core.py`, matching the one-way rule
`_state.py`, `_factories.py` and `_expressions.py` already establish.

It is a **small** module. The arithmetic is `_expressions.py`'s, which already implements every
operator this feature needs; what is left is one constructor, one accessor, two declaration
functions and three checks.

### 8.1 `sweep()` returns an `Expr`

```python
def sweep(name: str) -> Expr:
    """Reference a declared sweep, as an expression."""
    return Expr(SweepExpr(sweep=name))
```

That is the whole entry point. There is **no `Sweep` wrapper class** — the first version needed one
to hold `terms` and an `offset` and to fold operators into them; with the transform being an
ordinary tree, `Expr` already is that class. `sweep("d") * ext("m11") + ext("o1")` runs `Expr.__mul__`
and `Expr.__add__`, unmodified, and produces the tree §15 shows.

Consequences worth stating, because each deletes something the first version specified:

| Gone                                     | Because                                                          |
| ------------------------------------------ | ------------------------------------------------------------------ |
| The `Sweep` class                        | `Expr` is it                                                     |
| The §8.2 fold table (nine rows)          | `Expr`'s operators already do this, for every operand kind       |
| Term canonicalisation                    | nothing to canonicalise; `sweep("a") + sweep("a")` is a tree     |
| `unwrap()` returning a bare ref or an `AffineSweep` | `Expr.unwrap()` returns an `Expression`, always      |
| The six `TypeError`-by-absent-method cases | every one of them is now legal (§4.2)                          |

### 8.2 Indexing and `len_`

`Expr.__getitem__` is added and returns an `Expr` wrapping an `IndexExpr`; a tuple index becomes
multiple `indices`. It is bound on `Expr` rather than on a sweep-specific type, so the builder
checks the operand itself: **indexing an expression that reads no sweep raises `TypeError` at that
line**, rather than a `ValidationError` from `IndexExpr` two frames later. `sweep_names_in()` is
already there to ask.

`len_(x)` is a free function returning an `Expr` wrapping a `LenExpr`, checked the same way.

`__len__` is **not** bound, and Q4's reasoning is untouched by the revision: `len(x)` runs
`__index__` on the result and rejects anything that is not a non-negative `int`, so an expression
tree cannot survive it, and a sweep supplied per invocation usually has no concrete length to return
instead. `len_(s)` is the whole story.

### 8.3 Declarations and the three checks

```python
sweep_decl(name, dtype, *, shape=None, unit=None, default=None, limits=None)
sweep_group()                                       # context manager, matching sub_sequence()
```

Two declaration functions, not three: a transform is anonymous (§4.2), so there is nothing to
declare it with. It is written where it is read.

Declaration tracking in `_state.py` gains sweeps alongside variables and externals, backing three
build-time checks. All three are local; none is a traversal:

| Check                        | Rule                                                                                 |
| ------------------------------ | -------------------------------------------------------------------------------------- |
| **undeclared sweep**         | `sweep("x")` with no `sweep_decl` in scope, wherever in a tree it appears            |
| **at most one consuming `for_`** | a sweep read by two loops' `items` has no well-defined position (§7); the second raises, naming the first |
| **lock-step**                | every sweep a single expression reads is the same sweep or a member of one `SweepGroup` (§4.2) |

The lock-step check is the one that changed shape: it reads `sweep_names_in(tree)` instead of
`AffineSweep.terms.keys()`. It did not change *place* — group membership needed declaration scope
in the first version too, and was explicitly kept out of the models there. A cross-level combination
raises naming both sweeps, and the message points at §10's in-body alternative.

There is still no cycle check. An expression tree is finite and acyclic by construction, and a
transform has no name for another to reference.

`for_` accepts an `Expr` and calls `unwrap()`. Its `items` hint widens to `IterableSequence`, and
`builder/experimental/schedule.py` mirrors the same signature.

---

## 9. Decisions closed

| #   | Question                                                       | Decision                                                                                                                                        |
| ----- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q1  | Are sweeps read with `var()` or their own spelling?             | **Their own leaf node, `SweepExpr`, spelled `sweep("vg")`.** Rejected: `var()`, which makes `{"symbol": {"var": "vg"}}` mean a sweep or a scalar depending on a *sibling declaration* pydantic cannot see, so the rank of a tree could not be computed from the tree. With a distinct leaf it can be, by a bounded local walk. §3. |
| Q2  | General arithmetic over sweeps?                                 | **Yes — the ordinary expression grammar, elementwise, with every sweep in one expression lock-step.** `+ - * / %`, unary `-`, and every `CallExpr` function. This closes #3's deferred "element-wise operations on array variables": the answer is *the same operations as on scalars, applied per item*. **Revised 2026-08-26** from *affine only*; §17. |
| Q2a | Arithmetic **between** two sweeps?                              | **Yes, all of it, within one sweep group** (or a base and sweeps derived from it). Products and quotients included — they are elementwise like everything else; they merely do not survive `affine_form()`. Cross-level combination is still rejected; §10. **Revised 2026-08-26** from *`+` and `-` only*. |
| Q3  | Is `len` a `CallExpr` function or its own node?                 | **Own node, `LenExpr`,** on the precedent that split `CompareExpr` out — by result kind. It is the one operation returning an `int` from a non-number, and keeping it out leaves `CallExpr` as scalar functions of scalars. |
| Q4  | Bind `Expr.__len__` / `Sweep.__len__`?                         | **No.** `len()` runs `__index__` on the return and rejects non-`int`; an expression tree cannot survive it, and there is usually no concrete length. `len_()` only. `__getitem__` **is** bound — it may return anything. |
| Q5  | Categorical sweeps — channels, pulse references, strings?       | **No.** §10 carries the scheduling argument. Consequence: `SweepValue` is numeric, and `VariableDTypeType` needs no `"str"` member.            |
| Q6  | What if `for_` nesting disagrees with declaration order?         | **It cannot.** Each sweep takes its position from exactly one source — the loop that consumes it, or declaration order if none does. §7. The only rule left is local: at most one consuming `for_` per sweep. |
| Q7  | Keep `list[str]` in `IterableSequence`?                         | **Remove.** Nothing can consume it today and Q5 guarantees nothing will. Removal also deletes its special case in `_validate_vars_vs_items`. Breaking schema change, so it rides with this plan rather than alone. |
| Q8  | Can a transform read another transform?                         | **Yes, and it costs nothing.** A transform is a subtree; nesting one inside another is what an expression tree *is*. There is no recursion to guard and no cycle to check, because a transform has no name for another to reference. **Revised 2026-08-26** — the first version answered "it never needs to", which was true only because the flat `terms` mapping made it impossible. |
| Q9  | An explicit `placement` field — host or program?                | **No.** It is structural: a `for_` consumes the sweep, or nothing does. A field would be a second source of truth for something already unambiguous. |
| Q10 | Does `SweepGroup` hold declarations or names?                | **Full specifications** — `list[SweepSpec]`, the non-operation half of `SweepDecl`. Members need their own `dtype`, `unit` and `limits`; eq1lab's `TogetherSweep` routinely moves a voltage with a frequency. Rejected: `sweep_decl(["i", "q"], …)`, which forces one dtype on the group; and `list[SweepDecl]`, which repeats `sweep_decl:` on every member. §4.3, §15. |
| Q14 | How much does the wire form matter?                             | **It is a design target, and the revision costs it something.** A transform is now an operator tree — four lines of YAML where `terms: {d: 2}` was one. Accepted, because it is the *same* tree an author already reads under any pulse amplitude in the file: one grammar spelled one way everywhere beats two spellings of which the short one covers only the affine half. §15 stays normative and tested literally. Rejected: a leaner `{len: vg}` spelling that would need a new `NestedWireModel` mode and put `LenExpr` out of step with `NotExpr`. |
| Q15 | How is an accidental mV-for-V substitution caught?              | **A supplied sweep may state its unit, spelled as the unit-keyed wrapper `{mV: {start: …}}` that `SymbolValue` already uses for scalars; a checker compares it to the declaration as a string.** No conversion, so #6's "declare, never enforce" line holds — string inequality is not unit arithmetic. A supplied value with no unit key is taken to be in the declared unit. §16. |
| Q16 | Who verifies that an invocation matches the declared nesting?    | **A utility, not the models.** The *shape* of an invocation is a model (Q18); whether a given one fits a given program is not something a field validator can see. §16 specifies `check_arguments()` in `utilities/`: names, units, group membership and lengths, reported together. It is advisory — nothing calls it automatically. |
| Q17 | Where do a sweep's values come from?                             | **Always the caller.** No `ExternalDecl`-style resolve-by-name provenance, no provenance field. A sweep is supplied at invocation or falls back to its `default`, and that is the whole story — which is what makes §0's "invoke it with different ranges" the only way it ever varies. |
| Q18 | Is the invocation payload part of the IR?                        | **Yes.** `ProgramArguments` is a model in `models/arguments.py`, published in the schema, so a stored experiment *and* the arguments it was run with are both validated artifacts. The **checker stays a utility** (Q16): the payload is data the IR owns, but matching one against a program is analysis. |
| Q19 | Is the argument payload flat or nested?                          | **Nested** — `sweeps` is a list of levels, outermost first, and a level with several entries is a group. The caller's belief about the structure is then visible in the document's shape rather than needing a separate block. It is an *assertion*, checked against the program (§16 check 3), not a second source of truth: §7 still says position comes from the program alone. Rejected: a flat name → value mapping, which cannot state nesting at all and so cannot catch a program that has drifted since the invocation was written. |
| Q11 | Element iteration, index iteration, or both?                    | **Both.** Element binding is the common case; the index is needed when an item and its position meet in one expression, or to reach a fixed item. |
| Q12 | What are the public names?                                      | **`sweep()`** references, **`sweep_decl()`** declares a supplied sweep, **`sweep_group()`** declares a lock-step group — one `sweep*` prefix, and the wire keys match. A transform has no name at all (Q13). Rejected: `axis()` (contradicts Q5's "items may repeat and need not be ordered"); `derived_sweep()` and `parallel_sweep()` (both broke the prefix, and "parallel" already means simultaneous-in-time here); `together_sweep()` and `sweep_ref()` (near-misses). |
| Q13 | Is a transform named and declared?                              | **No — it is an anonymous value.** A sweep-valued expression goes wherever a sweep goes (`SweepSource`), so it is written where it is read and the loop variable already supplies the name. This removes an operation, a wire key, a `dtype` that could not be inferred, a scoping rule, a name-collision check and a cycle check. There is no assignment anywhere in this design. §4.2. |
| Q20 | How is rank enforced, now that a tree can be rank-1?            | **Two annotated aliases over `Expression`, each running a bounded walk.** `ScalarExpression` rejects a tree reading any sweep and `SweepSource` requires one. Two field edits apply the first: `ValueRef`, which nearly every value site goes through, and `ExternalParamValue`, which does not and so needs its own. Rejected: a whole-program `validate_ranks()` pass — the thing Q1 rejected `var()` for. This is not that: the walk is local to one field's value, bounded by `MAX_EXPRESSION_DEPTH`, and runs during validation like any other constraint. The cost, admitted in §3.3, is that a walk publishes no JSON Schema, so the rule is invisible to a consumer validating against the spec alone. §3.2. |
| Q21 | Which operators may take a sweep?                               | **All of them, uniformly.** A node is rank-1 exactly when an operand is. That admits boolean sweeps (`sweep("d") > 0`), which reach only `Iteration.items` and `IndexExpr.operand` and are harmless at both — a condition is a `ValueRef` and already rejects them. Rejected: a curated arithmetic-only allow-list, which needs a validator and a rule with no principle behind it. §5. |
| Q22 | Where did compact transport go?                                 | **Into `affine_form()`, a recogniser in `utilities/`.** It returns `terms` and an `offset` for the affine subset and `None` otherwise — the same fields the deleted model carried, produced by analysis rather than enforced by a type. Advisory, like `check_arguments()`; nothing calls it automatically. §2.2. |
| Q23 | Is lock-step checked by the models or the builder?              | **The builder, unchanged from the first version.** It needs declaration scope, which no field validator has. The first version could not check `AffineSweep.terms` in the model either, and said so; the revision changed the input to the check — a tree walk instead of a key list — not its home. §8.3. |
| Q24 | Is there a `SweepRef` reference type?                           | **No.** It existed to carry rank through union membership; with rank read off the tree, a sweep name is an `IdentifierStr` in the two places it appears and there is no union it must be told apart in. `models/reference_types.py` is untouched by this plan. Counter-argument recorded in §3.4: a consumer wanting a typed handle has `SweepExpr`, which is a model and is in the schema. |

### Deliberately not decided here

- **Whether `ProgramArguments` should also carry resolved externals.** A reproducible record of an
  invocation arguably wants the calibration values that were resolved for it, not just the arguments
  the caller passed. That is a result-side concern and a different lifetime — the caller supplies
  arguments *before* the run, externals are resolved *during* it. Left out; adding a third mapping
  later breaks nothing.
- **Slices.** `IndexExpr.indices` being a list already covers `a[i, j]`. A slice would keep the
  result a sweep and needs its own node and rule. Nothing in the purpose needs one, and
  `__getitem__` can grow to accept a `slice` later without changing what exists.
- **A host-side driver.** Reading the declarations back out to iterate unconsumed sweeps is
  eq1lab's job. eq1_pulse describes what to run.

---

## 10. Not in scope, and why

### Categorical sweeps over references

`OpSequence` schedules by earliest-possible-start **per channel**, so the first thing a consumer
does is partition operations by channel. Make the channel a loop variable and that partition becomes
data-dependent — there is no timeline to build until the loop is unrolled. Pulse references fail one
step later: the channel is known, but the pulse's duration is what every subsequent operation on
that channel is scheduled against, so each iteration is a different length and the body stops being
a repeatable block. On a backend, a loop should compile to a hardware loop, not a rolled-out program.

Sweeping `amplitude`, `frequency`, `phase` or `duration` is safe by contrast, because the body's
*shape* is invariant — the same operations on the same channels, one scalar differing.

> **The distinction that looks similar and is not.** `ChannelTarget` is already
> `ChannelRef | ExternalRef`, so `play({"ext": "q0.drive"}, …)` is legal today: a channel resolved
> from calibration **per invocation**, fixed before scheduling ever runs. Late binding per
> invocation is free. Late binding per iteration is what breaks.

### Sweep-valued expressions — adopted, 2026-08-26

This section previously read *"letting `*` and `+` build ordinary `BinaryExpr` trees over a sweep
symbol was proposed and rejected"*. It is now the design. The proposal that was rejected — and stays
rejected — is the *`var()`-spelled* one: a sweep read as `{"symbol": {"var": "vg"}}`, whose rank
depends on a sibling declaration no validator can see. What is adopted is the same arithmetic over a
**distinct leaf**, `SweepExpr`, which makes the rank of a tree computable from the tree. §3, §9 Q1.

### Combining sweeps from different nesting levels

`sweep("d1") + sweep("d2")` where `d1` and `d2` are *nested* rather than grouped is rejected — as
is any other operator between them. It is not elementwise: the two have independent lengths, and the
natural reading is an outer product, so the result is two-dimensional. That would make the
expression rank-2, break the one-sweep-one-level rule in §7, and require a broadcasting story the IR
does not have. Widening the arithmetic did **not** widen this: the lock-step rule is what makes
every permitted operation mean one unambiguous thing.

This matters because a full virtual-gate matrix over a 2-D charge-stability scan wants exactly that
— `P1 = m11*d1 + m12*d2`. Write it inside the body instead, on the loop variables, where it is
ordinary rank-0 arithmetic and needs nothing new:

```python
sweep_decl("d1", "float", unit="mV")
sweep_decl("d2", "float", unit="mV")
var_decl("p1", "float", unit="mV")

with for_("x1", sweep("d1")):
    with for_("x2", sweep("d2")):
        assign("p1", var("x1") * ext("vg.m11") + var("x2") * ext("vg.m12") + ext("vg.o1"))
        play("gate_1", step_pulse(amplitude=var("p1")))
```

The cost is §4.4's: the transform runs per iteration on the sequencer rather than being precomputed.
Where that is unaffordable, flatten the scan to a single sweep group and use the shorthand.

---

## 11. Tests

New: `tests/eq1lab_pulse/models/test_sweeps.py`, `tests/eq1lab_pulse/test_builder_sweeps.py`,
`tests/eq1lab_pulse/test_affine_form.py`. Extended: `test_expressions.py`, `test_control_flow.py`,
`test_sequence.py`, `test_schema_symmetry.py`. `test_reference_types.py` is **not** extended —
nothing in `reference_types.py` changes.

Load-bearing cases, beyond per-model round-trips:

- **The rank walk, in both directions.** A sweep at a `ValueRef` field is rejected; a sweep *nested
  four levels down* under one is rejected by the same error; a scalar tree at a `SweepSource` field
  is rejected. These three are §3.3, and nothing else tests them.
- **`IndexExpr` and `LenExpr` are rank-0 whatever their operand reads.** `sweep("vg")[var("i")]`
  under a `Play.amplitude` **validates**. This is the walk's one stop condition (§5) and the case
  most likely to be written wrong, because the naive walk rejects it and every other test still
  passes.
- **A second rebuild sweep.** `IterableSequence` and `Expression` both gain members. A missed
  `model_rebuild()` degrades a union member to `dict` silently. Follow
  `test_valueref_rebuild_sweep.py`'s shape: validate from a plain dict and assert the field is the
  model, not a dict standing in for one.
- **Every operator over a sweep builds and round-trips** — `+ - * / %`, unary `-`, `abs`,
  `call_expr_("sqrt", …)`, and a comparison. The six that used to raise `TypeError` are the point;
  assert they now produce trees, so a reintroduced restriction is caught.
- **A cross-level combination raises at build time**, naming both sweeps — §10. Its mirror also
  passes: the same two sweeps inside one `sweep_group()` combine fine, under `*` as well as `+`.
- **`affine_form()` recognises and declines.** `sweep("d") * 2 + 5` returns terms and an offset;
  `sweep("a") * sweep("b")` returns `None`; `sweep("a") + sweep("a")` returns one term of scale `2`
  — the canonicalisation the builder used to do, now done by the recogniser, and the reason it is
  tested here rather than dropped.
- **`list[str]` iteration now fails**, and the `_validate_vars_vs_items` zipped/broadcast cases
  still pass without it.
- **An `Expression` containing an `IndexExpr` round-trips through JSON**, not just `model_dump`.
- **The §15 wire forms, asserted literally.** §15 is normative and the only thing that can hold it
  true is a test comparing `model_dump()` against the exact dict — `{sweep: vg}` flat, no
  `sweep_decl:` key inside `sweep_group`, and elided defaults absent. Include the complete stored
  experiment from §15 as one round-trip case.

---

## 12. Schema and docs

`utilities/openapi_generator.py` — `"sweeps"` and `"arguments"` into `model_modules`, and a tag
entry for each. `SweepSpec` and `ProgramArguments` are `LeanModel`s that appear on the wire, not
base classes, so `excluded_base_classes` is untouched. `SweepExpr`, `IndexExpr` and `LenExpr` ride
in on `expressions`, which is already listed.

`docs/source/user_guide/builder_guide.rst` — a "Sweeps" section: what a sweep is and is not, why
`sweep()` is not `var()`, the three operations, that arithmetic over a sweep is the arithmetic
already documented one section up, the lock-step rule, and the §4.4 table on where the arithmetic
runs. `affine_form()` gets a paragraph beside `check_arguments()`, since a consumer that never
learns it exists pays for every point of every scan.

`examples/swept_gate_scan.py` — a program declaring one supplied sweep and one derived from it,
dumped as JSON twice with different ranges to show the point of §0. `tests/test_examples.py`
discovers `examples/**/*.py` by `rglob`, so there is no list to update.

§16's `check_arguments()` gets a short guide subsection of its own — it is advisory and nothing
calls it, so a user who does not know it exists never benefits from it. The mV-for-V case is the
example to lead with.

---

## 13. Worked examples

```python
# A -- gate scan, values supplied per invocation
with build_sequence() as seq:
    sweep_decl("vg", "float", unit="mV")            # no default: always supplied
    extern_decl("gate.gain", "float")
    var_decl("iq", "complex", unit="mV")

    with for_("v", sweep("vg")):
        play("gate", step_pulse(amplitude=var("v") * ext("gate.gain")))
        record("readout", "iq", duration="1us", integration=full_integration())
        store("scan", "iq", mode="average")

# invoked with {"vg": {"start": -400, "stop": 400, "num": 20001}}  -- three numbers
# then again with {"vg": {"start": -50, "stop": 50, "num": 201}}   -- same program
```

```python
# B -- Rabi with a default, indexed by position
with build_sequence() as seq:
    extern_decl("q0.f01", "float", unit="GHz")
    sweep_decl("t_pi", "float", unit="ns", default=LinSpace(start=0, stop=200, num=101))

    set_frequency("q0_drive", ext("q0.f01"))

    with for_("i", indices(len_(sweep("t_pi")))):
        play("q0_drive", square_pulse(duration=sweep("t_pi")[var("i")], amplitude="100mV"))
        record("q0_readout", "iq", duration="1us", integration=full_integration())
        store("rabi", "iq", mode="average")
```

```python
# C -- virtual gates: one supplied sweep, two transforms of it
sweep_decl("detuning", "float", unit="mV")

var_decl("p1", "float", unit="mV")
var_decl("p2", "float", unit="mV")

with for_(["p1", "p2"], [
    sweep("detuning") * ext("vg.m11") + ext("vg.o1"),
    sweep("detuning") * ext("vg.m21") + ext("vg.o2"),
]):
    play("gate_1", step_pulse(amplitude=var("p1")))
    play("gate_2", step_pulse(amplitude=var("p2")))

# One dimension: detuning. The transforms add none and need no SweepGroup -- reading one
# base already makes them lock-step. Each is an ordinary BinaryExpr tree, and each is
# affine, so a generator calling affine_form() still uploads three numbers per gate.
# The only names are p1 and p2, and those are the loop variables.
```

```python
# D -- independent sweeps in lock-step: what SweepGroup is actually for
with sweep_group():
    sweep_decl("i_amp", "float", unit="mV")
    sweep_decl("drive_freq", "float", unit="MHz")      # different unit, same group

with for_(["a", "f"], [sweep("i_amp"), sweep("drive_freq")]):
    set_frequency("q0_drive", var("f"))
    play("q0_drive", square_pulse(duration="40ns", amplitude=var("a")))
```

```python
# E -- outer and inner: who drives what is structural
sweep_decl("b_field", "float", unit="mT")             # nothing loops over it -> host drives it
sweep_decl("tau", "float", unit="ns", default=LinSpace(start=0, stop=5000, num=51))

with for_("t", sweep("tau")):                         # in-program
    ...

# Declared first, so b_field is outer. Result shape: (n_b, 51)
```

```python
# F -- repeating items: a list, not an axis
sweep_decl("amp_seq", "float", unit="mV", default=[100, 0, 100, 50, 100, 25])

with for_("a", sweep("amp_seq")):
    play("q0_drive", square_pulse(duration="40ns", amplitude=var("a")))
```

```python
# G -- sum and difference of lock-step sweeps, computed before the loop
with sweep_group():
    sweep_decl("d1", "float", unit="mV")
    sweep_decl("d2", "float", unit="mV")

var_decl("c", "float", unit="mV")
var_decl("e", "float", unit="mV")

with for_(["c", "e"], [
    sweep("d1") + sweep("d2"),
    sweep("d1") - sweep("d2"),
]):
    play("gate_c", step_pulse(amplitude=var("c")))
    play("gate_e", step_pulse(amplitude=var("e")))

# Still one dimension -- d1 and d2 are one sweep group, and both transforms ride on
# it. The two sums are computed before the loop, not on the sequencer (§4.4).
```

```python
# H -- what the revision added: a product of two lock-step sweeps
with sweep_group():
    sweep_decl("amp", "float", unit="mV")
    sweep_decl("scale", "float")                       # dimensionless correction, same length

var_decl("a", "float", unit="mV")

with for_("a", sweep("amp") * sweep("scale")):
    play("q0_drive", square_pulse(duration="40ns", amplitude=var("a")))

# Elementwise, one dimension, and not affine -- affine_form() returns None and a
# generator materialises the list. Under the first version this had no spelling at all:
# Sweep.__mul__ refused a Sweep operand, and the alternative was to move the product
# into the body as scalar arithmetic on two loop variables.
```

---

## 14. Mapping from eq1lab and qcodes

| eq1lab / qcodes                                  | eq1_pulse                                                   |
| -------------------------------------------------- | ------------------------------------------------------------- |
| `LinSweep(p, start, stop, num=N)`                | `{"start": …, "stop": …, "num": N}` supplied for `p`        |
| `LinSweep(p, start, stop, step=s)`               | `{"start": …, "stop": …, "step": s}`                        |
| `ArraySweep(p, arr)`                             | a bare array                                                |
| `TogetherSweep(a, b)`                            | `SweepGroup` plus a zipped `for_`                        |
| `SweepPlaceholder(num_points=N)`                 | `sweep_decl(name, shape=(N,))`, unconsumed                  |
| `ParameterExpr("VCM + ST1_sweep")`               | an inline `sweep("VCM") + …` — an expression, and unnamed |
| `ParameterExpr(..., tag="batch")`                | — batch evaluation is a consumer concern                    |
| argument order of `nd_sweep(a, b, c)`            | declaration order (§7)                                      |
| `do_nd_inner_loop(...)`                          | a `for_` consuming the sweep                                |
| `nd_sweep(...)` host loop                        | a sweep no `for_` consumes                                  |
| `normalize_sweep_argument`'s nine input forms    | — one `SweepValue` union, no qcodes objects                 |

`ParameterExpr`'s string, its globals mapping, its `NameError` suggestion machinery and its
`validate(*parameters)` pass all collapse into ordinary symbol scoping plus the lock-step rule. The
2026-08-26 revision narrows the gap further: `ParameterExpr` accepts arbitrary arithmetic over
parameters, and so, now, does this.
An unresolvable name in a derived sweep is the same build-time error as an unresolvable name
anywhere else.

---

## 15. Wire form reference

**Normative.** A stored experiment is a YAML file someone opens to see what it sweeps, so these are
design targets, not consequences. Where a form below disagrees with a model sketch above, this
section wins.

Three rules produce all of it, and none is new machinery:

1. **A sweep is `{sweep: name}`, everywhere.** One spelling, in a union or out of one, because a
   sweep is an expression node rather than a reference with two positional forms. This is *simpler*
   than `VariableRef`, which is bare in a `VarName` field and tagged in a union; there is no
   equivalent rule to learn here and no carve-out to write.
2. **A transform is the tree that computes it.** The same `binary_op` / `unary_op` / `function`
   nodes that appear under every pulse amplitude in the file, with `{sweep: …}` where a
   `{symbol: …}` would otherwise sit. No second grammar, no second spelling.
3. **No repeated key that the container already carries.** `SweepGroup` holds `SweepSpec`, not
   `SweepDecl`, so `sweep_decl:` appears once per group rather than once per member.

### Declarations

```yaml
- sweep_decl: {name: vg, dtype: float, unit: mV}

- sweep_decl:
    name: t_pi
    dtype: float
    unit: ns
    default: {start: 0, stop: 200, num: 101}

- sweep_decl:
    name: amp_seq
    dtype: float
    unit: mV
    default: [100, 0, 100, 50, 100, 25]

- sweep_group:
    sweeps:
      - {name: i_amp, dtype: float, unit: mV}
      - {name: drive_freq, dtype: float, unit: MHz}
```

`LeanModel` elides defaults, so `shape`, `limits` and an absent `default` never appear.

### Transforms

A transform is anonymous and appears inline, never as its own operation — and it is an expression:

```yaml
# detuning * vg.m11 + vg.o1, as one of a loop's items
binary_op:
  op: +
  lhs:
    binary_op:
      op: "*"
      lhs: {sweep: detuning}
      rhs: {symbol: {ext: vg.m11}}
  rhs: {symbol: {ext: vg.o1}}

# d1 - d2, over a sweep group
binary_op: {op: "-", lhs: {sweep: d1}, rhs: {sweep: d2}}

# i_amp * scale -- elementwise, not affine, and unremarkable on the wire
binary_op: {op: "*", lhs: {sweep: i_amp}, rhs: {sweep: scale}}
```

**This is longer than the `terms` mapping it replaces, and that is the revision's admitted cost**
(§9 Q14). What it buys is on the third line: the product has a wire form at all, and it is the same
one the sum has. A reader who can read a pulse amplitude can read all three without being told
anything new.

### Loops

```yaml
- for:
    var: v
    items: {sweep: vg}
    body: [...]

- for:
    var: i
    items: {count: {len_op: {operand: {sweep: vg}}}}
    body: [...]

- for:                                        # inline transform, no declaration
    var: p
    items:
      binary_op: {op: "*", lhs: {sweep: vg}, rhs: {symbol: {ext: gate.gain}}}
    body: [...]

- for:                                        # zipped over one sweep group
    var: [a, f]
    items: [{sweep: i_amp}, {sweep: drive_freq}]
    body: [...]
```

`items` admits any expression reading a sweep, and every expression is a sole-key object naming its
node — so the members of `IterableSequence` stay decidable against `start`, `count` and a bare
array with no discriminator change.

### Expressions

```yaml
{len_op: {operand: {sweep: vg}}}
{index_op: {operand: {sweep: vg}, indices: [{symbol: {var: i}}]}}

# the same two over an anonymous transform -- operand is SweepSource, so any tree fits
{len_op: {operand: {binary_op: {op: "*", lhs: {sweep: vg}, rhs: {value: 2}}}}}

# vg[i] * gate.gain, as a Play amplitude -- rank-0, because index_op is
amplitude:
  binary_op:
    op: "*"
    lhs: {index_op: {operand: {sweep: vg}, indices: [{symbol: {var: i}}]}}
    rhs: {symbol: {ext: gate.gain}}
```

The last block is the one to read twice. `{sweep: vg}` appears under a `Play.amplitude`, which is a
`ValueRef` and rejects sweeps — and it is legal, because the sweep is inside an `index_op`, and an
`index_op` is a scalar however deep the sweep sits. §5.

> **Noted, not taken.** `{len: vg}` reads better than `{len_op: {operand: {sweep: vg}}}`, and
> likewise for indexing. Getting it needs a `NestedWireModel` mode where a sole payload field is
> spelled bare, which nothing else in the tree would use, and it would put `LenExpr` out of step
> with `NotExpr` — the node it is otherwise a copy of. Consistency with the eight existing
> expression nodes is worth more than the characters. Revisit only if a second node wants the same
> mode.

### A complete stored experiment

```yaml
- sweep_decl: {name: detuning, dtype: float, unit: mV}
- var_decl: {name: p1, dtype: float, unit: mV}
- var_decl: {name: p2, dtype: float, unit: mV}
- var_decl: {name: iq, dtype: complex, unit: mV}
- for:
    var: [p1, p2]
    items:
      - binary_op:
          op: +
          lhs: {binary_op: {op: "*", lhs: {sweep: detuning}, rhs: {symbol: {ext: vg.m11}}}}
          rhs: {symbol: {ext: vg.o1}}
      - binary_op:
          op: +
          lhs: {binary_op: {op: "*", lhs: {sweep: detuning}, rhs: {symbol: {ext: vg.m21}}}}
          rhs: {symbol: {ext: vg.o2}}
    body:
      - play: {channel: gate_1, pulse: {pulse_type: step, amplitude: {var: p1}}}
      - play: {channel: gate_2, pulse: {pulse_type: step, amplitude: {var: p2}}}
      - record: {channel: readout, var: iq, duration: 1us, integration: {integration_type: full}}
      - store: {key: csd, source: iq, mode: average}
```

The virtual-gate matrix sits in the loop that uses it, not in two declarations above it. One sweep
is declared; everything else is a variable or a transform of that sweep.

Everything that varies between invocations is the one line supplying `detuning`. That is §0, on the
wire.

---

## 16. Checking an invocation

§0 makes a promise the IR cannot keep on its own: a stored program invoked with *the wrong* ranges
is still a valid program. Two failures matter enough to catch, and neither is visible to a model
validator, because an invocation is not part of the document being validated.

| Failure                                                                       | Why it is silent otherwise                                                       |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| A sweep declared in **mV** supplied in **V**, or vice versa                   | Both are numbers. The program runs, 1000× off, and looks fine.                   |
| Arguments that do not match the **declared nesting structure**                | A missing sweep, a group supplied with unequal lengths, a name that is not swept. |

### `ProgramArguments` — a model, in `models/arguments.py`

An invocation is a first-class artifact, not a loose dict a utility happens to understand (§9 Q18).
A stored experiment and the arguments it was run with are both validated and both in the published
schema.

```python
class QualifiedSweepValue(RootModel[dict[UnitKey, SweepValue]]):
    """A sweep value tagged with the unit it is expressed in: ``{"mV": {...}}``.

    Exactly one key, and it must be a known unit.
    """


type SweepArgument = SweepValue | QualifiedSweepValue


type SweepLevel = dict[IdentifierStr, SweepArgument]
"""One level of nesting. More than one entry means those sweeps are a group."""


class ProgramArguments(LeanModel):
    """What a caller supplies to invoke a stored program."""

    parameters: dict[IdentifierStr, SymbolValue] = {}
    sweeps: list[SweepLevel] = []
```

```yaml
parameters:
  n_shots: 1000

sweeps:
  - detuning:   {mV:  {start: -20,  stop: 20,   num: 81}}     # level 0 -- one sweep
  - i_amp:      {mV:  {start: -1,   stop: 1,    num: 20}}     # level 1 -- a group,
    drive_freq: {MHz: {start: 4900, stop: 5100, num: 20}}     #            two entries
  - vg: {start: -400, stop: 400, num: 20001}                  # level 2 -- unit omitted
```

**`sweeps` is a list of levels, outermost first.** A level with one entry is a single sweep; a level
with several *is* a group. The nesting the caller believes in is therefore visible in the shape of
the document — no separate structure block, no names repeated in a second place, and the group is
obvious to a reader because its members sit in one block.

**This does not make the payload a second source of truth.** §7 still holds: a sweep's position
comes from the program, and only from the program. What the payload carries is an **assertion**
about that position, which `check_arguments()` compares against the program's actual structure.
Disagreement is a finding, not a choice to resolve — and catching it is the point. A stored
invocation whose program has since had two `sweep_decl`s reordered, or one moved into a group, now
fails loudly instead of running something different under the same name.

The unit-keyed wrapper is the same spelling `SymbolValue` already uses for a scalar quantity
(`{"mV": 100}`), lifted one rank. It costs no new convention, reads correctly in YAML, and
`dimension_tag_of_unit_mapping` in `basic_types` already recognises the key.

**Why `parameters` and `sweeps` stay apart:** `{"mV": [1, 2]}` is a `ComplexVoltage` under
`SymbolValue` *and* a two-item array sweep under `SweepArgument`. One combined field could not tell
them apart without consulting the declaration, which is exactly what a standalone model cannot do.
Separating them makes "supplied a sweep where a parameter was declared" a **validation** error
rather than a checker finding.

`ExternalDecl` values are deliberately absent: they are resolved by the framework, not supplied by
the caller. See §9's remaining open note.

### `check_arguments()`

A utility in `utilities/`, **not** in `models/`, and **advisory** — nothing calls it automatically.
The payload is data the IR owns; matching one against a particular program is analysis, and no field
validator can see both. It walks a program's declarations and reports every problem it finds, rather
than raising on the first:

1. **Name coverage.** Every `SweepDecl` and `ParameterDecl` without a `default` has an argument;
   every argument names something declared. Transforms are anonymous and never appear here at all.
2. **Unit agreement.** Where an argument states a unit, it equals the declaration's `unit` string
   exactly. Where it does not, it is accepted as being in the declared unit. Never converted, never
   rescaled — plan §1, and #6's line.
3. **Nesting agreement.** The supplied levels match the program's structure position by position:
   the same number of levels, in the same order, with the same members in each. §7 gives the
   program's structure — unconsumed sweeps in declaration order, then consumed sweeps in `for_`
   nesting order — and the payload's list is checked against it. A reordered level, a member in the
   wrong level, or a level count mismatch is each a finding naming both what was asserted and what
   the program says.
4. **Group agreement.** Every entry in one level has the same length. A level is a group precisely
   because its members advance on one index, so unequal lengths are the failure it exists to
   prevent.
5. **Shape and limits.** Where `shape` pins a length, the supplied value has it; where `limits` are
   declared, the supplied endpoints are inside them.

Returns a list of findings, each naming the declaration and what is wrong. An empty list means the
arguments fit.

> **Deliberately advisory.** There is no runtime that could enforce this today, and a model
> validator cannot see a program and its arguments at once. A function anyone can call before
> invoking is the useful thing that can be built now — and because `ProgramArguments` is a model,
> what it checks is already well-formed by the time it runs.

---

## 17. The 2026-08-26 revision

The first version of this plan gave sweeps their own arithmetic: a `SweepRef` reference type, an
`AffineSweep` model of `terms` and an `offset`, and a builder `Sweep` class whose operators folded
into it. Everything about it worked. It was also a *second* expression language, sitting beside the
one #3 had just landed, covering a strict subset of what that language does and spelling the subset
differently.

The revision deletes it. **A sweep is an operand of the ordinary expression grammar.**

### What changed

| Area                    | Was                                                        | Is                                                      |
| ------------------------- | ------------------------------------------------------------ | --------------------------------------------------------- |
| Reading a sweep         | `SweepRef`, a `Reference` in `reference_types.py`           | `SweepExpr`, a leaf node in `expressions.py`             |
| A transform             | `AffineSweep(terms, offset)`                                | any `Expression` reading a sweep                        |
| `SweepSource`           | `SweepRef \| AffineSweep`                                   | `Annotated[Expression, AfterValidator(_require_sweep)]` |
| Permitted operations    | `+ -` between lock-step sweeps; `* /` by a scalar only      | `+ - * / %`, unary `-`, every `CallExpr` function        |
| Rank enforcement        | union membership — `SweepRef` kept out of `ValueRef`        | `ValueRef = SymbolRef \| ScalarExpression`, one walk     |
| Builder                 | a `Sweep` class and a nine-row fold table                   | `sweep()` returns an `Expr`; the operators already exist |
| Compact transport       | guaranteed by the model                                     | recognised by `affine_form()` in `utilities/`            |

### What did not change

Everything the plan is actually *for*. §0's purpose, `SweepDecl` and `SweepGroup` (§4.1, §4.3),
nesting order (§7), the two loop forms (§6), `IndexExpr` and `LenExpr` (§5), `ProgramArguments` and
`check_arguments()` (§16), and the lock-step and one-consuming-loop rules — which were build-time
checks before and are build-time checks now.

### Why

| Because                                                                                       | Therefore                                                                       |
| ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Six useful operations had no spelling — `s * s2`, `s / s2`, `k / s`, `abs(s)`, `sqrt(s)`, `s % k` | Authors met a `TypeError` and had to restructure the program to say something ordinary |
| The affine model duplicated arithmetic the IR already had                                     | Two grammars to learn, two to document, two to keep in step as #3 grows          |
| A consumer already walks `Expression`                                                         | It now handles sweeps by learning one leaf, not a parallel model                 |
| Rank was carried by a type that could only type a *leaf*                                      | `amplitude=sweep("vg") * 2` was unrepresentable, so it was also unrejectable; the walk rejects it |

### What it cost

Recorded here rather than buried, because both are real:

1. **A transform's wire form is four lines where it was one** (§9 Q14, §15). Accepted: it is the
   spelling already used everywhere else in the same file.
2. **Compactness is no longer guaranteed by the type** (§2.2, §9 Q22). A generator that wants three
   numbers instead of ten thousand calls `affine_form()`; one that does not, materialises. The
   utility is advisory, so a consumer that never learns it exists pays for every point of every
   scan — which is why §12 gives it a documentation paragraph rather than a footnote.

### For the execution breakdown

[sweeps-tasks.md](sweeps-tasks.md) is revised alongside this and the tasks are renumbered; its
*Closed since drafting* section carries the old-to-new mapping. In short: the `SweepRef` task and
the affine-fold task are both gone, the expression task becomes the load-bearing one and is
renumbered T1, the two builder tasks collapse into one, and a new task builds `affine_form()`. One
task fewer and one file fewer in `models/`, against one new file in `utilities/`.
