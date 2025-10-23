"""Tests for basic types used in eq1_pulse models."""

import cmath
from cmath import pi as π

import pytest
from pydantic import ValidationError

from eq1_pulse.models.basic_types import Amplitude, Angle, Duration, Frequency, Threshold, Time


def test_threshold_schema():
    """Test the JSON schema of Threshold."""
    expected_schema = {
        "anyOf": [
            {"const": 0, "type": "integer"},
            {"$ref": "#/$defs/Volts"},
            {"$ref": "#/$defs/Millivolts"},
        ],
        "title": "Threshold",
    }
    assert Threshold.model_json_schema() == expected_schema


def test_threshold_zero_init():
    """Test zero initialization of Threshold."""
    t = Threshold(0)
    assert t.V == 0


def test_threshold_init_volts():
    """Test initialization with volts."""
    t = Threshold(V=1.5)
    assert t.V == 1.5
    assert t.mV == 1500


def test_threshold_init_millivolts():
    """Test initialization with millivolts."""
    t = Threshold(mV=1500)
    assert t.V == 1.5
    assert t.mV == 1500


def test_threshold_property_conversion():
    """Test voltage unit conversions."""
    t = Threshold(V=2.5)
    assert t.mV == 2500

    t = Threshold(mV=3500)
    assert t.V == 3.5


def test_threshold_equality():
    """Test equality comparison between thresholds."""
    t1 = Threshold(V=1.5)
    t2 = Threshold(V=1.5)
    t3 = Threshold(mV=1500)
    t4 = Threshold(V=2.0)

    assert t1 == t2
    assert t1 == t3
    assert t1 != t4


def test_threshold_invalid_init():
    """Test invalid initialization cases."""
    with pytest.raises(ValidationError):
        Threshold.model_validate({"V": 1.5, "mV": 1500})

    with pytest.raises(ValidationError):
        Threshold.model_validate(1.5)  # Direct value not allowed

    with pytest.raises(ValidationError):
        Threshold.model_validate(None)  # Missing arguments


def test_angle_schema():
    """Test the JSON schema of Angle."""
    expected_schema = {
        "anyOf": [
            {"const": 0, "type": "integer"},
            {"$ref": "#/$defs/Degrees"},
            {"$ref": "#/$defs/Radians"},
            {"$ref": "#/$defs/Turns"},
            {"$ref": "#/$defs/HalfTurns"},
        ],
        "title": "Angle",
    }
    assert Angle.model_json_schema() == expected_schema


def test_angle_zero_init():
    """Test zero initialization of Angle."""
    a = Angle(0)
    assert a.deg == 0
    assert a.rad == 0


def test_angle_zero_validate():
    """Test zero validation of Angle."""
    a = Angle.model_validate(0)
    assert a.deg == 0
    assert a.rad == 0


def test_angle_init_degrees():
    """Test initialization with degrees."""
    a = Angle(deg=180)
    assert a.deg == 180
    assert a.rad == π
    assert a.turns == 0.5
    assert a.half_turns == 1.0


def test_angle_init_radians():
    """Test initialization with radians."""
    a = Angle(rad=π)
    assert a.deg == 180
    assert a.rad == π
    assert a.turns == 0.5
    assert a.half_turns == 1.0


def test_angle_equality():
    """Test equality comparison between angles."""
    a1 = Angle(deg=180)
    a2 = Angle(rad=π)
    a3 = Angle(deg=90)
    a4 = Angle(half_turns=0.5)

    assert a1 == a2
    assert a1 != a3
    assert a2 != a3
    assert a3 == a4


def test_angle_complex_rotation():
    """Test complex rotation property."""
    a = Angle(deg=0)
    assert a.complex_rotation == 1

    a = Angle(deg=90)
    assert a.complex_rotation == 1j

    a = Angle(deg=180)
    assert a.complex_rotation == -1

    a = Angle(deg=270)
    assert a.complex_rotation == -1j

    a = Angle(deg=45)
    assert a.complex_rotation == cmath.exp(1j * π / 4)


def test_angle_arithmetic():
    """Test arithmetic operations on Angle."""
    a1 = Angle(deg=90)
    a2 = Angle(deg=45)

    # Addition
    a3 = a1 + a2
    assert a3.deg == 135

    # Subtraction
    a4 = a1 - a2
    assert a4.deg == 45

    # Negation
    a5 = -a2
    assert a5.deg == -45

    # Multiplication with scalar
    a6 = a2 * 3
    assert a6.deg == 135

    # Right multiplication with scalar
    a7 = 4 * a2
    assert a7.deg == 180

    # True division with scalar
    a8 = a1 / 2
    assert a8.deg == 45

    # True division with another Angle (result is scalar)
    ratio = a1 / a2
    assert ratio == 2.0

    # Modulus with another Angle
    mod = Angle(deg=370) % Angle(deg=360)
    assert mod.deg == 10

    # Floor division with another Angle
    floor_div = Angle(deg=450) // Angle(deg=360)
    assert floor_div == 1


