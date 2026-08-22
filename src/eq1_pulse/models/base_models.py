"""Base Pydantic models used throughout the package.

These models provide a foundation for creating more complex data structures
and ensure consistency in validation and serialization.

Inheriting from these models ensures consistent behavior across the codebase.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from typing import TYPE_CHECKING, Any, Literal, Self, get_args

from pydantic import BaseModel, ConfigDict, GetJsonSchemaHandler, RootModel, TypeAdapter, model_serializer
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, PydanticUndefinedType

from .arithmetic import get_unit_value_field_name_and_type, parse_unit_suffixed_value

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


__all__ = (
    "FrozenLeanModel",
    "FrozenModel",
    "FrozenWrappedValueModel",
    "LeanModel",
    "NoExtrasModel",
    "WrappedValueModel",
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


def field_json_schemas(cls: type[BaseModel], handler: GetJsonSchemaHandler) -> dict[str, JsonSchemaValue]:
    """Build each of *cls*'s fields' own JSON schema from its annotation.

    This is independent of *cls*'s ``model_serializer``: a plain-mode ``@model_serializer`` with no
    declared ``return_type`` gives pydantic nothing to derive a serialization-mode schema from, so
    ``handler(core_schema)`` collapses to ``{}`` in that mode regardless of what the fields actually
    contain. Schema hooks that describe the serializer's output in terms of the underlying fields
    (unwrapping, as :class:`~.reference_types.Reference` does) build it from the field annotations
    directly instead, through this function.

    Reusing *handler* rather than a fresh :class:`~pydantic.TypeAdapter` schema generation keeps the
    result registered in the same ``$defs``/``components.schemas`` collection as the rest of the
    document, so shared field types are not duplicated under a second name.

    :param cls: the model whose fields to build schemas for.
    :param handler: the handler producing the default JSON schema, reused so refs land in the same
        ``$defs`` collection as the rest of the document.
    :return: a mapping of field name to that field's own JSON schema.
    """
    return {name: handler(TypeAdapter(field.annotation).core_schema) for name, field in cls.model_fields.items()}


def _find_model_schema(core_schema: CoreSchema) -> dict[str, Any]:
    """Find the ``model`` core schema nested inside *core_schema*.

    A model's core schema is wrapped in one "model" layer per ``@model_validator``/``@model_serializer``
    decorator and per generic parameterization, each nesting the next schema one level deeper under
    its own ``schema`` key. This walks down through them to the one actual ``model`` schema.

    :param core_schema: a model's core schema, however many wrapper layers deep.
    :return: the ``model`` core schema.
    :raises KeyError: if no ``model`` schema is found.
    """
    schema: Any = core_schema
    while isinstance(schema, dict):
        if schema.get("type") == "model":
            return schema
        schema = schema.get("schema")

    raise KeyError("no model schema found")


class WrappedValueModel(RootModel[Any]):
    """A :class:`~pydantic.RootModel` wrapping a single value, typically a quantity's unit model.

    The wrapped value *is* the wire form, in both directions and in both schema modes: there is no
    ``{"value": ...}`` object to unwrap and nothing to describe by hand. Subclasses narrow
    :attr:`root` to the union of units they accept.

    Unlike the rest of the hierarchy here this does not descend from :class:`NoExtrasModel`:
    pydantic rejects ``extra`` on a root model, which has no field namespace for an extra key to
    land in. The unit models it wraps are ordinary :class:`FrozenModel` subclasses, and it is
    their ``extra="forbid"`` that makes each one's single key exclusive.
    """

    root: Any

    def __repr__(self):  # noqa: D105
        return f"{self.__class__.__name__}({', '.join(k + '=' + repr(v) for k, v in self.model_dump().items())})"

    def __init__(self, *args, **kwargs):
        """Initialize the WrappedValueModel.

        Accepts either keyword arguments naming a unit (``Duration(us=10)``), or a single
        positional argument in one of the authoring forms: the literal ``0``, a
        ``"<number><unit>"`` string (``Duration("10us")``), or an already-built unit model.

        A positional *number* other than ``0`` is deliberately not accepted: with no unit
        attached, ``Duration(5)`` reads as "5" but silently means 5 seconds, and ``Amplitude(1)``
        silently means 1 Volt. 0 is exempt because it is the one value that means the same thing
        in every unit.

        These are authoring conveniences, not wire forms, and they stay that way because pydantic
        routes only a *mapping* input through a custom ``__init__``. A bare ``0``, a string or a
        unit model reaches root validation directly, never here -- and root validation takes the
        ``{unit: number}`` object and nothing else. What you can write is therefore wider than
        what the wire carries, and the schema remains the truth about the latter.

        :raises TypeError: If more than one positional argument is given, or a
            positional argument is combined with keyword arguments
        :raises ValueError: If the single positional argument is not one of the authoring forms
        """
        if args:
            if len(args) != 1:
                raise TypeError(f"expected at most 1 positional argument, got {len(args)}")
            if kwargs:
                raise TypeError("cannot combine a positional argument with keyword arguments")
            super().__init__(self._authoring_form(args[0]))
            return

        super().__init__(**kwargs)

    @classmethod
    def _authoring_form(cls, value: Any) -> Any:
        """Map a single positional constructor argument to the canonical wire form.

        :param value: The positional argument as given.
        :return: ``value`` itself if it is already canonical, or the ``{unit: number}`` object it
            denotes.
        :raises ValueError: If *value* is a number other than ``0``, or a string that does not
            name one of :meth:`_unit_classes`' units.
        """
        if isinstance(value, str):
            return parse_unit_suffixed_value(value, cls._unit_classes())
        if value == 0:
            return {cls._zero_unit(): 0}
        if isinstance(value, BaseModel | Mapping):
            return value

        raise ValueError(
            f"{value!r} is not a valid positional argument for {cls.__name__}(); "
            f"only the literal 0 is accepted positionally. Use a keyword argument instead, "
            f"e.g. {cls.__name__}({cls._zero_unit()}={value!r})."
        )

    @classmethod
    def parse(cls, text: str) -> Self:
        """Read a ``"<number><unit>"`` string as this quantity, e.g. ``Duration.parse("10us")``.

        **This is not a wire form.** ``model_validate`` takes the ``{unit: number}`` object and
        nothing else, in either direction; the suffixed string is an authoring convenience, and
        this method is where it is written down. The units it accepts are the ones :attr:`root`
        declares, read from the same registry :class:`~.units.UnitDiscriminator` reads.

        :param text: The string to read, e.g. ``"10us"`` or ``"5 GHz"``.
        :return: The quantity *text* denotes.
        :raises ValueError: If *text* is not a number followed by one of this quantity's units,
            or the result fails this quantity's own validation.
        """
        return cls.model_validate(parse_unit_suffixed_value(text, cls._unit_classes()))

    @classmethod
    @cache
    def _unit_classes(cls) -> tuple[type, ...]:
        """The unit models :attr:`root` accepts, in the order the subclass declares them.

        :return: The members of the narrowed ``root`` union, empty for an unnarrowed base.
        """
        return get_args(cls.model_fields["root"].annotation)

    @classmethod
    def _zero_unit(cls) -> str:
        """The unit a bare ``0`` is stored in: the first one :attr:`root` declares.

        Zero means the same thing in every unit, so which one it is stored in is a presentation
        choice, and the first declared unit is each quantity's base unit -- seconds, degrees,
        volts, hertz. Deriving it means a quantity declares its units once and nowhere else.

        :return: The name of the first declared unit's value field.
        :raises IndexError: If called on a base that has not narrowed ``root`` to a unit union.
        """
        return get_unit_value_field_name_and_type(cls._unit_classes()[0])[0]


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
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        """Rebuild the serialization-mode schema as if there were no custom serializer at all.

        :meth:`_wrap_serializer` is a plain ``@model_serializer(mode="wrap")`` with no declared
        ``return_type``, so ``handler(core_schema)`` has nothing to derive an output schema from
        and collapses to ``{}`` in serialization mode. Validation mode is untouched.

        Eliding a field that equals its default does not change what the schema says -- a
        defaulted field is already optional in both modes -- so the rebuilt schema is the
        ordinary object schema pydantic would have generated with no ``model_serializer`` present,
        not an attempt to encode the elision. That means the same ``title``, ``description``,
        ``additionalProperties`` and per-field ``title`` entries validation mode carries, built by
        the same code that builds them there: ``handler`` wraps the very
        :class:`~pydantic.json_schema.GenerateJsonSchema` instance running this document's whole
        generation pass, reachable via its (undocumented but stable) ``generate_json_schema``
        attribute, and its ``model_schema`` method is what every plain model's object schema
        already goes through -- called here directly, bypassing the hook dispatch that would
        otherwise recurse back into this very method.

        :param core_schema: the core schema the JSON schema is generated from.
        :param handler: the handler producing the default JSON schema.
        :return: the JSON schema, rebuilt from the field annotations in serialization mode.
        """
        if handler.mode != "serialization":
            return handler(core_schema)

        generator = handler.generate_json_schema  # type: ignore[attr-defined]
        return generator.model_schema(_find_model_schema(core_schema))  # type: ignore[no-any-return]

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


class FrozenWrappedValueModel(WrappedValueModel):
    """A :class:`WrappedValueModel` that is also frozen.

    Frozen by configuration rather than by inheriting :class:`FrozenModel`: the latter carries
    ``extra="forbid"``, which pydantic rejects on a root model.
    """

    model_config = ConfigDict(frozen=True)


class FrozenLeanModel(LeanModel, FrozenModel):
    """A frozen model that is also a lean model."""

    pass
