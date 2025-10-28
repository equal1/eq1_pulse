"""Models for measurement units used for the basic types in the package.

Basic types of physical quantities may represent their values in various measurement units and
conversion between the units should be automatic.
"""

from __future__ import annotations

import cmath
from typing import TYPE_CHECKING, Any, Literal, Union

if TYPE_CHECKING:
    pass

from pydantic import TypeAdapter, model_validator
from pydantic.json_schema import DEFAULT_REF_TEMPLATE, GenerateJsonSchema, JsonSchemaMode

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


class BaseUnit(FrozenModel):
    """Base class for units, a model that accepts a numeric string followed by a property name.

    It will be stripped of whitespace and converted to a dictionary where the key is the property name.
    """

    @model_validator(mode="before")
    @classmethod
    def _model_validate(cls, data: Any) -> Any:
        if isinstance(data, str):
            value = data.rstrip()
            unit_name, unit_type = get_unit_value_field_name_and_type(cls)
            if value.endswith(unit_name):
                value = value.removesuffix(unit_name)
                unit_type_adapter: TypeAdapter[Any] = (
                    TypeAdapter(unit_type) if len(unit_type) == 1 else TypeAdapter(Union[*unit_type])
                )
                return {unit_name: unit_type_adapter.validate_python(value.strip(), strict=False)}
        return data

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = "validation",
        *,
        union_format: Literal["any_of", "primitive_type_array"] = "any_of",
    ) -> dict[str, Any]:
        """Generate the JSON schema for the model, adjusting for wrapped value representation."""
        base_schema = super().model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
            union_format=union_format,
        )
        unit, _ = get_unit_value_field_name_and_type(cls)
        assert str.isidentifier(unit)

        return {"anyOf": [base_schema, {"type": "string", "pattern": unit + r"\s*$"}]}


@register_unit_value_field("deg")
class Degrees(BaseUnit, SupportUnitArithmeticOperations[int | float]):
    """Degrees as a unit of angle."""

    deg: int | float
    """The angle in degrees. This is the value stored."""

    @property
    def rad(self) -> float:
        """The angle in radians. Computed on the fly."""
        return self.deg * cmath.pi / 180

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
        return 180 * collapse_float(self.rad / cmath.pi)

    @property
    def turns(self) -> int | float:
        """The angle in turns. Computed on the fly."""
        return collapse_float(self.rad / cmath.tau)

    @property
    def half_turns(self) -> int | float:
        """The angle in half turns. Computed on the fly."""
        return collapse_float(self.rad / cmath.pi)


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
        return self.turns * cmath.tau  # 2π = τ

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
        return self.half_turns * cmath.pi

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
class Kilohertz(FrozenModel, SupportUnitArithmeticOperations[int | float]):
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
class Megahertz(FrozenModel, SupportUnitArithmeticOperations[int | float]):
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
