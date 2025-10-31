"""Tests for basic types used in eq1_pulse models."""

import cmath
import math
from cmath import pi as π

import pytest
from pydantic import ValidationError
from pytest import approx

from eq1_pulse.models.basic_types import (
    Amplitude,
    Angle,
    ComplexVoltage,
    Duration,
    Frequency,
    Magnitude,
    Phase,
    Threshold,
    Time,
    Voltage,
)


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


def test_amplitude_abs():
    """Test absolute value (magnitude) of Amplitude."""
    # Test with 3-4-5 right triangle (magnitude should be 5)
    a1 = Amplitude(V=3 + 4j)
    mag1 = abs(a1)
    assert mag1.V == 5.0
    assert isinstance(mag1, Magnitude)

    # Test with real-only amplitude
    a2 = Amplitude(V=5.0)
    mag2 = abs(a2)
    assert mag2.V == 5.0
    assert isinstance(mag2, Magnitude)

    # Test with imaginary-only amplitude
    a3 = Amplitude(V=12j)
    mag3 = abs(a3)
    assert mag3.V == 12.0
    assert isinstance(mag3, Magnitude)

    # Test with negative real part
    a4 = Amplitude(V=-3 + 4j)
    mag4 = abs(a4)
    assert mag4.V == 5.0
    assert isinstance(mag4, Magnitude)

    # Test with negative imaginary part
    a5 = Amplitude(V=3 - 4j)
    mag5 = abs(a5)
    assert mag5.V == 5.0
    assert isinstance(mag5, Magnitude)

    # Test with both negative
    a6 = Amplitude(V=-3 - 4j)
    mag6 = abs(a6)
    assert mag6.V == 5.0
    assert isinstance(mag6, Magnitude)

    # Test with zero
    a_zero = Amplitude(0)
    mag_zero = abs(a_zero)
    assert mag_zero.V == 0.0
    assert isinstance(mag_zero, Magnitude)

    # Test with millivolts
    a_mv = Amplitude(mV=3000 + 4000j)
    mag_mv = abs(a_mv)
    assert mag_mv.V == 5.0
    assert mag_mv.mV == 5000.0
    assert isinstance(mag_mv, Magnitude)


def test_complex_voltage_abs():
    """Test absolute value (magnitude) of ComplexVoltage."""
    # Test with 5-12-13 right triangle
    cv1 = ComplexVoltage(V=5 + 12j)
    mag1 = abs(cv1)
    assert mag1.V == 13.0
    assert isinstance(mag1, Magnitude)

    # Test with real-only
    cv2 = ComplexVoltage(V=-7.0)
    mag2 = abs(cv2)
    assert mag2.V == 7.0
    assert isinstance(mag2, Magnitude)

    # Test with imaginary-only
    cv3 = ComplexVoltage(V=-15j)
    mag3 = abs(cv3)
    assert mag3.V == 15.0
    assert isinstance(mag3, Magnitude)

    # Test with millivolts
    cv_mv = ComplexVoltage(mV=5000 + 12000j)
    mag_mv = abs(cv_mv)
    assert mag_mv.V == 13.0
    assert mag_mv.mV == 13000.0
    assert isinstance(mag_mv, Magnitude)

    # Test zero
    cv_zero = ComplexVoltage(0)
    mag_zero = abs(cv_zero)
    assert mag_zero.V == 0.0
    assert isinstance(mag_zero, Magnitude)


