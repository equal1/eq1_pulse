"""Modules to provide representation of symbolic references.

Note:
    All reference classes inherit from :class:`Reference` and Pydantic's BaseModel for validation
    and serialization support.

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypedDict

from pydantic import BaseModel, model_serializer, model_validator
from pydantic.json_schema import DEFAULT_REF_TEMPLATE, GenerateJsonSchema, JsonSchemaMode
from pydantic_core import PydanticSerializationUnexpectedValue

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
    """

    _serializes_bare: ClassVar[bool] = True
    """Whether instances of this class serialize to their bare field value.

    A descendant that keeps the wrapped object form must set this to :obj:`False` *and* override
    :meth:`_wrap_serializer`; see :class:`ExternalRef`."""

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
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = "validation",
        *,
        union_format: Literal["any_of", "primitive_type_array"] = "any_of",
    ) -> dict[str, Any]:
        """Generate the JSON schema for the model, wrapping it to allow direct values.

        :see: :obj:`pydantic.BaseModel.model_json_schema` for more details.
        """
        base_schema = super().model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
            union_format=union_format,
        )

        first_field_schema = base_schema["properties"][cls._first_field_name()]
        assert isinstance(first_field_schema, dict)
        return first_field_schema

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
        """Generate the JSON schema for the model, keeping the wrapped object form.

        This bypasses :meth:`Reference.model_json_schema`, which unwraps the schema of the single
        field, for the reason given in the class docstring.

        :see: :obj:`pydantic.BaseModel.model_json_schema` for more details.
        """
        return super(Reference, cls).model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
            union_format=union_format,
        )


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
