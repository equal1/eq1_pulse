# Raw research: Pydantic v2 JSON Schema customisation — the supported hooks

**Date:** 2026-08-21
**Tool:** `perplexity_research` (Perplexity Agent API, deep-research preset)
**Asked because:** every `model_json_schema()` override in `eq1_pulse.models` is silently bypassed
when the model is nested, so the generated OpenAPI schema describes internal representations that
never appear on the wire. See
[`../pydantic-json-schema-assessment.md`](../pydantic-json-schema-assessment.md).

**Query:** Pydantic v2 (2.11-2.13): what is the correct, supported way to customise the JSON Schema
a model produces, and why is overriding the `model_json_schema()` classmethod the wrong pattern?
Covering: (1) why the override does not work in general and the generation pipeline; (2) the
supported hooks `__get_pydantic_json_schema__` / `__get_pydantic_core_schema__`, `WithJsonSchema`,
`SkipJsonSchema`, `json_schema_extra`, `GenerateJsonSchema` subclassing and their precedence;
(3) models whose serialized form is not an object (single field + before-validator + model
serializer); (4) validation vs serialization schema divergence, `json_schema_mode_override`,
`json_schema_input_type`, and emitting both input and output schemas the way FastAPI does;
(5) inheritance of `__get_pydantic_json_schema__`; (6) relevant issues and 2.9→2.13 changes.

---

## Short answer

In Pydantic v2, **do not override `BaseModel.model_json_schema()` to define a model's schema**. That
method is only a convenience entry point for a direct call such as `MyModel.model_json_schema()`.
Model composition operates on the model's **core schema**, so a nested model's overridden
classmethod is never dispatched.

Use:

- `__get_pydantic_json_schema__` when only the emitted JSON Schema needs customization.
- `__get_pydantic_core_schema__` when validation or serialization itself must change.
- `WithJsonSchema`, `SkipJsonSchema`, or `Field(json_schema_extra=...)` for annotation/field-local changes.
- A `GenerateJsonSchema` subclass for generator-wide policy.

The documented pipeline is:

```text
Python annotation/model
    │
    ▼
GenerateSchema / __get_pydantic_core_schema__
    │
    ▼
CoreSchema stored as __pydantic_core_schema__
    │
    ▼
GenerateJsonSchema / __get_pydantic_json_schema__
    │
    ▼
JSON Schema
```

Pydantic's architecture documentation explicitly says that `GenerateJsonSchema.generate()` receives
the model's core schema; the corresponding supported wrapper hooks are `__get_pydantic_core_schema__`
and `__get_pydantic_json_schema__`.

---

## 1. Why overriding `model_json_schema()` is the wrong pattern

Consider this tempting implementation:

```python
from typing import Any
from pydantic import BaseModel


class ScalarText(BaseModel):
    value: str

    @classmethod
    def model_json_schema(cls, **kwargs: Any) -> dict[str, Any]:
        print("ScalarText.model_json_schema called")
        return {"type": "string"}


class Container(BaseModel):
    item: ScalarText
```

This works only here:

```python
assert ScalarText.model_json_schema() == {"type": "string"}
```

It does **not** define how `ScalarText` is represented when Pydantic processes its type elsewhere:

```python
from pydantic import TypeAdapter
from pydantic.json_schema import models_json_schema

# ScalarText.model_json_schema() is not called by any of these:
Container.model_json_schema()
TypeAdapter(ScalarText).json_schema()
TypeAdapter(ScalarText | int).json_schema()
models_json_schema([(ScalarText, "validation")])
```

The bypasses are:

| Position                                | Is an overridden `ScalarText.model_json_schema()` called? | Why                                                                    |
| ----------------------------------------- | -----------------------------------------------------------: | ------------------------------------------------------------------------ |
| Direct `ScalarText.model_json_schema()` | Yes                                                       | Normal Python method dispatch calls the override.                      |
| Field of another model                  | No                                                        | The outer generator walks the nested model's core schema.              |
| Member of a union                       | No                                                        | The union's core-schema branches are translated directly.              |
| `models_json_schema()`                  | No                                                        | It gathers model core schemas and invokes one `GenerateJsonSchema` instance over them. |
| `TypeAdapter(ScalarText).json_schema()` | No                                                        | `TypeAdapter` creates/uses a core schema and feeds that to its schema generator. |
| `TypeAdapter(ScalarText \| int).json_schema()` | No                                                 | Same, starting from the union core schema.                             |

