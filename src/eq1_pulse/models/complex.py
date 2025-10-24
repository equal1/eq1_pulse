"""This module defines a complex number type that can be serialized as a tuple of two floats (real, imag)."""

from __future__ import annotations

from typing import Annotated

import numpy as np
from pydantic import BeforeValidator, PlainSerializer, WithJsonSchema


def validate_complex_tuple(value: object) -> complex:
    """Validate and convert various input formats to a complex number."""
    match value:
        case complex() as c:
            return c
        case (real, imag):
            return complex(float(real), float(imag))  # type: ignore
        case [real, imag]:
            return complex(float(real), float(imag))  # type: ignore
        case str() as s:
            return complex(s)
        case np.complexfloating() as c:
            return complex(c.real, c.imag)
        case np.ndarray() as a if a.shape == (2,) and issubclass(a.dtype.type, np.integer | np.floating):
            return complex(float(a[0]), float(a[1]))

    raise ValueError("expected a complex number or tuple of two numbers representing (real, imag)")  # pragma: no cover


def serialize_complex_as_tuple(value: complex) -> tuple[float, float]:
    """Serialize a complex number to a tuple of two floats (real, imag)."""
    return (value.real, value.imag)


type complex_from_tuple = Annotated[
    complex,
    BeforeValidator(validate_complex_tuple),
    PlainSerializer(serialize_complex_as_tuple, return_type=tuple[float, float]),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                {
                    "type": "string",
                    "pattern": r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?"
                    + r"[+-](\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?j$",
                },
            ]
        }
    ),
]
"""Complex number serialized as a tuple of two floats (real, imag).

It also allows a string representation of a complex number as input.
"""
