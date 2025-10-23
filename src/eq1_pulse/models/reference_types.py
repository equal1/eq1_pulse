"""Modules to provide representation of symbolic references.

Note:
    All reference classes inherit from :class:`Reference` and Pydantic's BaseModel for validation
    and serialization support.

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from pydantic import BaseModel, model_serializer, model_validator

from ._identifier_str import IdentifierStr

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


class ChannelRef(Reference):
    """Reference to a channel.

    Channels are defined in the target's hardware configuration.
    """

    if TYPE_CHECKING:

        def __init__(self, channel: str, **data):  # noqa: D107
            super().__init__(channel=channel, **data)

    channel: IdentifierStr


class PulseRef(Reference):
    """Reference to a pulse.

    Pulses must be declared in the surrounding context or one of its parents.
    """

    if TYPE_CHECKING:

        def __init__(self, pulse_name: str, **data):  # noqa: D107
            super().__init__(pulse_name=pulse_name, **data)

    pulse_name: IdentifierStr


if TYPE_CHECKING:

    class ChannelRefDict(TypedDict):
        channel: str

    type ChannelRefLike = str | ChannelRef | ChannelRefDict

    class VarRefDict(TypedDict):
        var: str

    type VariableRefLike = str | VariableRef | VarRefDict

    class PulseRefDict(TypedDict):
        pulse_name: str

    type PulseRefLike = str | PulseRef | PulseRefDict