def test_angle_arithmetic_different_units():
    """Test arithmetic operations on Angle with different units."""
    a1 = Angle(deg=90)
    a2 = Angle(rad=π / 2)

    # Addition
    a3 = a1 + a2
    assert a3.deg == 180

    # Subtraction
    a4 = a1 - a2
    assert a4.deg == 0

    # Unary plus
    a_plus = +a2
    assert a_plus.deg == +90

    # Negation
    a5 = -a2
    assert a5.deg == -90

    # Multiplication with scalar
    a6 = a2 * 2
    assert a6.deg == 180

    # Right multiplication with scalar
    a7 = 3 * a2
    assert a7.deg == 270

    # True division with scalar
    a8 = a1 / 3
    assert a8.deg == 30

    # True division with another Angle (result is scalar)
    ratio = a1 / a2
    assert ratio == 1.0

    # Modulus with another Angle
    mod = Angle(deg=450) % Angle(rad=2 * π)
    assert mod.deg == 90

    # Floor division with another Angle
    floor_div = Angle(deg=720) // Angle(rad=2 * π)
    assert floor_div == 2


def test_time_zero_init():
    """Test zero initialization of Time."""
    t = Time(0)
    assert t.s == 0
    assert t.ms == 0
    assert t.us == 0
    assert t.ns == 0


def test_time_init_seconds():
    """Test initialization with seconds."""
    t = Time(s=1.5)
    assert t.s == 1.5
    assert t.ms == 1500
    assert t.us == 1500000
    assert t.ns == 1500000000


def test_time_init_milliseconds():
    """Test initialization with milliseconds."""
    t = Time(ms=1500)
    assert t.s == 1.5
    assert t.ms == 1500
    assert t.us == 1500000
    assert t.ns == 1500000000


def test_time_init_microseconds():
    """Test initialization with microseconds."""
    t = Time(us=1500000)
    assert t.s == 1.5
    assert t.ms == 1500
    assert t.us == 1500000
    assert t.ns == 1500000000


def test_time_init_nanoseconds():
    """Test initialization with nanoseconds."""
    t = Time(ns=1500000000)
    assert t.s == 1.5
    assert t.ms == 1500
    assert t.us == 1500000
    assert t.ns == 1500000000


def test_time_equality():
    """Test equality comparison between times."""
    t1 = Time(s=1.5)
    t2 = Time(s=1.5)
    t3 = Time(ms=1500)
    t4 = Time(us=1500000)
    t5 = Time(ns=1500000000)
    t6 = Time(s=2.0)

    assert t1 == t2
    assert t1 == t3
    assert t1 == t4
    assert t1 == t5
    assert t1 != t6


def test_time_bool_conversion():
    """Test boolean conversion of Time."""
    assert bool(Time(0)) is False
    assert bool(Time(s=1.5)) is True
    assert bool(Time(ms=0)) is False
    assert bool(Time(us=1000)) is True
    assert bool(Time(ns=0)) is False


def test_time_arithmetic():
    """Test arithmetic operations on Time."""
    t1 = Time(s=2.0)
    t2 = Time(s=1.0)

    # Addition
    t3 = t1 + t2
    assert t3.s == 3.0

    # Subtraction
    t4 = t1 - t2
    assert t4.s == 1.0

    # Unary plus
    t_plus = +t2
    assert t_plus.s == +1.0

    # Negation
    t5 = -t2
    assert t5.s == -1.0

    # Multiplication with scalar
    t6 = t2 * 3
    assert t6.s == 3.0

    # Right multiplication with scalar
    t7 = 4 * t2
    assert t7.s == 4.0

    # True division with scalar
    t8 = t1 / 2
    assert t8.s == 1.0

    # True division with another Time (result is scalar)
    ratio = t1 / t2
    assert ratio == 2.0

    # Modulus with another Time
    mod = t1 % t6
    assert mod.s == 2.0

    # Floor division with another Time
    floor_div = t1 // t2
    assert floor_div == 2


