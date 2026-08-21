"""Comparison invariants for ``RelTime``, the schedule-only quantity type.

Companion to ``tests/eq1lab_pulse/models/test_comparison_invariants.py``, which covers
every other quantity type. ``RelTime`` lives under ``eq1_pulse.models.experimental``, so
its cases are kept out of that file to preserve the import-boundary check in
``test_module_boundaries.py``.
"""

import pytest

from eq1_pulse.models.experimental.schedule import RelTime

EQUAL_PAIRS = [
    (RelTime(us=1), RelTime(ns=1000)),
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
