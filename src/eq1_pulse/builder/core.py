"""Core builder functions for constructing pulse sequences and schedules.

This module provides global functions for creating pulse programs with:

- Context managers for sequences, schedules, iterations, and conditionals
- Function calls for operations like playing pulses, recording, and barriers
- Token-based references for relative positioning in schedules
- Shorthand functions for common pulse types
- Measure functions for simultaneous play + record operations

Examples

.. code-block:: python

    from eq1_pulse.builder import *

    # Building a sequence
    with build_sequence() as seq:
        play("ch1", square_pulse(duration="10us", amplitude="100mV"))
        wait("ch1", "5us")
        play("ch1", sine_pulse(duration="20us", amplitude="50mV", frequency="5GHz"))

    # Building a schedule with relative positioning
    with build_schedule() as sched:
        op1 = play("ch1", square_pulse(duration="10us", amplitude="100mV"))
        op2 = play("ch2", square_pulse(duration="10us", amplitude="100mV"),
                        ref_op=op1, ref_pt="start", rel_time="5us")

    # Using control flow
    with build_sequence() as seq:
        with repeat(10):
            play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
            measure("qubit", result_var="readout", duration="1us", amplitude="50mV")

        var_decl("i", "int", unit="MHz")
        with for_("i", range(0, 100, 10)):
            set_frequency("qubit", var("i"))
            play("qubit", square_pulse(duration="100ns", amplitude="50mV"))
"""

from __future__ import annotations

import traceback
from collections import defaultdict
from collections.abc import Callable
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal, Unpack

from ..models.basic_types import LinSpace, Range
from ..models.channel_ops import (
    Barrier,
    DemodIntegration,
    FullIntegration,
    IntegrationType,
    Play,
    Record,
    SetFrequency,
    SetPhase,
    ShiftFrequency,
    ShiftPhase,
    Wait,
)
from ..models.data_ops import Discriminate, Store, VariableDecl
from ..models.pulse_types import ArbitrarySampledPulse, ExternalPulse, PulseType, SinePulse, SquarePulse
from ..models.reference_types import ChannelRef, PulseRef, VariableRef
from ..models.schedule import (
    SchedConditional,
    SchedIteration,
    SchedRepetition,
    Schedule,
    ScheduledOperation,
)
from ..models.sequence import Conditional, Iteration, OpSequence, Repetition
from .utils import OperationToken, ScheduleParams, resolve_schedule_params

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from ..models.basic_types import AmplitudeLike, DurationLike, FrequencyLike, PhaseLike, ThresholdLike
    from ..models.data_ops import ComparisonModeLike, ComplexToRealProjectionModeLike
    from ..models.reference_types import ChannelRefLike, PulseRefLike, VariableRefLike

__all__ = (
    "ScheduleBlock",
    "add_block",
    "arbitrary_pulse",
    "barrier",
    "build_schedule",
    "build_sequence",
    "channel",
    "discriminate",
    "external_pulse",
    "for_",
    "if_",
    "measure",
    "measure_and_discriminate",
    "measure_and_discriminate_and_if_",
    "nested_schedule",
    "nested_sequence",
    "play",
    "pulse_ref",
    "record",
    "repeat",
    "set_frequency",
    "set_phase",
    "shift_frequency",
    "shift_phase",
    "sine_pulse",
    "square_pulse",
    "store",
    "sub_schedule",
    "sub_sequence",
    "var",
    "var_decl",
    "wait",
)

# Module-level state for building context
_context_stack: list[
    OpSequence | Schedule | Repetition | Iteration | Conditional | SchedRepetition | SchedIteration | SchedConditional
] = []
_op_counter = 0
# Track unconsumed schedule blocks per context using defaultdict
# Key is id(context), value is list of unconsumed blocks
_unconsumed_blocks: defaultdict[int, list[ScheduleBlock]] = defaultdict(list)


def _generate_op_name() -> str:
    """Generate a unique operation name.

    :return: Unique operation name
    """
    global _op_counter
    _op_counter += 1
    return f"op_{_op_counter}"


def _current_context() -> Any:
    """Get the current building context.

    :return: The current sequence or schedule being built

    :raises RuntimeError: If no context is active
    """
    if not _context_stack:
        raise RuntimeError("No active building context. Use build_sequence() or bschedule() context manager first.")
    return _context_stack[-1]


def _add_to_sequence(operation: Any) -> None:
    """Add an operation to the current sequence context.

    :param operation: The operation to add

    :raises RuntimeError: If current context is not a sequence
    """
    context = _current_context()
    if isinstance(context, Repetition | Iteration | Conditional):
        context.body.items.append(operation)
    elif isinstance(context, OpSequence):
        context.items.append(operation)
    else:
        raise RuntimeError(f"Cannot add sequence operation to {type(context).__name__} context")


def _add_to_schedule(operation: Any, **schedule_params: Unpack[ScheduleParams]) -> OperationToken:
    """Add an operation to the current schedule context.

    :param operation: The operation to add
    :param schedule_params: Additional scheduling parameters

    :return: Token for referencing this operation

    :raises RuntimeError: If current context is not a schedule
    """
    context = _current_context()

    # Resolve any operation tokens to names
    resolved_params = resolve_schedule_params(schedule_params)  # type: ignore[arg-type]

    # Generate operation name if not provided
    if "name" not in resolved_params:
        resolved_params["name"] = _generate_op_name()

    sched_op = ScheduledOperation(op=operation, **resolved_params)  # type: ignore[arg-type]

    # Add to the appropriate schedule-like context
    if isinstance(context, SchedRepetition | SchedIteration | SchedConditional):
        context.body.items.append(sched_op)
    elif isinstance(context, Schedule):
        context.items.append(sched_op)
    else:
        raise RuntimeError(f"Cannot add scheduled operation to {type(context).__name__} context")

    return OperationToken(resolved_params["name"], sched_op)


# ============================================================================
# Context managers
# ============================================================================


