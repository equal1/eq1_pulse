from typing import Any

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models.basic_types import Amplitude, ComplexVoltage, Duration, Frequency, Magnitude, Phase, Voltage
from eq1_pulse.models.expressions import (
    BinaryExpr,
    CallExpr,
    CompareExpr,
    LiteralExpr,
    LogicalExpr,
    NotExpr,
    SymbolExpr,
    UnaryExpr,
)
from eq1_pulse.models.pulse_types import (
    ArbitrarySampledPulse,
    ExternalParamValue,
    ExternalPulse,
    PulseType,
    SinePulse,
    SquarePulse,
)
from eq1_pulse.models.reference_types import ExternalRef, PulseRef, VariableRef

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


def test_pulse_with_external_refs():
    """Test creating pulses with external symbol references."""
    square = SquarePulse(duration=ExternalRef(ext="q0.dur"), amplitude=ExternalRef(ext="q0.amp"))
    assert isinstance(square.duration, ExternalRef)
    assert isinstance(square.amplitude, ExternalRef)

    sine = SinePulse(
        duration=ExternalRef(ext="q0.dur"), amplitude=ExternalRef(ext="q0.amp"), frequency=ExternalRef(ext="q0.freq")
    )
    assert isinstance(sine.duration, ExternalRef)
    assert isinstance(sine.amplitude, ExternalRef)
    assert isinstance(sine.frequency, ExternalRef)


def test_pulse_with_expression():
    """Test that a widened pulse field accepts an Expression, not just a bare SymbolRef."""
    duration = BinaryExpr(binary_op="+", lhs=SymbolExpr(symbol=VariableRef("d")), rhs=LiteralExpr(value={"ns": 10}))
    square = SquarePulse(duration=duration, amplitude=Amplitude(V=0.5))
    assert isinstance(square.duration, BinaryExpr)

    document = square.model_dump()
    reloaded: Any = TypeAdapter(PulseType).validate_python(document)
    assert isinstance(reloaded, SquarePulse)
    assert isinstance(reloaded.duration, BinaryExpr)
    assert isinstance(reloaded.duration.lhs, SymbolExpr)


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


def test_external_pulse_creation():
    """Test creating an external pulse with basic parameters."""
    pulse = ExternalPulse(
        function="gaussian",
        duration=Duration(s=2e-6),
        amplitude=Amplitude(V=1.0),
        params={"sigma": 0.5},
    )
    assert pulse.pulse_type == "external"
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert pulse.duration.s == 2e-6
    assert pulse.amplitude.V == 1.0
    assert pulse.function == "gaussian"
    assert pulse.params == {"sigma": 0.5}


def test_external_pulse_creation_dicts():
    """Test creating an external pulse with basic parameters."""
    pulse = ExternalPulse(
        function="gaussian",
        duration={"s": 2e-6},
        amplitude={"V": 1.0},
        params={"sigma": 0.5},
    )
    assert pulse.pulse_type == "external"
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert pulse.duration.s == 2e-6
    assert pulse.amplitude.V == 1.0
    assert pulse.function == "gaussian"
    assert pulse.params == {"sigma": 0.5}


def test_external_pulse_json_serialization():
    """Test serializing an external pulse to JSON."""
    pulse = ExternalPulse(
        duration=Duration(s=2e-6),
        amplitude=Amplitude(V=1.0),
        function="gaussian",
        params={"sigma": 0.5},
    )
    assert pulse.model_dump_json() == (
        '{"pulse_type":"external",'
        + '"duration":{"s":2e-6},'
        + '"amplitude":{"V":1.0},'
        + '"function":"gaussian",'
        + '"params":{"sigma":0.5}'
        + "}"
    )


def test_external_pulse_json_validation():
    """Test deserializing an external pulse from JSON."""
    pulse: Any = TypeAdapter(PulseType).validate_json(
        '{"pulse_type":"external",'
        + '"duration":{"s":2e-6},'
        + '"amplitude":{"V":1.0},'
        + '"function":"gaussian",'
        + '"params":{"sigma":0.5}'
        + "}"
    )
    assert isinstance(pulse, ExternalPulse)
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert pulse.duration.s == 2e-6
    assert pulse.amplitude.V == 1.0
    assert pulse.function == "gaussian"
    assert pulse.params == {"sigma": 0.5}