def test_amplitude_phase():
    """Test phase property of Amplitude."""
    # Test positive real (0 degrees)
    a1 = Amplitude(V=5.0)
    phase1 = a1.phase
    assert phase1.rad == 0.0
    assert phase1.deg == 0.0
    assert isinstance(phase1, Phase)

    # Test positive imaginary (90 degrees)
    a2 = Amplitude(V=5j)
    phase2 = a2.phase
    assert phase2.rad == π / 2
    assert phase2.deg == 90
    assert isinstance(phase2, Phase)

    # Test negative real (180 degrees or -180 degrees)
    a3 = Amplitude(V=-5.0)
    phase3 = a3.phase
    assert abs(phase3.rad) == π
    assert abs(phase3.deg) == 180
    assert isinstance(phase3, Phase)

    # Test negative imaginary (-90 degrees)
    a4 = Amplitude(V=-5j)
    phase4 = a4.phase
    assert phase4.rad == -π / 2
    assert phase4.deg == -90
    assert isinstance(phase4, Phase)

    # Test 45 degrees (1+1j)
    a5 = Amplitude(V=1 + 1j)
    phase5 = a5.phase
    assert phase5.rad == π / 4
    assert phase5.deg == approx(45)
    assert isinstance(phase5, Phase)

    # Test 135 degrees (-1+1j)
    a6 = Amplitude(V=-1 + 1j)
    phase6 = a6.phase
    assert phase6.rad == 3 * π / 4
    assert phase6.deg == approx(135)
    assert isinstance(phase6, Phase)

    # Test -45 degrees (1-1j)
    a7 = Amplitude(V=1 - 1j)
    phase7 = a7.phase
    assert phase7.rad == -π / 4
    assert phase7.deg == approx(-45)
    assert isinstance(phase7, Phase)

    # Test -135 degrees (-1-1j)
    a8 = Amplitude(V=-1 - 1j)
    phase8 = a8.phase
    assert phase8.rad == -3 * π / 4
    assert phase8.deg == approx(-135)
    assert isinstance(phase8, Phase)


def test_amplitude_angle():
    """Test angle property of Amplitude."""
    # Test positive real (0 degrees)
    a1 = Amplitude(V=5.0)
    angle1 = a1.angle
    assert angle1.deg == 0.0
    assert angle1.rad == 0.0
    assert isinstance(angle1, Angle)

    # Test positive imaginary (90 degrees)
    a2 = Amplitude(V=5j)
    angle2 = a2.angle
    assert angle2.deg == 90
    assert angle2.rad == π / 2
    assert isinstance(angle2, Angle)

    # Test negative real (180 or -180 degrees)
    a3 = Amplitude(V=-5.0)
    angle3 = a3.angle
    assert abs(angle3.deg) == 180
    assert isinstance(angle3, Angle)

    # Test negative imaginary (-90 degrees)
    a4 = Amplitude(V=-5j)
    angle4 = a4.angle
    assert angle4.deg == -90
    assert isinstance(angle4, Angle)

    # Test 45 degrees
    a5 = Amplitude(V=1 + 1j)
    angle5 = a5.angle
    assert angle5.deg == approx(45)
    assert isinstance(angle5, Angle)

    # Test that angle and phase give consistent results
    a6 = Amplitude(V=3 + 4j)
    assert a6.angle.rad == approx(a6.phase.rad)
    assert a6.angle.deg == approx(a6.phase.deg)


def test_complex_voltage_phase():
    """Test phase property of ComplexVoltage."""
    # Test positive real (0 radians)
    cv1 = ComplexVoltage(V=10.0)
    phase1 = cv1.phase
    assert phase1.rad == 0.0
    assert phase1.deg == 0.0
    assert isinstance(phase1, Phase)

    # Test positive imaginary (π/2 radians)
    cv2 = ComplexVoltage(V=10j)
    phase2 = cv2.phase
    assert phase2.rad == π / 2
    assert phase2.deg == 90
    assert isinstance(phase2, Phase)

    # Test negative real (±π radians)
    cv3 = ComplexVoltage(V=-10.0)
    phase3 = cv3.phase
    assert abs(phase3.rad) == π
    assert isinstance(phase3, Phase)

    # Test negative imaginary (-π/2 radians)
    cv4 = ComplexVoltage(V=-10j)
    phase4 = cv4.phase
    assert phase4.rad == -π / 2
    assert phase4.deg == -90
    assert isinstance(phase4, Phase)

    # Test with millivolts
    cv_mv = ComplexVoltage(mV=1000 + 1000j)
    phase_mv = cv_mv.phase
    assert phase_mv.rad == π / 4
    assert phase_mv.deg == approx(45)
    assert isinstance(phase_mv, Phase)

    # Test 3-4-5 triangle (should give atan(4/3))
    cv5 = ComplexVoltage(V=3 + 4j)
    phase5 = cv5.phase
    expected_phase = cmath.phase(3 + 4j)
    assert phase5.rad == approx(expected_phase)
    assert isinstance(phase5, Phase)


