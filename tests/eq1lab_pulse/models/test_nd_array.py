from typing import Any

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models.nd_array import (
    NumpyArrayAdapter,
    NumpyArrayConfig,
    NumpyComplexArray1D,
    NumpyFloatArray1D,
    NumpyIntArray1D,
)


def test_numpy_array_serialization():
    x = np.array([1, 2, 3])
    assert NumpyArrayAdapter.dump_python(x) == [1, 2, 3]


def test_numpy_array_json_serialization():
    x = np.array([1, 2, 3])
    assert NumpyArrayAdapter.dump_json(x) == b"[1,2,3]"


def test_numpy_array_validation():
    result = NumpyArrayAdapter.validate_python([1, 2, 3])
    assert isinstance(result, np.ndarray)
    assert np.array_equal(result, [1, 2, 3])


def test_numpy_array_json_validation():
    result = NumpyArrayAdapter.validate_json(b"[1,2,3]")
    assert isinstance(result, np.ndarray)
    assert np.array_equal(result, [1, 2, 3])


def test_numpy_array_validation_2d():
    result = NumpyArrayAdapter.validate_python([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    assert isinstance(result, np.ndarray)
    assert np.array_equal(result, [[1, 2, 3], [4, 5, 6], [7, 8, 9]])


def test_numpy_array_json_validation_2d():
    result = NumpyArrayAdapter.validate_json(b"[[1,2,3],[4,5,6],[7,8,9]]")
    assert isinstance(result, np.ndarray)
    assert np.array_equal(result, [[1, 2, 3], [4, 5, 6], [7, 8, 9]])


def test_numpy_array_serialization_2d():
    x = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    assert NumpyArrayAdapter.dump_python(x) == [[1, 2, 3], [4, 5, 6], [7, 8, 9]]


def test_numpy_array_json_serialization_2d():
    x = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    assert NumpyArrayAdapter.dump_json(x) == b"[[1,2,3],[4,5,6],[7,8,9]]"


def test_int_1d_array_rejects_a_2d_real_array():
    """``(N, 2)`` is the authoring form of a 1-D *complex* array, and is not a 1-D integer one.

    The integer validator lets a real-*dtype* array through unconverted so that a float array is
    not silently truncated; the dimension check runs first, so that pass-through cannot make the
    integer member of a union accept the complex member's input.
    """
    adapter: TypeAdapter[Any] = TypeAdapter(NumpyIntArray1D, config=NumpyArrayConfig)
    with pytest.raises(ValidationError):
        adapter.validate_python([[1.0, 2.0], [3.0, 4.0]])


def test_iterable_array_union_selects_the_complex_member():
    """A ``(N, 2)`` real array reaches the complex member rather than stopping at the integer one."""
    adapter: TypeAdapter[Any] = TypeAdapter(
        NumpyIntArray1D | NumpyFloatArray1D | NumpyComplexArray1D, config=NumpyArrayConfig
    )
    result = adapter.validate_python([[1.0, 2.0], [3.0, 4.0]])
    assert np.array_equal(result, np.array([1 + 2j, 3 + 4j]))
