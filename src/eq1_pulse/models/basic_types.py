"""Reusable basic types for pulse library models.

These types are designed to be used throughout the pulse library for consistency
and ease of use.

The types include representations for physical quantities such as angles, time durations, voltages,
frequencies, and ranges, with support for multiple measurement units and automatic conversion.

Subclasses of these types may be more suitable for specific use cases. e.g Phase instead of Angle,
or Duration instead of Time.
"""

# ruff: noqa: D100 D101 D102 D105, D107, RUF100
from __future__ import annotations

import cmath
import operator
from collections.abc import Callable, Iterable, Mapping
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Final,
    Literal,
    NamedTuple,
    Self,
    TypeAliasType,
    TypedDict,
    TypeGuard,
    Union,
    get_args,
    overload,
)

import numpy as np
from pydantic import Discriminator, Field, GetCoreSchemaHandler, Tag, model_validator
from pydantic_core import CoreSchema

from .arithmetic import get_unit_value_field_name_and_type
from .base_models import FrozenModel, FrozenWrappedValueModel, LeanModel, NestedWireModel, WrappedValueModel
from .complex import complex_from_tuple
from .units import (
    ComplexMillivolts,
    ComplexVolts,
    Degrees,
    Gigahertz,
    HalfTurns,
    Hertz,
    Kilohertz,
    Megahertz,
    Microseconds,
    Milliseconds,
    Millivolts,
    Nanoseconds,
    Radians,
    Seconds,
    Turns,
    UnitDiscriminator,
    Volts,
)

__all__ = (
    "Amplitude",
    "Angle",
    "ComplexVoltage",
    "Duration",
    "Frequency",
    "LinSpace",
    "Magnitude",
    "OpBase",
    "OperationDiscriminator",
    "Phase",
    "Range",
    "Threshold",
    "Time",
    "Voltage",
    "op_tag_of",
)


