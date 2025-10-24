"""A small helper module to define identifier strings."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator


def str_is_identifier(s: str, /) -> str:
    """Validate that a string is a valid identifier."""
    if not s.isidentifier():
        raise ValueError(f"{s!r} is not a valid identifier")
    return s


type IdentifierStr = Annotated[str, AfterValidator(str_is_identifier)]


def str_is_fully_qualified_identifier(s: str, /) -> str:
    """Validate that a string is a valid fully qualified identifier."""
    parts = s.split(".")
    if not all(part.isidentifier() for part in parts):
        raise ValueError(f"{s!r} is not a valid fully qualified identifier")
    return s


type FullyQualifiedIdentifier = Annotated[str, AfterValidator(str_is_fully_qualified_identifier)]
"""A string that is a valid fully qualified identifier.

Fully qualified identifiers consist of dot-separated parts, each of which is a valid identifier."""