The public `models_json_schema()` API accepts `(model, mode)` pairs and produces definitions from
those models; it does not call each model's `model_json_schema()` method. Likewise, `TypeAdapter`
analyzes its supplied type into a core schema used for validation, serialization, and JSON Schema
generation.

This is not clearly highlighted as a warning in the main documentation, but it is a known footgun.
Pydantic issue **#7789, "Recursive `model_json_schema`"**, reports exactly this failure: an override
works directly but is not called when the model is part of another model.

A useful way to think about it is:

```python
# Conceptually similar to the direct entry point:
def model_json_schema(cls, ...):
    return GenerateJsonSchema(...).generate(
        cls.__pydantic_core_schema__,
        mode=mode,
    )
```

Overriding the outer function does not modify `cls.__pydantic_core_schema__` and does not install
anything into the core schema that another generator can discover.

---

## 2. The supported hooks and annotations

### `__get_pydantic_json_schema__`

Use this when validation is already correct, serialization is already correct, and only the JSON
Schema representation needs to be added, modified, or replaced.

```python
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema


class MyModel(...):
    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        ...
```

The usual wrapping pattern is:

```python
@classmethod
def __get_pydantic_json_schema__(
    cls,
    core_schema: CoreSchema,
    handler: GetJsonSchemaHandler,
) -> JsonSchemaValue:
    # Ask Pydantic/inner hooks for the normal schema.
    json_schema = handler(core_schema)

    # If that was {"$ref": ...}, obtain the actual definition before
    # trying to change properties on it.
    json_schema = handler.resolve_ref_schema(json_schema)

    json_schema["examples"] = [{"value": "example"}]
    return json_schema
```

`handler(core_schema)` invokes the next/default JSON Schema generator. `handler.resolve_ref_schema()`
turns a `$ref` result into the referenced definition so it can be mutated safely. This is the
documented model-customization pattern.

Important distinctions:

```python
# Add to the default:
schema = handler(core_schema)
schema = handler.resolve_ref_schema(schema)
schema["description"] = "..."
return schema
```

```python
# Completely replace the schema:
schema = handler(core_schema)
schema = handler.resolve_ref_schema(schema)
schema.clear()
schema.update(type="string")
return schema
```

You can also return a completely new dictionary, but resolving and mutating the generated definition
is often safer for models because the generator may already have created `$ref`/`$defs` bookkeeping
for it.

The handler also exposes its effective mode:

```python
if handler.mode == "serialization":
    ...
else:  # validation
    ...
```

The handler API documents both `mode` and `resolve_ref_schema()`.

### `__get_pydantic_core_schema__`

Use this when the actual validation or serialization graph needs customization: accepting a new
input representation; constructing a custom Python object; adding a validator that cannot be
expressed using ordinary decorators; installing custom serialization; defining a non-Pydantic
custom type.

```python
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class CustomType:
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        schema = handler(source_type)
        # Wrap or modify schema here.
        return schema
```

The core hook changes the schema used for **validation, serialization, and as the input to JSON
Schema generation**. The JSON hook changes only JSON Schema.

The `handler` is middleware-like: `handler(source_type)` asks the next metadata/type handler to
build that schema; `handler.generate_schema(OtherType)` builds an unrelated schema without applying
the current metadata context. For an arbitrary custom class that Pydantic otherwise does not
understand, calling `handler(source_type)` may fail; such a type often returns a custom
`core_schema.*` construction directly.

Prefer ordinary validators and serializers when they are sufficient. Core-schema construction is the
lowest-level public extension API and is more coupled to Pydantic internals.

### `WithJsonSchema`

`WithJsonSchema` is an annotation-local **replacement** for the base schema:

```python
from typing import Annotated
from pydantic import WithJsonSchema

SerializedString = Annotated[
    object,
    WithJsonSchema({"type": "string"}, mode="serialization"),
]
```

It is especially useful when you do not own the underlying type; one use site needs a different
schema; a type such as `Callable` has no normally generatable JSON Schema; or validation and
serialization need different schemas.

```python
from typing import Annotated
from pydantic import AfterValidator, PlainSerializer, TypeAdapter, WithJsonSchema

ScientificFloat = Annotated[
    float,
    AfterValidator(lambda x: round(x, 1)),
    PlainSerializer(lambda x: f"{x:.1e}", return_type=str),
    WithJsonSchema({"type": "string"}, mode="serialization"),
]

adapter = TypeAdapter(ScientificFloat)

assert adapter.json_schema(mode="validation") == {"type": "number"}
assert adapter.json_schema(mode="serialization") == {"type": "string"}
```