def test_complex_voltage_angle():
    """Test angle property of ComplexVoltage."""
    # Test positive real (0 degrees)
    cv1 = ComplexVoltage(V=10.0)
    angle1 = cv1.angle
    assert angle1.deg == 0.0
    assert isinstance(angle1, Angle)

    # Test positive imaginary (90 degrees)
    cv2 = ComplexVoltage(V=10j)
    angle2 = cv2.angle
    assert angle2.deg == 90
    assert isinstance(angle2, Angle)

    # Test negative real (±180 degrees)
    cv3 = ComplexVoltage(V=-10.0)
    angle3 = cv3.angle
    assert abs(angle3.deg) == 180
    assert isinstance(angle3, Angle)

    # Test negative imaginary (-90 degrees)
    cv4 = ComplexVoltage(V=-10j)
    angle4 = cv4.angle
    assert angle4.deg == -90
    assert isinstance(angle4, Angle)

    # Test 30 degrees (using polar representation)
    cv5 = ComplexVoltage(V=math.sqrt(3) + 1j)  # tan(30°) = 1/sqrt(3)
    angle5 = cv5.angle
    assert angle5.deg == approx(30)
    assert isinstance(angle5, Angle)

    # Test 60 degrees
    cv6 = ComplexVoltage(V=1 + math.sqrt(3) * 1j)  # tan(60°) = sqrt(3)
    angle6 = cv6.angle
    assert angle6.deg == approx(60)
    assert isinstance(angle6, Angle)

    # Verify angle and phase consistency
    cv7 = ComplexVoltage(V=5 + 12j)
    assert cv7.angle.rad == approx(cv7.phase.rad)
    assert cv7.angle.deg == approx(cv7.phase.deg)


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
    assert a.model_dump_json() == '{"V":[1.5,2.0]}'

    a = Amplitude(mV=1500 + 2000j)
    assert a.model_dump_json() == '{"mV":[1500.0,2000.0]}'


def test_threshold_serialization():
    """Test JSON serialization of Threshold."""
    t = Threshold(V=1.5)
    assert t.model_dump_json() == '{"V":1.5}'

    t = Threshold(mV=1500)
    assert t.model_dump_json() == '{"mV":1500}'


def test_complex_voltage_model_validation():
    """Test JSON model validation for ComplexVoltage based classes."""
    amp = Amplitude.model_validate_json('{"V": [1.5, 2]}')
    assert amp.V == 1.5 + 2j
    assert isinstance(amp, Amplitude)

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
    freq = Frequency.model_validate_strings("  0  ")
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


def test_angle_inequality_comparisons():
    """Test inequality comparisons for Angle."""
    a1 = Angle(deg=90)
    a2 = Angle(deg=180)
    a3 = Angle(deg=90)
    a4 = Angle(rad=π / 2)  # 90 degrees

    # Less than
    assert a1 < a2
    assert not (a2 < a1)
    assert not (a1 < a3)
    assert not (a1 < a4)

    # Less than or equal
    assert a1 <= a2
    assert not (a2 <= a1)
    assert a1 <= a3
    assert a1 <= a4

    # Greater than
    assert a2 > a1
    assert not (a1 > a2)
    assert not (a1 > a3)
    assert not (a1 > a4)

    # Greater than or equal
    assert a2 >= a1
    assert not (a1 >= a2)
    assert a1 >= a3
    assert a1 >= a4


