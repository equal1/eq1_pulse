"""Every schedule builder operation, exercised in every context it can legally appear in.

Operations dispatch on the type of the enclosing context. The bodies of schedule-side
``repeat``/``for_``/``if_`` are ``SchedRepetition``/``SchedIteration``/``SchedConditional``
rather than ``Schedule``, so an operation that only tests for ``Schedule`` works at the
top level of a schedule and fails one line deeper. This matrix pins all of them.
"""

from contextlib import contextmanager

import pytest

from eq1_pulse.builder import demod_integration, experimental, full_integration, square_pulse

PULSE = {"duration": "100ns", "amplitude": "50mV"}


def _declare_common_variables(declare):
    """Declare the variables the operations under test refer to.

    :param declare: The ``var_decl`` function of the builder API under test
    """
    declare("raw", "complex", unit="mV")
    declare("flag", "bool")
    declare("sweep", "int")


# Operations that must work identically at every level of a schedule.
SCHEDULE_OPERATIONS = {
    "play": lambda: experimental.play("q", square_pulse(**PULSE)),
    "wait": lambda: experimental.wait("q", duration="1us"),
    "set_frequency": lambda: experimental.set_frequency("q", "5GHz"),
    "shift_frequency": lambda: experimental.shift_frequency("q", "10MHz"),
    "set_phase": lambda: experimental.set_phase("q", "90deg"),
    "shift_phase": lambda: experimental.shift_phase("q", "45deg"),
    "record": lambda: experimental.record("q", "raw", duration="1us", integration=full_integration()),
    "discriminate": lambda: experimental.discriminate("flag", "raw", threshold="0.5mV"),
    "store": lambda: experimental.store("key", "raw", mode="average"),
    "measure": lambda: experimental.measure(
        "q", result_var="raw", duration="1us", amplitude="30mV", integration=demod_integration()
    ),
    "pulse_decl": lambda: experimental.pulse_decl("named", square_pulse(**PULSE)),
    "var_decl": lambda: experimental.var_decl("extra", "float", unit="mV"),
}


@contextmanager
def _schedule_context(kind: str):
    """Open a schedule context of the requested nesting.

    :param kind: Which schedule context to open

    :yield: Once the context is open
    """
    with experimental.build_schedule():
        _declare_common_variables(experimental.var_decl)
        match kind:
            case "top_level":
                yield
            case "repeat":
                with experimental.repeat(2):
                    yield
            case "for_":
                with experimental.for_("sweep", range(0, 10, 2)):
                    yield
            case "if_":
                with experimental.if_("flag"):
                    yield
            case "sub_schedule":
                with experimental.sub_schedule():
                    yield
            case _:  # pragma: no cover - guards the parametrization
                raise AssertionError(kind)


SCHEDULE_CONTEXTS = ["top_level", "repeat", "for_", "if_", "sub_schedule"]


@pytest.mark.parametrize("operation", sorted(SCHEDULE_OPERATIONS))
@pytest.mark.parametrize("context", SCHEDULE_CONTEXTS)
def test_operation_works_in_every_schedule_context(context: str, operation: str):
    """Test that each operation can be emitted from any schedule context."""
    with _schedule_context(context):
        SCHEDULE_OPERATIONS[operation]()


@pytest.mark.parametrize("context", SCHEDULE_CONTEXTS)
def test_barrier_is_rejected_in_every_schedule_context(context: str):
    """Test that barrier reports its own reason for being unavailable in schedules."""
    with pytest.raises(RuntimeError, match="not supported in schedule contexts"):
        with _schedule_context(context):
            experimental.barrier("q", "readout")


@pytest.mark.parametrize("context", SCHEDULE_CONTEXTS)
def test_sub_schedule_nests_in_every_schedule_context(context: str):
    """Test that sub_schedule can be opened from any schedule context."""
    with _schedule_context(context):
        with experimental.sub_schedule(op_name="nested"):
            experimental.play("q", square_pulse(**PULSE))


@pytest.mark.parametrize("context", SCHEDULE_CONTEXTS)
def test_add_block_works_in_every_schedule_context(context: str):
    """Test that add_block can place a @nested_schedule block from any schedule context."""

    @experimental.nested_schedule
    def block(channel: str):
        experimental.play(channel, square_pulse(**PULSE))

    with _schedule_context(context):
        token = experimental.add_block(block("q"), op_name="placed")
        assert token.name == "placed"


@pytest.mark.parametrize("context", SCHEDULE_CONTEXTS)
def test_schedule_parameters_accepted_in_every_schedule_context(context: str):
    """Test that timing parameters are honoured at every level of a schedule."""
    with _schedule_context(context):
        first = experimental.play("q", square_pulse(**PULSE), op_name="first")
        assert first is not None
        second = experimental.play("q", square_pulse(**PULSE), ref_op=first, ref_pt="end", rel_time="10ns")
        assert second is not None
        assert second.operation.ref_op == "first"
