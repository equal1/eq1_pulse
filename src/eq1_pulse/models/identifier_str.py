"""A small helper module to define identifier strings."""

from __future__ import annotations

import re
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


_INDEXED_SEGMENT = re.compile(r"^(?P<name>.+?)\[(?P<index>[0-9]+)\]$")
"""A single external symbol segment carrying a bracketed index, split into its name and its index."""


def str_is_external_symbol(s: str, /) -> str:
    """Validate that a string is a valid external symbol name.

    The grammar is a fully qualified identifier whose parts may each carry a bracketed
    non-negative integer index::

        external_symbol ::= segment ( "." segment )*
        segment         ::= identifier ( "[" integer "]" )?
    """
    for segment in s.split("."):
        match = _INDEXED_SEGMENT.match(segment)
        name = match["name"] if match is not None else segment
        if not name.isidentifier():
            raise ValueError(f"{s!r} is not a valid external symbol")
    return s


type ExternalSymbolStr = Annotated[str, AfterValidator(str_is_external_symbol)]
"""A string that names an external symbol.

External symbols consist of dot-separated segments, each of which is a valid identifier optionally
followed by a bracketed integer index, such as ``q0``, ``q0[1].amp`` or
``chip.q0[3].readout.threshold``."""
