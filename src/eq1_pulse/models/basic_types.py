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
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, TypedDict, overload

from pydantic import Field, model_validator

from .base_models import (
    FrozenLeanModel,
    FrozenModel,
    FrozenWrappedValueModel,
    LeanModel,
    WrappedValueOrZeroModel,
)
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
    Volts,
)

__all__ = (
    "Amplitude",
    "Angle",
    "ComplexMillivolts",
    "ComplexVoltage",
    "ComplexVolts",
    "ComplexVolts",
    "Degrees",
    "Duration",
    "Frequency",
    "Gigahertz",
    "HalfTurns",
    "Hertz",
    "Kilohertz",
    "LeanModel",
    "LinSpace",
    "Magnitude",
    "Megahertz",
    "Microseconds",
    "Milliseconds",
    "Milliseconds",
    "Millivolts",
    "Nanoseconds",
    "OpBase",
    "Phase",
    "Radians",
    "Range",
    "Seconds",
    "Threshold",
    "Time",
    "Turns",
    "Voltage",
    "Volts",
)


class ArithmeticFrozenWrappedValueModel[ScalarType](FrozenWrappedValueModel):
    def __neg__(self: Self) -> Self:
        return type(self).model_construct(value=-self.value)  # type: ignore[return-value]

    def __pos__(self: Self) -> Self:
        return type(self).model_construct(value=+self.value)  # type: ignore[return-value]

    def __add__(self: Self, other: Self) -> Self:
        return type(self).model_construct(value=self.value + other.value)  # type: ignore[return-value]

    def __sub__(self: Self, other: Self) -> Self:
        return type(self).model_construct(value=self.value - other.value)  # type: ignore[return-value]

    @overload
    def __floordiv__(self: Self, other: ScalarType) -> Self: ...

    @overload
    def __floordiv__(self: Self, other: Self) -> ScalarType: ...

    def __floordiv__(self: Self, other: ScalarType | Self) -> Self | ScalarType:
        if isinstance(other, type(self)) or isinstance(self, type(other)):
            return self.value // other.value  # type: ignore
        return type(self).model_construct(value=self.value // other)  # type: ignore[return-value]

    def __mod__(self: Self, other: Self) -> Self:
        return type(self).model_construct(value=self.value % other.value)  # type: ignore[return-value]

    def __mul__(self: Self, other: ScalarType) -> Self:
        return type(self).model_construct(value=self.value * other)  # type: ignore[return-value]

    def __rmul__(self: Self, other: ScalarType) -> Self:
        return type(self).model_construct(value=other * self.value)  # type: ignore[return-value]

    @overload
    def __truediv__(self, other: ScalarType) -> Self: ...
    @overload
    def __truediv__(self, other: Self) -> ScalarType: ...

    def __truediv__(self: Self, other: ScalarType | Self) -> Self | ScalarType:
        if isinstance(other, type(self)):
            return self.value / other.value  # type: ignore
        return type(self).model_construct(value=self.value / other)  # type: ignore[return-value]


class Angle(WrappedValueOrZeroModel, ArithmeticFrozenWrappedValueModel[int | float]):
    r"""A model representing an angle in either degrees, radians, turns or half-turns.

    Turns are also known as revolutions or cycles, also :math:`\tau=2\pi` radians or 360°.
    Half-turns are also known as half-cycles, also :math:`\pi` radians or 180°.
    """  # noqa: E501

    @overload
    def __init__(self, _: Literal[0], /): ...

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
        super().__init__(**self._apply_default_zero_args_to_init_data("rad", args, data))

    value: Degrees | Radians | Turns | HalfTurns
    """The underlying angle value in one of the supported units."""

    @property
    def deg(self) -> int | float:
        """Value in degrees."""
        return self.value.deg

    @property
    def rad(self) -> float:
        """Value in radians."""
        return self.value.rad

    @property
    def turns(self) -> float:
        """Value in turns."""
        return self.value.turns

    @property
    def half_turns(self) -> float:
        """Value in half-turns."""
        return self.value.half_turns

    def __eq__(self, other) -> bool:
        """Equality comparison with another Angle instance."""  # noqa: D401
        if not isinstance(other, Angle):
            return NotImplemented
        return self.value == other.value or self.value.turns == other.value.turns

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
    """Special case of Angle where the value represents a phase angle."""

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0], /): ...

        @overload
        def __init__(self, /, *, deg: int | float): ...

        @overload
        def __init__(self, /, *, rad: float): ...

        @overload
        def __init__(self, /, *, turns: float): ...

        def __init__(self, /, *args, **data): ...


