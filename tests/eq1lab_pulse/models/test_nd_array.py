import numpy as np

from eq1_pulse.models.nd_array import NumpyArrayAdapter


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