@contextmanager
def build_sequence() -> Iterator[OpSequence]:
    """Context manager for building an operation sequence.

    :yield: The operation sequence being built

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence() as seq:
            play("ch1", square_pulse(duration="10us", amplitude="100mV"))
            wait("ch1", "5us")
    """
    seq = OpSequence(items=[])
    _context_stack.append(seq)
    try:
        yield seq
    finally:
        _context_stack.pop()


@contextmanager
def sub_sequence() -> Iterator[OpSequence]:
    """Context manager for building a nested sub-sequence.

    This creates a sub-sequence that will be added to the parent sequence.
    Only works within a sequence context (including nested control flow contexts).

    :yield: The sub-sequence being built

    :raises RuntimeError: If not called within a sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence() as main:
            # Create a reusable operation block as sub-sequence
            with sub_sequence():
                play("qubit", square_pulse(duration="100ns", amplitude="200mV"))
                wait("qubit", duration="50ns")

            # Main sequence continues
            play("qubit", square_pulse(duration="20ns", amplitude="150mV"))

            # Another sub-sequence for measurement
            with sub_sequence():
                play("drive", square_pulse(duration="1us", amplitude="50mV"))
                record("readout", var="result", duration="1us")
    """
    # Must be called within a sequence context
    if not _context_stack:
        raise RuntimeError("sub_sequence can only be used within a build_sequence() context")

    context = _current_context()
    if not isinstance(context, OpSequence | Repetition | Iteration | Conditional):
        raise RuntimeError("sub_sequence can only be used within a sequence context (not in schedules)")

    # Create the nested sequence
    nested_seq = OpSequence(items=[])

    # Add it to the parent sequence
    _add_to_sequence(nested_seq)

    # Push nested sequence as current context for operations inside it
    _context_stack.append(nested_seq)
    try:
        yield nested_seq
    finally:
        _context_stack.pop()


@contextmanager
def build_schedule() -> Iterator[Schedule]:
    """Context manager for building a schedule.

    :yield: The schedule being built

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_schedule() as sched:
            op1 = play("ch1", square_pulse(duration="10us", amplitude="100mV"))
            op2 = play("ch2", square_pulse(duration="10us", amplitude="100mV"),
                            ref_op=op1, ref_pt="start", rel_time="5us")
    """
    sched = Schedule(items=[])
    _context_stack.append(sched)
    sched_id = id(sched)
    try:
        yield sched
    finally:
        # Check for unconsumed schedule blocks before popping context
        unconsumed = _unconsumed_blocks[sched_id]
        if unconsumed:
            count = len(unconsumed)
            # Build detailed error message with traceback info
            error_parts = [
                f"Schedule context closed with {count} unconsumed ScheduleBlock(s). "
                "All @nested_schedule decorated function calls must be passed to add_block() "
                "with schedule parameters.\n"
            ]

            # Add creation info for each unconsumed block
            for i, block in enumerate(unconsumed, 1):
                error_parts.append(f"\nUnconsumed block #{i} created at:")
                error_parts.append(block._get_creation_info())

            # Clean up before raising
            del _unconsumed_blocks[sched_id]
            _context_stack.pop()
            raise RuntimeError("".join(error_parts))
        # Clean up empty list
        if sched_id in _unconsumed_blocks:
            del _unconsumed_blocks[sched_id]
        _context_stack.pop()


@contextmanager
def sub_schedule(**schedule_params: Unpack[ScheduleParams]) -> Iterator[Schedule]:
    """Context manager for building a nested sub-schedule with timing parameters.

    This creates a sub-schedule that can be positioned relative to other operations
    in the parent schedule. Only works within a schedule context (not in sequences).

    :param schedule_params: Schedule timing parameters (name, ref_op, ref_pt, ref_pt_new, rel_time)

    :yield: The sub-schedule being built

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_schedule() as main:
            # Create initialization sub-schedule
            with sub_schedule(name="init") as init:
                play("qubit", square_pulse(duration="100ns", amplitude="200mV"))
                wait("qubit", duration="50ns")

            # Create gate operation positioned after init
            gate_op = play("qubit", square_pulse(duration="20ns", amplitude="150mV"),
                          ref_op="init", ref_pt="end", rel_time="10ns")

            # Create measurement block positioned after gate
            with sub_schedule(name="measure", ref_op=gate_op, ref_pt="end", rel_time="50ns"):
                play("drive", square_pulse(duration="1us", amplitude="50mV"))
                record("readout", var="result", duration="1us")
    """
    # Must be called within a schedule context
    if not _context_stack or not isinstance(_current_context(), Schedule):
        raise RuntimeError("sub_schedule can only be used within a build_schedule() context")

    # Create the nested schedule
    nested_sched = Schedule(items=[])

    # Add it to the parent schedule with timing parameters
    token = _add_to_schedule(nested_sched, **schedule_params)

    # Push nested schedule as current context for operations inside it
    _context_stack.append(nested_sched)
    sched_id = id(nested_sched)
    try:
        yield nested_sched
    finally:
        # Check for unconsumed schedule blocks before popping context
        unconsumed = _unconsumed_blocks[sched_id]
        if unconsumed:
            count = len(unconsumed)
            # Build detailed error message with traceback info
            error_parts = [
                f"sub_schedule context closed with {count} unconsumed ScheduleBlock(s). "
                "All @nested_schedule decorated function calls must be passed to add_block() "
                "with schedule parameters.\n"
            ]

            # Add creation info for each unconsumed block
            for i, block in enumerate(unconsumed, 1):
                error_parts.append(f"\nUnconsumed block #{i} created at:")
                error_parts.append(block._get_creation_info())

            # Clean up before raising
            del _unconsumed_blocks[sched_id]
            _context_stack.pop()
            raise RuntimeError("".join(error_parts))
        # Clean up empty list
        if sched_id in _unconsumed_blocks:
            del _unconsumed_blocks[sched_id]
        _context_stack.pop()

    # Return the token so it can be used for further references
    return token  # type: ignore[return-value]