It replaces the whole base schema for that annotation, so required keys such as `"type"` must be
supplied. Pydantic's documentation recommends it over a custom JSON hook for simple annotation-local
replacements because it is less error-prone.

### `SkipJsonSchema`

Use it to omit a field or a union branch from generated JSON Schema. It affects schema generation,
not runtime validation or serialization.

```python
from typing import Annotated
from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema


class Model(BaseModel):
    visible: str
    internal: Annotated[str, SkipJsonSchema()]
```

### `Field(json_schema_extra=...)`

Use it for field-site metadata rather than changing the underlying type: `description`, `examples`,
vendor extensions; adding or overriding keywords at one field occurrence; or a callable that edits
the generated field schema.

```python
def remove_default(schema: dict) -> None:
    schema.pop("default", None)


class Model(BaseModel):
    count: int = Field(1, json_schema_extra=remove_default)
```

Since v2.9, dictionary-valued `json_schema_extra` metadata from nested `Annotated` declarations is
merged instead of one dictionary simply replacing another. Mixing callable and dictionary forms
compositionally is not supported.

### Subclassing `GenerateJsonSchema`

Use this for **generator-wide policy**: changing definition names or reference policy; adding
`$schema`; changing ordering; omitting every unrepresentable field; globally changing how a
core-schema kind is translated.

```python
from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue


class OpenAPIGenerator(GenerateJsonSchema):
    def generate(self, schema, mode="validation") -> JsonSchemaValue:
        result = super().generate(schema, mode=mode)
        result["$schema"] = self.schema_dialect
        return result

    def sort(
        self,
        value: JsonSchemaValue,
        parent_key: str | None = None,
    ) -> JsonSchemaValue:
        # Preserve insertion order.
        return value
```

The generator class must be supplied to the relevant entry point:

```python
models_json_schema(
    [(Model, "validation")],
    schema_generator=OpenAPIGenerator,
)
```

### Practical precedence

There is not one simple numeric precedence order; these mechanisms operate at different layers:

1. `__get_pydantic_core_schema__` determines the validation/serialization core graph.
2. `GenerateJsonSchema` translates that graph.
3. Type-owned `__get_pydantic_json_schema__` wraps/defaults that translation.
4. `Annotated` metadata such as `WithJsonSchema` can replace the base schema for that annotation.
5. `Field(...)` metadata customizes the field occurrence around the type schema.
6. Model `ConfigDict(json_schema_extra=...)` customizes the model definition.
7. A custom generator's final `generate()` post-processing can rewrite the completed document.

Because hooks and `Annotated` metadata are middleware-like, annotation order can matter. Also, any
later hook that calls `clear()` or returns an entirely new dictionary naturally discards earlier
additions.

---

## 3. A model whose wire representation is a scalar

Suppose the Python model stores a field but accepts and emits a plain string:

```python
from typing import Any

from pydantic import BaseModel, model_serializer, model_validator


class TextValue(BaseModel):
    value: str

    @model_validator(mode="before")
    @classmethod
    def accept_scalar(cls, data: Any) -> Any:
        if isinstance(data, cls):
            return data
        if isinstance(data, str):
            return {"value": data}
        return data

    @model_serializer(mode="plain", return_type=str)
    def serialize_scalar(self) -> str:
        return self.value
```

Runtime behavior:

```python
v = TextValue.model_validate("hello")

assert v.value == "hello"
assert v.model_dump() == "hello"
assert v.model_dump_json() == '"hello"'
```

Without customization, the default **validation** schema is based principally on the model's
object-shaped core schema. A before model validator's arbitrary input transformation is not
automatically inferred, so it ordinarily describes:

```json
{
  "type": "object",
  "properties": {
    "value": {"type": "string"}
  }
}
```

The model serializer's explicit `return_type=str` gives Pydantic information that can make the
**serialization** schema scalar, but it does not rewrite the validation schema.

### Canonical scalar schema in both modes

If the public wire contract is deliberately "always a string" and object input is merely an
internal/backward-compatibility convenience, install the schema on the model type itself:

```python
    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        schema = handler(core_schema)
        schema = handler.resolve_ref_schema(schema)

        # Mutate the actual definition, not merely a {"$ref": ...} wrapper.
        schema.clear()
        schema.update(
            type="string",
            title=cls.__name__,
        )
        return schema
```

