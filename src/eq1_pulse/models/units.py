"""Models for measurement units used for the basic types in the package.

Basic types of physical quantities may represent their values in various measurement units and
conversion between the units should be automatic.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Annotated, Any, Union, get_args

from pydantic import Discriminator, GetCoreSchemaHandler, Tag
from pydantic_core import CoreSchema

from .arithmetic import (
    SupportUnitArithmeticOperations,
    collapse_float,
    collapse_scalar,
    get_unit_value_field_name_and_type,
    register_unit_value_field,
)
from .base_models import FrozenModel
from .complex import complex_from_tuple

#
# Angle units
#

__all__ = (
    "ComplexMillivolts",
    "ComplexVolts",
    "Degrees",
    "Gigahertz",
    "HalfTurns",
    "Hertz",
    "Kilohertz",
    "Megahertz",
    "Microseconds",
    "Milliseconds",
    "Millivolts",
    "Nanoseconds",
    "Radians",
    "Seconds",
    "Turns",
    "Volts",
)


class UnitDiscriminator:
    """Annotation marker turning a union of unit models into a union tagged by unit name.

    Written once and applied to every quantity's unit union::

        root: Annotated[Seconds | Milliseconds | Microseconds | Nanoseconds, UnitDiscriminator()]

    The tags come from :func:`~.arithmetic.register_unit_value_field`'s registry -- the same one
    the operator mixins and the ``"<number><unit>"`` parser read -- so a new unit is tagged by
    declaring it, with nothing here to keep in step.

    The tag function is bound to the units of the union it is applied to rather than being global:
    :class:`Volts` and :class:`ComplexVolts` both key on ``V`` and are only ever in *different*
    unions (:class:`~.basic_types.Voltage` and :class:`~.basic_types.ComplexVoltage`), where each
    union's keys are unique.

    Selection is a lookup on the sole key rather than a scoring pass over every member, so a unit
    typo is one ``union_tag_invalid`` error naming the units that exist, not one error per member.
    """

    def __get_pydantic_core_schema__(self, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        """Build the tagged union's core schema from *source_type*'s members.

        :param source_type: The union of unit models this annotates.
        :param handler: The handler generating core schemas, reused for the rebuilt annotation.
        :return: The core schema of the equivalent :class:`~pydantic.Discriminator`-keyed union.
        :raises TypeError: If applied to anything but a union -- there is nothing to discriminate.
        """
        if not (units := get_args(source_type)):
            raise TypeError(f"{type(self).__name__} annotates a union of unit models, not {source_type!r}")

        tags = {unit: get_unit_value_field_name_and_type(unit)[0] for unit in units}

        def unit_of(value: Any) -> str | None:
            """Return the unit *value* is spelled in, or :obj:`None` to report an unknown tag."""
            if isinstance(value, Mapping):
                return next(iter(value)) if len(value) == 1 else None
            return tags.get(type(value))

        members = tuple(Annotated[unit, Tag(tag)] for unit, tag in tags.items())
        return handler.generate_schema(Annotated[Union[*members], Discriminator(unit_of)])


class BaseUnit(FrozenModel):
    """Base class for units: a frozen model whose single field is named for the unit itself.

    ``extra="forbid"``, inherited from :class:`~.base_models.FrozenModel`, is what makes that one
    key exclusive, and so what lets :class:`UnitDiscriminator` select a unit by it.

    The unit-suffixed string (``"10us"``) used to be accepted here, by a before-validator paired
    with a schema hook that advertised a form nothing ever produced. It is now read only where it
    is authored, by :meth:`~.base_models.WrappedValueModel.parse` and the quantity constructors,
    over :func:`~.arithmetic.parse_unit_suffixed_value`.
    """


@register_unit_value_field("deg")
class Degrees(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Degrees as a unit of angle."""

    deg: int | float
    """The angle in degrees. This is the value stored."""

    @property
    def rad(self) -> float:
        """The angle in radians. Computed on the fly."""
        return math.radians(self.deg)

    @property
    def turns(self) -> int | float:
        """The angle in turns. Computed on the fly."""
        return collapse_float(self.deg / 360)

    @property
    def half_turns(self) -> int | float:
        """The angle in half turns. Computed on the fly."""
        return collapse_float(self.deg / 180)