@contextmanager
def repeat(count: int, **schedule_params: Unpack[ScheduleParams]) -> Iterator[Repetition | SchedRepetition]:
    """Context manager for building a repetition block.

    Creates a sequence repetition in sequence contexts, or a schedule repetition
    in schedule contexts.

    :param count: Number of times to repeat
    :param schedule_params:
        Additional scheduling parameters (name, ref_op, ref_pt, etc.) - only used in schedule context

    :yield: The repetition being built

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        # In sequence context
        with build_sequence():
            with repeat(10):
                play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

        # In schedule context with timing
        with build_schedule():
            op1 = play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
            with repeat(10, ref_op=op1, ref_pt="end"):
                play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
    """
    # Add to parent context if it exists
    if _context_stack:
        parent = _current_context()

        # Schedule context - create SchedRepetition
        if isinstance(parent, Schedule | SchedRepetition | SchedIteration | SchedConditional):
            sched_body = Schedule(items=[])
            sched_rep = SchedRepetition(count=count, body=sched_body)
            _add_to_schedule(sched_rep, **schedule_params)
            _context_stack.append(sched_rep)
            try:
                yield sched_rep  # type: ignore[misc]
            finally:
                _context_stack.pop()
            return

        # Sequence context - create Repetition
        elif isinstance(parent, OpSequence | Repetition | Iteration | Conditional):
            seq_body = OpSequence(items=[])
            rep = Repetition(count=count, body=seq_body)
            if isinstance(parent, OpSequence):
                parent.items.append(rep)
            else:
                parent.body.items.append(rep)
            _context_stack.append(rep)
            try:
                yield rep  # type: ignore[misc]
            finally:
                _context_stack.pop()
            return

    # No parent context - create sequence repetition by default
    seq_body = OpSequence(items=[])
    rep = Repetition(count=count, body=seq_body)
    _context_stack.append(rep)
    try:
        yield rep  # type: ignore[misc]
    finally:
        _context_stack.pop()


@contextmanager
def for_(
    var: VariableRefLike | list[VariableRefLike],
    items: Iterable[Any] | Range | LinSpace,
    **schedule_params: Unpack[ScheduleParams],
) -> Iterator[Iteration]:
    """Context manager for building an iteration (for loop).

    :param var: Variable reference(s) for the loop variable(s)
    :param items: Range, LinSpace, or iterable to iterate over
    :param schedule_params:
        Additional scheduling parameters (name, ref_op, ref_pt, etc.) - only used in schedule context

    :yield: The iteration being built

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        # In sequence context
        with build_sequence():
            var_decl("i", "int", unit="MHz")
            with for_("i", range(0, 100, 10)):
                set_frequency("qubit", var("i"))

        # In schedule context with timing
        with build_schedule():
            op1 = play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
            with for_("i", range(0, 5), ref_op=op1, ref_pt="end"):
                play("qubit", square_pulse(duration="20ns", amplitude="100mV"))
    """
    body = OpSequence(items=[])
    iter_obj = Iteration(var=var, items=items, body=body)

    # Add to parent context if it exists
    if _context_stack:
        parent = _current_context()
        if isinstance(parent, OpSequence):
            parent.items.append(iter_obj)
        elif isinstance(parent, Repetition | Iteration | Conditional):
            parent.body.items.append(iter_obj)
        elif isinstance(parent, Schedule | SchedRepetition | SchedIteration | SchedConditional):
            # For schedules, we need SchedIteration not Iteration
            sched_iter = SchedIteration(var=var, items=items, body=Schedule(items=[]))
            _add_to_schedule(sched_iter, **schedule_params)
            _context_stack.append(sched_iter)
            try:
                yield sched_iter  # type: ignore[misc]
            finally:
                _context_stack.pop()
            return

    _context_stack.append(iter_obj)
    try:
        yield iter_obj
    finally:
        _context_stack.pop()


@contextmanager
def if_(var: VariableRefLike, **schedule_params: Unpack[ScheduleParams]) -> Iterator[Conditional]:
    """Context manager for building a conditional block.

    :param var: Variable reference for the condition
    :param schedule_params:
        Additional scheduling parameters (name, ref_op, ref_pt, etc.) - only used in schedule context

    :yield: The conditional being built

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        # In sequence context
        with build_sequence():
            var_decl("result", "bool")
            # ... perform measurement to populate result ...
            with if_("result"):
                play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

        # In schedule context with timing
        with build_schedule():
            op1 = play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
            with if_("result", ref_op=op1, ref_pt="end"):
                play("qubit", square_pulse(duration="20ns", amplitude="100mV"))
    """
    body = OpSequence(items=[])
    cond = Conditional(var=var, body=body)

    # Add to parent context if it exists
    if _context_stack:
        parent = _current_context()
        if isinstance(parent, OpSequence):
            parent.items.append(cond)
        elif isinstance(parent, Repetition | Iteration | Conditional):
            parent.body.items.append(cond)
        elif isinstance(parent, Schedule | SchedRepetition | SchedIteration | SchedConditional):
            # For schedules, we need SchedConditional not Conditional
            sched_cond = SchedConditional(var=var, body=Schedule(items=[]))
            _add_to_schedule(sched_cond, **schedule_params)
            _context_stack.append(sched_cond)
            try:
                yield sched_cond  # type: ignore[misc]
            finally:
                _context_stack.pop()
            return

    _context_stack.append(cond)
    try:
        yield cond
    finally:
        _context_stack.pop()