That hook is part of the type's schema metadata, so it is honored in all relevant positions: direct
call, field of another model, union member, `TypeAdapter(...)`, and `models_json_schema()`.

This is the direct answer to the original problem: **put the customization in
`__get_pydantic_json_schema__`, not in `model_json_schema()`**.

### Truthful input and output schemas

If dict input is an intentional public API form, validation and serialization should differ:

```python
    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        generated = handler(core_schema)
        target = handler.resolve_ref_schema(generated)

        if handler.mode == "serialization":
            replacement: JsonSchemaValue = {
                "title": cls.__name__,
                "type": "string",
            }
        else:
            # The normal validation schema is the accepted object form.
            object_schema = deepcopy(target)
            replacement = {
                "title": cls.__name__,
                "anyOf": [
                    {"type": "string"},
                    object_schema,
                ],
            }

        target.clear()
        target.update(replacement)
        return target
```

A pre-existing `TextValue` Python instance is not a JSON wire representation and therefore should
not be added to JSON Schema.

---

## 4. Validation versus serialization schemas

Pydantic supports two modes — `validation` describes accepted input, `serialization` describes
emitted output:

```python
TextValue.model_json_schema(mode="validation")
TextValue.model_json_schema(mode="serialization")

TypeAdapter(TextValue).json_schema(mode="validation")
TypeAdapter(TextValue).json_schema(mode="serialization")
```

This matters for serializers, computed fields, `Json[T]`, `Decimal`, defaults, and any type where
accepted input differs from serialized output.

### `json_schema_mode_override`

This is a **model config option**, not a parameter of `models_json_schema()`:

```python
class InputOnlyModel(BaseModel):
    model_config = ConfigDict(
        json_schema_mode_override="validation",
    )
```

It forces that model to use the configured mode even if a caller requests the other mode. It is
useful when a framework asks for both modes but you intentionally want one shared representation. It
also prevents separate `-Input` and `-Output` definitions because both requests resolve to the same
effective mode. It was introduced in v2.4. Do **not** set it if the input and output really differ
and you want accurate OpenAPI.

### `json_schema_input_type`

This records input accepted by a *before*, *plain*, or *wrap* validator.

```python
class Model(BaseModel):
    value: str

    @field_validator(
        "value",
        mode="before",
        json_schema_input_type=str | int,
    )
    @classmethod
    def stringify_int(cls, value: Any) -> Any:
        if isinstance(value, int):
            return str(value)
        return value
```

Validation schema:

```json
{
  "anyOf": [
    {"type": "string"},
    {"type": "integer"}
  ]
}
```

The same argument exists on `BeforeValidator` and `PlainValidator`. For a `PlainValidator`, the
default input type is effectively `Any` if no `json_schema_input_type` is supplied, because the inner
validation schema is bypassed. These input-type annotations affect only validation-mode JSON Schema.

#### Important correction: `model_validator` does not support it

Through Pydantic 2.13, `@model_validator` has only the `mode` argument. It does **not** accept
`json_schema_input_type`. Therefore, for a whole-model before validator such as a scalar wrapper:

- describe the extra input in `__get_pydantic_json_schema__`; or
- implement a custom core schema whose validation branch explicitly models the union of inputs.

For this use case, the JSON hook is normally much simpler.

### Generating both input and output schemas

For a hand-written OpenAPI generator, generate both modes in the **same** `models_json_schema()`
call:

```python
roots, definitions_document = models_json_schema(
    [
        (TextValue, "validation"),
        (TextValue, "serialization"),
        (Envelope, "validation"),
        (Envelope, "serialization"),
    ],
    ref_template="#/components/schemas/{model}",
)

text_input = roots[(TextValue, "validation")]
text_output = roots[(TextValue, "serialization")]
```

Generating the two modes together lets Pydantic detect when the same model needs distinct
definitions and assign mode-specific references, ordinarily with `-Input` and `-Output` suffixes.

#### FastAPI's approach

FastAPI defaults to `FastAPI(separate_input_output_schemas=True)`, exposing components such as
`Item-Input` and `Item-Output`. The input component describes request validation, while the output
component describes response serialization. The option defaults to `True` and was added in FastAPI
0.102.0.

That is also the recommended design for a hand-rolled OpenAPI 3.1 generator:

