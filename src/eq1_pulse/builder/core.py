"""Core builder functions for constructing pulse sequences.

This module provides global functions for creating pulse programs with:

- Context managers for sequences, iterations, and conditionals
- Function calls for operations like playing pulses, recording, and barriers
- Shorthand functions for common pulse types
- Measure functions for simultaneous play + record operations

For the unused, experimental schedule API (explicit timing with reference points),
see :mod:`eq1_pulse.builder.experimental`.

Examples

.. code-block:: python

    from eq1_pulse.builder import *

    # Building a sequence
    with build_sequence() as seq:
        play("ch1", square_pulse(duration="10us", amplitude="100mV"))
        wait("ch1", duration="5us")
        play("ch1", sine_pulse(duration="20us", amplitude="50mV", frequency="5GHz"))

    # Using control flow
    with build_sequence() as seq:
        with repeat(10):
            play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
            measure("qubit", result_var="readout", duration="1us", amplitude="50mV",
                    integration=full_integration())

        var_decl("i", "int", unit="MHz")
        with for_("i", range(0, 100, 10)):
            set_frequency("qubit", var("i"))
            play("qubit", square_pulse(duration="100ns", amplitude="50mV"))
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal, cast, overload

from ..models.basic_types import LinSpace, Range
from ..models.channel_ops import (
    Barrier,
    DemodIntegration,
    FullIntegration,
    Play,
    Record,
    SetFrequency,
    SetPhase,
    ShiftFrequency,
    ShiftPhase,
    Wait,
)
from ..models.data_ops import Discriminate, PulseDecl, Store, StoreMode, StoreModeLiteral, VariableDecl
from ..models.external_block import ExternalBlock
from ..models.pulse_types import PulseType
from ..models.reference_types import VariableRef
from ..models.sequence import Conditional, Iteration, OpSequence, Repetition
from ._factories import (
    _convert_range_to_model,
    _validate_explicit_variable_ref,
    _validate_variable_ref,
    arbitrary_pulse,
    channel,
    demod_integration,
    external_pulse,
    full_integration,
    phase,
    pulse_ref,
    sine_pulse,
    square_pulse,
    var,
)
from ._factories import _validate_or_pass_through as _validate_or_pass_through
from ._state import (
    _current_context,
    _in_schedule,
    _in_sequence,
    _pop_context,
    _push_context,
    _register_variable,
)
from ._state import _get_state as _get_state

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from ..models.basic_types import AmplitudeLike, DurationLike, FrequencyLike, PhaseLike, ThresholdLike
    from ..models.data_ops import ComparisonModeLike, ComplexToRealProjectionModeLike
    from ..models.reference_types import ChannelRefLike, PulseRefLike, VariableRefLike

__all__ = (
    "arbitrary_pulse",
    "barrier",
    "build_sequence",
    "channel",
    "demod_integration",
    "discriminate",
    "external_block",
    "external_pulse",
    "for_",
    "full_integration",
    "if_",
    "measure",
    "nested_sequence",
    "phase",
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
    "sub_sequence",
    "var",
    "var_decl",
    "wait",
)


def _not_a_sequence_context(operation_name: str) -> RuntimeError:
    """Build the reciprocal-rejection error for an operation called outside a sequence.

    :param operation_name: Name of the operation for the error message, e.g. ``"play()"``

    :return: The error to raise
    """
    return RuntimeError(
        f"{operation_name} requires a build_sequence() context. Schedules are built with "
        "eq1_pulse.builder.experimental and cannot contain sequence operations."
    )


def _add_to_sequence(context: Any, operation: Any) -> None:
    """Add an operation to a sequence context.

    :param context: The sequence context to add to; anything else raises
    :param operation: The operation to add

    :raises RuntimeError: If context is not a sequence
    """
    if isinstance(context, Repetition | Iteration | Conditional):
        context.body.items.append(operation)
    elif isinstance(context, OpSequence):
        context.items.append(operation)
    else:
        raise RuntimeError(f"Cannot add sequence operation to {type(context).__name__} context")


# ============================================================================
# Context managers
# ============================================================================


@contextmanager
def build_sequence() -> Iterator[OpSequence]:
    """Context manager for building an operation sequence.

    :yield: The operation sequence being built

    :raises RuntimeError: If a build_schedule() context is already active

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence() as seq:
            play("ch1", square_pulse(duration="10us", amplitude="100mV"))
            wait("ch1", duration="5us")
    """
    state = _get_state()
    if state.context_stack and _in_schedule(state.context_stack[-1]):
        raise RuntimeError(
            "build_sequence() cannot be nested inside a build_schedule() context. "
            "Schedules are built with eq1_pulse.builder.experimental and cannot contain "
            "sequence operations."
        )
    seq = OpSequence(items=[])
    _push_context(seq)
    try:
        yield seq
    finally:
        _pop_context()


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
                record("readout", "result", duration="1us", integration=full_integration())
    """
    # Must be called within a sequence context
    context = _current_context("sub_sequence()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("sub_sequence()")

    # Create the nested sequence
    nested_seq = OpSequence(items=[])

    # Add it to the parent sequence
    _add_to_sequence(context, nested_seq)

    # Push nested sequence as current context for operations inside it
    _push_context(nested_seq)
    try:
        yield nested_seq
    finally:
        _pop_context()


@contextmanager
def repeat(count: int) -> Iterator[Repetition]:
    """Context manager for building a repetition block.

    :param count: Number of times to repeat

    :yield: The repetition being built

    :raises RuntimeError: If not called within a sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence():
            with repeat(10):
                play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
    """
    parent = _current_context("repeat()")

    if not _in_sequence(parent):
        raise _not_a_sequence_context("repeat()")

    rep = Repetition(count=count, body=OpSequence(items=[]))
    _add_to_sequence(parent, rep)
    _push_context(rep)
    try:
        yield rep
    finally:
        _pop_context()


@overload
@contextmanager
def for_(
    var: VariableRefLike,
    items: Iterable[Any] | Range | LinSpace,
) -> Iterator[Iteration]: ...


@overload
@contextmanager
def for_(
    var: list[VariableRefLike],
    items: list[Iterable[Any] | Range | LinSpace] | Iterable[Any] | Range | LinSpace,
) -> Iterator[Iteration]: ...


@contextmanager
def for_(
    var: VariableRefLike | list[VariableRefLike],
    items: Iterable[Any] | Range | LinSpace | list[Iterable[Any] | Range | LinSpace],
) -> Iterator[Iteration]:
    """Context manager for building an iteration (for loop).

    Supports both single and zipped iteration:

    - Single iteration: single variable over single iterable
    - Zipped iteration: multiple variables over corresponding iterables (like Python's zip())

    :param var: Variable reference(s) for the loop variable(s).
        Can be a single variable or list of variables for zipped iteration.
    :param items: Iterable(s) to iterate over.

        - For single iteration: Range, LinSpace, or any iterable
        - For zipped iteration: list of iterables, one per variable. A single iterable
          is broadcast across all of the variables.

    :yield: The iteration being built

    :raises RuntimeError: If not called within a sequence context
    :raises ValueError: If var/items length mismatch in zipped iteration

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        # Single iteration in sequence context
        with build_sequence():
            var_decl("i", "int", unit="MHz")
            with for_("i", range(0, 100, 10)):
                set_frequency("qubit", var("i"))

        # Zipped iteration over multiple variables
        with build_sequence():
            var_decl("freq", "float", unit="MHz")
            var_decl("amp", "float", unit="mV")
            with for_(
                ["freq", "amp"],
                [range(4000, 6000, 100), LinSpace(start=10, stop=100, num=100)]
            ):
                set_frequency("qubit", var("freq"))
                play("qubit", square_pulse(
                    duration="100ns",
                    amplitude=var("amp")
                ))
    """
    # Validate variable reference(s)
    if isinstance(var, list):
        validated_vars: list[VariableRefLike] | VariableRefLike = [_validate_variable_ref(v) for v in var]
    else:
        validated_vars = _validate_variable_ref(var)

    # Handle both single and zipped iteration items
    # For zipped iteration, items should be a list; convert single iterable to list
    validated_items: list[Iterable[Any] | Range | LinSpace] | Iterable[Any] | Range | LinSpace
    if isinstance(validated_vars, list):
        # Multiple variables - items must be a list of iterables (zipped iteration)
        if not isinstance(items, list):
            # A single iterable provided for multiple variables is broadcast, so that
            # for_(["i", "j"], range(10)) iterates the same range for both. Wrapping it
            # in a one-element list instead would fail the model's length check.
            validated_items = [_convert_range_to_model(items)] * len(validated_vars)
        else:
            if len(items) != len(validated_vars):
                names = [ref.var for ref in cast("list[VariableRef]", validated_vars)]
                raise ValueError(
                    f"Zipped iteration needs one iterable per variable: got {len(names)} "
                    f"variable(s) {names} but {len(items)} iterable(s)."
                )
            # Convert any range objects in the list
            validated_items = [_convert_range_to_model(item) for item in items]
    else:
        # Single variable - items can be single iterable
        validated_items = _convert_range_to_model(items)

    parent = _current_context("for_()")

    if not _in_sequence(parent):
        raise _not_a_sequence_context("for_()")

    iter_obj = Iteration(var=validated_vars, items=validated_items, body=OpSequence(items=[]))
    _add_to_sequence(parent, iter_obj)
    _push_context(iter_obj)
    try:
        yield iter_obj
    finally:
        _pop_context()


@contextmanager
def if_(var: VariableRefLike) -> Iterator[Conditional]:
    """Context manager for building a conditional block.

    :param var: Variable reference for the condition

    :yield: The conditional being built

    :raises RuntimeError: If not called within a sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence():
            var_decl("result", "bool")
            # ... perform measurement to populate result ...
            with if_("result"):
                play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
    """
    # Validate variable reference
    validated_var = _validate_variable_ref(var)

    parent = _current_context("if_()")

    if not _in_sequence(parent):
        raise _not_a_sequence_context("if_()")

    cond = Conditional(var=validated_var, body=OpSequence(items=[]))
    _add_to_sequence(parent, cond)
    _push_context(cond)
    try:
        yield cond
    finally:
        _pop_context()


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

    # Register the variable as declared in the current context
    _register_variable(name)

    context = _current_context("var_decl()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("var_decl()")
    _add_to_sequence(context, var_decl_obj)


def pulse_decl(
    name: str,
    pulse: PulseType,
) -> None:
    """Declare a pulse for use in the current context.

    Pulses can be declared and given a name, then referenced later using
    :func:`pulse_ref`. This allows reusing the same pulse definition multiple
    times without repeating the full definition.

    :param name: Name of the pulse (must be a valid identifier)
    :param pulse: The pulse definition (e.g., from :func:`square_pulse`, :func:`sine_pulse`)

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence():
            # Declare a pulse with a name
            pulse_decl("my_square", square_pulse(duration="100ns", amplitude="200mV"))

            # Use the pulse reference later
            play("qubit", pulse_ref("my_square"))
            play("qubit", pulse_ref("my_square"))  # Reuse the same pulse
    """
    pulse_decl_obj = PulseDecl(name=name, pulse=pulse)

    context = _current_context("pulse_decl()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("pulse_decl()")
    _add_to_sequence(context, pulse_decl_obj)


# ============================================================================
# Decorators for automatic sub-context wrapping
# ============================================================================


def nested_sequence[R, **P](func: Callable[P, R]) -> Callable[P, R]:
    """Decorator that automatically wraps a function body in a sub-sequence.

    This decorator creates a :func:`sub_sequence` context around the function body,
    allowing you to define reusable operation blocks that can be composed together
    in sequence contexts.

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
            record(readout_ch, result_var, duration="1us", integration=full_integration())

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
        state = _get_state()
        if state.context_stack:
            context = _current_context(f"@nested_sequence function {func.__name__}()")

            # In sequence context (OpSequence or control flow)
            if _in_sequence(context):
                # Use sub_sequence context
                with sub_sequence() as _:
                    return func(*args, **kwargs)  # type: ignore[return-value]
            # Not a sequence context - not supported, raise error
            else:
                raise RuntimeError(
                    "@nested_sequence decorator cannot be used in schedule context. "
                    "eq1_pulse.builder.experimental has its own @nested_schedule decorator "
                    "for functions that need schedule timing parameters."
                )

        # If not in a context, just call the function directly
        return func(*args, **kwargs)

    return wrapper


# ============================================================================
# Channel operations
# ============================================================================


def play(
    channel: ChannelRefLike,
    pulse: PulseType | PulseRefLike,
    *,
    scale_amp: float | complex | VariableRefLike | None = None,
    cond: VariableRefLike | None = None,
) -> None:
    """Play a pulse on a channel.

    :param channel: Channel to play on
    :param pulse: Pulse to play
    :param scale_amp: Optional amplitude scaling
    :param cond: Optional condition variable

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        play("ch1", square_pulse(duration="10us", amplitude="100mV"))
    """
    # scale_amp can be numeric or variable - only validate if it's a potential VariableRef type
    if scale_amp is not None and isinstance(scale_amp, str | dict | VariableRef):
        scale_amp = _validate_or_pass_through(scale_amp, param_name="scale_amp", context="play()")

    # cond is variable-only - use strict validation
    if cond is not None:
        cond = _validate_variable_ref(cond)

    op = Play(channel=channel, pulse=pulse, scale_amp=scale_amp, cond=cond)

    context = _current_context("play()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("play()")
    _add_to_sequence(context, op)


def wait(
    *channels: ChannelRefLike,
    duration: DurationLike | VariableRefLike,
) -> None:
    """Add wait operation on channel(s).

    Wait can be applied to multiple channels simultaneously, appending the
    wait time to each channel independently.

    :param channels: Channel(s) to wait on
    :param duration: Wait duration

    Examples

    .. code-block:: python

        from eq1_pulse.builder import wait

        # Single channel
        wait("ch1", duration="5us")

        # Multiple channels
        with build_sequence():
            wait("ch1", "ch2", duration="10us")
    """
    context = _current_context("wait()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("wait()")

    duration = _validate_or_pass_through(duration, param_name="duration", context="wait()")

    op = Wait(*channels, duration=duration)  # type: ignore[arg-type]

    _add_to_sequence(context, op)


def barrier(
    *channels: ChannelRefLike,
) -> None:
    """Add barrier (synchronization) on channel(s).

    The barrier operation synchronizes multiple channels, causing them to wait
    until all specified channels have reached the barrier point.

    :param channels: Channels to synchronize

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

    context = _current_context("barrier()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("barrier()")
    _add_to_sequence(context, op)


def set_frequency(
    channel: ChannelRefLike,
    frequency: FrequencyLike | VariableRefLike,
) -> None:
    """Set channel frequency.

    :param channel: Channel to set frequency on
    :param frequency: Frequency to set

    Examples

    .. code-block:: python

        from eq1_pulse.builder import set_frequency

        set_frequency("qubit", "5GHz")
    """
    frequency = _validate_or_pass_through(frequency, param_name="frequency", context="set_frequency()")

    op = SetFrequency(channel=channel, frequency=frequency)

    context = _current_context("set_frequency()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("set_frequency()")
    _add_to_sequence(context, op)


def shift_frequency(
    channel: ChannelRefLike,
    frequency: FrequencyLike | VariableRefLike,
) -> None:
    """Shift channel frequency.

    :param channel: Channel to shift frequency on
    :param frequency: Frequency shift amount

    Examples

    .. code-block:: python

        from eq1_pulse.builder import shift_frequency

        shift_frequency("qubit", "100MHz")
    """
    frequency = _validate_or_pass_through(frequency, param_name="frequency", context="shift_frequency()")

    op = ShiftFrequency(channel=channel, frequency=frequency)

    context = _current_context("shift_frequency()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("shift_frequency()")
    _add_to_sequence(context, op)


def set_phase(
    channel: ChannelRefLike,
    phase: PhaseLike | VariableRefLike,
) -> None:
    """Set channel phase.

    :param channel: Channel to set phase on
    :param phase: Phase to set

    Examples

    .. code-block:: python

        from eq1_pulse.builder import set_phase

        set_phase("qubit", "90deg")
    """
    phase = _validate_or_pass_through(phase, param_name="phase", context="set_phase()")

    op = SetPhase(channel=channel, phase=phase)

    context = _current_context("set_phase()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("set_phase()")
    _add_to_sequence(context, op)


def shift_phase(
    channel: ChannelRefLike,
    phase: PhaseLike | VariableRefLike,
) -> None:
    """Shift channel phase.

    :param channel: Channel to shift phase on
    :param phase: Phase shift amount

    Examples

    .. code-block:: python

        from eq1_pulse.builder import shift_phase

        shift_phase("qubit", "45deg")
    """
    phase = _validate_or_pass_through(phase, param_name="phase", context="shift_phase()")

    op = ShiftPhase(channel=channel, phase=phase)

    context = _current_context("shift_phase()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("shift_phase()")
    _add_to_sequence(context, op)


def record(
    channel: ChannelRefLike,
    var: VariableRefLike,
    *,
    duration: DurationLike,
    integration: FullIntegration | DemodIntegration,
) -> None:
    """Record (acquire) data from a channel.

    :param channel: Channel to record from
    :param var: Variable to store the result
    :param duration: Recording duration
    :param integration: Integration configuration (use :func:`full_integration` or :func:`demod_integration`)

    Examples

    .. code-block:: python

        from eq1_pulse.builder import (
            build_sequence, record, var_decl,
            full_integration, demod_integration
        )

        var_decl("result", "complex", unit="mV")
        with build_sequence() as seq:
            # Full integration
            record("readout", "result", duration="1us",
                   integration=full_integration())

            # Demodulation with phase rotation
            record("readout", "result", duration="1us",
                   integration=demod_integration(phase="45deg"))
    """
    # Validate variable reference
    validated_var = _validate_variable_ref(var)

    op = Record(channel=channel, var=validated_var, duration=duration, integration=integration)  # type: ignore[arg-type]

    context = _current_context("record()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("record()")
    _add_to_sequence(context, op)


def discriminate(
    target: VariableRefLike,
    source: VariableRefLike,
    threshold: ThresholdLike,
    *,
    rotation: PhaseLike = 0,
    compare: ComparisonModeLike = ">=",
    project: ComplexToRealProjectionModeLike = "real",
) -> None:
    """Discriminate a measurement result to a binary outcome.

    This operation applies a rotation, projects complex data to real, and compares
    against a threshold to produce a boolean result.

    :param target: Variable to store the discrimination result (boolean)
    :param source: Source variable containing the measurement data
    :param threshold: Threshold value for comparison
    :param rotation: Phase rotation to apply before projection (default: 0)
    :param compare: Comparison operator (default: ">=")
    :param project: Complex-to-real projection mode (default: "real")

    Examples

    .. code-block:: python

        from eq1_pulse.builder import discriminate

        # Simple discrimination with default parameters
        discriminate("bit", "measurement", threshold=0.5)

        # With rotation and different comparison
        discriminate("bit", "measurement", threshold=0.5,
                         rotation="45deg", compare=">", project="abs")
    """
    # Validate variable references
    validated_target = _validate_variable_ref(target)
    validated_source = _validate_variable_ref(source)

    op = Discriminate(
        target=validated_target,
        source=validated_source,
        threshold=threshold,
        rotation=rotation,  # type: ignore[arg-type]
        compare=compare,  # type: ignore[arg-type]
        project=project,  # type: ignore[arg-type]
    )

    context = _current_context("discriminate()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("discriminate()")
    _add_to_sequence(context, op)


def store(
    key: str,
    source: VariableRefLike,
    *,
    mode: StoreMode | StoreModeLiteral = "last",
) -> None:
    """Store a variable value for later retrieval.

    This operation stores the value of a variable to persistent storage
    for analysis after the pulse program completes. Different storage modes
    allow for averaging, counting, or trace capture.

    :param key: Storage key for retrieving the data
    :param source: Source variable to store
    :param mode: Storage mode - how to aggregate multiple values

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

            with repeat(100):
                measure("drive", result_var="m", duration="1us", amplitude="50mV",
                        integration=full_integration())
                store("avg_result", "m", mode="average")
    """
    # Validate variable reference
    validated_source = _validate_variable_ref(source)

    op = Store(key=key, source=validated_source, mode=mode)  # type: ignore[arg-type]

    context = _current_context("store()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("store()")
    _add_to_sequence(context, op)


def measure(
    channel: ChannelRefLike | tuple[ChannelRefLike, ChannelRefLike],
    *,
    result_var: VariableRefLike,
    duration: DurationLike,
    amplitude: AmplitudeLike,
    integration: FullIntegration | DemodIntegration,
) -> None:
    """Perform a measurement (simultaneous play + record).

    This is a convenience function that creates a square pulse play operation
    and a record operation that execute simultaneously.

    :param channel: Channel for measurement. Can be a single channel (used for both
        drive and readout) or a tuple of (drive_channel, readout_channel)
    :param result_var: Variable to store the measurement result
    :param duration: Measurement duration
    :param amplitude: Measurement pulse amplitude
    :param integration: Integration configuration (use :func:`full_integration` or :func:`demod_integration`)

    Examples

    .. code-block:: python

        from eq1_pulse.builder import (
            build_sequence, measure, var_decl,
            full_integration, demod_integration
        )

        var_decl("result", "complex", unit="mV")
        with build_sequence() as seq:
            # Single channel with full integration
            measure("qubit", result_var="result",
                    duration="1us", amplitude="50mV",
                    integration=full_integration())

            # Separate drive and readout channels with demodulation
            measure(("drive", "readout"), result_var="result",
                    duration="1us", amplitude="50mV",
                    integration=demod_integration(phase="0deg"))
    """
    # Fail fast if there is no active (sequence) context, matching the other operations.
    context = _current_context("measure()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("measure()")

    # Parse channel parameter
    if isinstance(channel, tuple):
        drive_channel, readout_channel = channel
    else:
        drive_channel = readout_channel = channel

    # Create measurement pulse
    meas_pulse = square_pulse(duration=duration, amplitude=amplitude)

    # Add operations sequentially.
    # Note: In a true measurement, play and record should be simultaneous.
    # This requires the backend to handle the timing correctly.
    play(drive_channel, meas_pulse)
    record(
        readout_channel,
        result_var,
        duration=duration,
        integration=integration,
    )


def external_block(
    *positional_channels: ChannelRefLike,
    program: str | None = None,
    channels: dict[str, ChannelRefLike] | None = None,
    params: dict[str, Any] | None = None,
    results: dict[str, VariableRefLike] | None = None,
    duration: DurationLike | VariableRefLike | None = None,
) -> None:
    """Reserve channels for an opaque, externally defined block of operations.

    Two forms are supported for specifying the reserved channels:

    - ``channels={"role": channel, ...}`` when the referenced program distinguishes between the
      channels it uses (e.g. drive vs. readout).
    - Positional channels when roles do not matter. Placeholder role keys are generated
      deterministically as ``"0"``, ``"1"``, ... in argument order.

    :param positional_channels: Channels to reserve when roles do not matter. Mutually exclusive
        with ``channels``
    :param program: Fully qualified reference to the externally defined program supplying the
        block's contents. :obj:`None` is a pure reservation (see :class:`~eq1_pulse.models.ExternalBlock`)
    :param channels: Channels to reserve, keyed by the role each plays in ``program``. Mutually
        exclusive with ``positional_channels``
    :param params: Input arguments passed to ``program``
    :param results: Output bindings: variables ``program`` writes into. Each variable must already
        be declared in an enclosing scope
    :param duration: Total duration. :obj:`None` means *flex*: the duration is whatever ``program``
        naturally takes

    :raises ValueError: If both positional channels and ``channels=`` are given, or if neither is

    Examples

    .. code-block:: python

        from eq1_pulse.builder import build_sequence, external_block, var, var_decl

        with build_sequence():
            var_decl("iq", "complex", unit="mV")

            # Named channel roles, input params, output binding
            external_block(
                program="eq1.cal.measure",
                channels={"drive": "q0", "readout": "q0_ro"},
                params={"amp": "50mV"},
                results={"iq": var("iq")},
            )

            # Positional form when roles do not matter
            external_block("q0", "q1", program="eq1.cal.cz")

            # Pure reservation, no referenced program
            external_block("q1", duration="1us")
    """
    if positional_channels and channels is not None:
        raise ValueError(
            "external_block() cannot accept both positional channels and a channels= mapping. "
            "Use one form or the other."
        )
    if positional_channels:
        resolved_channels: dict[str, ChannelRefLike] = {str(index): ch for index, ch in enumerate(positional_channels)}
    elif channels is not None:
        resolved_channels = channels
    else:
        raise ValueError("external_block() requires at least one channel, either positional or via channels=.")

    # A VariableRef in params is a read, validated the same way external_pulse() validates its params.
    if params is not None:
        params = {
            key: _validate_explicit_variable_ref(value, param_name=f"params['{key}']") for key, value in params.items()
        }

    # results are writes: the target variable must already be declared, exactly as record() enforces for its var.
    if results is not None:
        results = {key: _validate_variable_ref(value) for key, value in results.items()}

    duration = _validate_or_pass_through(duration, param_name="duration", context="external_block()")

    op = ExternalBlock(
        program=program,
        channels=resolved_channels,  # type: ignore[arg-type]
        params=params,  # type: ignore[arg-type]
        results=results,  # type: ignore[arg-type]
        duration=duration,  # type: ignore[arg-type]
    )

    context = _current_context("external_block()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("external_block()")
    _add_to_sequence(context, op)
