"""Base Pydantic models used throughout the package.

These models provide a foundation for creating more complex data structures
and ensure consistency in validation and serialization.

Inheriting from these models ensures consistent behavior across the codebase.
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING, Any, Final, Literal, Self, cast, get_args

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, model_serializer, model_validator
from pydantic.json_schema import DEFAULT_REF_TEMPLATE, GenerateJsonSchema, JsonSchemaMode
from pydantic_core import PydanticUndefinedType

if TYPE_CHECKING:
    from pydantic.config import ExtraValues
    from pydantic.fields import FieldInfo


class NoExtrasModel(BaseModel):
    """A :obj:`pydantic.BaseModel` that disallows extra fields in the input data."""

    if TYPE_CHECKING:

        def __init__(self, *args, **kwargs):
            """:meta private:"""  # noqa: D400

    model_config = ConfigDict(extra="forbid")


class FrozenModel(NoExtrasModel):
    """A :class:`NoExtrasModel` that is immutable (frozen) after creation."""

    if TYPE_CHECKING:

        def __init__(self, *args, **kwargs):
            """:meta private:"""  # noqa: D400

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

    def _apply_default_args_to_init_data(
        self, default_name: str, args: tuple[Any, ...], data: dict[str, Any]
    ) -> dict[str, Any]:
        match len(args):
            case 0:
                return data
            case 1:
                if default_name in data:
                    raise TypeError(f"duplicate parameter {default_name!r}")
                if "value" in data:
                    raise TypeError(f"duplicate parameter {'value'}")
                return data | {default_name: args[0]}
            case n:
                raise TypeError(f"expected at most 1 positional arguments after self, got {n}")

    def _apply_default_zero_args_to_init_data(
        self, default_name: str, args: tuple[Any, ...], data: dict[str, Any], *, zero=0
    ) -> dict[str, Any]:
        """
        Process positional arguments during initialization and apply default zero value if needed.

        This method handles the case where a single positional argument with value zero
        may be provided during initialization. If provided, it adds this value to the
        initialization data dictionary under the specified default name.

        :param default_name: The parameter name to use when adding the zero value to the data dictionary
        :param args: Positional arguments passed to the initialization method
        :param data: Dictionary of initialization data (typically from keyword arguments)
        :param zero: The expected value of the positional argument, defaults to 0

        :return: The updated initialization data dictionary

        :raises TypeError:
            If default_name or 'value' already exists in data, or if more than 1 positional argument
            is provided
        :raises ValueError: If the positional argument's value is not equal to the expected zero value
        """
        match len(args):
            case 0:
                return data
            case 1:
                if default_name in data:
                    raise TypeError(f"duplicate parameter {default_name!r}")
                if "value" in data:
                    raise TypeError(f"duplicate parameter {'value'}")
                if args[0] != zero:
                    raise ValueError(f"positional argument must be {zero}")
                return data | {default_name: zero}
            case n:
                raise TypeError(f"expected at most 1 positional arguments after self, got {n}")

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

    @classmethod
    def model_validate(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        extra: ExtraValues | None = None,
        from_attributes: bool | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        """Validate the input object, accepting literal 0 as valid input.

        The literal integer 0 is treated as a valid input and results in an instance
        of the class constructed with value 0. It's up to the derived class to handle
        this appropriately in its ``__init__`` method.

        :see: :obj:`pydantic.BaseModel.model_validate` for more details.
        """
        if obj == 0:
            return cls(0)  # type: ignore
        return super().model_validate(
            obj,
            strict=strict,
            extra=extra,
            from_attributes=from_attributes,
            context=context,
            by_alias=by_alias,
            by_name=by_name,
        )

    @classmethod
    def model_validate_json(
        cls,
        json_data: str | bytes | bytearray,
        *,
        strict: bool | None = None,
        extra: ExtraValues | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        """Validate the input JSON data, accepting literal 0 as valid input.

        The literal integer 0 is treated as a valid input and results in an instance
        of the class constructed with value 0. It's up to the derived class to handle
        this appropriately in its ``__init__`` method.
        """
        try:
            return super().model_validate_json(
                json_data,
                strict=strict,
                extra=extra,
                context=context,
                by_alias=by_alias,
                by_name=by_name,
            )
        except ValidationError as e:
            try:
                _LiteralZeroTypeAdapter.validate_json(
                    json_data,
                    strict=strict,
                    extra=extra,
                    context=context,
                    by_alias=by_alias,
                    by_name=by_name,
                )
            except ValidationError:
                raise e from None
            else:
                return cls(0)  # type: ignore

    @classmethod
    def model_validate_strings(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        extra: ExtraValues | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        """Validate the input string data, accepting literal 0 as valid input.

        The literal integer 0's string representation is treated as a valid input
        and results in an instance of the class constructed with value 0.
        It's up to the derived class to handle this appropriately in its ``__init__`` method.
        """
        try:
            return super().model_validate_strings(
                obj, strict=strict, extra=extra, context=context, by_alias=by_alias, by_name=by_name
            )
        except ValidationError as e:
            try:
                value = TypeAdapter(int).validate_strings(
                    obj,
                    strict=strict,
                    extra=extra,
                    context=context,
                    by_alias=by_alias,
                    by_name=by_name,
                )
            except ValidationError:
                pass
            else:
                if value == 0:
                    return cls(0)  # type: ignore
                e.add_note(f"parsed integer value {value} does not equal zero")
            raise e