def test_angle_inequality_comparisons_with_zero():
    """Test inequality comparisons for Angle with zero literal."""
    a_positive = Angle(deg=90)
    a_negative = Angle(deg=-90)
    a_zero = Angle(0)

    # Comparison with zero literal
    assert a_positive > 0
    assert a_positive >= 0
    assert not (a_positive < 0)
    assert not (a_positive <= 0)

    assert a_negative < 0
    assert a_negative <= 0
    assert not (a_negative > 0)
    assert not (a_negative >= 0)

    assert not (a_zero < 0)
    assert a_zero <= 0
    assert not (a_zero > 0)
    assert a_zero >= 0


def test_angle_inequality_comparisons_different_units():
    """Test inequality comparisons for Angle with different units."""
    a1 = Angle(deg=90)
    a2 = Angle(rad=π)  # 180 degrees
    a3 = Angle(turns=0.25)  # 90 degrees
    a4 = Angle(half_turns=1.0)  # 180 degrees

    # Less than
    assert a1 < a2
    assert not (a1 < a3)

    # Less than or equal
    assert a1 <= a2
    assert a1 <= a3

    # Greater than
    assert a2 > a1
    assert not (a1 > a3)

    # Greater than or equal
    assert a2 >= a1
    assert a1 >= a3
    assert a2 >= a4


def test_time_inequality_comparisons():
    """Test inequality comparisons for Time."""
    t1 = Time(s=1.0)
    t2 = Time(s=2.0)
    t3 = Time(s=1.0)
    t4 = Time(ms=1000)  # 1.0 second

    # Less than
    assert t1 < t2
    assert not (t2 < t1)
    assert not (t1 < t3)
    assert not (t1 < t4)

    # Less than or equal
    assert t1 <= t2
    assert not (t2 <= t1)
    assert t1 <= t3
    assert t1 <= t4

    # Greater than
    assert t2 > t1
    assert not (t1 > t2)
    assert not (t1 > t3)
    assert not (t1 > t4)

    # Greater than or equal
    assert t2 >= t1
    assert not (t1 >= t2)
    assert t1 >= t3
    assert t1 >= t4


def test_time_inequality_comparisons_with_zero():
    """Test inequality comparisons for Time with zero literal."""
    t_positive = Time(s=1.0)
    t_negative = Time(s=-1.0)
    t_zero = Time(0)

    # Comparison with zero literal
    assert t_positive > 0
    assert t_positive >= 0
    assert not (t_positive < 0)
    assert not (t_positive <= 0)

    assert t_negative < 0
    assert t_negative <= 0
    assert not (t_negative > 0)
    assert not (t_negative >= 0)

    assert not (t_zero < 0)
    assert t_zero <= 0
    assert not (t_zero > 0)
    assert t_zero >= 0


def test_time_inequality_comparisons_different_units():
    """Test inequality comparisons for Time with different units."""
    t1 = Time(s=1.0)
    t2 = Time(ms=2000)  # 2.0 seconds
    t3 = Time(us=1000000)  # 1.0 second
    t4 = Time(ns=2000000000)  # 2.0 seconds

    # Less than
    assert t1 < t2
    assert not (t1 < t3)

    # Less than or equal
    assert t1 <= t2
    assert t1 <= t3

    # Greater than
    assert t2 > t1
    assert not (t1 > t3)

    # Greater than or equal
    assert t2 >= t1
    assert t1 >= t3
    assert t2 >= t4


