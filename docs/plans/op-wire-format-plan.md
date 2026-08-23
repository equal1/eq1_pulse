# Plan: nested operation wire format

**Status:** in flight — all eight framing questions closed (§2). Tasks 1–3 landed; §3.1–§3.4
below are corrected to the API as built. Tasks 4–5 outstanding.
**Date:** 2026-08-23
**Predecessors:** builds directly on the `{tag: value}` reference forms established by
[#10](https://github.com/equal1/eq1_pulse/issues/10) and on the expression nodes added by
[#3](https://github.com/equal1/eq1_pulse/issues/3). Both must be landed first; both are.

---

## 0. What changes

An operation stops carrying its type as a sibling field and starts carrying it as the key of the
object that holds it.

```jsonc
// before
{"op_type": "play", "channel": "q0_drive", "pulse": {"pulse_type": "square", ...}}

// after
{"play": {"channel": "q0_drive", "pulse": {"pulse_type": "square", ...}}}
```

Three further shape changes ride along, each closed in §2: expression operator nodes nest the same
way, a field typed exactly `VariableRef` carries the bare name, and the old flat form stops being
accepted at all.

```jsonc
// a sequence, end to end
[
  {"var_decl": {"name": "iq", "dtype": "complex"}},
  {"for": {
      "var": "t",
      "items": {"start": 0, "stop": 1e-6, "num": 51},
      "body": [
        {"play": {"channel": "q0_drive",
                  "pulse": {"pulse_type": "square",
                            "duration": {"ns": 40},
                            "amplitude": {"mV": 100}}}},
        {"wait": {"channels": ["q0_drive"],
                  "duration": {"binary_op": {"op": "*",
                                             "lhs": {"symbol": {"var": "t"}},
                                             "rhs": {"value": 2}}}}},
        {"record": {"channel": "q0_read",
                    "var": "iq",
                    "duration": {"us": 2},
                    "integration": {"integration_type": "full"}}},
        {"discriminate": {"target": "outcome", "source": "iq", "threshold": {"mV": 500}}},
        {"if": {"var": {"symbol": {"var": "outcome"}},
                "body": [{"shift_phase": {"channel": "q0_drive", "phase": {"deg": 180}}}]}}
      ]}}
]
```

---

## 1. Why the tag moves

Three reasons, in the order they matter.

1. **One key answers "what is this?"** Today a consumer reads an object, finds `op_type`, then
   re-reads the same object for the payload. Nested, the sole key *is* the answer, and the payload
   is what it points at. This is the form
   [#10](https://github.com/equal1/eq1_pulse/issues/10) already settled on for every reference:
   `{"var": "amp"}`, `{"ext": "q0.f01"}`, `{"pulse_name": "pi"}`. Operations were the remaining
   holdout.
2. **The payload becomes a closed record.** `additionalProperties: false` on the inner object now
   guards only real fields; the discriminator no longer occupies a slot in the same namespace as
   the data.
3. **It reads as the thing it denotes.** `{"play": {...}}` is a play. `{"op_type": "play", ...}` is
   an object that claims to be one.

The cost is one extra nesting level per operation, and the loss of OpenAPI's `discriminator`
keyword on operation unions — see §6.

---

## 2. Decisions

Each was an open fork; each is closed. The rationale column is the argument that closed it, not a
restatement of the choice.

| #      | Decision                                                            | Rationale and consequence                                                                                                                                                                                                                                                                                                                                                                                                          |
| ------ | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | **Only the `op_type` family nests.**                                | `pulse_type` and `integration_type` keep their flat form. Pulses and integrations appear in exactly one field each and are never mixed into a heterogeneous list the way operations are, so the "sole key answers what it is" argument does not apply to them. Consequence: two conventions coexist on the wire, and §3.1 puts the mechanism on `OpBase` rather than on `LeanModel`.                                                    |
| **D2** | **Expression operator nodes nest; single-payload nodes stay flat.** | An operator node has an operator *and* operands, which is the same shape an operation has. `LiteralExpr` and `SymbolExpr` have exactly one field each, so nesting them would produce `{"value": {"value": ...}}` — the very redundancy D4 removes. See §3.4 for the per-node table.                                                                                                                                                     |
| **D3** | **An empty payload serializes as the bare tag string.**             | `{"barrier": {}}` carries no information the key does not already carry. **No operation can reach this today** — all 20 have at least one required field, and `LeanModel` elides only fields equal to a *default*, never required ones. So this is a forward-looking rule, and §3.1 applies it only to classes that can statically reach an empty payload, leaving every current op's schema untouched.                                 |
| **D4** | **A field typed exactly `VariableRef` carries the bare name.**      | `{"var": {"var": "iq"}}` is the redundancy. Applies to `Record.var`, `Trace.var`, `Iteration.var`, `Discriminate.target`/`.source`, `Store.source`, `ExternalBlock.results` values. Union positions (`Conditional.var: ValueRef`, `SymbolExpr.symbol: SymbolRef`) keep `{"var": ...}`, because there a bare string would have to be told apart from `ExternalRef` and from `ExternalParamValue`'s plain `str` member.                    |
| **D5** | **Hard cut. The flat form is not accepted on input.**               | Accepting both would make the accepted-input shape wider than the schema describes — precisely the asymmetry `test_no_model_differs_between_validation_and_serialization_schema` exists to catch, and precisely what #10's "one wire form, in both directions" commits to. Old documents fail with a `union_tag_not_found`. Note the error does **not** list the valid keys: for a callable discriminator pydantic says only `Unable to extract tag using discriminator op_tag_of()`. Tags are named only in `union_tag_invalid`, i.e. when a single-key object carries an unrecognised key.                                                                                       |
| **D6** | **`op_type` stays a Python field.**                                 | `op.op_type == "play"` keeps working; the builder, `_state.py` and the tests keep their existing spellings. `OpBase` lifts the field to the outer key on the way out and puts it back on the way in. The alternative — a class-level tag registry — buys cleaner class bodies at the price of touching every construction site.                                                                                                          |

---

## 3. Model changes

### 3.1 Where the wrap lives

`LeanModel` already computes the exact predicate this needs — `_non_discriminator_fields()` detects
"the first field is a single-valued `Literal`" and drops it — but D1 scopes the change to
operations, and that predicate is also true of `SquarePulse` and `FullIntegration`. So the shared
machinery goes on `LeanModel` as an **opt-in**, and the two families that opt in are `OpBase` and
the six nesting expression nodes.

Add to `base_models.py`:

```python
class NestedWireModel(LeanModel):
    """A LeanModel whose wire form is ``{tag: payload}`` rather than a flat object."""

    _wire_tag_source_: ClassVar[str] = ""                          # field the tag is read from; "" = inert
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "value"  # tag is that field's value, or its name
    _wire_payload_key_: ClassVar[str | None] = None                # inner key for the value, or None to drop
```

**Three knobs, not two.** The draft tied "the tag is the field's *name*" to "`_wire_payload_key_`
is set", which made `NotExpr`'s form in §3.4 — tagged by name, single-valued operator dropped —
inexpressible. Where the tag comes from and whether the tag source survives into the payload are
separate questions; all four combinations are reachable.

`_wire_tag_source_` defaults to `""`, meaning *not configured*: such a class, and one whose tag
source is not a single-valued `Literal` (an abstract base like `OpBase`, whose `op_type` is `Any`),
behaves exactly like `LeanModel` in both directions and both schema modes. So `OpBase` itself keeps
a flat schema while all 20 concrete ops nest — which is invisible, since `OpBase` is already in the
generator's `excluded_base_classes`.

with three hooks:

| Hook                             | Behaviour                                                                                                                                                                                                                                    |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `@model_serializer(mode="wrap")` | Runs `LeanModel`'s default elision, lifts the tag, returns `{tag: payload}` — or the bare `tag` string when `payload` is empty *and* the class can statically reach empty (D3).                                                                 |
| `@model_validator(mode="wrap")`  | Accepts `{tag: payload}` (and the bare `tag` string for the D3 classes), flattens it back to the field set pydantic already knows how to validate.                                                                                              |
| `__get_pydantic_json_schema__`   | Takes the flat object schema `LeanModel` already rebuilds, removes the tag field from `properties`/`required`, and wraps it in a single-key object schema. Identical in both modes, so schema symmetry holds.                                   |

`OpBase(NestedWireModel, FrozenModel)` sets `_wire_tag_source_ = "op_type"` and leaves the other
two at their defaults — the tag *is* the field's value, and it is not repeated inside. All 20
operations inherit it with no per-class edit.

Three further facts established by building it, each of which changes what a later task may assume:

1. **D5 is not enforced in the model validator, and must not be.** Pydantic routes `__init__`
   through the wrap validator, so `Play(channel=…, pulse=…)` and
   `model_validate({"op_type": "play", …})` arrive as the same dict — a rule strict enough to
   reject the flat wire form would also outlaw ordinary keyword construction, which D6 requires to
   keep working. The validator therefore passes anything that is not the nested form through
   untouched, and **D5 rejection lands entirely on the §3.3 union discriminators**, which is where
   §2's `union_tag_not_found` rationale already put it. Task 2 must not try to tighten the model
   validator. Consequence to accept: `Play.model_validate_json('{"op_type": "play", …}')` still
   succeeds. Every union site rejects it; a direct single-model validate does not.
2. **`model_dump()`'s declared return type is `dict[str, Any]`, and D3's bare-tag form returns
   `str`.** No current op can reach an empty payload, so nothing hits this today, but a future
   empty-capable class will need its callers to widen the annotation.
3. **The serializer must be named `_wrap_serializer`, overriding `LeanModel`'s by name.** A
   differently-named `@model_serializer` in a subclass silently replaces the parent's rather than
   erroring. `LeanModel`'s elision now lives in a reusable `_elide_defaults` so the override can
   call it instead of duplicating it.

### 3.2 The two tagging rules, and why they differ

| Family      | `_wire_tag_from_` | Tag is…                | Why                                                                                                                                                                                                              |
| ----------- | ----------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| operations  | `"value"`         | **value** (`"play"`)   | Every op shares the field *name* `op_type`, so only the value distinguishes them.                                                                                                                                  |
| expressions | `"name"`          | **name** (`binary_op`) | Values overlap — `"-"` is both `UnaryExpr` and `BinaryExpr` — so only the name distinguishes them. This is already how `_EXPRESSION_TAGS` works; the change is where the operator value goes, not what the tag is.  |

### 3.3 Discriminators to rewrite

Four unions move from `Discriminator("op_type")` to a callable reading the sole key:

| Union                        | File                                 |
| ---------------------------- | ------------------------------------ |
| `ChannelOp`                  | `models/channel_ops.py:352`          |
| `DataOp`                     | `models/data_ops.py:386`             |
| `DiscriminableOp`            | `models/sequence.py:50`              |
| `DiscriminableSchedulableOp` | `models/experimental/schedule.py:80` |

**A bare `Discriminator(op_tag_of)` is not implementable at these four sites**, and Task 2 found
this the hard way. Pydantic requires every *member* of a callable-discriminated union to carry a
`Tag`, and two of the four unions contain member unions — `DiscriminableOp` holds `ChannelOp` (10
tags) and `DataOp` (6). The **string** discriminator recursed into those; a callable one raises
`PydanticUserError: 'Tag' not provided for choice`.

So the callable is wrapped in an annotation marker, `OperationDiscriminator`, following the repo's
two existing precedents (`UnitDiscriminator` in `units.py`, `ReferenceDiscriminator` in
`reference_types.py`). It walks each member's annotation, attaches one `Tag` per operation that
member reaches, and builds `Annotated[Union[*members], Discriminator(op_tag_of)]`. A nested union
member gets several tags all pointing at it — which is what the string discriminator produced
before, so `ChannelOp` stays a named `$ref` in `DiscriminableOp`'s `oneOf` instead of the union
flattening to 22 leaf refs. All of this lives in `basic_types.py` beside `OpBase`.

`expression_tag_of` (Task 3) needs none of that: the `Expression` union's members are all concrete
node classes with no nested unions, so it stays a bare callable `Discriminator`. It tightens from
"the first known key present" to "the sole key, if known". `_external_param_value_tag` in
`pulse_types.py` delegates to it and needs no change beyond that tightening, since `pulse_type`
(D1) still resolves before it.

### 3.4 Expression nodes

| Node          | Before                                      | After                                               | `_wire_tag_source_` | `_wire_tag_from_` | `_wire_payload_key_` |
| ------------- | ------------------------------------------- | --------------------------------------------------- | ------------------- | ----------------- | -------------------- |
| `LiteralExpr` | `{"value": {"ns": 20}}`                     | *unchanged* — one field, already the flat form      | —                   | —                 | —                    |
| `SymbolExpr`  | `{"symbol": {"var": "t"}}`                  | *unchanged* — one field; D4 does not reach it (§2)  | —                   | —                 | —                    |
| `UnaryExpr`   | `{"unary_op": "-", "rhs": …}`               | `{"unary_op": {"op": "-", "rhs": …}}`               | `"unary_op"`        | `"name"`          | `"op"`               |
| `BinaryExpr`  | `{"binary_op": "+", "lhs": …, "rhs": …}`    | `{"binary_op": {"op": "+", "lhs": …, "rhs": …}}`    | `"binary_op"`       | `"name"`          | `"op"`               |
| `CompareExpr` | `{"compare_op": "<", "lhs": …, "rhs": …}`   | `{"compare_op": {"op": "<", "lhs": …, "rhs": …}}`   | `"compare_op"`      | `"name"`          | `"op"`               |
| `LogicalExpr` | `{"logical_op": "and", "lhs": …, "rhs": …}` | `{"logical_op": {"op": "and", "lhs": …, "rhs": …}}` | `"logical_op"`      | `"name"`          | `"op"`               |
| `NotExpr`     | `{"not_op": "not", "rhs": …}`               | `{"not_op": {"rhs": …}}`                            | `"not_op"`          | `"name"`          | `None`               |
| `CallExpr`    | `{"function": "min", "args": […]}`          | `{"function": {"name": "min", "args": […]}}`        | `"function"`        | `"name"`          | `"name"`             |

`NotExpr` is the row that forced the three-knob split in §3.1: it is tagged by the field *name*
like its siblings, but its operator has one possible value and so is dropped rather than repeated.
`_wire_tag_source_value()` recovers it on the way back in, from the field's sole `Literal`
argument — never from the tag, which for the name rule is the field name and not a valid value.

**A pydantic-core defect makes this the hazardous task**, and any future self-referential
`NestedWireModel` will hit it too. When a model carrying a `@model_serializer(mode="wrap")` is
*both* self-referential and reached through another model's field, pydantic-core (2.13.4) invokes
the serializer **twice on the same instance**, the second time over the first's output — upstream
[pydantic#11812](https://github.com/pydantic/pydantic/issues/11812) and
[pydantic#11563](https://github.com/pydantic/pydantic/issues/11563). It reproduces in six lines of
plain pydantic with no eq1_pulse code involved.

`Expression` has exactly that shape: `BinaryExpr.lhs: Expression` resolves straight back into
`BinaryExpr`, with no `RootModel` layer breaking the cycle the way `OpSequence` does for
operations — which is why Task 2 never saw it. Left unguarded it is silent wrong output, not a
crash: `{"unary_op": {"op": {"op": "-", …}}}` for a node that keeps its operator, and an empty
`{"not_op": {}}` for one that drops it.

`NestedWireModel._wrap_serializer` therefore carries a re-entrancy guard — a `ContextVar` holding
the ids of instances currently mid-serialize; the spurious re-entrant call passes straight through
to the plain field dump. Legitimate recursion into *distinct* nodes is untouched (different ids),
and a shared subtree appearing twice is unaffected (the calls are sequential, not nested).
`test_pydantic_still_double_invokes_a_recursive_wrap_serializer` asserts the defect is still there:
**that test failing is good news** and means the guard can be deleted.

`MAX_EXPRESSION_DEPTH` stays at 32. It caps *Python* nesting, which `_expression_depth` measures
and which does not change; the serialized JSON gains one level per operator node, so a maximal tree
is ~64 JSON levels deep instead of ~32 — still an order of magnitude under the serializer's
recursion limit, which is what the cap exists to protect.

### 3.5 Bare variable references

`VariableRef` itself is unchanged — its `{"var": ...}` form is still what appears in every union
position. D4 is an **annotation applied at the field**:

```python
type VarName = Annotated[VariableRef, _BareVariableRef()]
```

whose `__get_pydantic_core_schema__` returns a `json_or_python_schema`: the JSON side accepts an
`IdentifierStr` and builds a `VariableRef`; the Python side additionally accepts a `VariableRef`
instance and a `VarRefDict`, so authoring code and the builder are untouched. A plain serializer
emits `.var`, and a schema hook reports `{"type": "string"}` in **both** modes — which is what keeps
symmetry, since the Python-only widening never reaches the JSON schema.

Seven sites take it:

| Site                           | File                          | After                       |
| ------------------------------ | ----------------------------- | --------------------------- |
| `Record.var`                   | `models/channel_ops.py:245`   | `{"record": {"var": "iq"}}` |
| `Trace.var`                    | `models/channel_ops.py:284`   | `{"trace": {"var": "tr"}}`  |
| `IterationBase.var`            | `models/control_flow.py:102`  | `list[VarName] \| VarName`  |
| `Discriminate.target`          | `models/data_ops.py:319`      | `"outcome"`                 |
| `Discriminate.source`          | `models/data_ops.py:321`      | `"iq"`                      |
| `Store.source`                 | `models/data_ops.py:368`      | `"iq"`                      |
| `ExternalBlock.results` values | `models/external_block.py:96` | `{"m": "iq"}`               |

`ExternalBlock._validate_flex_duration_params` checks `isinstance(value, VariableRef)` over
`params`, not `results`, so it is unaffected.

---

## 4. Schema and generated artefacts

Each nested op's definition becomes a single-key object:

```jsonc
"Play": {
  "type": "object",
  "title": "Play",
  "description": "Play a pulse on a channel.",
  "additionalProperties": false,
  "required": ["play"],
  "properties": {
    "play": {
      "type": "object", "additionalProperties": false,
      "required": ["channel", "pulse"],
      "properties": {"channel": {...}, "pulse": {...}, "scale_amp": {...}, "cond": {...}}
    }
  }
}
```

`output/eq1_pulse_openapi.{json,yaml}` must be regenerated. They are stale independently of this
change — the checked-in copy predates expressions (no `BinaryExpr` definition) and still shows
`SymbolRef` where `ValueRef` is current — so the regeneration will produce a larger diff than this
plan alone accounts for. That is expected and should not be trimmed by hand.

---

## 5. Blast radius

| Area                                                                    | Extent                                                                                                                                                                          |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `models/base_models.py`                                                 | New `NestedWireModel`; `LeanModel` untouched in behaviour                                                                                                                           |
| `models/basic_types.py`                                                 | `OpBase` gains the opt-in, plus `op_tag_of`, `_operation_wire_tags` and `OperationDiscriminator` (3 new exports)                                                                     |
| `models/expressions.py`                                                 | 6 nodes opt in; `expression_tag_of` tightens                                                                                                                                        |
| `models/{channel_ops,data_ops,sequence}.py`, `experimental/schedule.py` | 4 union discriminators                                                                                                                                                              |
| `models/{channel_ops,control_flow,data_ops,external_block}.py`          | 7 `VarName` field sites                                                                                                                                                             |
| `models/reference_types.py`                                             | New `VarName` alias and its annotation                                                                                                                                              |
| `builder/`                                                              | **No change expected.** Nothing outside `models/` reads `op_type`, `pulse_type` or `integration_type`; the builder constructs models by keyword and never touches the wire form.     |
| `tests/`                                                                | 9 files assert on `op_type`; `test_schema_symmetry.py` round-trips 15 canonical documents; `test_openapi_generator.py` asserts on the generated document                             |
| `docs/`                                                                 | `user_guide/builder_guide.rst`, `examples/basic_usage.rst`, `examples/index.rst` show wire dumps                                                                                     |
| `examples/`                                                             | Re-run and re-verify; `expression_ramsey.py` is the one that exercises expressions                                                                                                  |
| `output/eq1_pulse_openapi.{json,yaml}`                                  | Regenerate                                                                                                                                                                          |

---

## 6. Known consequences to accept

1. **Operation unions lose OpenAPI's `discriminator` keyword.** Today `ChannelOp` carries
   `discriminator: {propertyName: "op_type", mapping: {...}}`. OpenAPI 3.1 requires `propertyName`
   to name a *sibling* property, which the nested form does not have, so the union degrades to a
   plain `oneOf`. SDK generators still produce a union; they lose the constant-time tag dispatch
   and fall back to trying members. `PulseType` keeps its `discriminator`.

   **There is no integration union.** `IntegrationType` is a base class, and `Record.integration` /
   `Trace.integration` are plain inline `FullIntegration | DemodIntegration` annotations that never
   carried a `discriminator` keyword to begin with. D1's "integration family" is really just those
   two inline annotations; they keep their flat `{"integration_type": "full"}` form, which is all
   D1 asked for.
2. **Two wire conventions coexist** — nested for operations, flat for pulses and integrations
   (D1). Anything documenting the wire format has to say so rather than state one rule.
3. **Every stored program is invalidated** (D5). If any exist outside this repo, they need a
   one-shot converter; that converter is not part of this plan.
4. **`FrozenLeanModel` is now dead.** `OpBase` was its only user and became
   `NestedWireModel, FrozenModel` in Task 2. The class is still defined and exported in
   `base_models.py` and still listed in `openapi_generator.excluded_base_classes`. Left alone
   deliberately rather than pruned mid-flight; Task 5 may remove it.
