"""Modules to provide representation of symbolic references.

Note:
    All reference classes inherit from :class:`Reference` and Pydantic's BaseModel for validation
    and serialization support.

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, TypedDict

from pydantic import BaseModel, model_serializer, model_validator
from pydantic.json_schema import DEFAULT_REF_TEMPLATE, GenerateJsonSchema, JsonSchemaMode

from .identifier_str import IdentifierStr

__all__ = (
    "ChannelRef",
    "PulseRef",
    "Reference",
    "VariableRef",
)


class Reference(BaseModel):
    """Base class for all symbolic references.

    Descendants must only define a single field (the reference name), which is serialized directly.
    """

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
