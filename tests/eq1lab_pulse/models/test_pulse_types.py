from typing import Any

from pydantic import TypeAdapter

from eq1_pulse.models.basic_types import Amplitude, Duration, Frequency
from eq1_pulse.models.pulse_types import PulseType, SinePulse, SquarePulse
from eq1_pulse.models.reference_types import VariableRef

"""Tests for pulse type models."""


def test_square_pulse_creation():
    """Test creating a square pulse with basic parameters."""
    pulse = SquarePulse(
        duration=Duration(s=1e-6),
        amplitude=Amplitude(V=0.5),
    )
    assert pulse.pulse_type == "square"
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert pulse.rise_time is None
    assert pulse.fall_time is None
    assert pulse.duration.s == 1e-6
    assert pulse.amplitude.V == 0.5


def test_ramp_pulse_creation():
    """Test creating a square pulse with basic parameters."""
    pulse = SquarePulse(
        duration=Duration(s=1e-6),
        amplitude=Amplitude(V=0.5),
        rise_time=Duration(s=1e-9),
        fall_time=Duration(s=1e-9),
    )
    assert pulse.pulse_type == "square"
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert isinstance(pulse.rise_time, Duration)
    assert isinstance(pulse.fall_time, Duration)
    assert pulse.duration.s == 1e-6
    assert pulse.amplitude.V == 0.5
    assert pulse.rise_time.s == 1e-9
    assert pulse.fall_time.s == 1e-9


def test_square_pulse_creation_dicts():
    """Test creating a square pulse with basic parameters."""
    pulse = SquarePulse(
        duration={"s": 1e-6},
        amplitude={"V": 0.5},
    )
    assert pulse.pulse_type == "square"
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert pulse.rise_time is None
    assert pulse.fall_time is None
    assert pulse.duration.s == 1e-6
    assert pulse.amplitude.V == 0.5


def test_ramp_pulse_creation_dicts():
    """Test creating a square pulse with basic parameters."""
    pulse = SquarePulse(
        duration={"s": 1e-6},
        amplitude={"V": 0.5},
        rise_time={"s": 1e-9},
        fall_time={"s": 1e-9},
    )
    assert pulse.pulse_type == "square"
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert isinstance(pulse.rise_time, Duration)
    assert isinstance(pulse.fall_time, Duration)
    assert pulse.duration.s == 1e-6
    assert pulse.amplitude.V == 0.5
    assert pulse.rise_time.s == 1e-9
    assert pulse.fall_time.s == 1e-9


def test_sine_pulse_creation():
    """Test creating a sine pulse with basic parameters."""
    pulse = SinePulse(
        duration=Duration(s=1e-6),
        amplitude=Amplitude(V=0.5),
        frequency=Frequency(Hz=1e6),
    )
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert isinstance(pulse.frequency, Frequency)

    assert pulse.pulse_type == "sine"
    assert pulse.duration.s == 1e-6
    assert pulse.amplitude.V == 0.5
    assert pulse.frequency.Hz == 1e6
    assert pulse.to_frequency is None


def test_pulse_with_variable_refs():
    """Test creating pulses with variable references."""
    square = SquarePulse(duration=VariableRef(var="dur"), amplitude=VariableRef(var="amp"))
    assert isinstance(square.duration, VariableRef)
    assert isinstance(square.amplitude, VariableRef)

    sine = SinePulse(
        duration=VariableRef(var="dur"), amplitude=VariableRef(var="amp"), frequency=VariableRef(var="freq")
    )
    assert isinstance(sine.duration, VariableRef)
    assert isinstance(sine.amplitude, VariableRef)
    assert isinstance(sine.frequency, VariableRef)


def test_sine_pulse_frequency_sweep():
    """Test creating a sine pulse with frequency sweep."""
    pulse = SinePulse(
        duration=Duration(s=1e-6),
        amplitude=Amplitude(V=0.5),
        frequency=Frequency(Hz=1e6),
        to_frequency=Frequency(Hz=2e6),
    )
    assert isinstance(pulse.frequency, Frequency)
    assert isinstance(pulse.to_frequency, Frequency)

    assert pulse.frequency.Hz == 1e6
    assert pulse.to_frequency.Hz == 2e6


def test_square_pulse_json_serialization_defaults():
    """Test serializing a square pulse to JSON."""
    pulse = SquarePulse(
        duration=Duration(s=1e-6),
        amplitude=Amplitude(V=0.5),
    )
    assert pulse.model_dump_json() == (
        '{"pulse_type":"square",'  #
        + '"duration":{"s":1e-6},'  #
        + '"amplitude":{"V":0.5}'  #
        + "}"
    )


