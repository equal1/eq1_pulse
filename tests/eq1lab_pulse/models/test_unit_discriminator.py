"""The unit union is discriminated by unit name, and derived from one registry.

See issue #10. The point of
:class:`~eq1_pulse.models.units.UnitDiscriminator` is not only that selection is a lookup rather
than a scoring pass, but that it is written once: a new unit is tagged by being declared, and no
per-quantity tag function exists to keep in step with it.
"""

from typing import Annotated

import pytest
from pydantic import ValidationError

from eq1_pulse.models.arithmetic import (
    SupportUnitArithmeticOperations,
    parse_unit_suffixed_value,
    register_unit_value_field,
)
from eq1_pulse.models.base_models import FrozenWrappedValueModel
from eq1_pulse.models.basic_types import ComplexVoltage, Duration, Frequency, Voltage
from eq1_pulse.models.units import (
    BaseUnit,
    ComplexMillivolts,
    ComplexVolts,
    Microseconds,
    Millivolts,
    Seconds,
    UnitDiscriminator,
    Volts,
)


def test_a_unit_typo_is_one_error_naming_the_units_that_exist():
    """Eight "did you mean" errors, one per union member, collapse to a single tag error."""
    with pytest.raises(ValidationError) as exc_info:
        Duration.model_validate({"usec": 3})

    (error,) = exc_info.value.errors()
    assert error["type"] == "union_tag_invalid"
    assert "'s', 'ms', 'us', 'ns'" in error["msg"]


def test_the_unit_selects_the_member_rather_than_the_first_one_that_fits():
    """Each unit name resolves to exactly its own model."""
    assert isinstance(Duration.model_validate({"s": 1}).root, Seconds)
    assert isinstance(Duration.model_validate({"us": 1}).root, Microseconds)
    assert isinstance(Voltage.model_validate({"mV": 1}).root, Millivolts)


def test_two_keys_is_not_a_tag():
    """A quantity is one unit, so an object with two of them names no member at all."""
    with pytest.raises(ValidationError) as exc_info:
        Frequency.model_validate({"Hz": 1e6, "MHz": 1.0})

    (error,) = exc_info.value.errors()
    assert error["type"] == "union_tag_not_found"


def test_the_shared_V_key_resolves_per_union():
    """``Volts`` and ``ComplexVolts`` share the key ``V`` and are told apart by their union.

    This is why the discriminator is bound to the units of the union it annotates rather than
    being one global function over the registry.
    """
    assert isinstance(Voltage.model_validate({"V": 1}).root, Volts)
    assert isinstance(ComplexVoltage.model_validate({"V": 1}).root, ComplexVolts)
    assert isinstance(ComplexVoltage.model_validate({"mV": [0, 1]}).root, ComplexMillivolts)


def test_declaring_a_unit_is_all_it_takes_to_tag_it():
    """A quantity built here, out of a unit registered here, discriminates with nothing else added.

    If this ever needs a tag function, a tag table or a per-quantity hook to pass, the mechanism
    has stopped being derived from :func:`register_unit_value_field`'s registry.
    """

    @register_unit_value_field("furlongs")
    class Furlongs(BaseUnit, SupportUnitArithmeticOperations[int | float]):
        """Furlongs as a unit of distance."""

        furlongs: int | float

    @register_unit_value_field("chains")
    class Chains(BaseUnit, SupportUnitArithmeticOperations[int | float]):
        """Chains as a unit of distance."""

        chains: int | float

    class Distance(FrozenWrappedValueModel):
        """A distance, in the units that matter."""

        root: Annotated[Furlongs | Chains, UnitDiscriminator()]

    assert Distance.model_validate({"furlongs": 3}).model_dump() == {"furlongs": 3}
    assert Distance.model_validate({"chains": 30}).model_dump() == {"chains": 30}
    with pytest.raises(ValidationError) as exc_info:
        Distance.model_validate({"fathoms": 3})
    assert exc_info.value.errors()[0]["type"] == "union_tag_invalid"


def test_the_discriminator_needs_a_union_to_discriminate():
    """Applied to a lone unit it says so, rather than failing somewhere inside typing."""
    with pytest.raises(TypeError, match="annotates a union of unit models"):

        class Distance(FrozenWrappedValueModel):
            """A distance with nothing to choose between."""

            root: Annotated[Seconds, UnitDiscriminator()]


def test_the_suffixed_string_parser_prefers_the_longer_unit():
    """``"10ms"`` is milliseconds, not ``"10m"`` seconds -- both end in ``s``."""
    units = Duration._unit_classes()
    assert parse_unit_suffixed_value("10ms", units) == {"ms": 10}
    assert parse_unit_suffixed_value("10s", units) == {"s": 10}
    assert parse_unit_suffixed_value(" 5 ns ", units) == {"ns": 5}

    with pytest.raises(ValueError, match="is not a number followed by one of the units"):
        parse_unit_suffixed_value("10 furlongs", units)