@register_unit_value_field("rad")
class Radians(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Radians as a unit of angle."""

    rad: float
    """The angle in radians. This is the value stored."""

    @property
    def deg(self) -> int | float:
        """The angle in degrees. Computed on the fly."""
        return collapse_float(math.degrees(self.rad))

    @property
    def turns(self) -> int | float:
        """The angle in turns. Computed on the fly."""
        return collapse_float(self.rad / math.tau)

    @property
    def half_turns(self) -> int | float:
        """The angle in half turns. Computed on the fly."""
        return collapse_float(self.rad / math.pi)


@register_unit_value_field("turns")
class Turns(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Turns as a unit of angle.

    A turn is a full rotation, i.e. 360 degrees or 2π radians.
    """

    turns: int | float
    """The angle in turns. This is the value stored."""

    @property
    def deg(self) -> int | float:
        """The angle in degrees. Computed on the fly."""
        return 360 * self.turns

    @property
    def rad(self) -> float:
        """The angle in radians. Computed on the fly."""
        return self.turns * math.tau  # 2π = τ

    @property
    def half_turns(self) -> int | float:
        """The angle in half turns. Computed on the fly."""
        return 2 * self.turns


@register_unit_value_field("half_turns")
class HalfTurns(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Half turns as a unit of angle.

    A half turn is half a full rotation, i.e. 180 degrees or π radians.
    """

    half_turns: int | float
    """The angle in half turns. This is the value stored."""

    @property
    def deg(self) -> int | float:
        """The angle in degrees. Computed on the fly."""
        return collapse_float(180 * self.half_turns)

    @property
    def rad(self) -> float:
        """The angle in radians. Computed on the fly."""
        return self.half_turns * math.pi

    @property
    def turns(self) -> int | float:
        """The angle in turns. Computed on the fly."""
        return collapse_float(self.half_turns / 2)


@register_unit_value_field("s")
class Seconds(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Seconds as a unit of time."""

    s: float
    """The time in seconds. This is the value stored."""

    @property
    def ms(self) -> float:
        """The time in milliseconds. Computed on the fly."""
        return self.s * 1000

    @property
    def us(self) -> int | float:
        """The time in microseconds. Computed on the fly."""
        return collapse_float(self.s * 1e6)

    @property
    def ns(self) -> int:
        """The time in nanoseconds. Computed on the fly."""
        return round(self.s * 1.0e9)

    @property
    def _raw(self):
        """The raw stored value."""
        return self.s


@register_unit_value_field("ms")
class Milliseconds(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Milliseconds as a unit of time."""

    ms: int | float
    """The time in milliseconds. This is the value stored."""

    @property
    def s(self) -> float:
        """The time in seconds. Computed on the fly."""
        return self.ms / 1000

    @property
    def us(self) -> int | float:
        """The time in microseconds. Computed on the fly."""
        return collapse_float(self.ms * 1e3)

    @property
    def ns(self) -> int:
        """The time in nanoseconds. Computed on the fly."""
        return round(self.ms * 1e6)

    @property
    def _raw(self):
        """The raw stored value."""
        return self.ms


@register_unit_value_field("us")
class Microseconds(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Microseconds as a unit of time."""

    us: int | float
    """The time in microseconds. This is the value stored."""

    @property
    def s(self) -> float:
        """The time in seconds. Computed on the fly."""
        return self.us / 1e6

    @property
    def ms(self) -> int | float:
        """The time in milliseconds. Computed on the fly."""
        return collapse_float(self.us / 1000)

    @property
    def ns(self) -> int:
        """The time in nanoseconds. Computed on the fly."""
        return round(self.us * 1000)

    @property
    def _raw(self):
        """The raw stored value."""
        return self.us


@register_unit_value_field("ns")
class Nanoseconds(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Nanoseconds as a unit of time."""

    ns: int
    """The time in nanoseconds. This is the value stored."""

    @property
    def s(self) -> float:
        """The time in seconds. Computed on the fly."""
        return self.ns / 1e9

    @property
    def ms(self) -> int | float:
        """The time in milliseconds. Computed on the fly."""
        return collapse_float(self.ns / 1e6)

    @property
    def us(self) -> int | float:
        """The time in microseconds. Computed on the fly."""
        return collapse_float(self.ns / 1000)

    @property
    def _raw(self):
        """The raw stored value."""
        return self.ns


#
#  Voltage units
#


@register_unit_value_field("V")
class Volts(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Volts as a unit of voltage (real)."""

    V: int | float
    """The voltage in volts. This is the value stored."""

    @property
    def mV(self) -> int | float:
        """The voltage in millivolts. Computed on the fly."""
        return collapse_float(self.V * 1000)

    @property
    def _raw(self) -> int | float:
        """The raw stored value."""
        return self.V

    def __abs__(self) -> Volts:
        """The magnitude of the complex voltage."""
        return Volts(V=abs(self.V))


@register_unit_value_field("mV")
class Millivolts(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Millivolts as a unit of voltage (real)."""

    mV: int | float
    """The voltage in millivolts. This is the value stored."""

    @property
    def V(self) -> int | float:
        """The voltage in volts. Computed on the fly."""
        return collapse_float(self.mV / 1000)

    @property
    def _raw(self) -> int | float:
        """The raw stored value."""
        return self.mV

    def __abs__(self) -> Millivolts:
        """The magnitude of the complex voltage."""
        return Millivolts(mV=abs(self.mV))


@register_unit_value_field("V", (int, float, complex))
class ComplexVolts(BaseUnit, SupportUnitArithmeticOperations[int | float | complex]):
    """Volts as a unit of voltage (real + imaginary)."""

    V: int | float | complex_from_tuple
    """The voltage in volts. This is the value stored."""

    @property
    def mV(self) -> int | float | complex:
        """The voltage in millivolts. Computed on the fly."""
        return collapse_scalar(self.V * 1000)

    @property
    def _raw(self) -> int | float | complex:
        """The raw stored value."""
        return self.V

    @property
    def real(self) -> Volts:
        """The real part of the voltage as Volts."""
        return Volts(V=self.V.real)

    @property
    def imag(self) -> Volts:
        """The imaginary part of the voltage as Volts."""
        return Volts(V=self.V.imag)

    def __abs__(self) -> Volts:
        """The magnitude of the complex voltage."""
        return Volts(V=abs(self.V))


@register_unit_value_field("mV", (int, float, complex))
class ComplexMillivolts(BaseUnit, SupportUnitArithmeticOperations[int | float | complex]):
    """Millivolts as a unit of voltage (real + imaginary)."""

    mV: int | float | complex_from_tuple
    """The voltage in millivolts. This is the value stored."""

    @property
    def V(self) -> float | complex:
        """The voltage in volts. Computed on the fly."""
        return collapse_scalar(self.mV / 1000)

    @property
    def _raw(self) -> int | float | complex:
        """The raw stored value."""
        return self.mV

    @property
    def real(self) -> Millivolts:
        """The real part of the voltage as Millivolts."""
        return Millivolts(mV=self.mV.real)

    @property
    def imag(self) -> Millivolts:
        """The imaginary part of the voltage as Millivolts."""
        return Millivolts(mV=self.mV.imag)

    def __abs__(self) -> Millivolts:
        """The magnitude of the complex voltage."""
        return Millivolts(mV=abs(self.mV))


#
#  Frequency units
#


@register_unit_value_field("Hz")
class Hertz(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Hertz as a unit of frequency."""

    Hz: int | float
    """The frequency in hertz. This is the value stored."""

    @property
    def kHz(self) -> int | float:
        """The frequency in kilohertz. Computed on the fly."""
        return collapse_float(self.Hz / 1000)

    @property
    def MHz(self) -> int | float:
        """The frequency in megahertz. Computed on the fly."""
        return collapse_float(self.Hz / 1e6)

    @property
    def GHz(self) -> int | float:
        """The frequency in gigahertz. Computed on the fly."""
        return collapse_float(self.Hz / 1e9)

    @property
    def _raw(self) -> int | float:
        """The raw stored value."""
        return self.Hz


@register_unit_value_field("kHz")
class Kilohertz(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Kilohertz as a unit of frequency."""

    kHz: int | float
    """The frequency in kilohertz. This is the value stored."""

    @property
    def Hz(self) -> int | float:
        """The frequency in hertz. Computed on the fly."""
        return collapse_float(self.kHz * 1000)

    @property
    def MHz(self) -> int | float:
        """The frequency in megahertz. Computed on the fly."""
        return collapse_float(self.kHz / 1000)

    @property
    def GHz(self) -> int | float:
        """The frequency in gigahertz. Computed on the fly."""
        return collapse_float(self.kHz / 1e6)

    @property
    def _raw(self) -> int | float:
        """The raw stored value."""
        return self.kHz


@register_unit_value_field("MHz")
class Megahertz(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Megahertz as a unit of frequency."""

    MHz: int | float
    """The frequency in megahertz. This is the value stored."""

    @property
    def Hz(self) -> int | float:
        """The frequency in hertz. Computed on the fly."""
        return collapse_float(self.MHz * 1e6)

    @property
    def kHz(self) -> int | float:
        """The frequency in kilohertz. Computed on the fly."""
        return collapse_float(self.MHz * 1000)

    @property
    def GHz(self) -> int | float:
        """The frequency in gigahertz. Computed on the fly."""
        return collapse_float(self.MHz / 1000)

    @property
    def _raw(self) -> int | float:
        """The raw stored value."""
        return self.MHz


@register_unit_value_field("GHz", (int, float))
class Gigahertz(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Gigahertz as a unit of frequency."""

    GHz: int | float
    """The frequency in gigahertz. This is the value stored."""

    @property
    def Hz(self) -> int | float:
        """The frequency in hertz. Computed on the fly."""
        return collapse_float(self.GHz * 1e9)

    @property
    def kHz(self) -> int | float:
        """The frequency in kilohertz. Computed on the fly."""
        return collapse_float(self.GHz * 1e6)

    @property
    def MHz(self) -> int | float:
        """The frequency in megahertz. Computed on the fly."""
        return collapse_float(self.GHz * 1000)

    @property
    def _raw(self) -> int | float:
        """The raw stored value."""
        return self.GHz