def test_square_pulse_json_serialization_rise_fall():
    """Test serializing a square pulse to JSON."""
    pulse = SquarePulse(
        duration=Duration(s=1e-6),
        amplitude=Amplitude(V=0.5),
        rise_time=Duration(s=1e-9),
        fall_time=Duration(s=1e-9),
    )
    assert pulse.model_dump_json() == (
        '{"pulse_type":"square",'
        + '"duration":{"s":1e-6},'
        + '"amplitude":{"V":0.5},'
        + '"rise_time":{"s":1e-9},'
        + '"fall_time":{"s":1e-9}'
        + "}"
    )


def test_sine_pulse_json_serialization():
    """Test serializing a sine pulse to JSON."""
    pulse = SinePulse(
        duration=Duration(s=1e-6),
        amplitude=Amplitude(V=0.5),
        frequency=Frequency(MHz=1.0),
    )
    assert pulse.model_dump_json() == (
        '{"pulse_type":"sine",'  #
        + '"duration":{"s":1e-6},'  #
        + '"amplitude":{"V":0.5},'  #
        + '"frequency":{"MHz":1.0}'  #
        + "}"
    )


def test_sine_pulse_json_serialization_frequency_sweep():
    """Test serializing a sine pulse to JSON."""
    pulse = SinePulse(
        duration=Duration(s=1e-6),
        amplitude=Amplitude(V=0.5),
        frequency=Frequency(MHz=1.0),
        to_frequency=Frequency(MHz=2.0),
    )
    assert pulse.model_dump_json() == (
        '{"pulse_type":"sine",'
        + '"duration":{"s":1e-6},'
        + '"amplitude":{"V":0.5},'
        + '"frequency":{"MHz":1.0},'
        + '"to_frequency":{"MHz":2.0}'
        + "}"
    )


def test_square_pulse_json_validation_rise_fall():
    """Test deserializing a square pulse from JSON."""
    pulse: Any = TypeAdapter(PulseType).validate_json(
        '{"pulse_type":"square",'
        + '"duration":{"s":1e-6},'
        + '"amplitude":{"V":0.5},'
        + '"rise_time":{"s":1e-9},'
        + '"fall_time":{"s":1e-9}'
        + "}"
    )
    assert isinstance(pulse, SquarePulse)
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert isinstance(pulse.rise_time, Duration)
    assert isinstance(pulse.fall_time, Duration)
    assert pulse.duration.s == 1e-6
    assert pulse.amplitude.V == 0.5
    assert pulse.rise_time.s == 1e-9
    assert pulse.fall_time.s == 1e-9


def test_square_pulse_json_validation_defaults():
    """Test deserializing a square pulse from JSON."""
    pulse: Any = TypeAdapter(PulseType).validate_json(
        '{"pulse_type":"square","duration":{"s":1e-6},"amplitude":{"V":0.5}}'
    )
    assert isinstance(pulse, SquarePulse)
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert pulse.rise_time is None
    assert pulse.fall_time is None
    assert pulse.duration.s == 1e-6
    assert pulse.amplitude.V == 0.5


def test_sine_pulse_json_validation():
    """Test deserializing a sine pulse from JSON."""
    pulse: Any = TypeAdapter(PulseType).validate_json(
        '{"pulse_type":"sine","duration":{"s":1e-6},"amplitude":{"V":0.5},"frequency":{"Hz":1e6}'  #
        + "}"
    )
    assert isinstance(pulse, SinePulse)
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert isinstance(pulse.frequency, Frequency)
    assert pulse.to_frequency is None
    assert pulse.duration.s == 1e-6
    assert pulse.amplitude.V == 0.5
    assert pulse.frequency.Hz == 1e6


def test_sine_pulse_json_validation_frequency_sweep():
    """Test deserializing a sine pulse from JSON."""
    pulse: Any = TypeAdapter(PulseType).validate_json(
        '{"pulse_type":"sine",'  #
        + '"duration":{"s":1e-6},'  #
        + '"amplitude":{"V":0.5},'  #
        + '"frequency":{"Hz":1e6},'  #
        + '"to_frequency":{"Hz":2e6}'  #
        + "}"
    )
    assert isinstance(pulse, SinePulse)
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert isinstance(pulse.frequency, Frequency)
    assert isinstance(pulse.to_frequency, Frequency)
    assert pulse.duration.s == 1e-6
    assert pulse.amplitude.V == 0.5
    assert pulse.frequency.Hz == 1e6
    assert pulse.to_frequency.Hz == 2e6