def test_arbitrary_sample_pulse_creation():
    """Test creating an arbitrary sample pulse with basic parameters."""
    pulse = ArbitrarySampledPulse(
        duration=Duration(s=2e-6),
        amplitude=Amplitude(V=1.0),
        samples=[0.0, 0.5, 1.0, 0.5, 0.0],
    )
    assert pulse.pulse_type == "arbitrary"
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert pulse.duration.s == 2e-6
    assert pulse.amplitude.V == 1.0
    assert isinstance(pulse.samples, np.ndarray)
    assert np.array_equal(pulse.samples, [0.0, 0.5, 1.0, 0.5, 0.0])


def test_arbitrary_sample_pulse_json_serialization():
    """Test serializing an arbitrary sample pulse to JSON."""
    pulse = ArbitrarySampledPulse(
        duration=Duration(s=2e-6),
        amplitude=Amplitude(V=1.0),
        samples=[0.0, 0.5, 1.0, 0.5, 0.0],
    )
    assert pulse.model_dump_json() == (
        '{"pulse_type":"arbitrary",'
        + '"duration":{"s":2e-6},'
        + '"amplitude":{"V":1.0},'
        + '"samples":[0.0,0.5,1.0,0.5,0.0]'
        + "}"
    )


def test_arbitrary_sample_pulse_json_validation():
    """Test deserializing an arbitrary sample pulse from JSON."""
    pulse: Any = TypeAdapter(PulseType).validate_json(
        '{"pulse_type":"arbitrary",'
        + '"duration":{"s":2e-6},'
        + '"amplitude":{"V":1.0},'
        + '"samples":[0.0,0.5,1.0,0.5,0.0]'
        + "}"
    )
    assert isinstance(pulse, ArbitrarySampledPulse)
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert pulse.duration.s == 2e-6
    assert pulse.amplitude.V == 1.0
    assert isinstance(pulse.samples, np.ndarray)
    assert np.array_equal(pulse.samples, [0.0, 0.5, 1.0, 0.5, 0.0])


def test_arbitrary_sample_pulse_creation_with_time_points_and_interpolation():
    """Test creating an arbitrary sample pulse with time points and interpolation."""
    pulse = ArbitrarySampledPulse(
        duration=Duration(s=2e-6),
        amplitude=Amplitude(V=1.0),
        samples=[0.0, 0.5, 1.0, 0.5, 0.0],
        time_points=[0.0, 0.5e-6, 1.0e-6, 1.5e-6, 2.0e-6],
        interpolation="linear",
    )
    assert pulse.pulse_type == "arbitrary"
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert pulse.duration.s == 2e-6
    assert pulse.amplitude.V == 1.0
    assert isinstance(pulse.samples, np.ndarray)
    assert np.array_equal(pulse.samples, [0.0, 0.5, 1.0, 0.5, 0.0])
    assert isinstance(pulse.time_points, np.ndarray)
    assert np.array_equal(pulse.time_points, [0.0, 0.5e-6, 1.0e-6, 1.5e-6, 2.0e-6])
    assert pulse.interpolation == "linear"


def test_arbitrary_sample_pulse_creation_with_complex_samples():
    """Test creating an arbitrary sample pulse with complex samples."""
    pulse = ArbitrarySampledPulse(
        duration=Duration(s=2e-6),
        amplitude=Amplitude(V=1.0),
        samples=[0.0 + 0.0j, 0.5 + 0.5j, 1.0 + 1.0j, 0.5 + 0.5j, 0.0 + 0.0j],
    )
    assert pulse.pulse_type == "arbitrary"
    assert isinstance(pulse.duration, Duration)
    assert isinstance(pulse.amplitude, Amplitude)
    assert pulse.duration.s == 2e-6
    assert pulse.amplitude.V == 1.0
    assert isinstance(pulse.samples, np.ndarray)
    assert np.array_equal(pulse.samples, [0.0 + 0.0j, 0.5 + 0.5j, 1.0 + 1.0j, 0.5 + 0.5j, 0.0 + 0.0j])