@contextmanager
def measure_and_discriminate_and_if_(
    channel: ChannelRefLike | tuple[ChannelRefLike, ChannelRefLike],
    *,
    raw_var: VariableRefLike,
    result_var: VariableRefLike,
    threshold: ThresholdLike,
    duration: DurationLike,
    amplitude: AmplitudeLike,
    integration: IntegrationType | Literal["full", "demod"] = "full",
    phase: PhaseLike | None = None,
    scale_cos: float = 1.0,
    scale_sin: float = 1.0,
    rotation: PhaseLike = 0,
    compare: ComparisonModeLike = ">=",
    project: ComplexToRealProjectionModeLike = "real",
    **schedule_params: Unpack[ScheduleParams],
) -> Iterator[Conditional]:
    """Measure, discriminate, and create a conditional block in one call.

    This is a convenience context manager that combines :func:`measure_and_discriminate`
    with :func:`if_`. It performs a measurement, discriminates the result,
    and opens a conditional block that executes if the discrimination result is true.

    :param channel: Channel for measurement. Can be a single channel (used for both
        drive and readout) or a tuple of (drive_channel, readout_channel)
    :param raw_var: Variable to store the raw measurement result
    :param result_var: Variable to store the discriminated binary result
    :param threshold: Threshold value for discrimination
    :param duration: Measurement duration
    :param amplitude: Measurement pulse amplitude
    :param integration: Integration type for recording
    :param phase: Phase for demod integration
    :param scale_cos: Cosine scaling for demod integration
    :param scale_sin: Sine scaling for demod integration
    :param rotation: Phase rotation for discrimination
    :param compare: Comparison operator for discrimination
    :param project: Complex-to-real projection mode for discrimination
    :param schedule_params: Additional scheduling parameters (for schedules)

    :yield: The conditional being built

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence():
            var_decl("raw", "complex", unit="mV")
            var_decl("state", "bool")
            # Measure, discriminate, and execute conditionally
            with measure_and_discriminate_and_if_(
                "qubit",
                raw_var="raw",
                result_var="state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV"
            ):
                # This block executes if state is true
                play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
    """
    # Perform measurement and discrimination
    measure_and_discriminate(
        channel,
        raw_var=raw_var,
        result_var=result_var,
        threshold=threshold,
        duration=duration,
        amplitude=amplitude,
        integration=integration,
        phase=phase,
        scale_cos=scale_cos,
        scale_sin=scale_sin,
        rotation=rotation,
        compare=compare,
        project=project,
        **schedule_params,
    )

    # Open conditional block using the discriminated result
    with if_(result_var) as cond:
        yield cond


# ============================================================================
# Pulse creation helpers
# ============================================================================


def square_pulse(
    *,
    duration: DurationLike,
    amplitude: AmplitudeLike,
    rise_time: DurationLike | None = None,
    fall_time: DurationLike | None = None,
) -> SquarePulse:
    """Create a square pulse.

    :param duration: Pulse duration
    :param amplitude: Pulse amplitude
    :param rise_time: Optional rise time
    :param fall_time: Optional fall time

    :return: Square pulse definition

    Examples

    .. code-block:: python

        from eq1_pulse.builder import square_pulse

        pulse = square_pulse(duration="10us", amplitude="100mV")
    """
    return SquarePulse(
        duration=duration,
        amplitude=amplitude,
        rise_time=rise_time,
        fall_time=fall_time,
    )


def sine_pulse(
    *,
    duration: DurationLike,
    amplitude: AmplitudeLike,
    frequency: FrequencyLike,
    to_frequency: FrequencyLike | None = None,
) -> SinePulse:
    """Create a sine pulse.

    :param duration: Pulse duration
    :param amplitude: Pulse amplitude
    :param frequency: Start frequency
    :param to_frequency: Optional end frequency for chirp

    :return: Sine pulse definition

    Examples

    .. code-block:: python

        from eq1_pulse.builder import sine_pulse

        pulse = sine_pulse(duration="20us", amplitude="50mV", frequency="5GHz")

        # Chirped sine pulse
        chirp = sine_pulse(
            duration="50us",
            amplitude="30mV",
            frequency="4.5GHz",
            to_frequency="5.5GHz"
        )
    """
    return SinePulse(
        duration=duration,
        amplitude=amplitude,
        frequency=frequency,
        to_frequency=to_frequency,
    )


def external_pulse(
    function: str,
    *,
    duration: DurationLike,
    amplitude: AmplitudeLike,
    params: dict[str, Any] | None = None,
) -> ExternalPulse:
    """Create an external pulse reference.

    References a pulse shape defined in an external function. The function
    should accept duration, amplitude, and any additional params, and return
    normalized waveform samples.

    :param function: Fully qualified function name (e.g., "my_lib.gaussian")
    :param duration: Pulse duration
    :param amplitude: Pulse amplitude (scale factor)
    :param params: Additional parameters passed to the pulse function

    :return: External pulse definition

    Examples

    .. code-block:: python

        from eq1_pulse.builder import external_pulse

        # Reference a Gaussian pulse from an external library
        pulse = external_pulse(
            "pulses.gaussian",
            duration="100ns",
            amplitude="80mV",
            params={"sigma": "20ns"}
        )

        # DRAG pulse with parameters
        drag = external_pulse(
            "pulses.drag",
            duration="50ns",
            amplitude="100mV",
            params={"beta": 0.5, "sigma": "10ns"}
        )
    """
    return ExternalPulse(
        function=function,
        duration=duration,
        amplitude=amplitude,
        params=params,
    )


def arbitrary_pulse(
    samples: list[float] | list[complex],
    *,
    duration: DurationLike,
    amplitude: AmplitudeLike,
    interpolation: str | None = None,
    time_points: list[float] | None = None,
) -> ArbitrarySampledPulse:
    """Create an arbitrary sampled pulse from explicit samples.

    Defines a pulse shape using explicitly provided sample points. Samples
    should be normalized (peak value of 1.0), and will be scaled by amplitude.

    :param samples: Normalized waveform samples (real or complex)
    :param duration: Total pulse duration
    :param amplitude: Pulse amplitude (scale factor for samples)
    :param interpolation: Interpolation method (e.g., "linear", "cubic")
    :param time_points: Optional time points for samples (normalized 0-1)

    :return: Arbitrary pulse definition

    Examples

    .. code-block:: python

        from eq1_pulse.builder import arbitrary_pulse

        # Simple triangle pulse
        triangle = arbitrary_pulse(
            samples=[0.0, 0.5, 1.0, 0.5, 0.0],
            duration="100ns",
            amplitude="50mV"
        )

        # Complex IQ pulse with explicit time points
        iq_samples = [0.0+0.0j, 0.5+0.3j, 1.0+0.0j, 0.5-0.3j, 0.0+0.0j]
        iq_pulse = arbitrary_pulse(
            samples=iq_samples,
            duration="80ns",
            amplitude="75mV",
            time_points=[0.0, 0.25, 0.5, 0.75, 1.0],
            interpolation="cubic"
        )
    """
    return ArbitrarySampledPulse(
        samples=samples,
        duration=duration,
        amplitude=amplitude,
        interpolation=interpolation,
        time_points=time_points,
    )