def test_duration_inequality_comparisons():
    """Test inequality comparisons for Duration."""
    d1 = Duration(s=1.0)
    d2 = Duration(s=2.0)
    d3 = Duration(s=1.0)
    d4 = Duration(ms=1000)  # 1.0 second

    # Less than
    assert d1 < d2
    assert not (d2 < d1)
    assert not (d1 < d3)
    assert not (d1 < d4)

    # Less than or equal
    assert d1 <= d2
    assert not (d2 <= d1)
    assert d1 <= d3
    assert d1 <= d4

    # Greater than
    assert d2 > d1
    assert not (d1 > d2)
    assert not (d1 > d3)
    assert not (d1 > d4)

    # Greater than or equal
    assert d2 >= d1
    assert not (d1 >= d2)
    assert d1 >= d3
    assert d1 >= d4


def test_duration_inequality_comparisons_with_zero():
    """Test inequality comparisons for Duration with zero literal."""
    d_positive = Duration(s=1.0)
    d_zero = Duration(0)

    # Comparison with zero literal
    assert d_positive > 0
    assert d_positive >= 0
    assert not (d_positive < 0)
    assert not (d_positive <= 0)

    assert not (d_zero < 0)
    assert d_zero <= 0
    assert not (d_zero > 0)
    assert d_zero >= 0


def test_duration_inequality_comparisons_different_units():
    """Test inequality comparisons for Duration with different units."""
    d1 = Duration(s=1.0)
    d2 = Duration(ms=2000)  # 2.0 seconds
    d3 = Duration(us=1000000)  # 1.0 second
    d4 = Duration(ns=500000000)  # 0.5 seconds

    # Less than
    assert d1 < d2
    assert not (d1 < d3)
    assert d4 < d1

    # Less than or equal
    assert d1 <= d2
    assert d1 <= d3
    assert d4 <= d1

    # Greater than
    assert d2 > d1
    assert not (d1 > d3)
    assert d1 > d4

    # Greater than or equal
    assert d2 >= d1
    assert d1 >= d3
    assert d1 >= d4


def test_frequency_inequality_comparisons():
    """Test inequality comparisons for Frequency."""
    f1 = Frequency(MHz=100)
    f2 = Frequency(MHz=200)
    f3 = Frequency(MHz=100)
    f4 = Frequency(Hz=100000000)  # 100 MHz

    # Less than
    assert f1 < f2
    assert not (f2 < f1)
    assert not (f1 < f3)
    assert not (f1 < f4)

    # Less than or equal
    assert f1 <= f2
    assert not (f2 <= f1)
    assert f1 <= f3
    assert f1 <= f4

    # Greater than
    assert f2 > f1
    assert not (f1 > f2)
    assert not (f1 > f3)
    assert not (f1 > f4)

    # Greater than or equal
    assert f2 >= f1
    assert not (f1 >= f2)
    assert f1 >= f3
    assert f1 >= f4


def test_frequency_inequality_comparisons_with_zero():
    """Test inequality comparisons for Frequency with zero literal."""
    f_positive = Frequency(MHz=100)
    f_zero = Frequency(0)

    # Comparison with zero literal
    assert f_positive > 0
    assert f_positive >= 0
    assert not (f_positive < 0)
    assert not (f_positive <= 0)

    assert not (f_zero < 0)
    assert f_zero <= 0
    assert not (f_zero > 0)
    assert f_zero >= 0


def test_frequency_inequality_comparisons_different_units():
    """Test inequality comparisons for Frequency with different units."""
    f1 = Frequency(MHz=100)
    f2 = Frequency(GHz=0.2)  # 200 MHz
    f3 = Frequency(kHz=100000)  # 100 MHz
    f4 = Frequency(Hz=50000000)  # 50 MHz

    # Less than
    assert f1 < f2
    assert not (f1 < f3)
    assert f4 < f1

    # Less than or equal
    assert f1 <= f2
    assert f1 <= f3
    assert f4 <= f1

    # Greater than
    assert f2 > f1
    assert not (f1 > f3)
    assert f1 > f4

    # Greater than or equal
    assert f2 >= f1
    assert f1 >= f3
    assert f1 >= f4


