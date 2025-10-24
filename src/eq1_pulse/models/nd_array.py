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


def np_complex_1d_array_validate(value: object) -> np.ndarray:
    value = np.asanyarray(value)
    if value.ndim == 1:
        if issubclass(value.dtype.type, complex):
            return value
        return value.astype(complex)
    if value.ndim != 2 and value.shape[1] != 2:
        raise ValueError("Array must be 2-dimensional with shape (N, 2)")

    float_type, complex_type = _detect_optimal_float_to_complex_type(value)
    c_array_float: np.ndarray[Any, np.dtype[np.floating[Any]]] = np.ascontiguousarray(value, dtype=float_type)
    c_array_view_complex: np.ndarray[Any, np.dtype[np.complexfloating[Any, Any]]] = c_array_float.view(
        dtype=complex_type
    )
    new_shape = (c_array_view_complex.shape[0],)
    result = c_array_view_complex.reshape(new_shape)
    return result


def np_complex_1d_array_serialize(value: np.ndarray) -> list[tuple[float, float]]:
    return [(c.real, c.imag) for c in value.tolist()]


type NumpyComplexArray1D = Annotated[
    np.ndarray[tuple[int], np.dtype[np.complexfloating[Any, Any]]],
    BeforeValidator(np_complex_1d_array_validate),
    PlainSerializer(np_complex_1d_array_serialize, return_type=list[tuple[float, float]]),
    WithJsonSchema(
        {"type": "array", "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}}
    ),
]


def np_float_1d_array_validate(value: object) -> np.ndarray:
    value = np.asanyarray(value)
    if np.iscomplexobj(value):
        raise ValueError("Array must be of float type, not complex")
    if value.ndim != 1:
        raise ValueError("Array must be 1-dimensional")
    if issubclass(value.dtype.type, float):
        return value
    else:
        return value.astype(float)


def np_float_1d_array_serialize(value: np.ndarray) -> list[float]:
    return value.tolist()  # type: ignore[no-any-return, return-value]


type NumpyFloatArray1D = Annotated[
    np.ndarray[tuple[int], np.dtype[np.floating[Any]]],
    BeforeValidator(np_float_1d_array_validate),
    PlainSerializer(np_float_1d_array_serialize, return_type=list[float]),
    WithJsonSchema({"type": "array", "items": {"type": "number"}}),
]


__all__ = ("NumpyArray", "NumpyComplexArray1D", "NumpyFloatArray1D")


def _detect_optimal_float_to_complex_type(array: np.ndarray[Any, np.dtype[np.floating[Any]]]) -> tuple[type, type]:
    float_type: type
    complex_type: type
    match array.dtype.type:
        case np.float32:
            float_type, complex_type = np.float32, np.complex64
        case np.float64:
            float_type, complex_type = np.float64, np.complex128
        case np.float128:
            float_type, complex_type = np.float128, np.complex256
        case _:
            float_type, complex_type = float, complex

    return float_type, complex_type
