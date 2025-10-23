"""NumPy array serialization helper for Pydantic.

It doesn't work out of the box, models and type adapters still have to enable
the ``ConfigDict(allow_arbitrary_types=True)`` setting to work with this.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

import numpy as np
from numpy import ndarray
from pydantic import BeforeValidator, ConfigDict, PlainSerializer, TypeAdapter, WithJsonSchema

type nd_array_type = ndarray[Any, Any]
if TYPE_CHECKING:
    type NumpyArrayLike = nd_array_type | list[Any]


def nd_array_validate(value: list[Any] | nd_array_type) -> nd_array_type:
    if isinstance(value, list):
        return np.array(value)
    return value


def nd_array_serialize(value: nd_array_type) -> list[Any]:
    return value.tolist()  # type: ignore[no-any-return, return-value]


type NumpyArray = Annotated[
    nd_array_type,
    BeforeValidator(nd_array_validate),
    PlainSerializer(nd_array_serialize, return_type=list),
    WithJsonSchema({"type": "array", "items": {"type": "any"}}),
]

NumpyArrayConfig = ConfigDict(arbitrary_types_allowed=True)
NumpyArrayAdapter: TypeAdapter[nd_array_type] = TypeAdapter(NumpyArray, config=NumpyArrayConfig)


__all__ = ("NumpyArray",)
