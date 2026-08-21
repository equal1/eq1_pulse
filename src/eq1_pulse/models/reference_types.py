"""Modules to provide representation of symbolic references.

Note:
    All reference classes inherit from :class:`Reference` and Pydantic's BaseModel for validation
    and serialization support.

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, TypedDict

from pydantic import BaseModel, GetJsonSchemaHandler, model_serializer, model_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, PydanticSerializationUnexpectedValue

from .base_models import field_json_schemas
from .identifier_str import ExternalSymbolStr, IdentifierStr

__all__ = (
    "ChannelRef",
    "ExtRefDict",
    "ExternalRef",
    "PulseRef",
    "Reference",
    "SymbolRef",
    "SymbolRefLike",
    "VariableRef",
)


class Reference(BaseModel):
    """Base class for all symbolic references.

    Descendants must only define a single field (the reference name), which is serialized directly.

    Note:
        A descendant that keeps the wrapped object form instead must set :attr:`_serializes_bare`
        to :obj:`False` *and* override :meth:`_wrap_serializer` to produce that form; see
        :class:`ExternalRef`. :meth:`__get_pydantic_json_schema__` already branches on
        :attr:`_serializes_bare`, so it needs no override. Declaring the flag without the serializer
        is rejected when the class is created — see :meth:`__pydantic_init_subclass__`.

    """

    _serializes_bare: ClassVar[bool] = True
    """Whether instances of this class serialize to their bare field value."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Enforce the invariants the serializer and the validator rely on.

        These are checked when the subclass is created, so a violation is an import-time error
        rather than a silently wrong wire format.

        :param kwargs: class keyword arguments, passed through to the base implementation.
        :raises TypeError: if the subclass does not define exactly one field, or if its
            :attr:`_serializes_bare` declaration disagrees with whether it overrides
            :meth:`_wrap_serializer`.
        """
        super().__pydantic_init_subclass__(**kwargs)

        if len(cls.model_fields) != 1:
            raise TypeError(
                f"{cls.__name__} must define exactly one field, got {len(cls.model_fields)}: "
                f"{list(cls.model_fields)}. A reference serializes to its single field."
            )

        overrides_serializer = cls._overrides_below_reference("_wrap_serializer")
        if cls._serializes_bare:
            if overrides_serializer:
                raise TypeError(
                    f"{cls.__name__} overrides _wrap_serializer but leaves _serializes_bare True. "
                    f"A union serializer would then offer values of other reference classes to it "
                    f"and accept the result; set _serializes_bare = False."
                )
        elif not overrides_serializer:
            raise TypeError(
                f"{cls.__name__} sets _serializes_bare = False but does not override "
                f"_wrap_serializer. The base implementation unwraps to the single field, which "
                f"contradicts the declaration."
            )

    @classmethod
    def _overrides_below_reference(cls, name: str) -> bool:
        """Whether *name* is provided by a class below :class:`Reference` in the MRO.

        :param name: the attribute to look for.
        :return: :obj:`True` if a descendant of :class:`Reference` defines it, :obj:`False` if it
            is inherited from :class:`Reference` itself.
        """
        for base in cls.__mro__:
            if base is Reference:
                break
            if name in base.__dict__:
                return True

        return False

    @classmethod
    def _first_field_name(cls) -> str:
        return next(iter(cls.model_fields))

    def __init__(self, *args, **data) -> None:
        """Create a reference.

        Accepts the type of the first field also as positional argument.
        """
        ff = self._first_field_name()
        assert len(args) in (0, 1)
        if len(args) == 1:
            assert ff not in data
            data[ff] = args[0]
        super().__init__(**data)

    @model_validator(mode="before")
    @classmethod
    def _wrap_validator(cls, data: Any) -> Any:
        return {cls._first_field_name(): data} if not isinstance(data, dict) else data

    @model_serializer
    def _wrap_serializer(self) -> Any:
        if not type(self)._serializes_bare:
            # A union serializer offers the value to each member in turn, and a plain model
            # serializer is called without an instance check -- so this may be a reference of a
            # class that serializes wrapped. Decline it, so the union tries the next member.
            raise PydanticSerializationUnexpectedValue(f"{type(self).__name__} does not serialize bare")

        return getattr(self, self._first_field_name())

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        """Describe the reference by :attr:`_serializes_bare`.

        A class that serializes bare (the default) accepts and describes both the bare value and
        the ``{"<field>": ...}`` object on input, per :meth:`_wrap_validator`, but only ever
        produces the bare value on output, per :meth:`_wrap_serializer`. A class that serializes
        wrapped (see :class:`ExternalRef`) keeps the object form in both directions; a bare string
        is still accepted by :meth:`_wrap_validator` for constructor convenience, but it is
        deliberately not advertised in the validation schema -- a bare string in a union always
        resolves to a bare-serializing reference, so advertising it here would describe an input
        this class never actually resolves from.

        :param core_schema: the core schema the JSON schema is generated from.
        :param handler: the handler producing the default JSON schema.
        :return: the JSON schema, describing whichever form :attr:`_serializes_bare` selects.
        """
        json_schema = handler(core_schema)
        target = handler.resolve_ref_schema(json_schema)

        if not cls.model_fields:
            # Reference itself declares no field to unwrap to.
            return json_schema

        if handler.mode == "serialization":
            # _wrap_serializer has no declared return_type, so handler(core_schema) has already
            # collapsed target to {} here; rebuild it from the field annotations instead.
            if cls._serializes_bare:
                replacement = dict(field_json_schemas(cls, handler)[cls._first_field_name()])
                if (title := target.get("title")) is not None:
                    replacement["title"] = title
                target.clear()
                target.update(replacement)
            else:
                target.update(
                    type="object",
                    properties=field_json_schemas(cls, handler),
                    required=list(cls.model_fields),
                )
            return json_schema

        if not cls._serializes_bare:
            # The default object schema already describes it; no bare form to add.
            return json_schema

        if not (properties := target.get("properties")):
            return json_schema

        bare_schema = dict(properties[cls._first_field_name()])
        title = target.pop("title", None)
        object_schema = dict(target)
        target.clear()
        target["anyOf"] = [bare_schema, object_schema]
        if title is not None:
            target["title"] = title

        return json_schema

    def __eq__(self, value):  # noqa: D105
        if not isinstance(value, Reference):
            first_field_value = getattr(self, self._first_field_name())
            return first_field_value == value

        return super().__eq__(value)

    def __req__(self, value):  # noqa: D105
        return self.__eq__(value)


class VariableRef(Reference):
    """Reference to a variable.

    Variables must be declared in the surrounding context or one of its parents.
    """

    if TYPE_CHECKING:

        def __init__(self, var: str, **data):  # noqa: D107
            super().__init__(var=var, **data)

    var: IdentifierStr
    """The name of the variable being referenced."""


class ExternalRef(Reference):
    """Reference to a constant that is resolved outside the program.

    External symbols must be declared in the surrounding context or one of its parents. Their value
    is supplied per submission by the framework running the program, so a serialized program can be
    re-submitted against fresh values without being rebuilt.

    Note:
        This is the one place where the reference hierarchy is deliberately not uniform: unlike
        every other :class:`Reference`, an external reference does **not** serialize to its bare
        field value but keeps the wrapped ``{"ext": "q0[1].amp"}`` form. A bare ``"q0"`` would be
        ambiguous with a :class:`VariableRef` because the leading identifier is the only mandatory
        part of the grammar. Validation still accepts a bare string, so ``ExternalRef("q0.f01")``
        works.

    """

    if TYPE_CHECKING:

        def __init__(self, ext: str, **data):  # noqa: D107
            super().__init__(ext=ext, **data)

    _serializes_bare: ClassVar[bool] = False

    ext: ExternalSymbolStr
    """The name of the external symbol being referenced."""

    @model_serializer
    def _wrap_serializer(self) -> Any:
        return {"ext": self.ext}


class ChannelRef(Reference):
    """Reference to a channel.

    Channels are defined in the target's hardware configuration.
    """

    if TYPE_CHECKING:

        def __init__(self, channel: str, **data):  # noqa: D107
            super().__init__(channel=channel, **data)

    channel: IdentifierStr
    """The name of the channel being referenced."""


class PulseRef(Reference):
    """Reference to a pulse.

    Pulses must be declared in the surrounding context or one of its parents.
    """

    if TYPE_CHECKING:

        def __init__(self, pulse_name: str, **data):  # noqa: D107
            super().__init__(pulse_name=pulse_name, **data)

    pulse_name: IdentifierStr
    """The name of the pulse being referenced."""


class ChannelRefDict(TypedDict):
    """Type dict for channel references.

    Example:
    .. code-block:: python

        {"channel": "<channel_name>"}
    """

    channel: str
    """The name of the channel being referenced."""


type ChannelRefLike = str | ChannelRef | ChannelRefDict
"""Type alias for valid arguments to create :class:`ChannelRef` instances."""


class VarRefDict(TypedDict):
    """Type dict for variable references.

    Example:

    .. code-block:: python

        {"var": "<variable_name>"}
    """

    var: str
    """The name of the variable being referenced."""


type VariableRefLike = str | VariableRef | VarRefDict
"""Type alias for valid arguments to create :class:`VariableRef` instances."""


class ExtRefDict(TypedDict):
    """Type dict for external symbol references.

    Example:

    .. code-block:: python

        {"ext": "<external_symbol>"}
    """

    ext: str
    """The name of the external symbol being referenced."""


type SymbolRef = VariableRef | ExternalRef
"""Type alias for any reference to a named value: a program variable or an external constant.

:class:`VariableRef` is listed first so that Pydantic's smart union mode resolves a bare string to
a variable reference, never to an external one."""

type SymbolRefLike = VariableRefLike | ExternalRef | ExtRefDict
"""Type alias for valid arguments to create :obj:`SymbolRef` values."""


class PulseRefDict(TypedDict):
    """Type dict for pulse references.

    Example:
    .. code-block:: python

        {"pulse_name": "<pulse_name>"}
    """

    pulse_name: str
    """The name of the pulse being referenced."""


type PulseRefLike = str | PulseRef | PulseRefDict
"""Type alias for valid arguments to create :class:`PulseRef` instances."""
