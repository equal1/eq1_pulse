# JSON Schema generation in eq1_pulse — assessment and fix

**Date:** 2026-08-21
**Branch context:** `hp-peti/parameters+expressions`
**Question asked:** is overriding `model_json_schema()` the wrong pattern, and if so, fix it
globally.
**Answer:** yes, it is the wrong pattern, and every use of it in `models/` was silently broken.
All five sites now use `__get_pydantic_json_schema__`.

Raw research backing this is in
[`raw/07-pydantic-json-schema-customisation.deep-research.md`](raw/07-pydantic-json-schema-customisation.deep-research.md).

---

## 1. The defect

`BaseModel.model_json_schema()` is a **direct-call entry point**, not an extension point. Schema
generation walks *core schemas* through `GenerateJsonSchema`; it never dispatches back to a model's
`model_json_schema()` classmethod. So an override applies when you call
`Duration.model_json_schema()` by hand and is bypassed everywhere else — nested in another model, in
a union, through `TypeAdapter(...).json_schema()`, and through `models_json_schema()`, which is what
`utilities/openapi_generator.py` uses.

Every schema customisation in `models/` was written as such an override. The published OpenAPI
document therefore described pydantic's *internal* representation rather than the wire format:

| Model         | Emitted by eq1_pulse    | `components.schemas` said                    |
| --------------- | ------------------------- | ---------------------------------------------- |
| `Duration`    | `{"us": 10}`            | `{"type": "object", "properties": {"value": …}, "required": ["value"]}` |
| `VariableRef` | `"amp"`                 | `{"type": "object", "properties": {"var": …}, "required": ["var"]}`     |
| `ChannelRef`  | `"ch1"`                 | `{"type": "object", "properties": {"channel": …}}`                      |
| `Seconds`     | `{"s": 10}`             | object only — the accepted `"10s"` string form was missing              |

`{"value": …}` is not merely unidiomatic, it is **unaccepted**: `WrappedValueModel._wrap_validator`
wraps whatever it is given, so an explicit `{"value": …}` gets wrapped a second time and rejected.
The schema described a document the library can neither produce nor consume.

Measured consequences, all reproduced on `main` before the fix:

- `Play(channel="ch1", pulse="p1").model_dump()` **fails validation against its own published
  schema** (`jsonschema.ValidationError`).
- `VariableRef.model_json_schema(mode="serialization")` raised `KeyError: 'properties'` — the
  override indexed `properties` on a schema that is empty in serialization mode.
- `Threshold.model_json_schema()` returned `anyOf` branches full of `$ref`s to `#/$defs/Volts` while
  **dropping the `$defs` section**, because the override returned an inner fragment and discarded
  the envelope. The refs did not resolve.

This is a known pydantic footgun, not a version-specific bug — see pydantic issue
[#7789](https://github.com/pydantic/pydantic/issues/7789), which reports exactly this and is closed
as a question rather than a defect.

## 2. The supported pattern

```python
@classmethod
def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
    json_schema = handler(core_schema)              # the default schema
    target = handler.resolve_ref_schema(json_schema)  # the $defs entry, not the {"$ref": …} wrapper
    ...                                             # mutate target in place
    return json_schema
```

Three details that matter and that the old code could not express:

- **`handler.resolve_ref_schema()`** — a nested model's schema arrives as `{"$ref": "#/$defs/X"}`.
  Mutating that wrapper does nothing; the definition it points at must be mutated instead. This is
  why the fix works in every position rather than only at the top level.
- **`handler.mode`** — `"validation"` describes accepted input, `"serialization"` describes emitted
  output. The old overrides had no way to distinguish them and crashed on one of the two.
- **Subclass override** — a subclass that wants pydantic's default instead of an inherited
  customisation returns `handler(core_schema)` directly rather than trying to undo the base. That is
  how `ExternalRef` opts out of `Reference`'s unwrapping.

## 3. What was changed

Five sites, all converted from `model_json_schema()` to `__get_pydantic_json_schema__`:

| Site                                      | Behaviour                                                                          |
| ------------------------------------------- | ------------------------------------------------------------------------------------ |
| `base_models.WrappedValueModel`           | Replaces the `{"value": …}` object with the wrapped value's own schema, in both modes — the object form is never valid in either direction. |
| `base_models.WrappedValueOrZeroModel`     | Adds `{"const": 0}` to the accepted forms. **Validation mode only:** zero is accepted in any unit but is stored and emitted in its registered unit, so it is never produced. |
| `units.BaseUnit`                          | Adds the `"10us"` suffixed-string form alongside `{"us": 10}`. **Validation mode only**, for the same reason. |
| `reference_types.Reference`               | Adds the bare value alongside the `{"var": …}` object form, since `_wrap_validator` accepts both. |
| `reference_types.ExternalRef`             | Opts out and keeps the object schema.                                              |

Two guards were needed because the hook, unlike the old classmethod, is also invoked for the
abstract bases themselves: `Reference` declares no field to unwrap to, and `BaseUnit` has no
registered unit. Both return the default schema untouched when their `properties` are empty.

### The accepted-input principle

The generator emits **validation mode**, so `components.schemas` now describes everything the models
*accept*, not just what they emit. `Duration` resolves to
`anyOf[{const 0}, Seconds, Milliseconds, Microseconds, Nanoseconds]`, and each unit resolves in turn
to `anyOf[{object}, {string with unit suffix}]` — so `0`, `"10us"` and `{"us": 10}` all validate
against the published document, which is exactly the set the models take. What eq1_pulse emits is a
subset of that, so serialized output validates too; this is now asserted end to end in
`test_serialized_operations_validate_against_the_generated_schema`.

### The one deliberate narrowing

`ExternalRef.model_validate("q0.f01")` succeeds — a bare string is accepted for constructor
ergonomics — but the schema advertises only `{"ext": "q0.f01"}`. Inside the `SymbolRef` union a bare
string always resolves to a `VariableRef` (plan §3.2), so advertising the bare form would describe
an input that the union never resolves to an external reference. The narrowing is documented on the
method.

## 4. Known remaining gap: serialization mode is empty

`mode="serialization"` now returns `{}` (unconstrained) for every wrapped model instead of raising,
because a plain `@model_serializer` with no declared return type gives pydantic nothing to infer
from. That is honest but uninformative, and it is why the hooks do their work in validation mode and
leave serialization mode alone rather than fabricating a shape.

Closing it properly is a separate piece of work:

1. Declare `return_type` on the model serializers so pydantic can derive an output schema.
2. Emit both modes from one `models_json_schema()` call and keep the distinct definitions, the way
   FastAPI's `separate_input_output_schemas` produces `Item-Input` / `Item-Output` components.

Not done here because it changes the shape of the published document, which is a decision rather
than a fix. Also worth noting: `jsonschema` is used by the end-to-end test via
`pytest.importorskip` because it is currently only a transitive dependency — declaring it as a dev
dependency would make that guard enforced rather than optional.

## 5. Rules of thumb for this codebase

- Never override `model_json_schema()`. It is an entry point, not a hook.
- Use `__get_pydantic_json_schema__` for schema-only changes; `__get_pydantic_core_schema__` only
  when validation or serialization itself must change.
- Always `handler.resolve_ref_schema()` before mutating, and mutate in place.
- Branch on `handler.mode` whenever accepted input differs from emitted output.
- `@model_validator` does **not** accept `json_schema_input_type` (through pydantic 2.13), so any
  input form a whole-model before-validator accepts has to be described in the JSON hook by hand.
  This is precisely the situation for every wrapping validator in `models/`.