# ============================================================================
# Reference helpers
# ============================================================================


def var(name: str) -> VariableRef:
    """Create a variable reference.

    :param name: Variable name

    :return: Variable reference

    Examples

    .. code-block:: python

        from eq1_pulse.builder import var

        freq_var = var("frequency")
    """
    return VariableRef(var=name)


def channel(name: str) -> ChannelRef:
    """Create a channel reference.

    :param name: Channel name

    :return: Channel reference

    Examples

    .. code-block:: python

        from eq1_pulse.builder import channel

        ch = channel("qubit_1")
    """
    return ChannelRef(channel=name)


def pulse_ref(name: str) -> PulseRef:
    """Create a pulse reference.

    :param name: Pulse name

    :return: Pulse reference

    Examples

    .. code-block:: python

        from eq1_pulse.builder import pulse_ref

        p = pulse_ref("pi_pulse")
    """
    return PulseRef(pulse_name=name)


# ============================================================================
# Variable declaration
# ============================================================================


def var_decl(
    name: str,
    dtype: Literal["bool", "int", "float", "complex"],
    *,
    shape: tuple[int, ...] | None = None,
    unit: str | None = None,
) -> None:
    """Declare a variable for use in the current context.

    Variables should be declared before they are used in iterations or conditionals.
    The declaration specifies the variable's data type, optional shape (for arrays),
    and optional unit for dimensional consistency.

    :param name: Name of the variable (must be a valid identifier)
    :param dtype: Data type of the variable ("bool", "int", "float", or "complex")
    :param shape: Optional shape for array variables (e.g., (10,) for 1D array)
    :param unit: Optional unit string (e.g., "mV", "ns", "GHz") for the variable

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence():
            # Declare a float variable for amplitude with unit
            var_decl("amp", "float", unit="mV")

            # Declare an integer variable for iteration
            var_decl("count", "int")

            # Declare a complex array variable
            var_decl("iq_data", "complex", shape=(100,))
    """
    var_decl_obj = VariableDecl(name=name, dtype=dtype, shape=shape, unit=unit)
    _add_to_sequence(var_decl_obj)


# ============================================================================
# Decorators for automatic sub-context wrapping
# ============================================================================


class ScheduleBlock:
    """A schedule block that must be added via add_block().

    This is returned by @nested_schedule decorated functions and must be
    passed to add_block() to be added to the schedule. Unconsumed blocks
    are tracked and verified when the schedule context closes.
    """

    def __init__(self, func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]):
        """Initialize the schedule block.

        :param func: The wrapped function to execute later
        :param args: Positional arguments for the function
        :param kwargs: Keyword arguments for the function
        """
        self._func = func
        self._args = args
        self._kwargs = kwargs

        # Capture the traceback of where this block was created
        # We'll use this to provide helpful error messages if the block is not consumed
        self._creation_traceback = traceback.format_stack()[:-1]  # Exclude this __init__ frame

        # Register this block with the current context
        context = _current_context()
        _unconsumed_blocks[id(context)].append(self)

    def _execute(self) -> None:
        """Execute the block's function and mark as consumed."""
        # Remove from unconsumed list (find the context this belongs to)
        for blocks in _unconsumed_blocks.values():
            if self in blocks:
                blocks.remove(self)
                break

        # Execute the function
        self._func(*self._args, **self._kwargs)

    def _get_creation_info(self) -> str:
        """Get formatted information about where this block was created."""
        # Format the traceback to show where the block was created
        return "".join(self._creation_traceback)


def add_block(block: ScheduleBlock, **schedule_params: Unpack[ScheduleParams]) -> OperationToken | None:
    """Add a schedule block to the current schedule with timing parameters.

    This function must be used with @nested_schedule decorated functions to
    add them to a schedule with positioning parameters.

    :param block: The ScheduleBlock returned by calling a @nested_schedule decorated function
    :param schedule_params: Schedule timing parameters (name, ref_op, ref_pt, ref_pt_new, rel_time)

    :return: Operation token for referencing this block

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        @nested_schedule
        def init_block(qubit: str):
            play(qubit, square_pulse(duration="100ns", amplitude="200mV"))

        with build_schedule():
            # Call the function to create a block, then add it with timing
            token = add_block(init_block("qubit0"), name="init")
            add_block(init_block("qubit1"), ref_op=token, ref_pt="end", rel_time="50ns")
    """
    if not isinstance(block, ScheduleBlock):
        raise TypeError("add_block() requires a ScheduleBlock from @nested_schedule decorated function")

    context = _current_context()
    if not isinstance(context, Schedule):
        raise RuntimeError("add_block() can only be used within a build_schedule() context")

    # Record the number of items before
    items_before = len(context.items)

    # Execute the block within a sub_schedule
    with sub_schedule(**schedule_params) as _:  # type: ignore[arg-type]
        block._execute()

    # Get the token from the newly added scheduled operation
    if len(context.items) > items_before:
        last_sched_op = context.items[-1]
        if last_sched_op.name:
            return OperationToken(last_sched_op.name, last_sched_op)
    return None


