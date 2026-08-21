# Plan: expression support

**Issue:** [#3 — Feature: Add Expression Support to eq1_pulse](https://github.com/equal1/eq1_pulse/issues/3)
**Status:** accepted — all open questions closed (§8); see
[expressions-tasks.md](expressions-tasks.md) for the execution breakdown
**Date:** 2026-08-21
**Predecessor:** [#6 — external constants and parameter variables](https://github.com/equal1/eq1_pulse/issues/6),
**landed**. It widens the `SymbolRef` alias introduced there; without it, every widening in §3 has
to be done twice. #6's plan is not in the tree — a plan for delivered work is a design record, so its
decisions and as-built notes live on the issue: [design record](https://github.com/equal1/eq1_pulse/issues/6#issuecomment-5371855226).

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
| **No new widening work.**                                                | §3 is a single-line change to the `SymbolRef` alias plus a `model_rebuild()` sweep, *because* #6 routed every read site through that alias. |
| **Arithmetic, comparison and logic are three separate node types.**      | `expr_type` alone answers "is this arithmetic, a predicate, or a connective?" without inspecting `op`. §2.1.                            |
| **`Conditional` accepts predicates only.**                              | A validator, not a type. `if_(expr(var("x")) + 1)` is rejected at build time — a check that needs no unit knowledge and so does not contradict §1. |
| **Expression depth is capped at 32.**                                   | Turns a `RecursionError` deep inside pydantic into a `ValidationError` at the boundary. One validator, one test.                        |

---

## 2. The expression model

New module `src/eq1_pulse/models/expressions.py`.

### 2.1 Node types

```text
ExprBase(LeanModel)
├── LiteralExpr    expr_type="literal"   value: SymbolValue
├── SymbolExpr     expr_type="symbol"    symbol: SymbolRef
├── UnaryExpr      expr_type="unary"     op: "-"                           operand: Expression
├── BinaryExpr     expr_type="binary"    op: "+" | "-" | "*" | "/" | "%"
│                                        left: Expression, right: Expression
├── CompareExpr    expr_type="compare"   op: "<" | "<=" | ">" | ">=" | "==" | "!="
│                                        left: Expression, right: Expression
├── LogicalExpr    expr_type="logical"   op: "and" | "or" | "not"          operands: list[Expression]
└── CallExpr       expr_type="call"      function: Literal[...]            args: list[Expression]

Expression = Annotated[LiteralExpr | SymbolExpr | UnaryExpr | BinaryExpr | CompareExpr | LogicalExpr | CallExpr,
                       Discriminator("expr_type")]
```

`CompareExpr` and `LogicalExpr` are separate from `BinaryExpr` rather than further `op` values
because their result type is categorically different — both yield booleans, and both are valid as a
`Conditional.var` where an arithmetic node is not. Keeping the three distinct means "is this a
predicate?" is answerable from the discriminator alone, without inspecting `op`. Applying that rule
consistently is what makes it a rule rather than a special case for comparisons.

`LogicalExpr` takes a `list[Expression]` rather than `left`/`right` because `not` is unary and
`and`/`or` are naturally n-ary; a validator checks that `not` has exactly one operand and
`and`/`or` have at least two. Same shape, and the same kind of validator, as `CallExpr` arity.

`LiteralExpr.value` reuses `SymbolValue` from #6 (`Amplitude | Duration | Frequency | Phase |
Magnitude | Voltage | Threshold | bool | int | float | complex`) — the same union that types a
declaration's `default`. One notion of "a concrete value" across both plans.

`SymbolExpr.symbol` is `SymbolRef` from #6, so `var("t1") + ext("q0.t2")` is expressible with no
extra work.

The `LeanModel` convention (first single-valued `Literal` field is the discriminator and is always
serialized) is satisfied by `expr_type` being declared first in every class. `op` is a *multi*-valued
`Literal` and is therefore an ordinary field, which is the behaviour wanted.

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

**Depth is capped at 32.** Without a cap, a deeply nested tree from a generated or hostile source
hits Python's recursion limit inside pydantic and surfaces as a `RecursionError` with no useful
location. A validator on the top-level `Expression` turns that into a `ValidationError` naming the
field. 32 is generous — hand-written expressions do not approach it — and the limit is a module
constant so it can be raised without touching logic.

---

## 3. Integrating expressions into the operation models

Because #6 introduced `SymbolRef` and routed every read site through it, integration is:

```python
# expressions.py — not reference_types.py, see §8 Q5
type ValueRef = SymbolRef | Expression
```

then a mechanical rename of `SymbolRef` → `ValueRef` at the §2 read-site inventory of the #6 plan.
Same list, same files, no new judgement calls about which sites are reads.

Three consequences to handle explicitly:

1. **`ConditionalBase.var` is special.** Every other read site accepts any `Expression`. A condition
   accepts a predicate only: a `SymbolRef`, a `CompareExpr`, or a `LogicalExpr`. The field is typed
   `ValueRef` like the rest and a model validator rejects the arithmetic nodes, with a message naming
   what was passed. Typing it as the narrow union instead is possible but produces a union that
   duplicates half of `Expression` and reads worse in the generated schema.
2. **`model_rebuild()` sweep.** Every model whose fields now transitively mention `Expression` needs
   rebuilding. Practically: `pulse_types`, `channel_ops`, `data_ops`, `external_block`, `control_flow`,
   `sequence`, and `experimental/schedule`. A test that imports the package and validates one model
   of each family catches a missed rebuild immediately.
3. **Union resolution cost.** `Duration | VariableRef | ExternalRef | Expression` is a six-way smart
   union at ordinary typed pulse read sites. Concrete values (`"10us"`, `{"ns": 100}`) must still
   resolve to `Duration`, and a bare identifier there must still resolve to `VariableRef`.
   `ExternalParamValue` dictionaries are deliberately different: unit-suffixed strings are
   pre-coerced, arbitrary strings stay `str`, and references use tagged/wrapped JSON objects. These
   distinctions are the highest regression risk in the plan; the existing
   `tests/eq1lab_pulse/models/test_pulse_types.py` coercion cases are the guard and must be run
   unchanged.

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

---

## 5. Example

```python
from eq1_pulse.builder import *

with build_sequence() as seq:
    extern_decl("q0.f01", "float", unit="GHz")
    param_decl("detuning", "float", unit="MHz", default=0.0)
    param_decl("tau_step", "float", unit="ns")
    var_decl("step", "int")

    set_frequency("q0_drive", expr(ext("q0.f01")) + expr(var("detuning")))

    with for_("step", range(0, 50)):
        play("q0_drive", square_pulse(duration="25ns", amplitude="80mV"))
        wait("q0_drive", duration=expr(var("step")) * expr(var("tau_step")))
        play("q0_drive", square_pulse(duration="25ns", amplitude="80mV"))
        measure("q0_readout", result_var="iq", duration="1us", amplitude="50mV")
```

---

## 6. Tests

| File                                                  | Add                                                                                      |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `tests/eq1lab_pulse/models/test_expressions.py` (new) | every node type constructs, round-trips, and discriminates; nesting to depth 3; `CallExpr` and `LogicalExpr` arity validators accept and reject; depth 33 raises `ValidationError`, not `RecursionError` |
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

---

## 8. Decisions closed

| #  | Question                                                                | Decision                                                                                                                                     |
| -- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Q1 | Should `var("a") * 2` work without `expr()`?                            | **No.** Operators live only on the `Expr` wrapper. `VariableRef` is a pydantic model whose `__eq__` already means value comparison and is tested (`var("a") == "a"` is `True`); giving it arithmetic makes one class do two jobs and puts a working `<` next to a `==` that means something else entirely. Rejected: dunders on the reference models; a `var()` that returns a dual-purpose wrapper (every `isinstance(x, VariableRef)` in models and builder would need re-examining). |
| Q2 | Should `Conditional.var` accept arbitrary expressions?                  | **Predicates only** — `SymbolRef`, `CompareExpr`, `LogicalExpr` — enforced by a validator with a message naming what was passed. Accepting `if_(expr(var("x")) + 1)` and deferring the error to a backend is worse than rejecting it here, and the check needs no unit knowledge. |
| Q3 | `abs` as a unary op or a call?                                          | **`CallExpr(function="abs")`.** `abs` is a named function everywhere else in the set; `"abs"` is dropped from the `UnaryExpr` op literal, leaving it with `"-"` alone. |
| Q4 | Cap expression depth?                                                   | **Yes, 32,** as a module constant. Converts a `RecursionError` with no location into a `ValidationError` naming the field.                    |
| Q5 | Where does the `ValueRef` alias live?                                   | **`expressions.py`.** Putting it in `reference_types.py` makes that module import `expressions`, which imports `reference_types` — a cycle breakable only with `TYPE_CHECKING`. Dependencies point one way: `reference_types` → `expressions` → operation modules. |
| Q6 | Comparison operators at all, given `==` cannot be one?                  | **Keep `<`, `<=`, `>`, `>=`.** Losing four working operators to hide one gap is a bad trade. The gap is documented in the `Expr` docstring and the builder guide, with the reason. |
| Q7 | Are `and`/`or` `BinaryExpr` ops or their own node?                      | **Own node, `LogicalExpr`,** with n-ary `operands`. Mixing `"+"` and `"and"` in one `op` literal means "is this arithmetic?" needs `op` inspection — the same argument that split `CompareExpr` out, applied consistently. Costs a seventh model. |

### Deliberately not decided here

- **Whether a backend evaluates expressions eagerly or lazily.** Issue #3's open question 1. The IR
  records the tree; when it collapses is the executor's business.
- **Type coercion rules for mixed-type expressions.** Issue #3's open question 8. Follows from §1:
  eq1_pulse does not type expressions, so it has no coercion rules to state.
- **Element-wise operations on array variables.** Issue #3's open question 6. Nothing in the node set
  forbids an array-shaped symbol appearing in one; nothing defines what it means either. Left open
  until something needs it.