def test_arbitrary_sample_pulse_json_serialization_with_complex_samples():
    """Test serializing an arbitrary sample pulse with complex samples to JSON."""
    pulse = ArbitrarySampledPulse(
        duration=Duration(s=2e-6),
        amplitude=Amplitude(V=1.0),
        samples=[0.0 + 0.0j, 0.5 + 0.5j, 1.0 + 1.0j, 0.5 + 0.5j, 0.0 + 0.0j],
    )
    assert pulse.model_dump_json() == (
        '{"pulse_type":"arbitrary",'
        + '"duration":{"s":2e-6},'
        + '"amplitude":{"V":1.0},'
        + '"samples":[[0.0,0.0],[0.5,0.5],[1.0,1.0],[0.5,0.5],[0.0,0.0]]'
        + "}"
    )


def test_external_param_value_voltage():
    """Test that a Voltage instance round-trips through ExternalParamValue."""
    value: Any = TypeAdapter(ExternalParamValue).validate_python(Voltage(V=0.5))
    assert isinstance(value, Voltage)
    assert value.V == 0.5


def test_external_param_value_amplitude_instance_survives_as_amplitude():
    """An Amplitude instance is tagged by its type, so it stays an Amplitude.

    The complex-voltage member is what admits it: :class:`~.basic_types.Amplitude` derives from
    :class:`~.basic_types.ComplexVoltage`, which is not a :class:`~.basic_types.Voltage` subclass,
    so before it was added the union rejected the most common pulse parameter outright.
    """
    value: Any = TypeAdapter(ExternalParamValue).validate_python(Amplitude(V=0.5))
    assert isinstance(value, Amplitude)
    assert value.V == 0.5


def test_external_param_value_complex_voltage_wire_form():
    """A ``(real, imag)`` pair under a voltage unit key is a ComplexVoltage and dumps back unchanged."""
    adapter: TypeAdapter[Any] = TypeAdapter(ExternalParamValue)
    value = adapter.validate_python({"mV": [1, 2]})
    assert isinstance(value, ComplexVoltage)
    assert value.mV == 1 + 2j
    assert adapter.dump_python(value) == {"mV": (1.0, 2.0)}


def test_external_param_value_real_voltage_key_is_still_a_voltage():
    """A real number under the same unit key still resolves to the real dimension."""
    value: Any = TypeAdapter(ExternalParamValue).validate_python({"mV": 100})
    assert type(value) is Voltage
    assert value.mV == 100


def test_external_param_value_unit_typo_reports_one_error():
    """An unknown unit key is one union_tag_not_found, not one error per member.

    The complex-voltage member is decided by value shape rather than by its own unit key, so it adds
    no second way for a typo to be reported.
    """
    with pytest.raises(ValidationError) as excinfo:
        TypeAdapter(ExternalParamValue).validate_python({"usec": 3})
    assert [error["type"] for error in excinfo.value.errors()] == ["union_tag_not_found"]


def test_external_param_value_duration():
    """Test that a Duration instance round-trips through ExternalParamValue."""
    value: Any = TypeAdapter(ExternalParamValue).validate_python(Duration(s=1e-6))
    assert isinstance(value, Duration)
    assert value.s == 1e-6


def test_external_param_value_frequency():
    """Test that a Frequency instance round-trips through ExternalParamValue."""
    value: Any = TypeAdapter(ExternalParamValue).validate_python(Frequency(Hz=1e6))
    assert isinstance(value, Frequency)
    assert value.Hz == 1e6


def test_external_param_value_phase():
    """Test that a Phase instance round-trips through ExternalParamValue."""
    value: Any = TypeAdapter(ExternalParamValue).validate_python(Phase(rad=1.0))
    assert isinstance(value, Phase)
    assert value.rad == 1.0


