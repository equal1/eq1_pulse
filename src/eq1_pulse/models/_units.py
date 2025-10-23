"""Models for physical units used for the basic types in the package.

Basic types may represent their values in various measurement units and
conversion between the units should be automatic.
"""

# ruff: noqa: D100 D101 D102 D105 D107 RUF100
from __future__ import annotations

import cmath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from ._arithmetic import SupportUnitArithmeticOperations, collapse_float, collapse_scalar, register_unit_value_field
from ._base_models import FrozenModel

#
# Angle units
#


@register_unit_value_field("deg")
class Degrees(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    """Degrees as a unit of angle."""

    deg: int | float

    @property
    def rad(self) -> float:
        return self.deg * cmath.pi / 180

    @property
    def turns(self) -> int | float:
        return collapse_float(self.deg / 360)

    @property
    def half_turns(self) -> int | float:
        return collapse_float(self.deg / 180)


@register_unit_value_field("rad")
class Radians(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    """Radians as a unit of angle."""

    rad: float

    @property
    def deg(self) -> int | float:
        return 180 * collapse_float(self.rad / cmath.pi)

    @property
    def turns(self) -> int | float:
        return collapse_float(self.rad / cmath.tau)

    @property
    def half_turns(self) -> int | float:
        return collapse_float(self.rad / cmath.pi)


@register_unit_value_field("turns")
class Turns(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    """Turns as a unit of angle.

    A turn is a full rotation, i.e. 360 degrees or 2π radians.
    """

    turns: int | float

    @property
    def deg(self) -> int | float:
        return 360 * self.turns

    @property
    def rad(self) -> float:
        return self.turns * cmath.tau  # 2π = τ

    @property
    def half_turns(self) -> int | float:
        return 2 * self.turns


@register_unit_value_field("half_turns")
class HalfTurns(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    """Half turns as a unit of angle.

    A half turn is half a full rotation, i.e. 180 degrees or π radians.
    """

    half_turns: int | float

    @property
    def deg(self) -> int | float:
        return collapse_float(180 * self.half_turns)

    @property
    def rad(self) -> float:
        return self.half_turns * cmath.pi

    @property
    def turns(self) -> int | float:
        return collapse_float(self.half_turns / 2)


@register_unit_value_field("s")
class Seconds(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    s: float

    @property
    def ms(self) -> float:
        return self.s * 1000

    @property
    def us(self) -> int | float:
        return collapse_float(self.s * 1e6)

    @property
    def ns(self) -> int:
        return round(self.s * 1.0e9)

    @property
    def _raw(self):
        return self.s


@register_unit_value_field("ms")
class Milliseconds(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    ms: int | float

    @property
    def s(self) -> float:
        return self.ms / 1000

    @property
    def us(self) -> int | float:
        return collapse_float(self.ms * 1e3)

    @property
    def ns(self) -> int:
        return round(self.ms * 1e6)

    @property
    def _raw(self):
        return self.ms


@register_unit_value_field("us")
class Microseconds(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    us: int | float

    @property
    def s(self) -> float:
        return self.us / 1e6

    @property
    def ms(self) -> int | float:
        return collapse_float(self.us / 1000)

    @property
    def ns(self) -> int:
        return round(self.us * 1000)

    @property
    def _raw(self):
        return self.us


@register_unit_value_field("ns")
class Nanoseconds(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    ns: int

    @property
    def s(self) -> float:
        return self.ns / 1e9

    @property
    def ms(self) -> int | float:
        return collapse_float(self.ns / 1e6)

    @property
    def us(self) -> int | float:
        return collapse_float(self.ns / 1000)

    @property
    def _raw(self):
        return self.ns


#
#  Voltage units
#


@register_unit_value_field("V")
class Volts(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    """Volts as a unit of voltage (real)."""

    V: int | float

    @property
    def mV(self) -> int | float:
        return collapse_float(self.V * 1000)

    @property
    def _raw(self) -> int | float:
        return self.V


@register_unit_value_field("mV")
class Millivolts(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    """Millivolts as a unit of voltage (real)."""

    mV: int | float

    @property
    def V(self) -> int | float:
        return collapse_float(self.mV / 1000)

    @property
    def _raw(self) -> int | float:
        return self.mV


@register_unit_value_field("V", (int, float, complex))
class ComplexVolts(FrozenModel, SupportUnitArithmeticOperations[int | float | complex]):
    """Volts as a unit of voltage (real + imaginary)."""

    V: int | float | complex

    @property
    def mV(self) -> int | float | complex:
        return collapse_scalar(self.V * 1000)

    @property
    def _raw(self) -> int | float | complex:
        return self.V

    @property
    def real(self) -> Volts:
        return Volts(V=self.V.real)

    @property
    def imag(self) -> Volts:
        return Volts(V=self.V.imag)


@register_unit_value_field("mV", (int, float, complex))
class ComplexMillivolts(FrozenModel, SupportUnitArithmeticOperations[int | float | complex]):
    """Millivolts as a unit of voltage (real + imaginary)."""

    mV: int | float | complex

    @property
    def V(self) -> float | complex:
        return collapse_scalar(self.mV / 1000)

    @property
    def _raw(self) -> int | float | complex:
        return self.mV

    @property
    def real(self) -> Millivolts:
        return Millivolts(mV=self.mV.real)

    @property
    def imag(self) -> Millivolts:
        return Millivolts(mV=self.mV.imag)


#
#  Frequency units
#


@register_unit_value_field("Hz")
class Hertz(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    Hz: int | float

    @property
    def kHz(self) -> int | float:
        return collapse_float(self.Hz / 1000)

    @property
    def MHz(self) -> int | float:
        return collapse_float(self.Hz / 1e6)

    @property
    def GHz(self) -> int | float:
        return collapse_float(self.Hz / 1e9)

    @property
    def _raw(self) -> int | float:
        return self.Hz


@register_unit_value_field("kHz")
class Kilohertz(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    kHz: int | float

    @property
    def Hz(self) -> int | float:
        return collapse_float(self.kHz * 1000)

    @property
    def MHz(self) -> int | float:
        return collapse_float(self.kHz / 1000)

    @property
    def GHz(self) -> int | float:
        return collapse_float(self.kHz / 1e6)

    @property
    def _raw(self) -> int | float:
        return self.kHz


@register_unit_value_field("MHz")
class Megahertz(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    MHz: int | float

    @property
    def Hz(self) -> int | float:
        return collapse_float(self.MHz * 1e6)

    @property
    def kHz(self) -> int | float:
        return collapse_float(self.MHz * 1000)

    @property
    def GHz(self) -> int | float:
        return collapse_float(self.MHz / 1000)

    @property
    def _raw(self) -> int | float:
        return self.MHz


@register_unit_value_field("GHz", (int, float))
class Gigahertz(FrozenModel, SupportUnitArithmeticOperations[int | float]):
    GHz: int | float

    @property
    def Hz(self) -> int | float:
        return collapse_float(self.GHz * 1e9)

    @property
    def kHz(self) -> int | float:
        return collapse_float(self.GHz * 1e6)

    @property
    def MHz(self) -> int | float:
        return collapse_float(self.GHz * 1000)

    @property
    def _raw(self) -> int | float:
        return self.GHz
