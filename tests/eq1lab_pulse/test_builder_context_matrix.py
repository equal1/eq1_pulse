"""Every builder operation, exercised in every context it can legally appear in.

Operations dispatch on the type of the enclosing context. This matrix pins that behaviour
for the sequence-side builder across every kind of nesting it supports.
"""

from collections.abc import Callable
from contextlib import contextmanager

import pytest

from eq1_pulse.builder import (
    barrier,
    build_sequence,
    demod_integration,
    discriminate,
    for_,
    full_integration,
    if_,
    measure,
    play,
    pulse_decl,
    record,
    repeat,
    set_frequency,
    set_phase,
    shift_frequency,
    shift_phase,
    square_pulse,
    store,
    sub_sequence,
    var,
    var_decl,
    wait,
)

PULSE = {"duration": "100ns", "amplitude": "50mV"}


def _declare_common_variables(declare: Callable[..., object]):
    """Declare the variables the operations under test refer to.

    :param declare: The ``var_decl`` function of the builder API under test
    """
    declare("raw", "complex", unit="mV")
    declare("flag", "bool")
    declare("sweep", "int")


# Operations that must work identically at every level of a sequence.
SEQUENCE_OPERATIONS = {
    "play": lambda: play("q", square_pulse(**PULSE)),
    "wait": lambda: wait("q", duration="1us"),
    "set_frequency": lambda: set_frequency("q", "5GHz"),
    "shift_frequency": lambda: shift_frequency("q", "10MHz"),
    "set_phase": lambda: set_phase("q", "90deg"),
    "shift_phase": lambda: shift_phase("q", "45deg"),
    "record": lambda: record("q", "raw", duration="1us", integration=full_integration()),
    "discriminate": lambda: discriminate("flag", "raw", threshold="0.5mV"),
    "store": lambda: store("key", "raw", mode="average"),
    "measure": lambda: measure(
        "q", result_var="raw", duration="1us", amplitude="30mV", integration=demod_integration()
    ),
    "pulse_decl": lambda: pulse_decl("named", square_pulse(**PULSE)),
    "var_decl": lambda: var_decl("extra", "float", unit="mV"),
}


@contextmanager
def _sequence_context(kind: str):
    """Open a sequence context of the requested nesting.

    :param kind: Which sequence context to open

    :yield: Once the context is open
    """
    with build_sequence():
        _declare_common_variables(var_decl)
        match kind:
            case "top_level":
                yield
            case "repeat":
                with repeat(2):
                    yield
            case "for_":
                with for_("sweep", range(0, 10, 2)):
                    yield
            case "if_":
                with if_("flag"):
                    yield
            case "sub_sequence":
                with sub_sequence():
                    yield
            case _:  # pragma: no cover - guards the parametrization
                raise AssertionError(kind)


SEQUENCE_CONTEXTS = ["top_level", "repeat", "for_", "if_", "sub_sequence"]


@pytest.mark.parametrize("operation", sorted(SEQUENCE_OPERATIONS))
@pytest.mark.parametrize("context", SEQUENCE_CONTEXTS)
def test_operation_works_in_every_sequence_context(context: str, operation: str):
    """Test that each operation can be emitted from any sequence context."""
    with _sequence_context(context):
        SEQUENCE_OPERATIONS[operation]()


@pytest.mark.parametrize("context", SEQUENCE_CONTEXTS)
def test_barrier_works_in_every_sequence_context(context: str):
    """Test that barrier, which is sequence-only, works throughout a sequence."""
    with _sequence_context(context):
        barrier("q", "readout")


@pytest.mark.parametrize("context", SEQUENCE_CONTEXTS)
def test_variables_from_enclosing_contexts_are_visible(context: str):
    """Test that a variable declared outside a nested context is still in scope."""
    with _sequence_context(context):
        assert var("raw").var == "raw"