class Time(WrappedValueOrZeroModel, ArithmeticFrozenWrappedValueModel[int | float]):
    """A model representing time (instant or difference).

    The model can represent time in seconds, milliseconds, microseconds, or nanoseconds,
    with automatic conversion between the units.

    The storage type for milliseconds is integer, while for other units it is float.
    Conversion to nanoseconds is rounded to the nearest integer.
    """

    value: Seconds | Milliseconds | Microseconds | Nanoseconds
    """The underlying time value in one of the supported units."""

    @property
    def s(self) -> float:
        """Value in seconds."""
        return self.value.s

    @property
    def ms(self) -> float:
        """Value in milliseconds."""
        return self.value.ms

    @property
    def us(self) -> float:
        """Value in microseconds."""
        return self.value.us

    @property
    def ns(self) -> int:
        """Value in nanoseconds."""
        return self.value.ns

    @overload
    def __init__(self, _: Literal[0], /): ...

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
        super().__init__(**self._apply_default_zero_args_to_init_data("s", args, data))

    def __eq__(self, other) -> bool:
        """Equality comparison with another Time instance."""  # noqa: D401
        if not isinstance(other, Time):
            return NotImplemented
        return self.value == other.value or self.value.s == other.value.s

    def __bool__(self) -> bool:
        """Return True if the time value is non-zero."""
        return bool(self.value._raw)


class Duration(Time):
    """Special case of non-negative Time representing a duration."""

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0], /): ...

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
        if data.value._raw < 0:
            raise ValueError("expected nonnegative duration value")
        return data


class Voltage(WrappedValueOrZeroModel, ArithmeticFrozenWrappedValueModel[int | float]):
    """A model representing a real voltage in volts or millivolts."""

    value: Volts | Millivolts

    @property
    def V(self) -> int | float:
        return self.value.V

    @property
    def mV(self) -> int | float:
        return self.value.mV

    @overload
    def __init__(self, _: Literal[0], /): ...

    @overload
    def __init__(self, /, *, V: int | float): ...

    @overload
    def __init__(self, /, *, mV: int | float): ...

    def __init__(self, /, *args, **data):
        super().__init__(**self._apply_default_zero_args_to_init_data("V", args, data))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Voltage | ComplexVoltage):
            return NotImplemented
        return self.value == other.value or self.value.V == other.value.V

    def __bool__(self) -> bool:
        return bool(self.value._raw)

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


class ComplexVoltage(WrappedValueOrZeroModel, ArithmeticFrozenWrappedValueModel[int | float | complex]):
    """A model representing a complex voltage in volts or millivolts.

    Complex voltages are used to represent both amplitude and phase information,
    and are used with with mixing or demodulation operations.
    """

    value: ComplexVolts | ComplexMillivolts

    @property
    def V(self) -> complex:
        return self.value.V

    @property
    def mV(self) -> complex:
        return self.value.mV

    @overload
    def __init__(self, _: Literal[0], /): ...

    @overload
    def __init__(self, /, *, V: complex): ...

    @overload
    def __init__(self, /, *, mV: complex): ...

    def __init__(self, /, *args, **data):
        super().__init__(**self._apply_default_zero_args_to_init_data("V", args, data))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Voltage | ComplexVoltage):
            return NotImplemented
        return self.value == other.value or self.value.V == other.value.V

    def __mul__(self: Self, other: int | float | complex) -> Self:
        if isinstance(other, int | float | complex):
            return type(self).model_construct(value=self.value * other)  # type: ignore[return-value]
        return NotImplemented  # type: ignore[unreachable]

    def __rmul__(self: Self, other: int | float | complex) -> Self:
        if isinstance(other, int | float | complex):
            return type(self).model_construct(value=other * self.value)  # type: ignore[return-value]
        return NotImplemented  # type: ignore[unreachable]

    def __bool__(self) -> bool:
        return bool(self.value._raw)

    @classmethod
    def create_from(cls, real: Voltage, imag: Voltage = Voltage(0), /) -> Self:  # noqa: B008
        """Create a ComplexVoltage from a Voltage, setting the imaginary part to zero."""
        if isinstance(real.value, Volts):
            return cls(V=complex(real.V, imag.V))
        else:
            return cls(mV=complex(real.mV, imag.mV))

    @property
    def real(self) -> Voltage:
        """Get the real part of the complex voltage as a Voltage instance."""
        return Voltage.from_value(self.value.real)

    @property
    def imag(self) -> Voltage:
        """Get the imaginary part of the complex voltage as a Voltage instance."""
        return Voltage.from_value(self.value.imag)


class Frequency(WrappedValueOrZeroModel, ArithmeticFrozenWrappedValueModel[int | float]):
    """A model representing a frequency in Hertz, Kilohertz, Megahertz, or Gigahertz."""

    value: Hertz | Kilohertz | Megahertz | Gigahertz

    @property
    def Hz(self) -> int | float:
        return self.value.Hz

    @property
    def kHz(self) -> int | float:
        return self.value.kHz

    @property
    def MHz(self) -> int | float:
        return self.value.MHz

    @property
    def GHz(self) -> int | float:
        return self.value.GHz

    @overload
    def __init__(self, _: Literal[0], /): ...

    @overload
    def __init__(self, /, Hz: float): ...

    @overload
    def __init__(self, /, *, kHz: float): ...

    @overload
    def __init__(self, /, *, MHz: float): ...

    @overload
    def __init__(self, /, *, GHz: float): ...

    def __init__(self, /, *args, **data):
        super().__init__(**self._apply_default_zero_args_to_init_data("Hz", args, data))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Frequency):
            return NotImplemented
        return self.value == other.value or self.value.Hz == other.value.Hz

    def __bool__(self) -> bool:
        return bool(self.value._raw)


