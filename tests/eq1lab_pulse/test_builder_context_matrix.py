"""Every builder operation, exercised in every context it can legally appear in.

Operations dispatch on the type of the enclosing context. The bodies of schedule-side
``repeat``/``for_``/``if_`` are ``SchedRepetition``/``SchedIteration``/``SchedConditional``
rather than ``Schedule``, so an operation that only tests for ``Schedule`` works at the
top level of a schedule and fails one line deeper. This matrix pins all of them.
"""

from contextlib import contextmanager

import pytest

from eq1_pulse.builder import (
    add_block,
    barrier,
    build_schedule,
    build_sequence,
    demod_integration,
    discriminate,
    for_,
    full_integration,
    if_,
    measure,
    nested_schedule,
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
    sub_schedule,
    sub_sequence,
    var,
    var_decl,
    wait,
)

PULSE = {"duration": "100ns", "amplitude": "50mV"}


def _declare_common_variables():
    """Declare the variables the operations under test refer to."""
    var_decl("raw", "complex", unit="mV")
    var_decl("flag", "bool")
    var_decl("sweep", "int")


# Operations that must work identically in both sequence and schedule contexts.
COMMON_OPERATIONS = {
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
        _declare_common_variables()
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


@contextmanager
def _schedule_context(kind: str):
    """Open a schedule context of the requested nesting.

    :param kind: Which schedule context to open

    :yield: Once the context is open
    """
    with build_schedule():
        _declare_common_variables()
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
            case "sub_schedule":
                with sub_schedule():
                    yield
            case _:  # pragma: no cover - guards the parametrization
                raise AssertionError(kind)


SEQUENCE_CONTEXTS = ["top_level", "repeat", "for_", "if_", "sub_sequence"]
SCHEDULE_CONTEXTS = ["top_level", "repeat", "for_", "if_", "sub_schedule"]


@pytest.mark.parametrize("operation", sorted(COMMON_OPERATIONS))
@pytest.mark.parametrize("context", SEQUENCE_CONTEXTS)
def test_operation_works_in_every_sequence_context(context: str, operation: str):
    """Test that each operation can be emitted from any sequence context."""
    with _sequence_context(context):
        COMMON_OPERATIONS[operation]()


@pytest.mark.parametrize("operation", sorted(COMMON_OPERATIONS))
@pytest.mark.parametrize("context", SCHEDULE_CONTEXTS)
def test_operation_works_in_every_schedule_context(context: str, operation: str):
    """Test that each operation can be emitted from any schedule context."""
    with _schedule_context(context):
        COMMON_OPERATIONS[operation]()


@pytest.mark.parametrize("context", SEQUENCE_CONTEXTS)
def test_barrier_works_in_every_sequence_context(context: str):
    """Test that barrier, which is sequence-only, works throughout a sequence."""
    with _sequence_context(context):
        barrier("q", "readout")


@pytest.mark.parametrize("context", SCHEDULE_CONTEXTS)
def test_barrier_is_rejected_in_every_schedule_context(context: str):
    """Test that barrier reports its own reason for being unavailable in schedules."""
    with pytest.raises(RuntimeError, match="not supported in schedule contexts"):
        with _schedule_context(context):
            barrier("q", "readout")


@pytest.mark.parametrize("context", SCHEDULE_CONTEXTS)
def test_sub_schedule_nests_in_every_schedule_context(context: str):
    """Test that sub_schedule can be opened from any schedule context."""
    with _schedule_context(context):
        with sub_schedule(op_name="nested"):
            play("q", square_pulse(**PULSE))


@pytest.mark.parametrize("context", SCHEDULE_CONTEXTS)
def test_add_block_works_in_every_schedule_context(context: str):
    """Test that add_block can place a @nested_schedule block from any schedule context."""

    @nested_schedule
    def block(channel: str):
        play(channel, square_pulse(**PULSE))

    with _schedule_context(context):
        token = add_block(block("q"), op_name="placed")
        assert token.name == "placed"


@pytest.mark.parametrize("context", SCHEDULE_CONTEXTS)
def test_schedule_parameters_accepted_in_every_schedule_context(context: str):
    """Test that timing parameters are honoured at every level of a schedule."""
    with _schedule_context(context):
        first = play("q", square_pulse(**PULSE), op_name="first")
        assert first is not None
        second = play("q", square_pulse(**PULSE), ref_op=first, ref_pt="end", rel_time="10ns")
        assert second is not None
        assert second.operation.ref_op == "first"


@pytest.mark.parametrize("context", SEQUENCE_CONTEXTS)
def test_schedule_parameters_rejected_in_every_sequence_context(context: str):
    """Test that timing parameters are refused at every level of a sequence."""
    with pytest.raises(RuntimeError, match="not allowed in sequence context for 'play'"):
        with _sequence_context(context):
            play("q", square_pulse(**PULSE), rel_time="10ns")


@pytest.mark.parametrize("context", SEQUENCE_CONTEXTS)
def test_variables_from_enclosing_contexts_are_visible(context: str):
    """Test that a variable declared outside a nested context is still in scope."""
    with _sequence_context(context):
        assert var("raw").var == "raw"