def test_time_invalid_init():
    """Test invalid initialization cases."""
    with pytest.raises(ValidationError):
        Time.model_validate({"s": 1.5, "ms": 1500})  # Multiple units

    with pytest.raises(ValidationError):
        Time.model_validate(1.5)  # Direct value not allowed

    with pytest.raises(ValidationError):
        Time.model_validate(None)  # Missing arguments


def test_duration_zero_init():
    """Test zero initialization of Duration."""
    d = Duration(0)
    assert d.s == 0
    assert d.ms == 0
    assert d.us == 0
    assert d.ns == 0


def test_duration_positive_values():
    """Test Duration with positive values."""
    d = Duration(s=1.5)
    assert d.s == 1.5
    assert d.ms == 1500
    assert d.us == 1500000
    assert d.ns == 1500000000


def test_duration_negative_values():
    """Test Duration rejects negative values."""
    with pytest.raises(ValueError, match="expected nonnegative duration value"):
        Duration(s=-1.5)

    with pytest.raises(ValueError, match="expected nonnegative duration value"):
        Duration(ms=-1500)

    with pytest.raises(ValueError, match="expected nonnegative duration value"):
        Duration(us=-1500000)

    with pytest.raises(ValueError, match="expected nonnegative duration value"):
        Duration(ns=-1500000000)


def test_duration_equality():
    """Test equality comparison between durations."""
    d1 = Duration(s=1.5)
    d2 = Duration(s=1.5)
    d3 = Duration(ms=1500)
    d4 = Duration(us=1500000)
    d5 = Duration(ns=1500000000)
    d6 = Duration(s=2.0)

    assert d1 == d2
    assert d1 == d3
    assert d1 == d4
    assert d1 == d5
    assert d1 != d6


def test_duration_bool_conversion():
    """Test boolean conversion of Duration."""
    assert bool(Duration(0)) is False
    assert bool(Duration(s=1.5)) is True
    assert bool(Duration(ms=0)) is False
    assert bool(Duration(us=1000)) is True
    assert bool(Duration(ns=0)) is False


def test_amplitude_zero_init():
    """Test zero initialization of Amplitude."""
    a = Amplitude(0)
    assert a.V == 0
    assert a.mV == 0


def test_duration_arithmetic_different_units():
    """Test arithmetic operations on Duration with different units."""
    d1 = Duration(s=2.0)
    d2 = Duration(ms=1000)

    # Addition
    d3 = d1 + d2
    assert d3.s == 3.0

    # Subtraction
    d4 = d1 - d2
    assert d4.s == 1.0

    # Negation
    d5 = -d2
    assert d5.s == -1.0

    # Multiplication with scalar
    d6 = d2 * 2
    assert d6.s == 2.0

    # Right multiplication with scalar
    d7 = 3 * d2
    assert d7.s == 3.0

    # True division with scalar
    d8 = d1 / 2
    assert d8.s == 1.0

    # True division with another Duration (result is scalar)
    ratio = d1 / d2
    assert ratio == 2.0

    # Modulus with another Duration
    mod = Duration(s=3.5) % Duration(ms=1000)
    assert mod.s == 0.5

    # Floor division with another Duration
    floor_div = Duration(s=5.0) // Duration(ms=1000)
    assert floor_div == 5


def test_amplitude_init_volts():
    """Test initialization with real and complex volts."""
    a = Amplitude(V=1.5)
    assert a.V == 1.5
    assert a.mV == 1500

    a = Amplitude(V=1.5 + 2j)
    assert a.V == 1.5 + 2j
    assert a.mV == 1500 + 2000j


def test_amplitude_init_millivolts():
    """Test initialization with real and complex millivolts."""
    a = Amplitude(mV=1500)
    assert a.V == 1.5
    assert a.mV == 1500

    a = Amplitude(mV=1500 + 2000j)
    assert a.V == 1.5 + 2j
    assert a.mV == 1500 + 2000j


def test_amplitude_multiplication():
    """Test multiplication of amplitude with scalars."""
    a = Amplitude(V=1 + 1j)

    # Multiply by real
    a2 = a * 2
    assert a2.V == 2 + 2j
    assert isinstance(a2, Amplitude)

    # Multiply by complex
    a3 = a * (1 + 1j)
    assert a3.V == (1 + 1j) * (1 + 1j)
    assert isinstance(a3, Amplitude)

    # Right multiply
    a4 = 2 * a
    assert a4.V == 2 + 2j
    assert isinstance(a4, Amplitude)