class ArithmeticFrozenWrappedValueModel[ScalarType](FrozenWrappedValueModel):
    """Base class for wrapped value models that support arithmetic operations."""

    def __neg__(self: Self) -> Self:
        return type(self).model_construct(root=-self.root)  # type: ignore[return-value]

    def __pos__(self: Self) -> Self:
        return type(self).model_construct(root=+self.root)  # type: ignore[return-value]

    def __add__(self: Self, other: Self) -> Self:
        return type(self).model_construct(root=self.root + other.root)  # type: ignore[return-value]

    def __sub__(self: Self, other: Self) -> Self:
        return type(self).model_construct(root=self.root - other.root)  # type: ignore[return-value]

    @overload
    def __floordiv__(self: Self, other: ScalarType) -> Self: ...

    @overload
    def __floordiv__(self: Self, other: Self) -> ScalarType: ...

    def __floordiv__(self: Self, other: ScalarType | Self) -> Self | ScalarType:
        if isinstance(other, type(self)) or isinstance(self, type(other)):
            return self.root // other.root  # type: ignore
        return type(self).model_construct(root=self.root // other)  # type: ignore[return-value]

    def __mod__(self: Self, other: Self) -> Self:
        return type(self).model_construct(root=self.root % other.root)  # type: ignore[return-value]

    def __mul__(self: Self, other: ScalarType) -> Self:
        return type(self).model_construct(root=self.root * other)  # type: ignore[return-value]

    def __rmul__(self: Self, other: ScalarType) -> Self:
        return type(self).model_construct(root=other * self.root)  # type: ignore[return-value]

    @overload
    def __truediv__(self, other: ScalarType) -> Self: ...
    @overload
    def __truediv__(self, other: Self) -> ScalarType: ...

    def __truediv__(self: Self, other: ScalarType | Self) -> Self | ScalarType:
        if isinstance(other, type(self)):
            return self.root / other.root  # type: ignore
        return type(self).model_construct(root=self.root / other)  # type: ignore[return-value]


class ComparisonCompatibleUnitAndTypes(NamedTuple):
    """A tuple to hold the unit of comparison and compatible types for equality checks."""

    unit: str
    """The unit of comparison for equality checks when the values have different units."""
    types: set[type]
    """Set of types that are considered equality compatible with the registered type.
    Must include the registered type itself."""

    raw: str | None
    """The raw value attribute to use for zero comparisons, if different from the unit of comparison.

    It is also used for boolean evaluation."""


_comparison_unit_and_types: dict[type[ComparableWrappedValueOrZeroModel], ComparisonCompatibleUnitAndTypes] = {}
"""Maps a type to a tuple of (unit_of_comparison, set of equality compatible types)."""


def register_comparison_unit[T: ComparableWrappedValueOrZeroModel](
    unit: str, *, compatible_with: type | Iterable[type] = (), raw: str | None = None
) -> Callable[[type[T]], type[T]]:
    """Decorator to register a unit of comparison for equality checks for a type and extra compatible types.

    :param unit: The unit of comparison to use for equality checks.
    :param extra_types: Extra types that are considered equality compatible with the decorated type.
    :return: The decorated type.
    """
    if not isinstance(compatible_with, Iterable):
        assert isinstance(compatible_with, type)
        compatible_with = (compatible_with,)

    def decorator(cls: type[T]) -> type[T]:
        _comparison_unit_and_types[cls] = ComparisonCompatibleUnitAndTypes(
            unit=unit,
            types={cls, *compatible_with},
            raw=raw,
        )
        return cls

    return decorator


def _find_registered_equality_comparison_type_info(type1: type) -> ComparisonCompatibleUnitAndTypes | None:
    """Find the registered type info for a type, checking its MRO if needed."""
    type1_comp = _comparison_unit_and_types.get(type1)
    if type1_comp is None:
        for base_type1 in type1.__mro__:
            if base_type1 in _comparison_unit_and_types:
                type1_comp = _comparison_unit_and_types[base_type1]
                _comparison_unit_and_types[type1] = type1_comp
                break
    return type1_comp


def _get_equality_comparison_unit(type1: type, type2: type) -> str | None:
    """Return the unit of comparison for two types, if they are compatible.

    The relationship is symmetrical, but the unit of comparison is preferred
    from type1 if both types are compatible.
    """
    type1_comp = _find_registered_equality_comparison_type_info(type1)

    def find_type_in_types(type_to_find: type, types_set: set[type]) -> TypeGuard[type]:
        if type_to_find in types_set:
            return True
        for base_type in type_to_find.__mro__:
            if base_type in types_set:
                types_set.add(type_to_find)
                return True
        return False

    if type1_comp is not None and find_type_in_types(type2, type1_comp.types):
        return type1_comp.unit

    type2_comp = _find_registered_equality_comparison_type_info(type2)
    if type2_comp is not None and find_type_in_types(type1, type2_comp.types):
        # Avoid the second path next time if result is the same unit
        if type1_comp is not None and type1_comp.unit == type2_comp.unit:
            type1_comp.types.add(type2)
            return type1_comp.unit
        return type2_comp.unit

    return None


def _get_raw_value_attribute(type1: type) -> str | None:
    """Return the raw value attribute for a type, if it is registered.

    Falls back to the equality comparison unit, if available.
    Returns :obj:`None` if not found.
    """
    type_comp = _find_registered_equality_comparison_type_info(type1)
    if type_comp is None:
        return None

    return type_comp.raw if type_comp.raw is not None else type_comp.unit


def _comparable_hash(self: ComparableWrappedValueOrZeroModel) -> int:
    """Hash on the normalized magnitude, so that equal values hash equally.

    :meth:`ComparableWrappedValueOrZeroModel.__eq__` compares across units and across
    registered compatible types, so hashing the stored field (as pydantic's generated
    model hash does) would break the ``a == b implies hash(a) == hash(b)`` invariant
    and silently corrupt any use of these types in a :class:`set` or as a
    :class:`dict` key.

    The type is deliberately not part of the hash: equality holds across the whole
    registered compatibility group, so every member of it must hash alike. Python's
    numeric hash is already consistent across :class:`int`, :class:`float` and
    :class:`complex`, so no further normalization is needed.

    :param self: The value to hash

    :return: Hash of the value expressed in its registered comparison unit
    """
    # The *comparison* unit, not the raw one: raw is the value in whichever unit it
    # happens to be stored in (1 for both 1us and 1ns), which is only good enough for
    # the zero checks it exists for. Equality normalizes, so the hash must too.
    type_info = _find_registered_equality_comparison_type_info(type(self))
    if type_info is None:
        return object.__hash__(self)
    return hash(getattr(self.root, type_info.unit))


class ComparableWrappedValueOrZeroModel(WrappedValueModel):
    """A :class:`WrappedValueModel` that supports comparison with the zero literal and compatible types.

    Zero is no longer a *wire* form -- ``Duration.model_validate(0)`` raises -- but it remains the
    one value that means the same thing in every unit, so comparing against it is well defined and
    is what "OrZero" names here.

    The unit of comparison and additional compatible types for equality checks is registered using the
    :func:`register_equality_comparison_unit` decorator
    """

    def __eq__(self, value: object) -> bool:
        """Check equality with another object, considering zero literal and wrapped value types.

        It handles comparisons with the literal 0 and other WrappedValueModel instances which
        have compatible value types. (either same type of registered as `extra_equality_compatible_types`)
        """
        if isinstance(value, WrappedValueModel):
            cls = type(self)
            unit_of_comparison = _get_equality_comparison_unit(cls, type(value))
            if unit_of_comparison is None:
                return NotImplemented
            return (  # type: ignore[no-any-return]
                self.root == value.root
                or getattr(self.root, unit_of_comparison) == getattr(value.root, unit_of_comparison)
            )

        if isinstance(value, int | float | complex) and value == 0:
            cls = type(self)
            unit_of_zero = _get_raw_value_attribute(cls)
            if unit_of_zero is None:
                return NotImplemented

            return getattr(self.root, unit_of_zero) == 0  # type: ignore[no-any-return]

        return super().__eq__(value)

    def __hash__(self) -> int:
        """Hash consistently with :meth:`__eq__`; see :func:`_comparable_hash`."""
        return _comparable_hash(self)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Re-apply :func:`_comparable_hash` to every subclass.

        Pydantic generates a fresh field-based ``__hash__`` on each frozen model
        class, which would shadow the inherited one. This hook runs after the class
        is fully built, so assigning here wins.
        """
        super().__pydantic_init_subclass__(**kwargs)
        cls.__hash__ = _comparable_hash  # type: ignore[assignment, method-assign]

    def __compare(self, other: object, op: Callable[[Any, Any], bool]) -> bool | None:
        """Apply an ordering operator against a compatible value or the zero literal.

        :param other: The right-hand operand
        :param op: The operator to apply to the two normalized magnitudes

        :return: The result of ``op``, or :obj:`None` if ``other`` is not comparable
        """
        if isinstance(other, WrappedValueModel):
            unit_of_comparison = _get_equality_comparison_unit(type(self), type(other))
            if unit_of_comparison is None:
                return None
            return bool(op(getattr(self.root, unit_of_comparison), getattr(other.root, unit_of_comparison)))

        if isinstance(other, int | float | complex) and other == 0:
            unit_of_zero = _get_raw_value_attribute(type(self))
            if unit_of_zero is None:
                return None
            return bool(op(getattr(self.root, unit_of_zero), 0))

        return None

    def __lt__(self, other: object) -> bool:
        """Less-than comparison with another object, considering zero literal and compatible types."""
        result = self.__compare(other, operator.lt)
        return NotImplemented if result is None else result

    def __le__(self, other: object) -> bool:
        """Less-than-or-equal comparison with another object, considering zero literal and compatible types."""
        result = self.__compare(other, operator.le)
        return NotImplemented if result is None else result

    def __gt__(self, other: object) -> bool:
        """Greater-than comparison with another object, considering zero literal and compatible types.

        Evaluated directly rather than as ``not self <= other``: negating the
        complementary operator reports ``True`` for both directions when either
        operand is NaN.
        """
        result = self.__compare(other, operator.gt)
        return NotImplemented if result is None else result

    def __ge__(self, other: object) -> bool:
        """Greater-than-or-equal comparison with another object, considering zero literal and compatible types.

        Evaluated directly rather than as ``not self < other``; see :meth:`__gt__`.
        """
        result = self.__compare(other, operator.ge)
        return NotImplemented if result is None else result

    def __bool__(self) -> bool:
        """Return True if the wrapped value is non-zero, based on the registered raw value attribute."""
        cls = type(self)
        unit_of_zero = _get_raw_value_attribute(cls)
        if unit_of_zero is None:
            return NotImplemented  # type: ignore[no-any-return]

        return bool(getattr(self.root, unit_of_zero))  # type: ignore[no-any-return]


@register_comparison_unit("turns")
class Angle(ComparableWrappedValueOrZeroModel, ArithmeticFrozenWrappedValueModel[int | float]):
    r"""A model representing an angle in either degrees, radians, turns or half-turns.

    Turns are also known as revolutions or cycles, also :math:`\tau=2\pi` radians or 360°.
    Half-turns are also known as half-cycles, also :math:`\pi` radians or 180°.
    """  # noqa: E501

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0] | str, /): ...

        @overload
        def __init__(self, /, *, deg: int | float): ...

        @overload
        def __init__(self, /, *, rad: float): ...

        @overload
        def __init__(self, /, *, turns: int | float): ...

        @overload
        def __init__(self, /, *, half_turns: int | float): ...

        def __init__(self, /, *args, **data):
            """"""  # noqa: D419
            ...

    root: Annotated[Degrees | Radians | Turns | HalfTurns, UnitDiscriminator()]
    """The underlying angle value in one of the supported units."""

    @property
    def deg(self) -> int | float:
        """Value in degrees."""
        return self.root.deg

    @property
    def rad(self) -> float:
        """Value in radians."""
        return self.root.rad

    @property
    def turns(self) -> float:
        """Value in turns."""
        return self.root.turns

    @property
    def half_turns(self) -> float:
        """Value in half-turns."""
        return self.root.half_turns

    if TYPE_CHECKING:

        def __eq__(self, other: Angle | Literal[0]) -> bool: ...  # type: ignore[override]

    @property
    def complex_rotation(self) -> complex:
        r"""The complex rotation :math:`e^{i \theta}` represented by this angle."""
        match self.deg % 360:
            case 0:
                return 1
            case 90:
                return 1j
            case 180:
                return -1
            case 270:
                return -1j
        return cmath.exp(1j * self.rad)


class Phase(Angle):
    """Special case of Angle where the value represents a phase angle.

    Matrix-multiplying "@" a :class:`Voltage` or :class:`ComplexVoltage` with a :class:`Phase`
    will result in a complex rotated :class:`Amplitude`.
    """

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0] | str, /): ...

        @overload
        def __init__(self, /, *, deg: int | float): ...

        @overload
        def __init__(self, /, *, rad: float): ...

        @overload
        def __init__(self, /, *, turns: float): ...

        @overload
        def __init__(self, /, *, half_turns: float): ...

        def __init__(self, /, *args, **data): ...

    @staticmethod
    def __as_amplitude(other: object) -> Amplitude | None:
        """Coerce an operand to an :class:`Amplitude`, or :obj:`None` if it is not one.

        :param other: The operand to coerce

        :return: The operand as an :class:`Amplitude`, or :obj:`None` if incompatible
        """
        if isinstance(other, str) or other == 0 or isinstance(other, dict):
            return Amplitude(other)  # type: ignore[arg-type]
        if isinstance(other, Amplitude):
            return other
        if isinstance(other, ComplexVoltage):
            return Amplitude.create_from(other.real, other.imag)
        if isinstance(other, Voltage):
            return Amplitude.create_from(other)

        return None

    def __matmul__(self, other: Voltage | ComplexVoltageLike) -> Amplitude:
        """Matrix-multiply this Phase with magnitude or voltage.

        :return: The resulting complex amplitude after rotation.
        """
        rhs = self.__as_amplitude(other)
        if rhs is None:
            return NotImplemented
        return self.complex_rotation * rhs

    def __rmatmul__(self, other: Voltage | ComplexVoltageLike) -> Amplitude:
        """Matrix-multiply a magnitude or voltage with this Phase.

        :return: The resulting complex amplitude after rotation.
        """
        lhs = self.__as_amplitude(other)
        if lhs is None:
            return NotImplemented
        return lhs * self.complex_rotation


@register_comparison_unit("s", raw="_raw")
class Time(ComparableWrappedValueOrZeroModel, ArithmeticFrozenWrappedValueModel[int | float]):
    """A model representing time (instant or difference).

    The model can represent time in seconds, milliseconds, microseconds, or nanoseconds,
    with automatic conversion between the units.

    The storage type for milliseconds is integer, while for other units it is float.
    Conversion to nanoseconds is rounded to the nearest integer.
    """

    root: Annotated[Seconds | Milliseconds | Microseconds | Nanoseconds, UnitDiscriminator()]
    """The underlying time value in one of the supported units."""

    @property
    def s(self) -> float:
        """Value in seconds."""
        return self.root.s

    @property
    def ms(self) -> float:
        """Value in milliseconds."""
        return self.root.ms

    @property
    def us(self) -> float:
        """Value in microseconds."""
        return self.root.us

    @property
    def ns(self) -> int:
        """Value in nanoseconds."""
        return self.root.ns

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0] | str, /): ...

        @overload
        def __init__(self, /, *, s: float): ...

        @overload
        def __init__(self, /, *, ms: float): ...

        @overload
        def __init__(self, /, *, us: float): ...

        @overload
        def __init__(self, /, *, ns: int): ...

        def __init__(self, /, *args, **data):
            """"""  # noqa: D419
            ...

    if TYPE_CHECKING:

        def __eq__(self, other: Time | Literal[0]) -> bool: ...  # type: ignore[override]

    def __bool__(self) -> bool:
        """Return True if the time value is non-zero."""
        return bool(self.root._raw)


class Duration(Time):
    """Special case of non-negative Time representing a duration."""

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0] | str, /): ...

        @overload
        def __init__(self, /, *, s: float): ...

        @overload
        def __init__(self, /, *, ms: float): ...

        @overload
        def __init__(self, /, *, us: float): ...

        @overload
        def __init__(self, /, *, ns: int): ...

        def __init__(self, /, *args, **data): ...

    @model_validator(mode="wrap")
    @classmethod
    def _validate_nonnegative_raw_value(cls, data, handler):
        data = handler(data)
        if data.root._raw < 0:
            raise ValueError("expected nonnegative duration value")
        return data


@register_comparison_unit("V", raw="_raw")
class Voltage(ComparableWrappedValueOrZeroModel, ArithmeticFrozenWrappedValueModel[int | float]):
    """A model representing a real voltage in volts or millivolts."""

    root: Annotated[Volts | Millivolts, UnitDiscriminator()]

    @property
    def V(self) -> int | float:
        return self.root.V

    @property
    def mV(self) -> int | float:
        return self.root.mV

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0] | str, /): ...

        @overload
        def __init__(self, /, *, V: int | float): ...

        @overload
        def __init__(self, /, *, mV: int | float): ...

        def __init__(self, /, *args, **data): ...

        def __eq__(self, other: Voltage | ComplexVoltage | Literal[0]) -> bool: ...  # type: ignore[override]

    @classmethod
    def from_value(cls, value: Volts | Millivolts) -> Self:
        """Create a Voltage instance from a Volts or Millivolts value."""
        match value:
            case Volts():
                return cls(V=value.V)
            case Millivolts():
                return cls(mV=value.mV)
            case _:
                raise TypeError(f"expected Volts or Millivolts, got {type(value)}")  # pragma: no cover


@register_comparison_unit("V", compatible_with=Voltage, raw="_raw")
class ComplexVoltage(ComparableWrappedValueOrZeroModel, ArithmeticFrozenWrappedValueModel[int | float | complex]):
    """A model representing a complex voltage in volts or millivolts.

    Complex voltages are used to represent both amplitude and phase information,
    and are used with with mixing or demodulation operations.
    """

    root: Annotated[ComplexVolts | ComplexMillivolts, UnitDiscriminator()]

    @property
    def V(self) -> complex:
        return self.root.V

    @property
    def mV(self) -> complex:
        return self.root.mV

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0] | str, /): ...

        @overload
        def __init__(self, /, *, V: complex): ...

        @overload
        def __init__(self, /, *, mV: complex): ...

        def __init__(self, /, *args, **data): ...

        def __eq__(self, other: Voltage | ComplexVoltage | Literal[0]) -> bool: ...  # type: ignore[override]

    @classmethod
    def create_from(cls, real: Voltage, imag: Voltage = Voltage(0), /) -> Self:  # noqa: B008
        """Create a ComplexVoltage from a Voltage, setting the imaginary part to zero."""
        if isinstance(real.root, Volts):
            return cls(V=complex(real.V, imag.V))
        else:
            return cls(mV=complex(real.mV, imag.mV))

    @property
    def real(self) -> Voltage:
        """Get the real part of the complex voltage as a Voltage instance."""
        return Voltage.from_value(self.root.real)

    @property
    def imag(self) -> Voltage:
        """Get the imaginary part of the complex voltage as a Voltage instance."""
        return Voltage.from_value(self.root.imag)

    def __abs__(self) -> Magnitude:
        """Get the magnitude of the complex voltage as a Magnitude instance."""
        return Magnitude.from_value(abs(self.root))  # type: ignore[arg-type]

    @property
    def phase(self) -> Phase:
        """Get the phase of the complex voltage as a Phase instance (radians)."""
        return Phase(rad=cmath.phase(self.root._raw))  # type: ignore[arg-type]

    @property
    def angle(self) -> Angle:
        """Get the angle of the complex voltage as an Angle instance (degrees)."""
        return Angle(deg=self.phase.deg)  # type: ignore[arg-type]


@register_comparison_unit("Hz", raw="_raw")
class Frequency(ComparableWrappedValueOrZeroModel, ArithmeticFrozenWrappedValueModel[int | float]):
    """A model representing a frequency in Hertz, Kilohertz, Megahertz, or Gigahertz."""

    root: Annotated[Hertz | Kilohertz | Megahertz | Gigahertz, UnitDiscriminator()]

    @property
    def Hz(self) -> int | float:
        return self.root.Hz

    @property
    def kHz(self) -> int | float:
        return self.root.kHz

    @property
    def MHz(self) -> int | float:
        return self.root.MHz

    @property
    def GHz(self) -> int | float:
        return self.root.GHz

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0] | str, /): ...

        @overload
        def __init__(self, /, Hz: float): ...

        @overload
        def __init__(self, /, *, kHz: float): ...

        @overload
        def __init__(self, /, *, MHz: float): ...

        @overload
        def __init__(self, /, *, GHz: float): ...

        def __init__(self, /, *args, **data): ...

        def __eq__(self, other: Frequency | Literal[0]) -> bool: ...  # type: ignore[override]


class Amplitude(ComplexVoltage):
    """Model to represent the (complex) amplitude of a voltage signal."""

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0] | str, /): ...

        @overload
        def __init__(self, /, *, V: float | complex): ...

        @overload
        def __init__(self, /, *, mV: float | complex): ...

        def __init__(self, *args, **data): ...


class Threshold(Voltage):
    """Model to represent a (real) threshold voltage level."""

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0] | str, /): ...

        @overload
        def __init__(self, /, *, V: float): ...

        @overload
        def __init__(self, /, *, mV: float): ...

        def __init__(self, *args, **data): ...


class Magnitude(Voltage):
    """Special case of non-negative real Voltage representing a maximum amplitude."""

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0] | str, /): ...

        @overload
        def __init__(self, /, *, V: float): ...

        @overload
        def __init__(self, /, *, mV: float): ...

        def __init__(self, /, *args, **data): ...

    @model_validator(mode="wrap")
    @classmethod
    def _validate_nonnegative_raw_value(cls, data, handler):
        data = handler(data)
        if data.root._raw < 0:
            raise ValueError("expected nonnegative magnitude value")
        return data


_DIMENSION_TAGS: Final[dict[type[Time] | type[Voltage] | type[Frequency] | type[Angle], str]] = {
    Time: "time",
    Voltage: "voltage",
    Frequency: "frequency",
    Angle: "angle",
}
"""The one type per *real* dimension the open value unions (:data:`~.data_ops.SymbolValue`,
:data:`~.pulse_types.ExternalParamValue`) list -- see issue #10 -- mapped to the tag each is given in
those unions. Their refinements (:class:`Duration`, :class:`Threshold`, :class:`Magnitude`,
:class:`Phase`) stay the correct types for *closed* fields, where the field itself says which
refinement applies.

:class:`ComplexVoltage` (and its refinement :class:`Amplitude`) is deliberately **not** here: this
dict is also what :func:`dimension_unit_tag_map` iterates, and :class:`~.units.ComplexVolts` /
:class:`~.units.ComplexMillivolts` carry the same ``V`` / ``mV`` keys as :class:`~.units.Volts` /
:class:`~.units.Millivolts`, so listing it would make every voltage key resolve to whichever of the
two was iterated last. It gets :data:`COMPLEX_VOLTAGE_TAG` instead, decided by value shape --
see :func:`dimension_tag_of_unit_mapping`."""


COMPLEX_VOLTAGE_TAG: Final = "complex_voltage"
"""The tag the open value unions give :class:`ComplexVoltage`.

Not a member of :data:`_DIMENSION_TAGS`, for the reason given there: the complex voltage units share
their unit keys with the real ones, so the two dimensions are told apart by the *shape* of the value
under the key rather than by the key itself.
"""

_VOLTAGE_TAG: Final = _DIMENSION_TAGS[Voltage]
"""The tag of the real voltage dimension -- the only one a complex spelling can refine."""


def dimension_unit_tag_map() -> dict[str, str]:
    """Map each unit key to the tag of the dimension that owns it.

    Read from the same :func:`~.arithmetic.register_unit_value_field` registry
    :class:`~.units.UnitDiscriminator` reads, so a new unit needs no change here.
    """
    tags: dict[str, str] = {}
    for quantity, dimension_tag in _DIMENSION_TAGS.items():
        for unit in get_args(quantity.model_fields["root"].annotation):
            unit_tag, _ = get_unit_value_field_name_and_type(unit)
            tags[unit_tag] = dimension_tag
    return tags


def is_complex_voltage_spelling(value: Any) -> bool:
    """Whether *value* is the value of a unit key spelled as a complex quantity.

    The shape test behind :data:`COMPLEX_VOLTAGE_TAG`: within a voltage unit key a real number is a
    :class:`Voltage` and a ``(real, imag)`` pair is a :class:`ComplexVoltage`. ``{"mV": 100}`` and
    ``{"mV": [1, 2]}`` are distinct wire shapes, so the two dimensions keep one wire form each
    (issue #10).

    :param value: The value found under a unit key
    :return: :obj:`True` if *value* is a complex number or a two-element ``(real, imag)`` pair, in
        any of the spellings :func:`~.complex.validate_complex_tuple` accepts
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, complex | np.complexfloating):
        return True
    if isinstance(value, list | tuple):
        return len(value) == 2
    if isinstance(value, np.ndarray):
        return value.shape == (2,) and issubclass(value.dtype.type, np.integer | np.floating)
    return False


def dimension_tag_of_unit_mapping(value: Mapping[str, Any], unit_tags: Mapping[str, str]) -> str | None:
    """Return the tag the single-unit-key mapping *value* is spelled with.

    Shared by :data:`~.data_ops.SymbolValue`'s and :data:`~.pulse_types.ExternalParamValue`'s
    discriminators, so that the complex-voltage carve-out is written once.

    :param value: A candidate wire mapping for an open, dimension-carrying union
    :param unit_tags: The unit key -> dimension tag map from :func:`dimension_unit_tag_map`
    :return: The dimension tag *value*'s sole unit key names, refined to
        :data:`COMPLEX_VOLTAGE_TAG` when a voltage key carries a complex spelling, or :obj:`None`
        if *value* is not a single known unit key
    """
    if len(value) != 1:
        return None
    key = next(iter(value))
    tag = unit_tags.get(key)
    if tag == _VOLTAGE_TAG and is_complex_voltage_spelling(value[key]):
        return COMPLEX_VOLTAGE_TAG
    return tag


def dimension_tag_of(value: Any) -> str | None:
    """Return the tag *value* is expressed in.

    Checked against :data:`~.data_ops.SymbolValue` and :data:`~.pulse_types.ExternalParamValue`'s
    dimensional members. Unlike :func:`dimension_tag_of_unit_mapping` this reads an already-built
    instance, whose type says which dimension it is with no shape test needed.

    :param value: A candidate value for an open, dimension-carrying union
    :return: ``"time"``, ``"voltage"``, ``"complex_voltage"``, ``"frequency"`` or ``"angle"`` if
        *value* is a :class:`Time`, :class:`Voltage`, :class:`ComplexVoltage`, :class:`Frequency` or
        :class:`Angle` (or a refinement of one), otherwise :obj:`None`
    """
    if isinstance(value, ComplexVoltage):
        return COMPLEX_VOLTAGE_TAG
    for quantity, tag in _DIMENSION_TAGS.items():
        if isinstance(value, quantity):
            return tag
    return None


class OpBase(NestedWireModel, FrozenModel):
    """Base class for all operation models.

    The ``op_type`` field should be a literal string representing the operation type,
    overridden in subclasses. It names the operation rather than sitting beside its data: every
    concrete operation's wire form is the single-key object ``{op_type: payload}`` --
    ``{"play": {"channel": "q0_drive", "pulse": {...}}}`` -- lifted there by
    :class:`~.base_models.NestedWireModel`, which the whole family inherits with no per-operation
    opt-in. The Python field stays, so ``op.op_type == "play"`` and keyword construction are
    untouched.

    :class:`OpBase` itself keeps the flat form. Its ``op_type`` is not yet a single-valued literal,
    so there is no tag to lift statically, which is exactly the "not configured" case
    :class:`~.base_models.NestedWireModel` leaves alone -- invisible in the generated document,
    since this class is never referenced by a union.
    """

    if TYPE_CHECKING:

        def __init__(self, *args, **kwargs): ...

    _wire_tag_source_: ClassVar[str] = "op_type"
    """The tag is this field's *value*, and is not repeated inside the payload."""

    op_type: Any  # str


def op_tag_of(value: Any) -> str | None:
    """Return the wire key that discriminates *value* as an operation, or :obj:`None`.

    An operation's sole key *is* its type, so a mapping is tagged by that key and by nothing else.
    A mapping carrying any other number of keys has no tag, and that is what makes the superseded
    flat form -- ``{"op_type": "play", "channel": ...}`` -- fail at every union an operation can be
    selected by, as one ``union_tag_not_found`` rather than one error per operation tried.

    Returning :obj:`None` for everything else is load-bearing beyond error quality:
    :data:`~.sequence.OpSequenceItem` is ``DiscriminableOp | OpSequence``, and a nested sequence is
    a JSON array. Reporting no tag for an array lets that plain union fall through to
    :class:`~.sequence.OpSequence` rather than rejecting the array as a malformed operation.

    :param value: A mapping (raw input), an :class:`OpBase` instance, or anything else.
    :return: The discriminating key, or :obj:`None` if *value* carries none.
    """
    if isinstance(value, Mapping):
        return next(iter(value)) if len(value) == 1 else None
    if isinstance(value, OpBase):
        return type(value)._wire_tag()
    return None


def _operation_wire_tags(annotation: Any) -> tuple[str, ...]:
    """The wire tags every operation reachable through *annotation* is spelled with.

    An operation contributes its own tag; a union -- or an alias for one, which is how
    :data:`~.channel_ops.ChannelOp` reaches :data:`~.sequence.DiscriminableOp` -- contributes the
    tags of everything in it. Nothing is skipped silently: a member that is neither is a mistake
    that would otherwise drop out of the union unnoticed.

    :param annotation: An operation model, or a union of them however aliased or annotated.
    :return: The tags, in declaration order.
    :raises TypeError: If *annotation* is neither an operation nor a union of them, or names an
        operation whose tag is not statically known.
    """
    if isinstance(annotation, TypeAliasType):
        return _operation_wire_tags(annotation.__value__)
    if hasattr(annotation, "__metadata__"):
        return _operation_wire_tags(get_args(annotation)[0])
    if isinstance(annotation, type) and issubclass(annotation, OpBase):
        if (tag := annotation._wire_tag()) is None:
            raise TypeError(f"{annotation.__name__} has no statically known wire tag to discriminate it by")
        return (tag,)
    if members := get_args(annotation):
        return tuple(tag for member in members for tag in _operation_wire_tags(member))

    raise TypeError(f"{annotation!r} is neither an operation nor a union of operations")


class OperationDiscriminator:
    """Annotation marker turning a union of operations into a union tagged by wire key.

    Written once and applied to each union of operations::

        type ChannelOp = Annotated[Play | Wait | ..., OperationDiscriminator()]

    A member is tagged by the sole key its wire object carries -- the value of its ``op_type``
    literal, which :class:`~.base_models.NestedWireModel` lifts to that key -- so a new operation
    is tagged by declaring it, with nothing here to keep in step. A member that is itself a union
    of operations, as :data:`~.channel_ops.ChannelOp` is inside
    :data:`~.sequence.DiscriminableOp`, contributes one tag per operation it reaches while staying
    one named schema, which is what :obj:`~pydantic.Discriminator`'s string form did for the same
    nesting.

    The tag function is :func:`op_tag_of`, shared by every operation union rather than rebuilt per
    union: the tags are globally unique across operations, so there is no per-union binding to make
    the way :class:`~.units.UnitDiscriminator` needs one.
    """

    def __get_pydantic_core_schema__(self, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        """Build the tagged union's core schema from *source_type*'s members.

        :param source_type: The union of operation models this annotates.
        :param handler: The handler generating core schemas, reused for the rebuilt annotation.
        :return: The core schema of the equivalent :class:`~pydantic.Discriminator`-keyed union.
        :raises TypeError: If applied to anything but a union -- there is nothing to discriminate.
        """
        if not (operations := get_args(source_type)):
            raise TypeError(f"{type(self).__name__} annotates a union of operation models, not {source_type!r}")

        members = tuple(
            Annotated[operation, Tag(tag)] for operation in operations for tag in _operation_wire_tags(operation)
        )
        return handler.generate_schema(Annotated[Union[*members], Discriminator(op_tag_of)])


class _StartStopInterval(FrozenModel):
    """Internal base class for intervals defined by start and stop values."""

    start: int | float | complex
    """Start of the interval. It is included in the interval."""
    stop: int | float | complex
    """Stop of the interval. It is included in the interval."""

    _fields_to_scale_: ClassVar[tuple[str, ...]] = ("start", "stop")
    """Field names which should be scaled by multiplication/division operations."""
    _fields_to_offset_: ClassVar[tuple[str, ...]] = ("start", "stop")
    """Field names which should be offset by addition/subtraction operations."""

    def __mul__(self, other: int | float | complex) -> Self:
        if not isinstance(other, int | float | complex):
            return NotImplemented  # type: ignore[unreachable]
        return self.model_copy(update={field: getattr(self, field) * other for field in self._fields_to_scale_})  # type: ignore[return-value]

    def __rmul__(self, other: int | float | complex) -> Self:
        if not isinstance(other, int | float | complex):
            return NotImplemented  # type: ignore[unreachable]
        return self.model_copy(update={field: other * getattr(self, field) for field in self._fields_to_scale_})  # type: ignore[return-value]

    def __truediv__(self, other: int | float | complex) -> Self:
        if not isinstance(other, int | float | complex):
            return NotImplemented  # type: ignore[unreachable]
        return self.model_copy(update={field: getattr(self, field) / other for field in self._fields_to_scale_})  # type: ignore[return-value]

    def __add__(self, other: int | float | complex) -> Self:
        if not isinstance(other, int | float | complex):
            return NotImplemented  # type: ignore[unreachable]
        return self.model_copy(update={field: getattr(self, field) + other for field in self._fields_to_offset_})  # type: ignore[return-value]

    def __radd__(self, other: int | float | complex) -> Self:
        if not isinstance(other, int | float | complex):
            return NotImplemented  # type: ignore[unreachable]
        return self.model_copy(update={field: other + getattr(self, field) for field in self._fields_to_offset_})  # type: ignore[return-value]

    def __sub__(self, other: int | float | complex) -> Self:
        if not isinstance(other, int | float | complex):
            return NotImplemented  # type: ignore[unreachable]
        return self.model_copy(update={field: getattr(self, field) - other for field in self._fields_to_offset_})  # type: ignore[return-value]

    def __rsub__(self, other: int | float | complex) -> Self:
        if not isinstance(other, int | float | complex):
            return NotImplemented  # type: ignore[unreachable]
        return self.model_copy(update={field: other - getattr(self, field) for field in self._fields_to_offset_})  # type: ignore[return-value]


class LinSpace(LeanModel, _StartStopInterval):
    """Represents a linear space between two values.

    :ivar start: Starting value (can be real or complex)
    :ivar stop: Ending value (can be real or complex)
    :ivar num: Number of points in the space, including endpoints.

    .. note::
        Units should be specified in the variable declaration, not in the LinSpace itself.
    """

    num: int = Field(ge=1)
    """Number of points in the linear space, including both endpoints."""

    @model_validator(mode="after")
    def validate_model(self) -> Self:
        start, stop, num = self.start, self.stop, self.num
        if start != stop and num <= 1:
            raise ValueError("num must be greater than 1 for a non-trivial range")

        return self

    def __len__(self) -> int:
        """Return the number of points in the linear space."""
        return self.num


class Range(LeanModel, _StartStopInterval):
    """Represents a range of values with a start, stop, and step.

    The step can only be zero if the start and stop values are equal. Otherwise,
    the step must evenly divide the difference between the start and stop values.

    In case of complex numbers, the the difference must be an integral multiple of the step.
    The sign of the step is adjusted to ensure the stop value is reached.

    **The stop point is always included in the range.**

    :ivar start: Starting value (can be real or complex)
    :ivar stop: Ending value (can be real or complex) included in the range
    :ivar step: Step size (can be real or complex)

    .. note::
        Units should be specified in the variable declaration, not in the Range itself.
    """

    step: int | float | complex_from_tuple

    _fields_to_scale_ = ("start", "stop", "step")

    @cached_property
    def num(self) -> int:
        """Number of steps in the range, including both endpoints."""
        return abs(self._ndivs) + 1

    @model_validator(mode="after")
    def validate_model(self) -> Self:
        if self.step == 0:
            if self.start != self.stop:
                raise ValueError("step can only be 0 if start == stop")
        else:
            ndivs = self._ndivs
            step = -self.step if ndivs < 0 else self.step
            if not cmath.isclose(self.stop, self.start + step * ndivs):
                raise ValueError("step does not divide start - stop evenly")

        return self

    @cached_property
    def _ndivs(self) -> int:
        """Number of divisions between start and stop (excluding endpoints).

        It can be negative if step is in the opposite direction of start to stop.
        """
        return round(((self.stop - self.start) / self.step).real) if self.step != 0 else 0

    @cached_property
    def directional_step(self) -> int | float | complex:
        """Step value adjusted to ensure the stop value is reached from start."""
        return self.step if self._ndivs >= 0 else -self.step

    def __len__(self) -> int:
        """Return the number of points in the range."""
        return self.num


#
# These types below are only for type checking and IDE support for initialization arguments.
#


class AngleDict(TypedDict, total=False):
    """Dictionary representation of the arguments of Angle constructor.

    The fields are mutually exclusive; only one should be provided.
    """

    deg: int | float
    """degrees"""
    rad: float
    """radians"""
    turns: int | float
    """turns"""
    half_turns: int | float
    """half_turns"""


type AngleLike = Angle | Literal[0] | AngleDict | str
"""Type alias for Angle initialization arguments."""


type PhaseLike = Phase | Literal[0] | AngleDict | str
"""Type alias for Phase initialization arguments."""


class TimeDict(TypedDict, total=False):
    """Dictionary representation of the arguments of Time constructor.

    The fields are mutually exclusive; only one should be provided.
    """

    s: int | float
    """seconds"""
    ms: int | float
    """milliseconds"""
    us: int | float
    """microseconds"""
    ns: int


type TimeLike = Time | Literal[0] | TimeDict | str
"""Type alias for Time initialization arguments."""

type DurationLike = Duration | Literal[0] | TimeDict | str
"""Type alias for Duration initialization arguments."""


class VoltageDict(TypedDict, total=False):
    """Dictionary representation of the arguments of Voltage constructor.

    The fields are mutually exclusive; only one should be provided.
    """

    V: int | float
    """volts"""
    mV: int | float


type VoltageLike = Voltage | Literal[0] | VoltageDict | str
"""Type alias for Voltage initialization arguments."""
type AmplitudeLike = Amplitude | Literal[0] | VoltageDict | str
"""Type alias for Amplitude initialization arguments."""
type ThresholdLike = Threshold | Literal[0] | VoltageDict | str
"""Type alias for Threshold initialization arguments."""
type MagnitudeLike = Magnitude | Literal[0] | VoltageDict | str
"""Type alias for Magnitude initialization arguments."""


class ComplexVoltageDict(TypedDict, total=False):
    """Dictionary representation of the arguments of ComplexVoltage constructor.

    The fields are mutually exclusive; only one should be provided.
    """

    V: int | float | complex
    """volts"""
    mV: int | float | complex
    """millivolts"""


type ComplexVoltageLike = ComplexVoltage | Literal[0] | ComplexVoltageDict | str
"""Type alias for ComplexVoltage initialization arguments.

The fields are mutually exclusive; only one should be provided.
"""


class FrequencyDict(TypedDict, total=False):
    """Dictionary representation of the arguments of Frequency constructor.

    The fields are mutually exclusive; only one should be provided.
    """

    Hz: int | float
    """hertz"""
    kHz: int | float
    """kilohertz"""
    MHz: int | float
    """megahertz"""
    GHz: int | float


type FrequencyLike = Frequency | Literal[0] | FrequencyDict | str
"""Type alias for Frequency initialization arguments."""


class LinSpaceDict(TypedDict, total=True):
    """Dictionary representation of the arguments of LinSpace constructor.

    The fields are all required.
    """

    start: int | float | complex
    stop: int | float | complex
    num: int


type LinSpaceLike = LinSpace | LinSpaceDict
"""The type alias for LinSpace initialization arguments."""


class RangeDict(TypedDict, total=True):
    """Dictionary representation of the arguments of Range constructor.

    The fields are all required.
    """

    start: int | float | complex
    stop: int | float | complex
    step: int | float | complex


type RangeLike = Range | RangeDict
"""The type alias for Range initialization arguments."""
