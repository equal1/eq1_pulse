from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator


def str_is_identifier(s: str, /) -> str:
    """Validate that a string is a valid identifier."""
    if not s.isidentifier():
        raise ValueError(f"{s!r} is not a valid identifier")
    return s


type IdentifierStr = Annotated[str, AfterValidator(str_is_identifier)]
