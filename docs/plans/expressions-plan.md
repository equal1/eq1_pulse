# Plan: expression support

**Issue:** [#3 — Feature: Add Expression Support to eq1_pulse](https://github.com/equal1/eq1_pulse/issues/3)
**Status:** accepted — all open questions closed (§8); see
[expressions-tasks.md](expressions-tasks.md) for the execution breakdown
**Date:** 2026-08-21, revised 2026-08-22 against the landed type-system work (#10)
**Predecessors, both landed:**

- [#6 — external constants and parameter variables](https://github.com/equal1/eq1_pulse/issues/6).
  This plan widens the `SymbolRef` alias introduced there; without it, every widening in §3 has to be
  done twice. #6's plan is not in the tree — a plan for delivered work is a design record, so its
  decisions and as-built notes live on the issue: [design record](https://github.com/equal1/eq1_pulse/issues/6#issuecomment-5371855226).
- [#10 — one wire form per type](https://github.com/equal1/eq1_pulse/issues/10). Landed *after* this
  plan was written, and it moved ground this plan stands on.

---

## Revision — what #10 changed here

#10 established one rule: for every model, `model_json_schema(mode="validation")` equals
`model_json_schema(mode="serialization")`. Getting there replaced the shape-guessing unions with
tagged ones, removed authoring spellings from the wire, and moved the authoring grammars into the
builder. Five consequences for this plan, each measured against the landed tree rather than
reasoned about:

| v1 said                                                                        | Now                                                                                                 | Where   |
| -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | --------- |
| `SymbolValue` is `Amplitude \| Duration \| … \| complex`                       | Dimension-level, behind a callable `Discriminator` — and missing complex voltage entirely, so `LiteralExpr` cannot hold an `Amplitude`. Fixed here. | §2.1, §2.4 |
| `op` is multi-valued and therefore an ordinary field                           | True of four nodes. `UnaryExpr.op` is `Literal["-"]`, single-valued, and a default silently elides it from the wire. | §2.1    |
| §3 is "a single-line change to the `SymbolRef` alias"                          | True at the aliased read sites. `ExternalParamValue` is a hand-tagged union and needs an explicit member. | §3      |
| `"10us"` resolves to `Duration`; a bare identifier to `VariableRef`            | Both are **rejected** by the models. They survive as builder authoring sugar only.                  | §3      |
| The depth cap turns a `RecursionError` into a `ValidationError`                | Validation already does that in pydantic-core. The cap earns its keep on the *serializer*, which has no guard. | §2.3    |

Two further things #10 left that this plan must use rather than re-invent: `builder/_coerce.py`,
the one place the string/dict/zero grammars are now read (§4.1), and `test_schema_symmetry.py`,
which checks the new nodes only once `"expressions"` is in `openapi_generator.model_modules` (§3).

---

## 0. Relationship to the issue as filed

Issue #3 proposes five phases. This plan implements phases 1–3 and **deliberately drops phases 4
and 5's checking work.** The reasons are about what belongs in the IR, not about effort:

| Issue phase                              | This plan                                                                                                            |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| 1 — core expression model                  | **In.** §2.                                                                                                          |
| 2 — integration with pulse/op models       | **In.** §3, and it is one alias edit because #6 already did the widening.                                             |
| 3 — builder interface                      | **In.** §4.                                                                                                          |
| 4 — type inference, unit compatibility     | **Out.** #6 settled that eq1_pulse declares units and never enforces them. An expression type-checker would have to do unit conversion to decide whether `ext("q0.f01") + var("detuning")` is legal — precisely the job the IR handed to the outside framework. Adding it here would contradict a decision made one plan earlier. |
| 4 — expression simplification (`x + 0 → x`)| **Out.** The IR's job is to say what the user wrote. A backend that wants to fold constants has strictly more information than the builder does. |
| 5 — notebooks, API reference build-out     | **Reduced** to a builder-guide section and one example, matching how #6 and the schedule-isolation work documented themselves. |

What remains is: a serializable expression tree, the ability to put one wherever a value can go, and
Python operators to build it. That is the whole of the user-visible feature.

---

## 1. Scope and framing decisions

| Decision                                                                 | Consequence                                                                                                                            |
| -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **Expressions are opaque to eq1_pulse beyond structural validation.**     | The IR validates that the tree is well-formed and that its leaves reference declared symbols. It does not evaluate, type, simplify, or dimension-check. |
| **One model per *arity and result kind*, not one per operator.**         | `BinaryExpr(op="+")` rather than `AddExpr`. Five concrete node types plus two leaves instead of fifteen classes. See §2.1.              |
| **`==` and `!=` are not overloaded.**                                    | `Reference.__eq__` already means value comparison, and pydantic models rely on `__eq__`/`__hash__`. Repurposing them to build a `CompareExpr` would break both. Comparison nodes are built with `.eq()` / `.ne()` methods. See §4.2. |
| **The `Expr` wrapper is the only thing with operators.**                 | `VariableRef` and `ExternalRef` stay plain pydantic models. `expr(var("a")) * 2`, not `var("a") * 2`. See §8 Q1.                        |
| **Function calls are a closed `Literal` set.**                           | Open-ended function names would make the IR unconsumable without an out-of-band registry. A closed set is checkable from the schema alone. |
| **Almost no new widening work.**                                         | §3 is a single-line change to the `SymbolRef` alias plus a `model_rebuild()` sweep, *because* #6 routed every read site through that alias. The one site not behind the alias is `ExternalParamValue`, whose members #10 spelled out with explicit tags. |
| **`SymbolValue` gains a complex-voltage member.**                        | Not expression work, but expressions cannot ship without it: as #10 left it, `LiteralExpr.value` cannot hold an `Amplitude` at all. §2.4, §8 Q8. |
| **Arithmetic, comparison and logic are three separate node types.**      | `expr_type` alone answers "is this arithmetic, a predicate, or a connective?" without inspecting `op`. §2.1.                            |
| **`Conditional` accepts predicates only.**                              | A validator, not a type. `if_(expr(var("x")) + 1)` is rejected at build time — a check that needs no unit knowledge and so does not contradict §1. |
| **Expression depth is capped at 32.**                                   | Turns a `RecursionError` deep inside pydantic into a `ValidationError` at the boundary. One validator, one test.                        |

---

## 2. The expression model

New module `src/eq1_pulse/models/expressions.py`.

**Revision — operator-keyed serialization.** The wire form described below has been revised by a
follow-up change (see `docs/plans/expression-serialization-tasks.md`): `expr_type` was removed and
each node is keyed on its own field — the operator for the four operator nodes, the payload field
for the others. The node set, validators and builder API are unchanged; only the wire form changed.

### 2.1 Node types

```text
ExprBase(LeanModel)
├── LiteralExpr    value: SymbolValue
├── SymbolExpr     symbol: SymbolRef
├── UnaryExpr      unary_op: "-"                           rhs: Expression
├── BinaryExpr     binary_op: "+" | "-" | "*" | "/" | "%"
│                  lhs: Expression, rhs: Expression
├── CompareExpr    compare_op: "<" | "<=" | ">" | ">=" | "==" | "!="
│                  lhs: Expression, rhs: Expression
├── LogicalExpr    logical_op: "and" | "or" | "not"        operands: list[Expression]
└── CallExpr       function: Literal[...]                   args: list[Expression]

Expression = Annotated[LiteralExpr | SymbolExpr | UnaryExpr | BinaryExpr | CompareExpr | LogicalExpr | CallExpr,
                       Discriminator(...)]
```

`CompareExpr` and `LogicalExpr` are separate from `BinaryExpr` rather than further `op` values
because their result type is categorically different — both yield booleans, and both are valid as a
`Conditional.var` where an arithmetic node is not. Keeping the three distinct means "is this a
predicate?" is answerable from the discriminator alone, without inspecting `op`. Applying that rule
consistently is what makes it a rule rather than a special case for comparisons.

`LogicalExpr` takes a `list[Expression]` for `operands` rather than `lhs`/`rhs` because `not` is unary and
`and`/`or` are naturally n-ary; a validator checks that `not` has exactly one operand and
`and`/`or` have at least two. Same shape, and the same kind of validator, as `CallExpr` arity.

`LiteralExpr.value` reuses `SymbolValue` from #6 — the same union that types a declaration's
`default`. One notion of "a concrete value" across both plans. #10 rewrote that union: it lists **one
type per dimension** (`Time | Voltage | Frequency | Angle`) plus `bool | int | float | complex`,
behind a callable `Discriminator`, rather than one type per refinement. `Duration`, `Amplitude`,
`Magnitude`, `Threshold` and `Phase` are indistinguishable on the wire from their base dimension, so
listing them would make resolution depend on declaration order. §2.4 covers the one dimension that
rewrite dropped.

`SymbolExpr.symbol` is `SymbolRef` from #6, so `var("t1") + ext("q0.t2")` is expressible with no
extra work.

.. note::

    **[Revision: operator-keyed serialization]** The `LeanModel` convention has changed: each node
    is now keyed on its own field (the operator or payload), and the discriminator is callable
    rather than a literal field. The first field on each operator node is now the operator itself
    (``unary_op``, ``binary_op``, ``compare_op``, ``logical_op``), and it is always serialized.


### 2.2 Function set

```python
function: Literal["min", "max", "abs", "sqrt", "sin", "cos", "tan", "exp", "log"]
```

Arity is not encoded in the type. A model validator checks it: `min`/`max` take ≥ 2 args, everything
else takes exactly 1. Together with `LogicalExpr`'s operand count and the §2.3 depth cap, this is the
whole of the semantic validation in the plan, and all three earn their keep by being decidable from
the node alone with no unit knowledge.

`abs` is a `CallExpr` function only — it is not a `UnaryExpr` op. Python's `abs()` maps to the call
node, and every other named mathematical operation lives in the same place.

### 2.3 Recursion

`Expression` is mutually recursive with its node types. The module needs the standard pydantic dance:
`from __future__ import annotations`, forward references, and an explicit `model_rebuild()` for each
node class at the bottom of the module. Anything importing `Expression` into a *widened union*
(§3) must also be rebuilt, or the union silently resolves against an incomplete model.

**Depth is capped at 32** — but not for the reason v1 gave. Measured on the landed tree, pydantic-core
has its own recursion guard on the validation path: a 1000-deep tree already raises a
`ValidationError`, not a `RecursionError`. The cap earns its keep on the **serialization** path,
which has no such guard. At that depth `model_dump_json()` degrades into a storm of
`PydanticSerializationUnexpectedValue` *warnings* and emits wrong output — silent, and so worse than
the error the cap was meant to convert. A validator that rejects a too-deep tree on the way in means
one can never be built to serialize. 32 is generous — hand-written expressions do not approach it —
and the limit is a module constant so it can be raised without touching logic.

### 2.4 `SymbolValue` must gain a complex-voltage member

`LiteralExpr.value: SymbolValue` cannot hold an `Amplitude` as `SymbolValue` stands. Measured:

```text
SymbolValue(Amplitude(mV=100))   -> REJECTED (union_tag_not_found)
SymbolValue({"mV": (1.0, 2.0)})  -> REJECTED   # Amplitude's own model_dump output
```

`Amplitude` derives from `ComplexVoltage`, which is **not** a `Voltage` subclass, and
`_DIMENSION_TAGS` in `basic_types.py` lists only `Time | Voltage | Frequency | Angle`. So the
complex-voltage dimension is absent from `SymbolValue` and from `ExternalParamValue` altogether — not
narrowed to a base dimension the way `Duration` and `Magnitude` are, but unrepresentable. Both unions'
docstrings claim the opposite, naming `Amplitude` among the refinements said to be covered by their
base dimension; those are wrong and are corrected with the fix.

This is a pre-existing gap from #10 rather than one expressions introduce — it equally blocks
`param_decl("amp", default=Amplitude("100mV"))` — but expressions cannot ship around it. Scaling an
amplitude is the motivating use, `expr(var("scale")) * Amplitude("80mV")` is one line from §5's
example, and a literal that cannot spell the most common pulse parameter is not a literal. Fixed
here, in task 1 (§8 Q8).

**The rule.** Within a voltage unit key, the *shape of the value* says which dimension it is: a real
number is a `Voltage`, a `(real, imag)` pair is a `ComplexVoltage`. `{"mV": 100}` and `{"mV": [1, 2]}`
are distinct wire shapes, so this satisfies #10's one-wire-form-per-type invariant rather than
reopening it.

**Where it goes.** `_symbol_value_tag` (`data_ops.py`) and `_external_param_value_tag`
(`pulse_types.py`) both end in `dimension_tag_of` for an already-built instance, and both read
`dimension_unit_tag_map()` for a wire mapping. The shape test belongs with those two helpers in
`basic_types.py`, so one edit serves both unions; each then gains a `complex_voltage` member.

**The trap.** `ComplexVoltage` must **not** simply be added to `_DIMENSION_TAGS`. That dict is also
what `dimension_unit_tag_map()` iterates to build the unit-key → dimension map, and
`ComplexVolts` / `ComplexMillivolts` carry the same `V` / `mV` keys as `Volts` / `Millivolts` —
adding it there makes every voltage key resolve to whichever of the two was iterated last. The
unit-key map stays keyed on the real dimensions; the complex carve-out sits on top of it, decided by
value shape.

**The consequence to accept.** A *real-valued* `ComplexVoltage` — `Amplitude(mV=100)` — dumps
`{"mV": 100}` and revalidates as `Voltage`. The document round-trips unchanged; the type narrows.
That is exactly the narrowing #10 already accepts for `Duration` → `Time` and `Magnitude` → `Voltage`,
for the same reason: on the wire the two are the same thing. Instances passed directly are unaffected —
`Amplitude(mV=100)` stays an `Amplitude`, because the instance branch tags it before any wire shape is
considered.

A prototype of the rewritten union was measured against the landed tree: all eighteen forms above and
in §3 round-trip document-identically, `Amplitude(mV=1+2j)` resolves to `ComplexVoltage` and stays
there, and a unit typo still produces exactly one `union_tag_not_found`.

---

## 3. Integrating expressions into the operation models

Because #6 introduced `SymbolRef` and routed every read site through it, integration at those sites
is:

```python
# expressions.py — not reference_types.py, see §8 Q5
type ValueRef = SymbolRef | Expression
```

then a mechanical rename of `SymbolRef` → `ValueRef` at the §2 read-site inventory of the #6 plan.
Same list, same files, no new judgement calls about which sites are reads.

`ValueRef` stays a plain `|` union rather than a callable-discriminator union in #10's style
(§8 Q9). Its three members are unambiguous by wire shape and a prototype resolves every form
correctly; the only cost is that a malformed value reports three error branches instead of two.

**One read site is not behind the alias.** `ExternalParamValue` in `pulse_types.py` spells its
members out with explicit `Tag`s over a hand-written `_external_param_value_tag`. It gains an
`Expression` member too (§8 Q10): `VariableRef` and `ExternalRef` are already members, so the
consuming framework already resolves names out of band, and a tree is the same job one level up.
That is a `Tag` entry plus a branch in the tag function — not an alias rename — and so an explicit
step in task 2 rather than part of the sweep.

Four consequences to handle explicitly:

1. **`ConditionalBase.var` is special.** Every other read site accepts any `Expression`. A condition
   accepts a predicate only: a `SymbolRef`, a `CompareExpr`, or a `LogicalExpr`. The field is typed
   `ValueRef` like the rest and a model validator rejects the arithmetic nodes, with a message naming
   what was passed. Typing it as the narrow union instead is possible but produces a union that
   duplicates half of `Expression` and reads worse in the generated schema.
2. **`model_rebuild()` sweep.** Every model whose fields now transitively mention `Expression` needs
   rebuilding. Practically: `pulse_types`, `channel_ops`, `data_ops`, `external_block`, `control_flow`,
   `sequence`, and `experimental/schedule`. A test that imports the package and validates one model
   of each family catches a missed rebuild immediately.
3. **Union resolution.** `Duration | ValueRef` at a typed read site is a three-branch union whose
   members are each independently discriminated: `Duration` on its unit key, `SymbolRef` on
   `var`/`ext`, `Expression` on `expr_type`. v1 called this "a six-way smart union" and listed the
   invariants it had to preserve; #10 removed the shape-guessing behind both the name and the list.
   What a typed read site actually does today, measured on `SquarePulse.duration`:

   | input             | resolves to                                                                    |
   | ------------------- | -------------------------------------------------------------------------------- |
   | `{"ns": 100}`     | `Duration`                                                                     |
   | `{"var": "d"}`    | `VariableRef`                                                                  |
   | `{"ext": "q0.t"}` | `ExternalRef`                                                                  |
   | `"10us"`          | **rejected** — not a wire form since #10; authoring sugar in the builder only   |
   | `"my_dur"`        | **rejected** — a bare identifier is a string, never promoted to a reference     |

   Adding `Expression` must disturb none of the five. `tests/eq1lab_pulse/models/test_pulse_types.py`
   and the `test_authoring_forms.py` ledger #10 added are the guard, and must be run unchanged.

4. **The schema-symmetry invariant covers the new nodes.** `test_schema_symmetry.py` asserts
   `model_json_schema(mode="validation") == model_json_schema(mode="serialization")` for every model
   `get_all_pydantic_models()` discovers — and that function reads
   `openapi_generator.model_modules`. The expression nodes are therefore checked only once
   `"expressions"` is in that list, so the entry goes in **with the module, in task 1**, not with the
   schema work in §7. A prototype of every node shape passes symmetry unchanged, so this is cheap
   insurance — but insurance bought in the task that can still act on it.

---

## 4. Builder

### 4.1 `expr()` and the `Expr` wrapper

New module `src/eq1_pulse/builder/_expressions.py`, re-exported from `builder/__init__.py` as
`expr`. (Leading underscore matches `_factories.py` / `_state.py`; only the public name is exported.)

```python
class Expr:
    """Operator-overloading wrapper that builds an Expression tree."""

    def __init__(self, value: Expression | Expr | SymbolRef | SymbolValue): ...
    def unwrap(self) -> Expression: ...
```

`expr(x)` is the sole entry point. It accepts an `Expr` (identity), a `SymbolRef`, a raw
`SymbolValue`, or a bare `Expression`, and normalizes to `LiteralExpr` / `SymbolExpr` accordingly.

**The raw-value branch goes through `builder/_coerce.py`'s `as_symbol_value`** — a module that did
not exist when this plan was written. Since #10 it is "the single place the string, dict, and zero
grammars are read": the models validate the canonical object form and nothing else, and `"10us"`,
`"80mV"` and the bare `0` survive only where a constructor runs. So `expr("10us")` works if and only
if `expr()` routes strings through `as_symbol_value`, and re-implementing that reading anywhere else
puts a second copy of the grammar in the tree. The case belongs in
`tests/eq1lab_pulse/models/test_authoring_forms.py`, which #10 added to hold exactly this ledger.

### 4.2 Operators

| Python                            | Node                            |
| ----------------------------------- | --------------------------------- |
| `+ - * / %` and their `r`-variants | `BinaryExpr`                    |
| unary `-`                         | `UnaryExpr(op="-")`             |
| `abs()`                           | `CallExpr(function="abs")`      |
| `< <= > >=`                       | `CompareExpr`                   |
| `.eq(other)` / `.ne(other)`       | `CompareExpr(op="==" / "!=")`   |
| `.and_(other)` / `.or_(other)` / `.not_()` | `LogicalExpr`          |

The reflected variants (`__radd__`, `__rmul__`, …) are what make `2 * expr(var("a"))` work, and are
worth the six extra methods.

`==` / `!=` / `and` / `or` / `not` are **not** overloaded, for the reason in §1: Python's `and`/`or`/
`not` cannot be overloaded at all (they coerce to `bool`), and `__eq__` is already spoken for.
Providing `.eq()` alongside working `<` is an asymmetry, so it must be called out in the docstring
and the guide, with the reason. Dropping the comparison operators entirely, so that everything is a
method, was the alternative; it was considered and rejected — §8 Q6.

`Expr` must set `__hash__ = None` explicitly, since it defines `__eq__`-adjacent semantics without
defining `__eq__`; and it must **not** be a pydantic model.

### 4.3 Where `Expr` is accepted

Every builder function that today calls `_validate_or_pass_through` gets one more branch: an `Expr`
is unwrapped to its `Expression` and its leaves are checked for declaration. Leaf checking walks the
tree once and calls the existing `_check_variable_declared` / `_check_external_declared` per
`SymbolExpr`. This is the only new traversal in the plan and belongs next to the validation helpers
in `_factories.py`.

A bare `Expression` model passed directly (not wrapped in `Expr`) is also accepted — users
deserializing a fragment should not be forced to re-wrap it.

Three functions form that chain, not two. The pulse factories reach `_validate_or_pass_through`
through `_coerce_or_ref`, which routes on `isinstance(resolved, VariableRef | ExternalRef)` and hands
everything else to an `as_*` coercion — so an `Expression` reaching it goes to `as_amplitude()`
rather than through. It needs the same widening, and it is the one that silently mis-handles rather
than failing to type-check.

---

## 5. Example

```python
from eq1_pulse.builder import *
from eq1_pulse.models import Amplitude

with build_sequence() as seq:
    extern_decl("q0.f01", "float", unit="GHz")
    param_decl("detuning", "float", unit="MHz", default=0.0)
    param_decl("tau_step", "float", unit="ns")
    param_decl("scale", "float", default=1.0)
    var_decl("step", "int")

    set_frequency("q0_drive", expr(ext("q0.f01")) + expr(var("detuning")))

    with for_("step", range(0, 50)):
        pi_half = square_pulse(duration="25ns", amplitude=expr(var("scale")) * Amplitude("80mV"))
        play("q0_drive", pi_half)
        wait("q0_drive", duration=expr(var("step")) * expr(var("tau_step")))
        play("q0_drive", pi_half)
        measure("q0_readout", result_var="iq", duration="1us", amplitude="50mV")
```

The `amplitude=` line is the one §2.4 unblocks: it is a `BinaryExpr` whose right operand is a
`LiteralExpr` holding an `Amplitude`, which `SymbolValue` rejects outright as #10 left it. It is in
the example deliberately, so the fix has a user-visible consumer rather than only a unit test.

---

## 6. Tests

| File                                                  | Add                                                                                      |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `tests/eq1lab_pulse/models/test_expressions.py` (new) | every node type constructs, round-trips, and discriminates; nesting to depth 3; `CallExpr` and `LogicalExpr` arity validators accept and reject; depth 33 raises `ValidationError`; `UnaryExpr` serializes its `op` |
| `tests/eq1lab_pulse/models/test_schema_symmetry.py`   | the expression nodes reach `get_all_pydantic_models()` and satisfy the invariant; one goes in `_canonical_round_trip_instances()` (§3.4) |
| `tests/eq1lab_pulse/models/test_data_ops.py`          | `SymbolValue` accepts an `Amplitude` and `{"mV": [1, 2]}`; a real `{"mV": 100}` is still a `Voltage` (§2.4) |
| `tests/eq1lab_pulse/models/test_authoring_forms.py`   | `expr("10us")` and `expr("80mV")` read the same grammar `as_symbol_value` does (§4.1) |
| `tests/eq1lab_pulse/models/test_pulse_types.py`       | pulse parameters accept an `Expression`; **all existing coercion cases still pass** (§3.3) |
| `tests/eq1lab_pulse/models/test_channel_ops.py`       | one widened field per family accepts an `Expression`                                       |
| `tests/eq1lab_pulse/models/test_sequence.py`          | a sequence containing expressions round-trips through JSON                                 |
| `tests/eq1lab_pulse/models/test_control_flow.py`      | `Conditional` accepts `CompareExpr`/`LogicalExpr`/`SymbolRef`, rejects `BinaryExpr`        |
| `tests/eq1lab_pulse/test_builder_expressions.py` (new)| operator coverage incl. reflected forms; `.eq()`/`.ne()`; undeclared leaf raises; `Expr` is unhashable |
| `tests/test_openapi_generator.py`                     | the seven expression models are present; `ExprBase` is absent                              |

The round-trip test matters more than usual here: a discriminated recursive union is exactly the
shape that silently degrades to `dict` when a `model_rebuild()` is missed, and the failure surfaces
far from its cause.

---

## 7. Schema

`"expressions"` is added to `openapi_generator.model_modules`, `"ExprBase"` to
`excluded_base_classes`, and an `{"name": "expressions", ...}` entry to the tag list — the three
places the generator names modules explicitly.

**The first two move into task 1, with the module.** `model_modules` is what
`get_all_pydantic_models()` reads, so it is also what decides whether `test_schema_symmetry.py` sees
the new nodes at all (§3.4); and `excluded_base_classes` must gain `"ExprBase"` in the same commit or
a field-less base class appears in the schema the moment the module is listed. The tag-list entry and
the generator's own test stay here — they are documentation of a module that is already covered.

---

## 8. Decisions closed

| #  | Question                                                                | Decision                                                                                                                                     |
| -- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Q1 | Should `var("a") * 2` work without `expr()`?                            | **No.** Operators live only on the `Expr` wrapper. `VariableRef` is a pydantic model whose `__eq__` already means value comparison and is tested (`var("a") == "a"` is `True`); giving it arithmetic makes one class do two jobs and puts a working `<` next to a `==` that means something else entirely. Rejected: dunders on the reference models; a `var()` that returns a dual-purpose wrapper (every `isinstance(x, VariableRef)` in models and builder would need re-examining). |
| Q2 | Should `Conditional.var` accept arbitrary expressions?                  | **Predicates only** — `SymbolRef`, `CompareExpr`, `LogicalExpr` — enforced by a validator with a message naming what was passed. Accepting `if_(expr(var("x")) + 1)` and deferring the error to a backend is worse than rejecting it here, and the check needs no unit knowledge. |
| Q3 | `abs` as a unary op or a call?                                          | **`CallExpr(function="abs")`.** `abs` is a named function everywhere else in the set; `"abs"` is dropped from the `UnaryExpr` op literal, leaving it with `"-"` alone. |
| Q4 | Cap expression depth?                                                   | **Yes, 32,** as a module constant — but not for v1's reason. pydantic-core already turns a deep *validation* into a `ValidationError`; it is the *serializer* that has no recursion guard and degrades to warnings plus wrong output. §2.3. |
| Q5 | Where does the `ValueRef` alias live?                                   | **`expressions.py`.** Putting it in `reference_types.py` makes that module import `expressions`, which imports `reference_types` — a cycle breakable only with `TYPE_CHECKING`. Dependencies point one way: `reference_types` → `expressions` → operation modules. |
| Q6 | Comparison operators at all, given `==` cannot be one?                  | **Keep `<`, `<=`, `>`, `>=`.** Losing four working operators to hide one gap is a bad trade. The gap is documented in the `Expr` docstring and the builder guide, with the reason. |
| Q7 | Are `and`/`or` `BinaryExpr` ops or their own node?                      | **Own node, `LogicalExpr`,** with n-ary `operands`. Mixing `"+"` and `"and"` in one `op` literal means "is this arithmetic?" needs `op` inspection — the same argument that split `CompareExpr` out, applied consistently. Costs a seventh model. |

Three more were opened by #10 landing after this plan was written, and closed on 2026-08-22:

| #   | Question                                                               | Decision                                                                                                                                     |
| --- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Q8  | `SymbolValue` cannot hold an `Amplitude`. Fix it, or document the limit? | **Fix it, in task 1.** Add a complex-voltage member routed by value shape (§2.4). Deferring was the alternative: it would ship a literal that cannot spell the most common pulse parameter, and it would leave `param_decl(default=Amplitude(...))` broken too. The fix is confined to one shape test shared by the two tag functions, and a prototype was measured before this was written. Rejected: giving `LiteralExpr.value` a wider union of its own, which would abandon "one notion of a concrete value" for a saving of nothing. |
| Q9  | Plain `\|` union at the widened read sites, or a #10-style discriminator? | **Plain `\|`.** `Duration \| ValueRef`'s three members are unambiguous by wire shape, and a prototype resolves every form correctly. #10's discriminators exist to remove *ambiguity*, which is not present here; the residual cost is three error branches instead of two on a malformed value. Adopting the pattern would need one hand-written tagged union per quantity type at every read site, turning §3's rename into a rewrite. |
| Q10 | Does `ExternalParamValue` accept an `Expression`?                       | **Yes.** `VariableRef` and `ExternalRef` are already members, so the consuming framework already resolves symbols out of band; a tree is the same obligation one level up, and excluding it would make "an expression goes wherever a value goes" false in exactly one place. Costs a `Tag` entry and a branch in `_external_param_value_tag` — an explicit step in task 2, not part of the alias sweep. |

### Deliberately not decided here

- **Whether a backend evaluates expressions eagerly or lazily.** Issue #3's open question 1. The IR
  records the tree; when it collapses is the executor's business.
- **Type coercion rules for mixed-type expressions.** Issue #3's open question 8. Follows from §1:
  eq1_pulse does not type expressions, so it has no coercion rules to state.
- **Element-wise operations on array variables.** Issue #3's open question 6. Nothing in the node set
  forbids an array-shaped symbol appearing in one; nothing defines what it means either. Left open
  until something needs it.
