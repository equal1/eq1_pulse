"""Invariants of the cross-unit comparison and hashing of quantity models.

``ComparableWrappedValueOrZeroModel`` compares across units and across registered
compatible types, which puts two contracts at risk that the ordinary equality tests do
not exercise: ``a == b`` must imply ``hash(a) == hash(b)``, and the four ordering
operators must agree with each other -- including on NaN, where deriving ``>`` as
``not <=`` reports "greater" in both directions.
"""

import math

import pytest

from eq1_pulse.models import Amplitude, Duration, Frequency, Phase, Time
from eq1_pulse.models.basic_types import Angle, ComplexVoltage, Voltage

# Pairs that denote the same physical quantity written two different ways.
# The experimental-only RelTime type has an equivalent set of cases in
# tests/eq1lab_pulse/experimental/test_comparison_invariants.py.
EQUAL_PAIRS = [
    (Duration(us=1), Duration(ns=1000)),
    (Duration(s=1), Duration(ms=1000)),
    (Time(us=1), Time(ns=1000)),
    (Time(s=2), Duration(ms=2000)),
    (Frequency(GHz=1), Frequency(MHz=1000)),
    (Frequency(MHz=1), Frequency(kHz=1000)),
    (Amplitude(V=1), Amplitude(mV=1000)),
    (Voltage(V=1), Voltage(mV=1000)),
    (Voltage(V=1), ComplexVoltage(V=1)),
    (Angle(deg=180), Angle(rad=math.pi)),
    (Angle(deg=180), Angle(half_turns=1)),
    (Angle(deg=360), Angle(turns=1)),
    (Phase(deg=90), Phase(turns=0.25)),
]

UNEQUAL_PAIRS = [
    (Duration(us=1), Duration(us=2)),
    (Frequency(GHz=1), Frequency(GHz=2)),
    (Amplitude(mV=50), Amplitude(mV=51)),
    (Angle(deg=90), Angle(deg=180)),
]


@pytest.mark.parametrize(("left", "right"), EQUAL_PAIRS, ids=repr)
def test_equal_values_compare_equal(left, right):
    """Test that the same quantity written in different units compares equal."""
    assert left == right
    assert right == left


@pytest.mark.parametrize(("left", "right"), EQUAL_PAIRS, ids=repr)
def test_equal_values_hash_equal(left, right):
    """Test the ``a == b implies hash(a) == hash(b)`` invariant.

    Without this, these types are silently broken as set members and dict keys.
    """
    assert hash(left) == hash(right)


@pytest.mark.parametrize(("left", "right"), EQUAL_PAIRS, ids=repr)
def test_equal_values_collapse_in_a_set(left, right):
    """Test that equal values are a single element of a set and a single dict key."""
    assert len({left, right}) == 1
    assert {left: "value"}[right] == "value"


@pytest.mark.parametrize(("left", "right"), UNEQUAL_PAIRS, ids=repr)
def test_unequal_values_stay_distinct(left, right):
    """Test that genuinely different quantities remain distinct."""
    assert left != right
    assert len({left, right}) == 2


@pytest.mark.parametrize(
    ("smaller", "larger"),
    [
        (Duration(us=1), Duration(ms=1)),
        (Duration(ns=999), Duration(us=1)),
        (Frequency(MHz=1), Frequency(GHz=1)),
        (Amplitude(mV=1), Amplitude(V=1)),
    ],
)
def test_ordering_is_consistent(smaller, larger):
    """Test that the four ordering operators agree across units."""
    assert smaller < larger
    assert smaller <= larger
    assert larger > smaller
    assert larger >= smaller
    assert not (larger < smaller)
    assert not (larger <= smaller)
    assert not (smaller > larger)
    assert not (smaller >= larger)


def test_ordering_against_zero():
    """Test comparison against the literal zero in both directions."""
    assert Duration(us=1) > 0
    assert Duration(us=1) >= 0
    assert not (Duration(us=1) < 0)
    assert Duration(us=0) == 0
    assert Duration(us=0) >= 0
    assert Duration(us=0) <= 0
    assert Angle(deg=-90) < 0


def test_nan_is_not_ordered_in_either_direction():
    """Test that NaN compares False every way round.

    Deriving ``>`` as ``not <=`` and ``>=`` as ``not <`` makes a NaN report as greater
    than everything, including itself.
    """
    nan = Duration(s=float("nan"))
    assert not (nan > 0)
    assert not (nan >= 0)
    assert not (nan < 0)
    assert not (nan <= 0)

    other = Duration(s=1)
    assert not (nan > other)
    assert not (nan >= other)
    assert not (nan < other)
    assert not (nan <= other)


def test_incomparable_types_are_not_equal():
    """Test that unrelated quantities do not compare equal or order against each other."""
    assert Duration(us=1) != Frequency(MHz=1)
    with pytest.raises(TypeError):
        _ = Duration(us=1) < Frequency(MHz=1)