def test_external_param_value_magnitude():
    """Test that a Magnitude instance round-trips through ExternalParamValue."""
    value: Any = TypeAdapter(ExternalParamValue).validate_python(Magnitude(V=0.5))
    assert isinstance(value, Magnitude)
    assert value.V == 0.5


def test_external_param_value_variable_ref():
    """Test that a VariableRef instance round-trips through ExternalParamValue."""
    value: Any = TypeAdapter(ExternalParamValue).validate_python(VariableRef(var="x"))
    assert isinstance(value, VariableRef)
    assert value.var == "x"


def test_external_param_value_pulse_ref():
    """Test that a PulseRef instance round-trips through ExternalParamValue."""
    value: Any = TypeAdapter(ExternalParamValue).validate_python(PulseRef(pulse_name="p1"))
    assert isinstance(value, PulseRef)
    assert value.pulse_name == "p1"


def test_external_param_value_external_ref():
    """Test that an ExternalRef instance round-trips through ExternalParamValue."""
    value: Any = TypeAdapter(ExternalParamValue).validate_python(ExternalRef(ext="q0.f01"))
    assert isinstance(value, ExternalRef)
    assert value.ext == "q0.f01"


def test_external_param_value_pulse_type():
    """Test that an inline PulseType instance round-trips through ExternalParamValue."""
    inner = SquarePulse(duration=Duration(s=1e-6), amplitude=Amplitude(V=0.5))
    value: Any = TypeAdapter(ExternalParamValue).validate_python(inner)
    assert isinstance(value, SquarePulse)
    assert value == inner


def test_external_param_value_scalars():
    """Test that bool, float, int, and complex scalars round-trip through ExternalParamValue."""
    adapter: TypeAdapter[Any] = TypeAdapter(ExternalParamValue)
    assert adapter.validate_python(True) is True
    assert adapter.validate_python(1.5) == 1.5
    assert adapter.validate_python(3) == 3
    assert adapter.validate_python(1 + 2j) == 1 + 2j


def test_external_param_value_numpy_complex_forms_are_tagged_as_complex():
    """A 2-element numpy array or a numpy complex scalar is recognized as the complex tag.

    :func:`~eq1_pulse.models.complex.validate_complex_tuple` accepts both, so the discriminator
    must route them there instead of falling through to :obj:`None`.
    """
    adapter: TypeAdapter[Any] = TypeAdapter(ExternalParamValue)
    assert adapter.validate_python(np.array([1.0, 2.0])) == 1 + 2j
    assert adapter.validate_python(np.complex128(1 + 2j)) == 1 + 2j


def test_external_param_value_strings_are_kept_as_plain_strings():
    """Test that a unit-suffixed string is kept as a plain string, not coerced to a dimensional quantity.

    A bare string in :data:`ExternalParamValue` is opaque data passed to an external program, not an
    authored quantity, so it is never coerced -- however unit-suffixed it looks.
    """
    adapter: TypeAdapter[Any] = TypeAdapter(ExternalParamValue)
    assert adapter.validate_python("10us") == "10us"
    assert adapter.validate_python("100mV") == "100mV"
    assert adapter.validate_python("5GHz") == "5GHz"
    assert adapter.validate_python("foo") == "foo"


def test_external_param_value_variable_ref_round_trips_through_json():
    """Test that a VariableRef survives a JSON round-trip through ExternalParamValue.

    It is spelled ``{"var": ...}`` here and everywhere else: the ``{"var_ref": ...}`` spelling
    this union used to invent for itself went with the rest of the ad-hoc tagging.
    """
    adapter: TypeAdapter[Any] = TypeAdapter(ExternalParamValue)
    dumped = adapter.dump_json(VariableRef(var="x"))
    assert dumped == b'{"var":"x"}'
    restored = adapter.validate_json(dumped)
    assert restored == VariableRef(var="x")