def nested_sequence[R, **P](func: Callable[P, R]) -> Callable[P, R]:
    """Decorator that automatically wraps a function body in a sub-sequence.

    This decorator creates a :func:`sub_sequence` context around the function body,
    allowing you to define reusable operation blocks that can be composed together
    in sequence contexts. Use this for functions that don't need schedule-specific
    timing parameters.

    :param func: The function to decorate

    :return: The decorated function that creates a sub-sequence when called

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        @nested_sequence
        def hadamard_gate(qubit: str):
            '''Apply a Hadamard gate.'''
            play(qubit, square_pulse(duration="20ns", amplitude="100mV"))
            shift_phase(qubit, "90deg")
            play(qubit, square_pulse(duration="20ns", amplitude="100mV"))
            shift_phase(qubit, "-90deg")

        @nested_sequence
        def measurement_block(drive_ch: str, readout_ch: str, result_var: str):
            '''Perform readout measurement.'''
            play(drive_ch, square_pulse(duration="1us", amplitude="50mV"))
            record(readout_ch, var=result_var, duration="1us")

        # Use in sequence context - automatically creates sub_sequence
        with build_sequence():
            var_decl("readout", "complex", unit="mV")
            hadamard_gate("qubit0")
            measurement_block("drive0", "readout0", "readout")
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        # Check if we're in a context
        if _context_stack:
            context = _current_context()

            # In sequence context (OpSequence or control flow)
            if isinstance(context, OpSequence | Repetition | Iteration | Conditional):
                # Use sub_sequence context
                with sub_sequence() as _:
                    return func(*args, **kwargs)  # type: ignore[return-value]
            # In schedule context - not supported, raise error
            elif isinstance(context, Schedule):
                raise RuntimeError(
                    "@nested_sequence decorator cannot be used in schedule context. "
                    "Use @nested_schedule decorator instead for functions that need schedule timing parameters."
                )

        # If not in a context, just call the function directly
        return func(*args, **kwargs)

    return wrapper


def nested_schedule[**P](func: Callable[P, Any]) -> Callable[P, ScheduleBlock]:
    """Decorator that creates schedule blocks for modular composition.

    Functions decorated with @nested_schedule return a :class:`ScheduleBlock` when called.
    This block must be passed to :func:`add_block` along with schedule timing parameters
    to be added to the schedule.

    This approach provides proper type safety: the decorated function's parameters are
    preserved, and schedule parameters are provided separately via :func:`add_block`.

    :param func: The function to decorate

    :return: A function that returns a ScheduleBlock when called

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        @nested_schedule
        def initialization(qubit: str):
            '''Initialize qubit.'''
            play(qubit, square_pulse(duration="100ns", amplitude="200mV"))
            wait(qubit, duration="50ns")

        @nested_schedule
        def measurement_block(drive_ch: str, readout_ch: str, result_var: str):
            '''Perform readout measurement.'''
            play(drive_ch, square_pulse(duration="1us", amplitude="50mV"))
            record(readout_ch, var=result_var, duration="1us")

        # Use in schedule context - pass block to add_block with schedule parameters
        with build_schedule():
            var_decl("result", "complex", unit="mV")

            # Create block and add with timing parameters
            init_token = add_block(initialization("qubit0"), name="init")

            # Position second block relative to first
            add_block(
                measurement_block("drive0", "readout0", "result"),
                ref_op=init_token,
                ref_pt="end",
                rel_time="100ns"
            )
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> ScheduleBlock:
        return ScheduleBlock(func, args, kwargs)

    return wrapper


# ============================================================================
# Channel operations
# ============================================================================


