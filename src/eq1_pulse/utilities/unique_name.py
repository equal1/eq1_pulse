"""Utility classes for generating unique identifiers and names."""

from typing import ClassVar
from uuid import UUID, uuid4, uuid5

__all__ = ("UniqueIDGenerator", "unique_name")


class UniqueIDGenerator:
    """Generate unique identifiers using UUID version 5."""

    _last_counter: ClassVar[int] = 0
    _format_counter: ClassVar[str] = "{}"
    _uuid_ns: UUID = uuid4()  # a random UUID

    @classmethod
    def unique_id(cls) -> UUID:
        """Generate a unique name using UUID version 5."""
        id = uuid5(cls._uuid_ns, cls._format_counter.format(cls._last_counter))
        cls._last_counter += 1
        return id


def unique_name() -> str:
    """Generate a unique name using UUID version 5."""
    return str(UniqueIDGenerator.unique_id()).upper()