def test_amplitude_equality():
    """Test equality comparison between amplitudes."""
    a1 = Amplitude(V=1.5 + 2j)
    a2 = Amplitude(V=1.5 + 2j)
    a3 = Amplitude(mV=1500 + 2000j)
    a4 = Amplitude(V=2 + 3j)

    assert a1 == a2
    assert a1 == a3
    assert a1 != a4


def test_amplitude_invalid_init():
    """Test invalid initialization cases."""
    with pytest.raises(ValidationError):
        Amplitude.model_validate({"V": 1.5, "mV": 1500})

    with pytest.raises(ValidationError):
        Amplitude.model_validate(1.5)  # Direct value not allowed

    with pytest.raises(ValidationError):
        Amplitude.model_validate(None)  # Missing arguments


def test_frequency_zero_init():
    """Test zero initialization of Frequency."""
    f = Frequency(0)
    assert f.Hz == 0
    assert f.MHz == 0
    assert f.GHz == 0


def test_frequency_init_hertz():
    """Test initialization with hertz."""
    f = Frequency(Hz=1e6)
    assert f.Hz == 1e6
    assert f.kHz == 1000.0
    assert f.MHz == 1.0
    assert f.GHz == 0.001


def test_frequency_init_kilohertz():
    """Test initialization with kilohertz."""
    f = Frequency(kHz=1000.0)
    assert f.Hz == 1e6
    assert f.kHz == 1000.0
    assert f.MHz == 1.0
    assert f.GHz == 0.001


def test_frequency_init_megahertz():
    """Test initialization with megahertz."""
    f = Frequency(MHz=1.0)
    assert f.Hz == 1e6
    assert f.MHz == 1.0
    assert f.GHz == 0.001


def test_frequency_init_gigahertz():
    """Test initialization with gigahertz."""
    f = Frequency(GHz=1.0)
    assert f.Hz == 1e9
    assert f.MHz == 1000
    assert f.GHz == 1.0


def test_frequency_equality():
    """Test equality comparison between frequencies."""
    f1 = Frequency(Hz=1e9)
    f2 = Frequency(MHz=1000)
    f3 = Frequency(GHz=1.0)
    f4 = Frequency(Hz=2e9)
    f5 = Frequency(kHz=1e6)

    assert f1 == f2
    assert f1 == f3
    assert f1 != f4
    assert f1 == f5


def test_frequency_invalid_init():
    """Test invalid initialization cases."""
    with pytest.raises(ValidationError):
        Frequency.model_validate({"Hz": 1e6, "MHz": 1.0})

    with pytest.raises(ValidationError):
        Frequency.model_validate(1e6)  # Direct value not allowed

    with pytest.raises(ValidationError):
        Frequency.model_validate(None)  # Missing arguments


def test_frequency_bool_conversion():
    """Test boolean conversion of Frequency."""
    assert bool(Frequency(0)) is False
    assert bool(Frequency(Hz=1e6)) is True
    assert bool(Frequency(MHz=0)) is False
    assert bool(Frequency(GHz=1.0)) is True


def test_angle_serialization():
    """Test JSON serialization of Angle."""
    a = Angle(deg=180)
    assert a.model_dump_json() == '{"deg":180}'

    a = Angle(rad=π)
    assert a.model_dump_json() == '{"rad":3.141592653589793}'


def test_time_serialization():
    """Test JSON serialization of Time."""
    t = Time(s=1.5)
    assert t.model_dump_json() == '{"s":1.5}'

    t = Time(ms=1500)
    assert t.model_dump_json() == '{"ms":1500}'

    t = Time(us=1500000)
    assert t.model_dump_json() == '{"us":1500000}'

    t = Time(ns=1500000000)
    assert t.model_dump_json() == '{"ns":1500000000}'


def test_frequency_serialization():
    """Test JSON serialization of Frequency."""
    f = Frequency(Hz=1e6)
    assert f.model_dump_json() == '{"Hz":1000000.0}'

    f = Frequency(kHz=1000.0)
    assert f.model_dump_json() == '{"kHz":1000.0}'

    f = Frequency(MHz=1.0)
    assert f.model_dump_json() == '{"MHz":1.0}'

    f = Frequency(GHz=1.0)
    assert f.model_dump_json() == '{"GHz":1.0}'


def test_amplitude_serialization():
    """Test JSON serialization of Amplitude."""
    a = Amplitude(V=1.5 + 2j)
    assert a.model_dump_json() == '{"V":"1.5+2j"}'

    a = Amplitude(mV=1500 + 2000j)
    assert a.model_dump_json() == '{"mV":"1500+2000j"}'