def play(
    channel: ChannelRefLike,
    pulse: PulseType | PulseRefLike,
    *,
    scale_amp: float | complex | VariableRef | None = None,
    cond: VariableRefLike | None = None,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Play a pulse on a channel.

    :param channel: Channel to play on
    :param pulse: Pulse to play
    :param scale_amp: Optional amplitude scaling
    :param cond: Optional condition variable
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        # In sequence
        play("ch1", square_pulse(duration="10us", amplitude="100mV"))

        # In schedule with positioning
        op = play("ch1", square_pulse(duration="10us", amplitude="100mV"),
                      ref_op=previous_op, ref_pt="end")
    """
    op = Play(channel=channel, pulse=pulse, scale_amp=scale_amp, cond=cond)

    context = _current_context()
    if isinstance(context, Schedule | SchedRepetition | SchedIteration | SchedConditional):
        return _add_to_schedule(op, **schedule_params)
    else:
        _add_to_sequence(op)
        return None


def wait(
    *channels: ChannelRefLike,
    duration: DurationLike,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Add wait operation on channel(s).

    In sequences, wait can be applied to multiple channels simultaneously,
    appending the wait time to each channel independently.

    In schedules, wait can only be applied to a single channel due to complex
    semantics (multi-channel wait would be equivalent to a subschedule where
    all channels idle, which contradicts the sequence definition).

    :param channels: Channel(s) to wait on. Multiple channels allowed in sequences,
        single channel only in schedules.
    :param duration: Wait duration
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    :raises RuntimeError: If multiple channels specified in a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import wait

        # Single channel (works in both sequences and schedules)
        wait("ch1", duration="5us")

        # Multiple channels (only works in sequences)
        with build_sequence():
            wait("ch1", "ch2", duration="10us")
    """
    context = _current_context()

    # Validate multi-channel wait in schedules
    if isinstance(context, Schedule | SchedRepetition | SchedIteration | SchedConditional) and len(channels) > 1:
        raise RuntimeError(
            f"Wait with multiple channels ({len(channels)} channels) is not allowed "
            "in schedule context. Multi-channel wait has complex semantics in schedules "
            "(equivalent to a subschedule with all channels idling), which contradicts "
            "the sequence definition. Use single-channel wait in schedules."
        )

    op = Wait(*channels, duration=duration)  # type: ignore[arg-type]

    if isinstance(context, Schedule | SchedRepetition | SchedIteration | SchedConditional):
        return _add_to_schedule(op, **schedule_params)
    else:
        _add_to_sequence(op)
        return None


def barrier(
    *channels: ChannelRefLike,
) -> None:
    """Add barrier (synchronization) on channel(s).

    The barrier operation synchronizes multiple channels, causing them to wait
    until all specified channels have reached the barrier point. This is only
    meaningful in sequence contexts where relative timing between channels
    may vary. In schedule contexts, explicit timing makes barriers unnecessary.

    :param channels: Channels to synchronize

    :raises RuntimeError: If called in a schedule context (barriers only work in sequences)

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence():
            # Operations on different channels may have different durations
            play("drive", square_pulse(duration="10us", amplitude="100mV"))
            play("readout", sine_pulse(duration="5us", amplitude="50mV", frequency="5GHz"))

            # Barrier ensures both channels are synchronized before continuing
            barrier("drive", "readout")

            # After barrier, both channels start together
            play("drive", square_pulse(duration="20us", amplitude="80mV"))
            play("readout", square_pulse(duration="20us", amplitude="40mV"))
    """
    op = Barrier(*channels)

    context = _current_context()
    if isinstance(context, Schedule):
        raise RuntimeError(
            "Barrier operations are not supported in schedule contexts. "
            "Schedules use explicit timing, making barriers unnecessary. "
            "Use sequence context instead."
        )
    else:
        _add_to_sequence(op)


def set_frequency(
    channel: ChannelRefLike,
    frequency: FrequencyLike | VariableRefLike,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Set channel frequency.

    :param channel: Channel to set frequency on
    :param frequency: Frequency to set
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import set_frequency

        set_frequency("qubit", "5GHz")
    """
    op = SetFrequency(channel=channel, frequency=frequency)

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(op, **schedule_params)
    else:
        _add_to_sequence(op)
        return None


def shift_frequency(
    channel: ChannelRefLike,
    frequency: FrequencyLike | VariableRefLike,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Shift channel frequency.

    :param channel: Channel to shift frequency on
    :param frequency: Frequency shift amount
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import shift_frequency

        shift_frequency("qubit", "100MHz")
    """
    op = ShiftFrequency(channel=channel, frequency=frequency)

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(op, **schedule_params)
    else:
        _add_to_sequence(op)
        return None


def set_phase(
    channel: ChannelRefLike,
    phase: PhaseLike | VariableRefLike,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Set channel phase.

    :param channel: Channel to set phase on
    :param phase: Phase to set
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import set_phase

        set_phase("qubit", "90deg")
    """
    op = SetPhase(channel=channel, phase=phase)

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(op, **schedule_params)
    else:
        _add_to_sequence(op)
        return None


def shift_phase(
    channel: ChannelRefLike,
    phase: PhaseLike | VariableRefLike,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Shift channel phase.

    :param channel: Channel to shift phase on
    :param phase: Phase shift amount
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import shift_phase

        shift_phase("qubit", "45deg")
    """
    op = ShiftPhase(channel=channel, phase=phase)

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(op, **schedule_params)
    else:
        _add_to_sequence(op)
        return None


def record(
    channel: ChannelRefLike,
    var: VariableRefLike,
    *,
    duration: DurationLike,
    integration: IntegrationType | Literal["full", "demod"] = "full",
    phase: PhaseLike | None = None,
    scale_cos: float = 1.0,
    scale_sin: float = 1.0,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Record (acquire) data from a channel.

    :param channel: Channel to record from
    :param var: Variable to store the result
    :param duration: Recording duration
    :param integration: Integration type ("full" or "demod")
    :param phase: Phase for demod integration
    :param scale_cos: Cosine scaling for demod integration
    :param scale_sin: Sine scaling for demod integration
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import build_sequence, record, var_decl

        var_decl("result", "complex", unit="mV")
        with build_sequence() as seq:
            record("readout", "result", duration="1us", integration="demod")
    """
    # Handle integration type
    if isinstance(integration, str):
        if integration == "full":
            integration_obj: IntegrationType = FullIntegration()
        elif integration == "demod":
            integration_obj = DemodIntegration(phase=phase, scale_cos=scale_cos, scale_sin=scale_sin)  # type: ignore[arg-type]
        else:
            raise ValueError(f"Invalid integration type: {integration}")
    else:
        integration_obj = integration

    op = Record(channel=channel, var=var, duration=duration, integration=integration_obj)  # type: ignore[arg-type]

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(op, **schedule_params)
    else:
        _add_to_sequence(op)
        return None


def discriminate(
    target: VariableRefLike,
    source: VariableRefLike,
    threshold: ThresholdLike,
    *,
    rotation: PhaseLike = 0,
    compare: ComparisonModeLike = ">=",
    project: ComplexToRealProjectionModeLike = "real",
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Discriminate a measurement result to a binary outcome.

    This operation applies a rotation, projects complex data to real, and compares
    against a threshold to produce a boolean result.

    :param target: Variable to store the discrimination result (boolean)
    :param source: Source variable containing the measurement data
    :param threshold: Threshold value for comparison
    :param rotation: Phase rotation to apply before projection (default: 0)
    :param compare: Comparison operator (default: ">=")
    :param project: Complex-to-real projection mode (default: "real")
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import discriminate

        # Simple discrimination with default parameters
        discriminate("bit", "measurement", threshold=0.5)

        # With rotation and different comparison
        discriminate("bit", "measurement", threshold=0.5,
                         rotation="45deg", compare=">", project="abs")
    """
    op = Discriminate(
        target=target,
        source=source,
        threshold=threshold,
        rotation=rotation,  # type: ignore[arg-type]
        compare=compare,  # type: ignore[arg-type]
        project=project,  # type: ignore[arg-type]
    )

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(op, **schedule_params)
    else:
        _add_to_sequence(op)
        return None


def store(
    key: str,
    source: VariableRefLike,
    *,
    mode: Literal["last", "average", "count", "trace"] = "last",
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Store a variable value for later retrieval.

    This operation stores the value of a variable to persistent storage
    for analysis after the pulse program completes. Different storage modes
    allow for averaging, counting, or trace capture.

    :param key: Storage key for retrieving the data
    :param source: Source variable to store
    :param mode: Storage mode - how to aggregate multiple values
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence():
            var_decl("measurement", "complex", unit="mV")
            var_decl("result", "complex", unit="mV")
            # ... perform measurement to populate measurement ...

            # Store single measurement
            store("result", "measurement", mode="last")

        # Average multiple measurements
        with build_sequence():
            var_decl("i", "int")
            var_decl("m", "complex", unit="mV")
            var_decl("avg_result", "complex", unit="mV")
            with for_("i", range(100)):
                measure("drive", result_var="m", duration="1us", amplitude="50mV")
                store("avg_result", "m", mode="average")
    """
    op = Store(key=key, source=source, mode=mode)  # type: ignore[arg-type]

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(op, **schedule_params)
    else:
        _add_to_sequence(op)
        return None


def measure(
    channel: ChannelRefLike | tuple[ChannelRefLike, ChannelRefLike],
    *,
    result_var: VariableRefLike,
    duration: DurationLike,
    amplitude: AmplitudeLike,
    integration: IntegrationType | Literal["full", "demod"] = "full",
    phase: PhaseLike | None = None,
    scale_cos: float = 1.0,
    scale_sin: float = 1.0,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Perform a measurement (simultaneous play + record).

    This is a convenience function that creates a square pulse play operation
    and a record operation that execute simultaneously.

    :param channel: Channel for measurement. Can be a single channel (used for both
        drive and readout) or a tuple of (drive_channel, readout_channel)
    :param result_var: Variable to store the measurement result
    :param duration: Measurement duration
    :param amplitude: Measurement pulse amplitude
    :param integration: Integration type for recording
    :param phase: Phase for demod integration
    :param scale_cos: Cosine scaling for demod integration
    :param scale_sin: Sine scaling for demod integration
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import build_sequence, measure, var_decl

        var_decl("result", "complex", unit="mV")
        with build_sequence() as seq:
            # Single channel for both drive and readout
            measure("qubit", result_var="result",
                    duration="1us", amplitude="50mV", integration="demod")

            # Separate drive and readout channels
            measure(("drive", "readout"), result_var="result",
                    duration="1us", amplitude="50mV", integration="demod")
    """
    # Parse channel parameter
    if isinstance(channel, tuple):
        drive_channel, readout_channel = channel
    else:
        drive_channel = readout_channel = channel

    # Create measurement pulse
    meas_pulse = square_pulse(duration=duration, amplitude=amplitude)

    context = _current_context()

    if isinstance(context, Schedule):
        # In schedule: create both operations with same timing
        play_token = play(drive_channel, meas_pulse, **schedule_params)

        # Record starts at the same time as play
        record_params = schedule_params.copy()
        if play_token:
            record_params["ref_op"] = play_token.name
            record_params["ref_pt"] = "start"
            record_params["ref_pt_new"] = "start"
            record_params["rel_time"] = 0

        return record(
            readout_channel,
            result_var,
            duration=duration,
            integration=integration,
            phase=phase,
            scale_cos=scale_cos,
            scale_sin=scale_sin,
            **record_params,
        )
    else:
        # In sequence: add operations sequentially
        # Note: In a true measurement, play and record should be simultaneous
        # This requires the backend to handle the timing correctly
        play(drive_channel, meas_pulse)
        record(
            readout_channel,
            result_var,
            duration=duration,
            integration=integration,
            phase=phase,
            scale_cos=scale_cos,
            scale_sin=scale_sin,
        )
        return None


def measure_and_discriminate(
    channel: ChannelRefLike | tuple[ChannelRefLike, ChannelRefLike],
    *,
    raw_var: VariableRefLike,
    result_var: VariableRefLike,
    threshold: ThresholdLike,
    duration: DurationLike,
    amplitude: AmplitudeLike,
    integration: IntegrationType | Literal["full", "demod"] = "full",
    phase: PhaseLike | None = None,
    scale_cos: float = 1.0,
    scale_sin: float = 1.0,
    rotation: PhaseLike = 0,
    compare: ComparisonModeLike = ">=",
    project: ComplexToRealProjectionModeLike = "real",
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Perform measurement and discrimination in one call.

    This is a convenience function that combines :func:`measure` and
    :func:`discriminate` operations. It performs a measurement, stores
    the raw result, discriminates it to a binary outcome, and returns
    a token for the discrimination operation.

    :param channel: Channel for measurement. Can be a single channel (used for both
        drive and readout) or a tuple of (drive_channel, readout_channel)
    :param raw_var: Variable to store the raw measurement result
    :param result_var: Variable to store the discriminated binary result
    :param threshold: Threshold value for discrimination
    :param duration: Measurement duration
    :param amplitude: Measurement pulse amplitude
    :param integration: Integration type for recording
    :param phase: Phase for demod integration
    :param scale_cos: Cosine scaling for demod integration
    :param scale_sin: Sine scaling for demod integration
    :param rotation: Phase rotation for discrimination
    :param compare: Comparison operator for discrimination
    :param project: Complex-to-real projection mode for discrimination
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence():
            var_decl("raw_data", "complex", unit="mV")
            var_decl("qubit_state", "bool")

            # Measure and discriminate in one call
            measure_and_discriminate(
                "qubit",
                raw_var="raw_data",
                result_var="qubit_state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV"
            )

            # Then use the result in a conditional
            with if_("qubit_state"):
                play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
    """
    # Perform measurement
    measure(
        channel,
        result_var=raw_var,
        duration=duration,
        amplitude=amplitude,
        integration=integration,
        phase=phase,
        scale_cos=scale_cos,
        scale_sin=scale_sin,
        **schedule_params,
    )

    # Discriminate the result
    return discriminate(
        target=result_var,
        source=raw_var,
        threshold=threshold,
        rotation=rotation,
        compare=compare,
        project=project,
        **schedule_params,
    )