def test_threshold_inequality_comparisons():
    """Test inequality comparisons for Threshold."""
    t1 = Threshold(V=1.0)
    t2 = Threshold(V=2.0)
    t3 = Threshold(V=1.0)
    t4 = Threshold(mV=1000)  # 1.0 V

    # Less than
    assert t1 < t2
    assert not (t2 < t1)
    assert not (t1 < t3)
    assert not (t1 < t4)

    # Less than or equal
    assert t1 <= t2
    assert not (t2 <= t1)
    assert t1 <= t3
    assert t1 <= t4

    # Greater than
    assert t2 > t1
    assert not (t1 > t2)
    assert not (t1 > t3)
    assert not (t1 > t4)

    # Greater than or equal
    assert t2 >= t1
    assert not (t1 >= t2)
    assert t1 >= t3
    assert t1 >= t4


def test_threshold_inequality_comparisons_with_zero():
    """Test inequality comparisons for Threshold with zero literal."""
    t_positive = Threshold(V=1.0)
    t_negative = Threshold(V=-1.0)
    t_zero = Threshold(0)

    # Comparison with zero literal
    assert t_positive > 0
    assert t_positive >= 0
    assert not (t_positive < 0)
    assert not (t_positive <= 0)

    assert t_negative < 0
    assert t_negative <= 0
    assert not (t_negative > 0)
    assert not (t_negative >= 0)

    assert not (t_zero < 0)
    assert t_zero <= 0
    assert not (t_zero > 0)
    assert t_zero >= 0


def test_threshold_inequality_comparisons_different_units():
    """Test inequality comparisons for Threshold with different units."""
    t1 = Threshold(V=1.0)
    t2 = Threshold(mV=2000)  # 2.0 V
    t3 = Threshold(mV=1000)  # 1.0 V

    # Less than
    assert t1 < t2
    assert not (t1 < t3)

    # Less than or equal
    assert t1 <= t2
    assert t1 <= t3

    # Greater than
    assert t2 > t1
    assert not (t1 > t3)

    # Greater than or equal
    assert t2 >= t1
    assert t1 >= t3


def test_amplitude_inequality_comparisons_real():
    """Test inequality comparisons for Amplitude with real values."""
    a1 = Amplitude(V=1.0)
    a2 = Amplitude(V=2.0)
    a3 = Amplitude(V=1.0)
    a4 = Amplitude(mV=1000)  # 1.0 V

    # Less than
    assert a1 < a2
    assert not (a2 < a1)
    assert not (a1 < a3)
    assert not (a1 < a4)

    # Less than or equal
    assert a1 <= a2
    assert not (a2 <= a1)
    assert a1 <= a3
    assert a1 <= a4

    # Greater than
    assert a2 > a1
    assert not (a1 > a2)
    assert not (a1 > a3)
    assert not (a1 > a4)

    # Greater than or equal
    assert a2 >= a1
    assert not (a1 >= a2)
    assert a1 >= a3
    assert a1 >= a4


def test_amplitude_inequality_comparisons_with_zero():
    """Test inequality comparisons for Amplitude with zero literal."""
    a_positive = Amplitude(V=1.0)
    a_negative = Amplitude(V=-1.0)
    a_zero = Amplitude(0)

    # Comparison with zero literal (uses real part for real values)
    assert a_positive > 0
    assert a_positive >= 0
    assert not (a_positive < 0)
    assert not (a_positive <= 0)

    assert a_negative < 0
    assert a_negative <= 0
    assert not (a_negative > 0)
    assert not (a_negative >= 0)

    assert not (a_zero < 0)
    assert a_zero <= 0
    assert not (a_zero > 0)
    assert a_zero >= 0