def test_threshold_serialization():
    """Test JSON serialization of Threshold."""
    t = Threshold(V=1.5)
    assert t.model_dump_json() == '{"V":1.5}'

    t = Threshold(mV=1500)
    assert t.model_dump_json() == '{"mV":1500}'


def test_complex_voltage_model_validation():
    """Test JSON model validation for ComplexVoltage based classes."""
    # Test Amplitude validation
    amp = Amplitude.model_validate_json('{"V": "1.5+2j"}')
    assert amp.V == 1.5 + 2j
    assert isinstance(amp, Amplitude)

    # Test validation with real numbers
    amp = Amplitude.model_validate_json('{"V": 1.5}')
    assert amp.V == 1.5
    assert isinstance(amp, Amplitude)

    # Test validation with millivolts
    amp = Amplitude.model_validate_json('{"mV": "1500+2000j"}')
    assert amp.mV == 1500 + 2000j
    assert isinstance(amp, Amplitude)

    # Test validation failures
    with pytest.raises(ValidationError):
        Amplitude.model_validate_json('{"V": "invalid"}')

    with pytest.raises(ValidationError):
        Amplitude.model_validate_json('{"V": "1.5+2j", "mV": 1500}')

    with pytest.raises(ValidationError):
        Amplitude.model_validate_json("{}")


def test_angle_model_validation():
    """Test JSON model validation for Angle."""
    # Test degrees validation
    angle = Angle.model_validate_json('{"deg": 180}')
    assert angle.deg == 180
    assert isinstance(angle, Angle)

    # Test radians validation
    angle = Angle.model_validate_json('{"rad": 3.141592653589793}')
    assert angle.rad == π
    assert isinstance(angle, Angle)

    # Test validation failures
    with pytest.raises(ValidationError):
        Angle.model_validate_json('{"deg": "invalid"}')

    with pytest.raises(ValidationError):
        Angle.model_validate_json('{"deg": 180, "rad": 3.14}')


def test_time_model_validation():
    """Test JSON model validation for Time."""
    # Test each time unit
    time = Time.model_validate_json('{"s": 1.5}')
    assert time.s == 1.5

    time = Time.model_validate_json('{"ms": 1500}')
    assert time.ms == 1500

    time = Time.model_validate_json('{"us": 1500000}')
    assert time.us == 1500000

    time = Time.model_validate_json('{"ns": 1500000000}')
    assert time.ns == 1500000000

    # Test validation failures
    with pytest.raises(ValidationError):
        Time.model_validate_json('{"s": "invalid"}')

    with pytest.raises(ValidationError):
        Time.model_validate_json('{"s": 1.5, "ms": 1500}')


def test_frequency_model_validation():
    """Test JSON model validation for Frequency."""
    # Test each frequency unit
    freq = Frequency.model_validate_json(" 0 ")
    assert freq.Hz == 0

    freq = Frequency.model_validate_json(' {"Hz": 1000000.0} ')
    assert freq.Hz == 1e6

    freq = Frequency.model_validate_json('{"kHz": 1000.0}')
    assert freq.kHz == 1000.0

    freq = Frequency.model_validate_json('{"MHz": 1.0}')
    assert freq.MHz == 1.0

    freq = Frequency.model_validate_json('{"GHz": 1.0}')
    assert freq.GHz == 1.0

    # Test validation failures
    with pytest.raises(ValidationError):
        Frequency.model_validate_json('{"Hz": "invalid"}')

    with pytest.raises(ValidationError):
        Frequency.model_validate_json('{"Hz": 1e6, "MHz": 1.0}')


def test_frequency_model_string_data_validation_for_zero():
    """Test string data JSON model validation for Frequency."""
    freq = Frequency.model_validate_strings(" 0 ")
    assert freq.Hz == 0


def test_frequency_model_string_data_validation():
    freq = Frequency.model_validate_strings({"Hz": " 1000000.0"})
    assert freq.Hz == 1e6

    freq = Frequency.model_validate_strings({"kHz": " 1000.0"})
    assert freq.kHz == 1000.0

    freq = Frequency.model_validate_strings({"MHz": " 1.0"})
    assert freq.MHz == 1.0

    freq = Frequency.model_validate_strings({"GHz": " 1.0"})
    assert freq.GHz == 1.0

    # Test validation failures
    with pytest.raises(ValidationError):
        Frequency.model_validate_strings({"Hz": "invalid"})

    with pytest.raises(ValidationError):
        Frequency.model_validate_strings({"Hz": "1e6", "MHz": " 1.0"})
