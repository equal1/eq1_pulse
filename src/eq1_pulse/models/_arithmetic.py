"""Helper classes to support arithmetic operations on unit classes."""

# ruff: noqa: D100 D101 D102 D105 D107 RUF100
from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Any, Self, overload
from weakref import WeakKeyDictionary

type _SupportedScalarTypes = int | float | complex

_VALUE_FIELDS: MutableMapping[type, tuple[str, tuple[type, ...]]] = WeakKeyDictionary()


def register_unit_value_field[T: type](name: str, dtype: tuple[type, ...] = (int, float)) -> Callable[[T], T]:
    """A class decorator to register the name of the value field for a unit class.

    The value field is the field that holds the numeric value of the unit.
    This is used by mixins to implement operations like multiplication and division
    with scalars.

    Args:
        name: The name of the value field.

    """

    def decorator(cls: T) -> T:
        _VALUE_FIELDS[cls] = (name, dtype)
        return cls

    return decorator


def get_unit_value_field_name_and_type(cls: type) -> tuple[str, tuple[type, ...]]:
    """Get the name of the value field for a unit class.

    Args:
        cls: The unit class.

    Returns:
        The name of the value field.

    Raises:
        KeyError: If the class is not registered.
    """
    if field := _VALUE_FIELDS.get(cls):
        return field

    for base in cls.__mro__:
        if field := _VALUE_FIELDS.get(base):
            _VALUE_FIELDS[cls] = field
            return field

    err = KeyError(cls)
    err.add_note("The class is not registered. Did you forget to use the @register_value_field decorator?")
    raise err


class SupportScalarMulDiv[ScalarType: _SupportedScalarTypes]:
    """A mixin to add support for multiplication and division with scalars to unit classes."""

    def __mul__(self, other: ScalarType) -> Self:
        field, dtype = get_unit_value_field_name_and_type(type(self))
        if isinstance(other, dtype):
            value = collapse_scalar(getattr(self, field) * other)
            return type(self)(**{field: value})

        return NotImplemented  # type: ignore[unreachable]

    def __rmul__(self, other: ScalarType) -> Self:
        field, dtype = get_unit_value_field_name_and_type(type(self))
        if isinstance(other, dtype):
            value = collapse_scalar(other * getattr(self, field))  # type: ignore
            return type(self)(**{field: value})

        return NotImplemented  # type: ignore[unreachable]

    @overload
    def __truediv__(self, other: ScalarType) -> Self: ...
    @overload
    def __truediv__(self, other: Self) -> ScalarType: ...

    def __truediv__(self, other: Self | ScalarType) -> Self | ScalarType:
        field, dtype = get_unit_value_field_name_and_type(type(self))
        if isinstance(other, dtype):
            value = collapse_scalar(getattr(self, field) / other)
            return type(self)(**{field: value})
        try:
            other_value = getattr(other, field)
        except AttributeError:
            return NotImplemented  # type: ignore[unreachable]
        else:
            return collapse_scalar(getattr(self, field) / other_value)  # type: ignore


class SupportAdditiveOperations:
    """A mixin to add support for addition and subtraction with same unit classes."""

    def __neg__(self) -> Self:
        field, _ = get_unit_value_field_name_and_type(type(self))
        value = -getattr(self, field)
        return type(self)(**{field: value})

    def __pos__(self) -> Self:
        field, _ = get_unit_value_field_name_and_type(type(self))
        value = +getattr(self, field)
        return type(self)(**{field: value})

    def __add__(self, other: Any) -> Self:
        field, _ = get_unit_value_field_name_and_type(type(self))
        value = getattr(self, field) + getattr(other, field)
        return type(self)(**{field: value})

    def __sub__(self, other: Any) -> Self:
        field, _ = get_unit_value_field_name_and_type(type(self))
        value = getattr(self, field) - getattr(other, field)
        return type(self)(**{field: value})


class SupportDivModOperation[ScalarType: _SupportedScalarTypes]:
    """A mixin to add support for modulus operation with same unit classes."""

    def __floordiv__(self, other: Self) -> int:
        try:
            field, _ = get_unit_value_field_name_and_type(type(other))
        except KeyError:
            return NotImplemented  # type: ignore[unreachable]
        try:
            my_value = getattr(self, field)
        except AttributeError:
            return NotImplemented  # type: ignore[unreachable]
        else:
            value = my_value // getattr(other, field)
            return ensure_int(value)  # type: ignore[return-value]

    def __mod__(self, other: Self) -> Self:
        try:
            field, _ = get_unit_value_field_name_and_type(type(other))
        except KeyError:
            return NotImplemented  # type: ignore[unreachable]
        try:
            my_value = getattr(self, field)
        except AttributeError:
            return NotImplemented  # type: ignore[unreachable]
        else:
            value = collapse_scalar(my_value % getattr(other, field))

        return type(other)(**{field: value})


class SupportUnitArithmeticOperations[ScalarType: _SupportedScalarTypes](
    SupportAdditiveOperations,
    SupportScalarMulDiv[ScalarType],
    SupportDivModOperation[ScalarType],
):
    """A mixin to add support for basic arithmetic operations with scalars and same unit classes."""

    pass


def ensure_int(value: int | float | complex) -> int:
    """Ensure that a value is an integer, raising ValueError if not.

    :param value: The value to check.

    :return: The integer value.
    :raises ValueError: If the value is not an integer.

    The function accepts int, float, and complex types. If a complex number is provided,
    it must have a zero imaginary part to be converted to an integer.
    If a float is provided, it must represent an integer value (e.g., 3.0 is acceptable, but 3.5 is not).

    The type of the returned value is guaranteed to be int.
    """
    if isinstance(value, complex):
        if value.imag != 0:
            raise ValueError(f"Cannot convert complex number with non-zero imaginary part to int: {value}")
        value = value.real
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"Cannot convert non-integer float to int: {value}")
    return int(value)


def collapse_float(value: int | float) -> int | float:
    """Collapse a float to an int if it represents an integer value.

    :param value: The value to collapse.
    :return: The collapsed value, either as an int or float.
    """
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def collapse_scalar(value: int | float | complex) -> int | float | complex:
    """Collapse a scalar to a float if it represents a real value, int if it represents an integer value.

    :param value: The value to collapse.
    :return: The collapsed value, either as an int, float, or complex.

    Complex numbers with a non-zero imaginary part are returned unchanged.
    Complex numbers with a zero imaginary part are converted to their real part,
    which is then collapsed to an int if it represents an integer value.
    """
    if isinstance(value, complex):
        if value.imag != 0:
            return value
        value = value.real

    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value