def test_external_param_value_pulse_ref_round_trips_through_json():
    """Test that a PulseRef survives a JSON round-trip through ExternalParamValue."""
    adapter: TypeAdapter[Any] = TypeAdapter(ExternalParamValue)
    dumped = adapter.dump_json(PulseRef(pulse_name="p1"))
    assert dumped == b'{"pulse_name":"p1"}'
    restored = adapter.validate_json(dumped)
    assert restored == PulseRef(pulse_name="p1")


def test_external_param_value_external_ref_round_trips_through_json():
    """Test that an ExternalRef survives a JSON round-trip through ExternalParamValue, not degrading to str."""
    adapter: TypeAdapter[Any] = TypeAdapter(ExternalParamValue)
    dumped = adapter.dump_json(ExternalRef(ext="q0.f01"))
    assert dumped == b'{"ext":"q0.f01"}'
    restored = adapter.validate_json(dumped)
    assert isinstance(restored, ExternalRef)
    assert restored == ExternalRef(ext="q0.f01")


def test_external_param_value_complex_round_trips_through_json():
    """Test that a complex scalar survives a JSON round-trip through ExternalParamValue."""
    adapter: TypeAdapter[Any] = TypeAdapter(ExternalParamValue)
    dumped = adapter.dump_json(1 + 2j)
    restored = adapter.validate_json(dumped)
    assert restored == 1 + 2j


@pytest.mark.parametrize(
    ("expr_mapping", "expr_type"),
    [
        pytest.param({"value": 1}, LiteralExpr, id="literal"),
        pytest.param({"symbol": {"var": "x"}}, SymbolExpr, id="symbol"),
        pytest.param(
            {"unary_op": {"op": "-", "rhs": {"value": 1}}},
            UnaryExpr,
            id="unary",
        ),
        pytest.param(
            {"binary_op": {"op": "+", "lhs": {"value": 1}, "rhs": {"value": 2}}},
            BinaryExpr,
            id="binary",
        ),
        pytest.param(
            {"compare_op": {"op": "<", "lhs": {"value": 1}, "rhs": {"value": 2}}},
            CompareExpr,
            id="compare",
        ),
        pytest.param(
            {"logical_op": {"op": "and", "lhs": {"value": 1}, "rhs": {"value": 2}}},
            LogicalExpr,
            id="logical",
        ),
        pytest.param(
            {"not_op": {"rhs": {"value": 1}}},
            NotExpr,
            id="not",
        ),
        pytest.param(
            {"function": {"name": "abs", "args": [{"value": 1}]}},
            CallExpr,
            id="call",
        ),
    ],
)
def test_external_param_value_expression(expr_mapping: dict[str, Any], expr_type: type):
    """An Expression is tagged on its own node key and survives round-tripping from a mapping.

    Its dict shape (a single key naming the node type) is what the ``_external_param_value_tag``
    branch has to recognize -- via :func:`~.expressions.expression_tag_of` -- before falling
    through to the single-key-mapping checks the rest of the union relies on.
    """
    adapter: TypeAdapter[Any] = TypeAdapter(ExternalParamValue)
    value = adapter.validate_python(expr_mapping)
    assert isinstance(value, expr_type)

    dumped = adapter.dump_python(value)
    restored = adapter.validate_python(dumped)
    assert isinstance(restored, expr_type)
    assert restored == value


def test_external_pulse_params_widened_types():
    """Test that ExternalPulse.params accepts the widened ExternalParamValue members."""
    pulse = ExternalPulse(
        function="gate",
        duration=Duration(s=1e-6),
        amplitude=Amplitude(V=1.0),
        params={
            "phase": Phase(rad=1.0),
            "threshold": Magnitude(V=0.1),
            "pulse_ref": PulseRef(pulse_name="p1"),
            "label": "foo",
        },
    )
    assert pulse.params is not None
    assert isinstance(pulse.params["phase"], Phase)
    assert isinstance(pulse.params["threshold"], Magnitude)
    assert isinstance(pulse.params["pulse_ref"], PulseRef)
    assert pulse.params["label"] == "foo"