def test_voltage_inequality_comparisons():
    """Test inequality comparisons for Voltage."""
    v1 = Voltage(V=1.0)
    v2 = Voltage(V=2.0)
    v3 = Voltage(V=1.0)
    v4 = Voltage(mV=1000)  # 1.0 V

    # Less than
    assert v1 < v2
    assert not (v2 < v1)
    assert not (v1 < v3)
    assert not (v1 < v4)

    # Less than or equal
    assert v1 <= v2
    assert not (v2 <= v1)
    assert v1 <= v3
    assert v1 <= v4

    # Greater than
    assert v2 > v1
    assert not (v1 > v2)
    assert not (v1 > v3)
    assert not (v1 > v4)

    # Greater than or equal
    assert v2 >= v1
    assert not (v1 >= v2)
    assert v1 >= v3
    assert v1 >= v4


def test_voltage_inequality_comparisons_with_zero():
    """Test inequality comparisons for Voltage with zero literal."""
    v_positive = Voltage(V=1.0)
    v_negative = Voltage(V=-1.0)
    v_zero = Voltage(0)

    # Comparison with zero literal
    assert v_positive > 0
    assert v_positive >= 0
    assert not (v_positive < 0)
    assert not (v_positive <= 0)

    assert v_negative < 0
    assert v_negative <= 0
    assert not (v_negative > 0)
    assert not (v_negative >= 0)

    assert not (v_zero < 0)
    assert v_zero <= 0
    assert not (v_zero > 0)
    assert v_zero >= 0


def test_voltage_inequality_comparisons_different_units():
    """Test inequality comparisons for Voltage with different units."""
    v1 = Voltage(V=1.0)
    v2 = Voltage(mV=2000)  # 2.0 V
    v3 = Voltage(mV=1000)  # 1.0 V

    # Less than
    assert v1 < v2
    assert not (v1 < v3)

    # Less than or equal
    assert v1 <= v2
    assert v1 <= v3

    # Greater than
    assert v2 > v1
    assert not (v1 > v3)

    # Greater than or equal
    assert v2 >= v1
    assert v1 >= v3


def test_magnitude_inequality_comparisons():
    """Test inequality comparisons for Magnitude."""
    m1 = Magnitude(V=1.0)
    m2 = Magnitude(V=2.0)
    m3 = Magnitude(V=1.0)
    m4 = Magnitude(mV=1000)  # 1.0 V

    # Less than
    assert m1 < m2
    assert not (m2 < m1)
    assert not (m1 < m3)
    assert not (m1 < m4)

    # Less than or equal
    assert m1 <= m2
    assert not (m2 <= m1)
    assert m1 <= m3
    assert m1 <= m4

    # Greater than
    assert m2 > m1
    assert not (m1 > m2)
    assert not (m1 > m3)
    assert not (m1 > m4)

    # Greater than or equal
    assert m2 >= m1
    assert not (m1 >= m2)
    assert m1 >= m3
    assert m1 >= m4


def test_magnitude_inequality_comparisons_with_zero():
    """Test inequality comparisons for Magnitude with zero literal."""
    m_positive = Magnitude(V=1.0)
    m_zero = Magnitude(0)

    # Comparison with zero literal
    assert m_positive > 0
    assert m_positive >= 0
    assert not (m_positive < 0)
    assert not (m_positive <= 0)

    assert not (m_zero < 0)
    assert m_zero <= 0
    assert not (m_zero > 0)
    assert m_zero >= 0


def test_magnitude_inequality_comparisons_different_units():
    """Test inequality comparisons for Magnitude with different units."""
    m1 = Magnitude(V=1.0)
    m2 = Magnitude(mV=2000)  # 2.0 V
    m3 = Magnitude(mV=1000)  # 1.0 V

    # Less than
    assert m1 < m2
    assert not (m1 < m3)

    # Less than or equal
    assert m1 <= m2
    assert m1 <= m3

    # Greater than
    assert m2 > m1
    assert not (m1 > m3)

    # Greater than or equal
    assert m2 >= m1
    assert m1 >= m3
