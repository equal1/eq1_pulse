"""Base Pydantic models used throughout the package.

These models provide a foundation for creating more complex data structures
and ensure consistency in validation and serialization.

Inheriting from these models ensures consistent behavior across the codebase.
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING, Any, Final, Literal, cast, get_args, override

from pydantic import BaseModel, ConfigDict, TypeAdapter, model_serializer, model_validator
from pydantic.json_schema import DEFAULT_REF_TEMPLATE, GenerateJsonSchema, JsonSchemaMode
from pydantic_core import PydanticUndefinedType

if TYPE_CHECKING:
    from pydantic.config import ExtraValues
    from pydantic.fields import FieldInfo


__all__ = (
    "FrozenLeanModel",
    "FrozenModel",
    "FrozenWrappedValueModel",
    "LeanModel",
    "NoExtrasModel",
    "WrappedValueModel",
    "WrappedValueOrZeroModel",
)


class NoExtrasModel(BaseModel):
    """A :obj:`pydantic.BaseModel` that disallows extra fields in the input data."""

    if TYPE_CHECKING:

        def __init__(self, *args, **kwargs):
            """"""  # noqa: D419

    model_config = ConfigDict(extra="forbid")


class FrozenModel(NoExtrasModel):
    """A :class:`NoExtrasModel` that is immutable (frozen) after creation."""

    if TYPE_CHECKING:

        def __init__(self, *args, **kwargs):
            """"""  # noqa: D419

    model_config = ConfigDict(frozen=True)


class WrappedValueModel(NoExtrasModel):
    """A :class:`NoExtrasModel` that wraps a single value in a field named 'value'."""

    value: Any

    @model_validator(mode="before")
    @classmethod
    def _wrap_validator(cls, data: Any) -> Any:
        return {"value": data}

    @model_serializer
    def _wrap_serializer(self) -> Any:
        return self.value

    def __repr__(self):  # noqa: D105
        return f"{self.__class__.__name__}({', '.join(k + '=' + repr(v) for k, v in self.model_dump().items())})"

    def __init__(self, *args, **kwargs):
        """Initialize the WrappedValueModel.

        Accepts either a single positional argument representing the value
        or keyword arguments corresponding to the model fields.
        """
        if args and len(args) == 1 and not kwargs:
            super().__init__(**{get_unit_of_zero(self.__class__): args[0]})
        else:
            super().__init__(*args, **kwargs)

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = "validation",
        *,
        union_format: Literal["any_of", "primitive_type_array"] = "any_of",
    ) -> dict[str, Any]:
        """Generate the JSON schema for the model, adjusting for wrapped value representation.

        :see: :obj:`pydantic.BaseModel.model_json_schema` for more details.
        """
        base_schema = super().model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
            union_format=union_format,
        )

        if (properties := base_schema.get("properties")) is not None and (
            len(properties) == 1
            and (value_schema := properties.get("value")) is not None
            and isinstance(value_schema, dict)
        ):
            return cast(
                dict[str, Any],
                value_schema | {"title": title} if (title := base_schema.get("title")) is not None else value_schema,
            )

        return base_schema


class LeanModel(NoExtrasModel):
    """A :class:`NoExtrasModel` which doesn't serialize the default values, except the first literal field.

    The first literal field should only have one possible value (to be considered the discriminator).
    """

    @model_serializer(mode="wrap")
    def _wrap_serializer(self, wrapped) -> Any:
        from numpy import array_equal, ndarray

        def is_eq(attribute_value, default_value):
            match default_value:
                case PydanticUndefinedType():
                    return False
                case None:
                    return attribute_value is None
                case ndarray():
                    return array_equal(attribute_value, default_value)
                case _:
                    return attribute_value == default_value

        return {k: v for k, v in wrapped(self).items() if not is_eq(getattr(self, k), self._default_value_of(k))}

    @classmethod
    @cache
    def _non_discriminator_fields(cls) -> dict[str, FieldInfo]:
        fields = cls.model_fields
        discriminator_name, first_field = next(iter(fields.items()))
        lit: Any = first_field.annotation
        if isinstance(lit, type(Literal[Any])):  # noqa: SIM102
            if len(_args := get_args(lit)) == 1:
                fields = dict(fields)
                del fields[discriminator_name]
        return fields

    @classmethod
    @cache
    def _default_value_of(cls, field_name: str) -> Any:
        fields = cls._non_discriminator_fields()
        return fields[field_name].get_default(call_default_factory=True) if field_name in fields else None


class FrozenWrappedValueModel(WrappedValueModel, FrozenModel):
    """A :class:`WrappedValueModel` that is also frozen."""

    pass


class FrozenLeanModel(LeanModel, FrozenModel):
    """A frozen model that is also a lean model."""

    pass


_LiteralZeroTypeAdapter: Final[TypeAdapter[Literal[0]]] = TypeAdapter(Literal[0])

_unit_of_zero: dict[type, str] = {}


def register_unit_of_zero(unit: str):
    """Register a unit string for the zero value of a specific type.

    This decorator is used to provide appropriate handling of the value 0.

    :param unit: The unit string associated with the zero value of the type.

    :return: A decorator function that registers the unit for the decorated class.

    Example:

    .. code-block:: python

        @register_unit_of_zero("m")
        class Distance(WrappedValueOrZeroModel):
            value: Meters | Kilometers | Millimeters
    """

    def decorator(cls: type) -> type:
        _unit_of_zero[cls] = unit
        return cls

    return decorator


def get_unit_of_zero(type_: type) -> str:
    """Get the registered unit string for the zero value of a specific type.

    :param type_: The type for which to get the registered unit.
    :return: The unit string if registered, otherwise None.
    """
    if type_ in _unit_of_zero:
        return _unit_of_zero[type_]
    for base_type in type_.__mro__:
        if unit := _unit_of_zero.get(base_type):
            _unit_of_zero[type_] = unit
            return unit
    raise KeyError(f"No unit registered for type {type_}")


class WrappedValueOrZeroModel(WrappedValueModel):
    """A WrappedValueModel that also accepts the literal integer 0 as valid input.

    This is a mixin class and will not treat 0 in the ``__init__`` method specially.
    It is the responsibility of the derived class to handle that.
    """

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = "validation",
        *,
        union_format: Literal["any_of"] | Literal["primitive_type_array"] = "any_of",
    ) -> dict[str, Any]:
        """Generate the JSON schema for the model, adjusting for wrapped value or zero representation.

        :see: :obj:`pydantic.BaseModel.model_json_schema` for more details.
        :see: :obj:`WrappedValueModel.model_json_schema` for details on wrapped value handling.
        """
        base_schema = super().model_json_schema(
            by_alias, ref_template, schema_generator, mode, union_format=union_format
        )

        if "anyOf" in base_schema:
            any_of = base_schema["anyOf"]
            if isinstance(any_of, list):
                zero_schema = _LiteralZeroTypeAdapter.json_schema(
                    by_alias=by_alias,
                    ref_template=ref_template,
                    schema_generator=schema_generator,
                    mode=mode,
                    union_format=union_format,
                )
                any_of.insert(0, zero_schema)

        return base_schema

    @model_validator(mode="before")
    @classmethod
    def _model_validate(cls, value: Any) -> Any:
        if value == 0:
            return {get_unit_of_zero(cls): 0}

        return value

    @classmethod
    @override
    def model_validate_strings(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        extra: ExtraValues | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Any:
        if isinstance(obj, str) and obj.strip() == "0":
            obj = {get_unit_of_zero(cls): 0}

        return super().model_validate_strings(
            obj,
            strict=strict,
            extra=extra,
            context=context,
            by_alias=by_alias,
            by_name=by_name,
        )