1. collect request models as `validation`;
2. collect response models as `serialization`;
3. pass all pairs to one `models_json_schema()` invocation;
4. preserve distinct components whenever the generated schemas differ;
5. only force one mode with `json_schema_mode_override` if the API intentionally has one shared contract.

---

## 5. Inheritance of `__get_pydantic_json_schema__`

The hook is an ordinary inherited classmethod, so a base-class hook affects every subclass.

Extending the base behavior:

```python
class ConstrainedChild(ScalarBase):
    value: str

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = super().__get_pydantic_json_schema__(core_schema, handler)
        schema = handler.resolve_ref_schema(schema)
        schema["minLength"] = 1
        return schema
```

Bypassing the base customization — if the subclass should return to Pydantic's normal object schema,
do not call the customized `super()` implementation:

```python
class ObjectChild(ScalarBase):
    value: str
    extra: int

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        # Invoke the underlying/default generation directly.
        return handler(core_schema)
```

That is cleaner than trying to reverse a base hook that has already called `clear()`.

### Inheritance gotchas

1. **The method applies to all subclasses.** If only some subclasses are scalar, put the hook on a
   narrower intermediate base or override it explicitly.
2. **Use `cls`, not a hard-coded base class** — e.g. `schema["title"] = cls.__name__`.
3. **Resolve references before mutating the definition.** A nested or multiply used subclass may
   initially produce only `{"$ref": "#/$defs/Child"}`; mutating that wrapper does not necessarily
   alter the target definition. Use `handler.resolve_ref_schema()`.
4. **Do not manually assume `$defs` names.** Generic specialization, duplicate class names, modes,
   and custom generators can all change definition names.
5. **`model_config` is inherited/merged separately.** If the hook replaces the schema with `clear()`,
   previously generated titles, descriptions, examples, or config extras may be discarded; copy back
   anything that should survive.
6. **Rebuild after runtime monkey-patching** — `Child.model_rebuild(force=True)`.

---

## 6. Relevant version changes and issues

| Version / tracker  | Relevant change                                                                                     |
| -------------------- | ----------------------------------------------------------------------------------------------------- |
| Pydantic v2 generally | `__modify_schema__` was removed; `__get_pydantic_json_schema__` is the supported replacement.       |
| Issue #7789        | Records the exact nested-model failure caused by overriding `model_json_schema()`; closed as a question rather than changing recursive dispatch. |
| v2.9               | Added `json_schema_input_type` support for validators; merged dictionary-valued `json_schema_extra`; removed old `allOf` reference workarounds and fixed several validation/serialization schema cases. |
| v2.10              | Made `GenerateJsonSchema.sort()` public and fixed several reference, serializer, and `json_schema_input_type` schema-generation cases. |
| v2.11              | Added easier customization of default inclusion and fixed traversal of `function-before` schemas and referenceable schemas carrying JSON metadata. |
| v2.12              | Added the `union_format` argument to JSON Schema entry points, supporting `any_of` or primitive type arrays where possible. |
| v2.13              | Fixed nested-model schema deduplication and preserved additional `RootModel` core metadata; it did not replace the hook architecture described above. |
| Current 2.13 line  | The latest listed 2.13 patch is 2.13.4.                                                             |

---

## Key sources

- Pydantic — JSON Schema concepts: https://docs.pydantic.dev/latest/concepts/json_schema/
- Pydantic — `json_schema.md` in-repo: https://github.com/pydantic/pydantic/blob/main/docs/concepts/json_schema.md
- Pydantic — annotated handlers API (`GetJsonSchemaHandler.mode`, `resolve_ref_schema`): https://docs.pydantic.dev/latest/api/annotated_handlers/
- Pydantic — architecture / internals: https://docs.pydantic.dev/latest/architecture/
- Pydantic — custom types: https://docs.pydantic.dev/latest/concepts/types/
- Pydantic — validators (`json_schema_input_type`): https://docs.pydantic.dev/latest/concepts/validators/
- Pydantic issue #7789, "Recursive `model_json_schema`": https://github.com/pydantic/pydantic/issues/7789
- Pydantic HISTORY.md: https://github.com/pydantic/pydantic/blob/main/HISTORY.md
- FastAPI — separate OpenAPI schemas for input and output: https://fastapi.tiangolo.com/how-to/separate-openapi-schemas/
- FastAPI — `separate_input_output_schemas` PR: https://github.com/fastapi/fastapi/pull/10145
