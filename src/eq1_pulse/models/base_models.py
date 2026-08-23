"""Base Pydantic models used throughout the package.

These models provide a foundation for creating more complex data structures
and ensure consistency in validation and serialization.

Inheriting from these models ensures consistent behavior across the codebase.
"""

from __future__ import annotations

import contextvars
from collections.abc import Mapping
from functools import cache
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    GetJsonSchemaHandler,
    RootModel,
    TypeAdapter,
    ValidatorFunctionWrapHandler,
    model_serializer,
    model_validator,
)
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import CoreSchema, PydanticUndefinedType

from .arithmetic import get_unit_value_field_name_and_type, parse_unit_suffixed_value

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


__all__ = (
    "FrozenLeanModel",
    "FrozenModel",
    "FrozenWrappedValueModel",
    "LeanModel",
    "NestedWireModel",
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
        return self._elide_defaults(wrapped(self))

    def _elide_defaults(self, dumped: dict[str, Any]) -> dict[str, Any]:
        """Drop from *dumped* every entry whose value equals its field's default.

        Split out of :meth:`_wrap_serializer` so a subclass that reshapes the wire form --
        :class:`NestedWireModel` -- reuses the elision instead of re-deriving it. For a plain
        :class:`LeanModel` this *is* what :meth:`_wrap_serializer` returns.

        :param dumped: the fields as pydantic's own serializer produced them.
        :return: *dumped* without the entries equal to their field's default.
        """
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

        return {k: v for k, v in dumped.items() if not is_eq(getattr(self, k), self._default_value_of(k))}

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


_wire_serializing: contextvars.ContextVar[frozenset[int]] = contextvars.ContextVar(
    "_wire_serializing", default=frozenset()
)
"""Object ids of :class:`NestedWireModel` instances whose :meth:`~NestedWireModel._wrap_serializer`
is currently on the call stack.

Works around a pydantic-core defect in recursive models with a ``@model_serializer(mode="wrap")``
(upstream `pydantic#11812 <https://github.com/pydantic/pydantic/issues/11812>`_ and the related
`pydantic#11563 <https://github.com/pydantic/pydantic/issues/11563>`_): when such a model is
reached *through another model's field* and the model's own schema is also self-referential --
exactly the shape :data:`~.expressions.Expression` has, recursing directly through operand fields
with no intervening container -- pydantic-core inserts the wrap serializer twice in series for that
outer reference. The spurious second call receives the *same* instance, not its sibling operands, so
it is detectable by object identity and made a no-op: only the outer (first) call performs the tag
lift, the inner one passes the plain field dump straight through.
"""


class NestedWireModel(LeanModel):
    """A :class:`LeanModel` whose wire form is ``{tag: payload}`` rather than a flat object.

    A plain :class:`LeanModel` publishes its discriminator as a sibling of the data --
    ``{"op_type": "play", "channel": "q0_drive", ...}``. A ``NestedWireModel`` lifts it to the key
    of a single-entry object instead -- ``{"play": {"channel": "q0_drive", ...}}`` -- so the sole
    key answers "what is this?", and the payload it points at is a closed record of real fields
    only, with the discriminator no longer occupying a slot in the same namespace as the data.

    This is **opt-in, and inert until configured.** A subclass that leaves
    :attr:`_wire_tag_source_` unset -- or names a field whose tag cannot be read statically, as an
    abstract base whose ``op_type`` is not yet a concrete literal does -- behaves exactly like
    :class:`LeanModel`, in both directions and in both schema modes.

    Two independent knobs configure the wire form, and they are orthogonal on purpose -- where the
    tag comes from and whether the tag source survives into the payload are separate questions, and
    every combination of them is wanted by some model:

    :attr:`_wire_tag_from_` -- where the tag comes from
        ``"value"`` takes the tag from the tag-source field's **value**. The field must be
        annotated with a single-valued :obj:`~typing.Literal` string, which is what makes the tag
        statically known -- the JSON schema has to *name* the key, so a tag that only exists at
        runtime is no use. Operations use this: ``op_type: Literal["play"]`` gives
        ``{"play": {...}}``.

        ``"name"`` takes the tag from the field's **name**. Expression nodes use this, because
        operator *values* overlap between node types -- ``"-"`` is both unary and binary -- so only
        the field name tells them apart.

    :attr:`_wire_payload_key_` -- whether the tag source's value is kept
        :obj:`None` drops it; a string keeps it under that key. Dropping is right when the value
        carries nothing the tag does not already carry, which is the case for a single-valued
        operator: ``not_op: Literal["not"]`` with ``_wire_tag_from_ = "name"`` gives
        ``{"not_op": {"rhs": ...}}``, not a redundant ``{"op": "not"}`` inside it.

    So ``unary_op: Literal["-"]`` with ``_wire_tag_from_ = "name"`` and
    ``_wire_payload_key_ = "op"`` gives ``{"unary_op": {"op": "-", "rhs": ...}}``, while the same
    field with ``_wire_tag_from_ = "value"`` would give ``{"-": {"rhs": ...}}``.

    An empty payload serializes as the bare tag string, ``"barrier"`` rather than
    ``{"barrier": {}}``: the object carries nothing the key does not already carry. That form is
    given only to a class that can *statically* reach an empty payload, meaning every field other
    than the tag source has a default. A class with a required field never grows the alternate
    form, neither in its serializer nor in its schema.

    Note:
        The validator accepts the nested form, and the bare tag string where that applies.
        Anything else -- keyword construction from Python, an already-built instance -- passes
        through untouched, so ``Play(channel=..., pulse=...)`` keeps working; pydantic routes
        ``__init__`` through this same validator, so a stricter rule here would outlaw ordinary
        construction. Rejecting the superseded *flat wire form* is therefore not done here: it is
        the job of the discriminated union that selects this class, which reads the sole key and
        finds no tag in a flat object.

    """

    _wire_tag_source_: ClassVar[str] = ""
    """The field the tag is read from. Empty means "not configured", and the model stays flat."""

    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "value"
    """Whether the tag is the tag-source field's value or its name. See the class docstring."""

    _wire_payload_key_: ClassVar[str | None] = None
    """The inner key the tag source's value is kept under, or :obj:`None` to drop it from the payload.

    Independent of :attr:`_wire_tag_from_`: a node may take its tag from the field name and still
    drop the value, which is what a single-valued operator wants. See the class docstring.
    """

    @classmethod
    @cache
    def _wire_tag(cls) -> str | None:
        """The sole key this model's wire object carries, if it is statically determined.

        :return: The tag, or :obj:`None` if this class is not configured for the nested form --
            in which case every hook below falls back to :class:`LeanModel`'s behaviour.
        """
        source = cls._wire_tag_source_
        if not source or source not in cls.model_fields:
            return None
        if cls._wire_tag_from_ == "name":
            return source

        lit: Any = cls.model_fields[source].annotation
        if isinstance(lit, type(Literal[Any])) and len(args := get_args(lit)) == 1 and isinstance(args[0], str):
            return args[0]
        return None

    @classmethod
    @cache
    def _wire_payload_can_be_empty(cls) -> bool:
        """Whether an instance of this class can reach an empty payload, and so take the bare-tag form.

        Read off the field declarations, not off any one instance: the bare-tag form is part of
        this class's schema or it is not, and a class with a required field must never grow it.
        A class keeping the tag source inside the payload always has at least that key, so it can
        never be empty.

        :return: :obj:`True` if every field other than the tag source has a default.
        """
        if cls._wire_payload_key_ is not None:
            return False
        source = cls._wire_tag_source_
        return all(not field.is_required() for name, field in cls.model_fields.items() if name != source)

    @classmethod
    @cache
    def _wire_tag_source_value(cls) -> Any:
        """The value the tag-source field takes, for a payload that does not carry it.

        When the tag *is* that value (:attr:`_wire_tag_from_` ``== "value"``) the tag is the
        answer. When the tag is the field's *name* instead, the value was dropped from the payload
        as redundant, and it is recovered from the field's sole :obj:`~typing.Literal` argument --
        which is the only case in which dropping it is legitimate, since a field with more than one
        possible value carries information the tag does not.

        :return: The value to restore the tag-source field to, or :obj:`None` if it cannot be read
            statically, in which case validation falls back to whatever default the field declares.
        """
        if cls._wire_tag_from_ == "value":
            return cls._wire_tag()

        lit: Any = cls.model_fields[cls._wire_tag_source_].annotation
        if isinstance(lit, type(Literal[Any])) and len(args := get_args(lit)) == 1:
            return args[0]
        return None

    @classmethod
    def _flatten_payload(cls, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Turn a wire payload into the flat field mapping pydantic already knows how to validate.

        :param payload: The object the tag pointed at.
        :return: The same entries, with the tag source restored as an ordinary field.
        """
        source = cls._wire_tag_source_
        payload_key = cls._wire_payload_key_
        if payload_key is None:
            source_value = cls._wire_tag_source_value()
            # A value that cannot be read statically is left out rather than written as None, so
            # the field's own default applies -- which is what :meth:`_wire_tag_source_value` says.
            return dict(payload) if source_value is None else {source: source_value, **payload}
        if payload_key not in payload:
            return dict(payload)
        return {source: payload[payload_key], **{k: v for k, v in payload.items() if k != payload_key}}

    @model_serializer(mode="wrap")
    def _wrap_serializer(self, wrapped) -> Any:
        key = id(self)
        in_progress = _wire_serializing.get()
        if key in in_progress:
            # The pydantic-core duplicate-call defect described at `_wire_serializing`: this is the
            # spurious inner invocation for the instance the outer call is already wrapping.
            return wrapped(self)

        token = _wire_serializing.set(in_progress | {key})
        try:
            return self._wrap_payload(wrapped)
        finally:
            _wire_serializing.reset(token)

    def _wrap_payload(self, wrapped) -> Any:
        payload = self._elide_defaults(wrapped(self))
        tag = self._wire_tag()
        if tag is None:
            return payload

        source = self._wire_tag_source_
        tag_value = payload.pop(source) if source in payload else getattr(self, source)
        if (payload_key := self._wire_payload_key_) is not None:
            return {tag: {payload_key: tag_value, **payload}}
        if not payload and self._wire_payload_can_be_empty():
            return tag
        return {tag: payload}

    @model_validator(mode="wrap")
    @classmethod
    def _unwrap_validator(cls, data: Any, handler: ValidatorFunctionWrapHandler) -> Any:
        """Flatten the ``{tag: payload}`` wire form back into the field set pydantic validates.

        Input that is not this class's wire form is handed to *handler* untouched -- see the note
        in the class docstring for why that is deliberate rather than lax.

        :param data: The value being validated.
        :param handler: The inner validator, called with the flattened field mapping.
        :return: The validated model.
        """
        tag = cls._wire_tag()
        if tag is None:
            return handler(data)

        if isinstance(data, str):
            if data == tag and cls._wire_payload_can_be_empty():
                # Restored through the same path the object form takes: when the tag is the field
                # *name* the tag source's value is its sole literal, not the tag itself.
                return handler(cls._flatten_payload({}))
            return handler(data)

        if isinstance(data, Mapping) and len(data) == 1 and next(iter(data)) == tag:
            payload = data[tag]
            if isinstance(payload, Mapping) and cls._wire_tag_source_ not in payload:
                return handler(cls._flatten_payload(payload))

        return handler(data)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        """Wrap the flat object schema :class:`LeanModel` builds in the single-key wire object.

        This runs identically in both schema modes: it reshapes whatever
        :meth:`LeanModel.__get_pydantic_json_schema__` returned, and that method has already made
        the two modes agree. Symmetry therefore holds by construction rather than by a second,
        parallel derivation that could drift from the first.

        :param core_schema: The core schema the JSON schema is generated from.
        :param handler: The handler producing the default JSON schema.
        :return: The single-key object schema, or the flat one if this class is not configured.
        """
        flat = super().__get_pydantic_json_schema__(core_schema, handler)
        tag = cls._wire_tag()
        return flat if tag is None else cls._nested_json_schema(flat, tag)

    @classmethod
    def _nested_json_schema(cls, flat: JsonSchemaValue, tag: str) -> JsonSchemaValue:
        """Reshape the flat object schema *flat* into the ``{tag: payload}`` wire object.

        ``title`` and ``description`` move to the outer schema, which is the one published under
        the model's name; the payload underneath keeps the field ``properties``, the ``required``
        list and the ``additionalProperties: false`` that make it a closed record. The tag source
        leaves ``properties`` altogether when the tag is its value, and is renamed to
        :attr:`_wire_payload_key_` when the tag is its name.

        :param flat: The object schema the model would publish without the wrap.
        :param tag: The sole key of the wire object.
        :return: The wrapped schema.
        """
        inner = dict(flat)
        outer: JsonSchemaValue = {key: inner.pop(key) for key in ("title", "description") if key in inner}

        source = cls._wire_tag_source_
        was_required = source in inner.get("required", ())
        properties = dict(inner.get("properties", {}))
        required = [name for name in inner.get("required", ()) if name != source]
        tag_schema = properties.pop(source, None)
        if (payload_key := cls._wire_payload_key_) is not None and tag_schema is not None:
            properties = {payload_key: cls._retitled(tag_schema, source, payload_key), **properties}
            if was_required:
                required.insert(0, payload_key)

        for key, value in (("properties", properties), ("required", required)):
            if value:
                inner[key] = value
            else:
                inner.pop(key, None)

        wrapped: JsonSchemaValue = {
            "type": "object",
            "additionalProperties": False,
            "properties": {tag: inner},
            "required": [tag],
        }
        if cls._wire_payload_can_be_empty():
            return {**outer, "anyOf": [wrapped, {"const": tag, "type": "string"}]}
        return {**outer, **wrapped}

    @staticmethod
    def _retitled(tag_schema: JsonSchemaValue, source: str, payload_key: str) -> JsonSchemaValue:
        """Re-derive the ``title`` pydantic generated for a tag source published under another key.

        Pydantic titles a property after the field it was generated from, so a tag source renamed
        to :attr:`_wire_payload_key_` would otherwise announce itself under a field name the wire
        form does not have -- ``{"op": {"const": "-", "title": "Unary Op"}}`` -- and a client
        generator driven off the published document would name that member after it. A title the
        model set deliberately says something the field name does not, and is left alone.

        :param tag_schema: The tag source's property schema.
        :param source: The field that schema was generated for.
        :param payload_key: The key it is published under instead.
        :return: The same schema, titled after *payload_key* if the title was pydantic's own.
        """
        titles = GenerateJsonSchema()
        if tag_schema.get("title") != titles.get_title_from_name(source):
            return tag_schema
        return {**tag_schema, "title": titles.get_title_from_name(payload_key)}


class FrozenWrappedValueModel(WrappedValueModel):
    """A :class:`WrappedValueModel` that is also frozen.

    Frozen by configuration rather than by inheriting :class:`FrozenModel`: the latter carries
    ``extra="forbid"``, which pydantic rejects on a root model.
    """

    model_config = ConfigDict(frozen=True)


class FrozenLeanModel(LeanModel, FrozenModel):
    """A frozen model that is also a lean model."""

    pass
