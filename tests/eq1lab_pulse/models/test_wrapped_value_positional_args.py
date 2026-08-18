"""``WrappedValueModel.__init__`` accepts a single positional argument only for 0.

Without a unit attached, a positional number is ambiguous: ``Duration(5)`` reads like
"5" but would silently mean 5 seconds, and ``Amplitude(1)`` would silently mean 1 Volt.
0 is the one value that means the same thing in every unit, so it is the only value
exempt from requiring an explicit keyword.
"""

import pytest

from eq1_pulse.models import Amplitude, Duration, Frequency, Phase


@pytest.mark.parametrize("cls", [Duration, Amplitude, Phase, Frequency])
def test_zero_is_accepted_positionally(cls):
    """Test that the literal 0 is accepted as a single positional argument."""
    assert cls(0) == 0


@pytest.mark.parametrize("cls", [Duration, Amplitude, Phase, Frequency])
def test_nonzero_positional_value_is_rejected(cls):
    """Test that a nonzero positional value raises rather than picking an implicit unit."""
    with pytest.raises(ValueError, match="only the literal 0 is accepted positionally"):
        cls(5)


@pytest.mark.parametrize("cls", [Duration, Amplitude, Phase, Frequency])
def test_too_many_positional_arguments_are_rejected(cls):
    """Test that more than one positional argument raises."""
    with pytest.raises(TypeError, match="expected at most 1 positional argument"):
        cls(0, 0)


@pytest.mark.parametrize(
    ("cls", "kwarg"),
    [(Duration, "us"), (Amplitude, "mV"), (Phase, "deg"), (Frequency, "MHz")],
)
def test_positional_and_keyword_arguments_cannot_be_combined(cls, kwarg):
    """Test that a positional argument alongside keyword arguments raises."""
    with pytest.raises(TypeError, match="cannot combine a positional argument with keyword arguments"):
        cls(0, **{kwarg: 0})


def test_keyword_arguments_are_unaffected():
    """Test that ordinary keyword construction still works."""
    assert Duration(us=5).us == 5
    assert Amplitude(mV=100).mV == 100
