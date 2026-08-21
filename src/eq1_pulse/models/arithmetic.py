"""The registry of unit value fields, and the helper classes built on top of it.

Every unit class registers the name and numeric type of its single value field here. That one
registry is what lets the operator mixins below, the unit discriminator in :mod:`~.units` and the
``"<number><unit>"`` parser in this module all be written once rather than once per unit.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, MutableMapping
from typing import Any, Self, Union, overload
from weakref import WeakKeyDictionary

from pydantic import TypeAdapter, ValidationError

type _SupportedScalarTypes = int | float | complex

_VALUE_FIELDS: MutableMapping[type, tuple[str, tuple[type, ...]]] = WeakKeyDictionary()
"""Dictionary mapping unit classes to their value field names and types."""


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


def parse_unit_suffixed_value(text: str, units: Iterable[type]) -> dict[str, Any]:
    """Read a ``"<number><unit>"`` string as the ``{unit: number}`` object it denotes.

    Longer unit names are tried first, so that ``"10ms"`` is read as milliseconds rather than as
    ``"10m"`` seconds. A unit whose name matches but whose numeric part does not parse is passed
    over rather than reported, for the same reason: ``"10ms"`` also ends in ``"s"``.

    :param text: The string to read, e.g. ``"10us"`` or ``"5 GHz"``.
    :param units: The unit classes to read *text* against, each registered with
        :func:`register_unit_value_field`.
    :return: The single-key object form, e.g. ``{"us": 10}``.
    :raises ValueError: If *text* does not end in any of the units' names, or the numeric part
        does not parse as that unit's value type.
    """
    value = text.strip()
    names = {unit: get_unit_value_field_name_and_type(unit) for unit in units}
    for name, dtype in sorted(names.values(), key=lambda item: len(item[0]), reverse=True):
        if not value.endswith(name):
            continue
        adapter: TypeAdapter[Any] = TypeAdapter(dtype[0]) if len(dtype) == 1 else TypeAdapter(Union[*dtype])
        try:
            number = adapter.validate_python(value.removesuffix(name).strip(), strict=False)
        except ValidationError:
            continue
        return {name: number}

    expected = ", ".join(sorted(name for name, _ in names.values()))
    raise ValueError(f"{text!r} is not a number followed by one of the units {expected}")


class SupportScalarMulDiv[ScalarType: _SupportedScalarTypes]:
    """A mixin to add support for multiplication and division with scalars to unit classes."""

    def __mul__(self, other: ScalarType) -> Self:
        """Multiplication operation with a scalar.

        The operation returns a new instance of the unit class.
        """
        field, dtype = get_unit_value_field_name_and_type(type(self))
        if isinstance(other, dtype):
            value = collapse_scalar(getattr(self, field) * other)
            return type(self)(**{field: value})

        return NotImplemented  # type: ignore[unreachable]

    def __rmul__(self, other: ScalarType) -> Self:
        """Right multiplication operation with a scalar.

        The operation returns a new instance of the unit class.
        """
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
        """True division operation.

        Division by scalar returns a new instance of the unit class.
        Division by another instance of the same unit class returns a scalar.
        """
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
    """A mixin to add support for addition and subtraction with same unit classes.

    This mixin also adds support for unary plus and minus operations.

    Both operands will be converted to the *1st* operand's type before performing the operation.
    """

    def __neg__(self) -> Self:
        """Unary minus operation.

        Returns a new instance of the unit class with the negated value.
        """
        field, _ = get_unit_value_field_name_and_type(type(self))
        value = -getattr(self, field)
        return type(self)(**{field: value})

    def __pos__(self) -> Self:
        """Unary plus operation.

        Returns a new instance of the unit class with the same value.
        """
        field, _ = get_unit_value_field_name_and_type(type(self))
        value = +getattr(self, field)
        return type(self)(**{field: value})

    def __add__(self, other: Any) -> Self:
        """Addition operation with another instance of the same or compatible unit class.

        Returns a new instance of the unit class on the left hand side with the summed value.
        """
        field, _ = get_unit_value_field_name_and_type(type(self))
        value = getattr(self, field) + getattr(other, field)
        return type(self)(**{field: value})

    def __sub__(self, other: Any) -> Self:
        """Subtraction operation with another instance of the same or compatible unit class.

        Returns a new instance of the unit class on the left hand side with the subtracted value.
        """
        field, _ = get_unit_value_field_name_and_type(type(self))
        value = getattr(self, field) - getattr(other, field)
        return type(self)(**{field: value})


class SupportDivModOperation[ScalarType: _SupportedScalarTypes]:
    """A mixin to add support for floor division and modulus operation with same unit classes.

    Both operands must be of the same unit class.
    Division returns an integer, the 1st operand converted to the *2nd* operand's type first.
    Modulus returns a new instance of the type of the *2nd* operand.
    """

    def __floordiv__(self, other: Self) -> int:
        """Floor division operation.

        Returns an integer result of the floor division.
        The 1st operand is converted to the 2nd operand's type before performing the operation.
        """
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
        """Modulus operation.

        Returns a new instance of the type of the 2nd operand with the modulus result.
        """
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
