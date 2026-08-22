"""The string and zero spellings are authoring forms, not wire forms.

See issue #10. A quantity validates the
``{unit: number}`` object and nothing else, in either direction. The two conveniences that used
to be accepted on the wire survive where they are actually written: the quantity constructors,
:meth:`~eq1_pulse.models.base_models.WrappedValueModel.parse`, the builder, and the pulse
factories. There is deliberately no validation-context flag that reopens them.
"""

import pytest
from pydantic import ValidationError

from eq1_pulse.builder import square_pulse
from eq1_pulse.models import Amplitude, Angle, Duration, Frequency, Phase, Time, Voltage
from eq1_pulse.models.channel_ops import Wait
from eq1_pulse.models.pulse_types import SquarePulse

QUANTITIES = (Time, Duration, Angle, Phase, Voltage, Amplitude, Frequency)


@pytest.mark.parametrize("cls", QUANTITIES)
def test_the_suffixed_string_is_not_a_wire_form(cls):
    """``model_validate`` reads the object form only."""
    with pytest.raises(ValidationError):
        cls.model_validate("10us" if cls in (Time, Duration) else "1V")


@pytest.mark.parametrize("cls", QUANTITIES)
def test_the_bare_zero_is_not_a_wire_form(cls):
    """Nor is the literal ``0``, which used to be accepted in place of a value in any unit."""
    with pytest.raises(ValidationError):
        cls.model_validate(0)


@pytest.mark.parametrize("cls", QUANTITIES)
def test_both_survive_as_constructor_arguments(cls):
    """What a program writes is unchanged; only what a document may say is narrower."""
    assert cls(0) == 0


def test_parse_reads_the_grammar_for_every_quantity():
    """One method on the quantity base, over each quantity's own declared units."""
    assert Duration.parse("10us").us == 10
    assert Duration.parse(" 10 ms ").ms == 10
    assert Frequency.parse("5 GHz").GHz == 5
    assert Angle.parse("90deg").deg == 90
    assert Amplitude.parse("100mV").mV == 100


def test_parse_rejects_a_unit_the_quantity_does_not_have():
    """``Duration.parse("5GHz")`` is an error, not a frequency."""
    with pytest.raises(ValueError, match="is not a number followed by one of the units"):
        Duration.parse("5GHz")


def test_parse_still_applies_the_quantity_s_own_validation():
    """A duration read from a string is still a duration, non-negativity included."""
    with pytest.raises(ValidationError, match="nonnegative"):
        Duration.parse("-10us")


def test_the_constructor_and_parse_agree_with_the_object_form():
    """Three spellings, one value, one wire form."""
    canonical = Duration.model_validate({"us": 10})
    assert Duration("10us") == Duration.parse("10us") == canonical
    assert canonical.model_dump() == {"us": 10}


def test_the_authoring_paths_that_remain():
    """The builder and the pulse factories still take what a user means.

    Plan §5: the builder takes what you mean, the model takes what the wire says.
    """
    pulse = square_pulse(duration="10us", amplitude="100mV")
    assert pulse.duration == Duration(us=10)
    assert pulse.amplitude == Amplitude(mV=100)

    assert Wait(channels=["ch1"], duration=Duration("10us")).duration == Duration(us=10)
    with pytest.raises(ValidationError):
        Wait(channels=["ch1"], duration="10us")  # type: ignore[call-overload]

    assert SquarePulse(duration=Duration("10us"), amplitude=Amplitude("100mV")).duration == Duration(us=10)
    with pytest.raises(ValidationError):
        SquarePulse(duration="10us", amplitude="100mV")  # type: ignore[arg-type]