class Amplitude(ComplexVoltage):
    """Model to represent the (complex) amplitude of a voltage signal."""

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0], /): ...

        @overload
        def __init__(self, /, *, V: float | complex): ...

        @overload
        def __init__(self, /, *, mV: float | complex): ...

        def __init__(self, *args, **data): ...


class Threshold(Voltage):
    """Model to represent a (real) threshold voltage level."""

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0], /): ...

        @overload
        def __init__(self, /, *, V: float | complex): ...

        @overload
        def __init__(self, /, *, mV: float | complex): ...

        def __init__(self, *args, **data): ...


class Magnitude(Voltage):
    """Special case of non-negative real Voltage representing a maximum amplitude."""

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0], /): ...

        @overload
        def __init__(self, /, *, V: float): ...

        @overload
        def __init__(self, /, *, mV: float): ...

        def __init__(self, /, *args, **data): ...

    @model_validator(mode="wrap")
    @classmethod
    def _validate_nonnegative_raw_value(cls, data, handler):
        data = handler(data)
        if data.value._raw < 0:
            raise ValueError("expected nonnegative magnitude value")
        return data


class OpBase(FrozenLeanModel):
    """Base class for all operation models.

    The ``op_type`` field should be a literal string representing the operation type,
    overridden in subclasses.
    """

    if TYPE_CHECKING:

        def __init__(self, *args, **kwargs): ...

    op_type: Any  # str


class _StartStopInterval(FrozenModel):
    start: int | float | complex
    stop: int | float | complex

    _fields_to_scale_: ClassVar[tuple[str, ...]] = ("start", "stop")
    _fields_to_offset_: ClassVar[tuple[str, ...]] = ("start", "stop")

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


class LinSpace(_StartStopInterval):
    """Represents a linear space between two values.

    :ivar start: Starting value (can be real or complex)
    :ivar stop: Ending value (can be real or complex)
    :ivar num: Number of points in the space, including endpoints.
    """

    num: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_model(self) -> Self:
        start, stop, num = self.start, self.stop, self.num
        if start != stop and num <= 1:
            raise ValueError("num must be greater than 1 for a non-trivial range")

        return self

    def __len__(self) -> int:
        """Return the number of points in the linear space."""
        return self.num


class Range(_StartStopInterval):
    """Represents a range of values with a start, stop, and step.

    The step can only be zero if the start and stop values are equal. Otherwise,
    the step must evenly divide the difference between the start and stop values.

    In case of complex numbers, the the difference must be an integral multiple of the step.
    The sign of the step is adjusted to ensure the stop value is reached.

    The stop point is always included in the range.

    :ivar start: Starting value (can be real or complex)
    :ivar stop: Ending value (can be real or complex) included in the range
    :ivar step: Step size (can be real or complex)
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
# These types below are only for type checking and not part of the runtime code.
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


type AngleLike = Angle | Literal[0] | AngleDict
"""Type alias for Angle initialization arguments."""


type PhaseLike = Phase | Literal[0] | AngleDict
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


type TimeLike = Time | Literal[0] | TimeDict
"""Type alias for Time initialization arguments."""

type DurationLike = Duration | Literal[0] | TimeDict
"""Type alias for Duration initialization arguments."""


class VoltageDict(TypedDict, total=False):
    """Dictionary representation of the arguments of Voltage constructor.

    The fields are mutually exclusive; only one should be provided.
    """

    V: int | float
    """volts"""
    mV: int | float


type VoltageLike = Voltage | Literal[0] | VoltageDict
"""Type alias for Voltage initialization arguments."""
type AmplitudeLike = Amplitude | Literal[0] | VoltageDict
"""Type alias for Amplitude initialization arguments."""
type ThresholdLike = Threshold | Literal[0] | VoltageDict
"""Type alias for Threshold initialization arguments."""
type MagnitudeLike = Magnitude | Literal[0] | VoltageDict
"""Type alias for Magnitude initialization arguments."""


class ComplexVoltageDict(TypedDict, total=False):
    """Dictionary representation of the arguments of ComplexVoltage constructor.

    The fields are mutually exclusive; only one should be provided.
    """

    V: int | float | complex
    """volts"""
    mV: int | float | complex
    """millivolts"""


type ComplexVoltageLike = ComplexVoltage | Literal[0] | ComplexVoltageDict
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


type FrequencyLike = Frequency | Literal[0] | FrequencyDict
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
