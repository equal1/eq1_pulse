"""Schedule-side builder functions for constructing explicitly-timed pulse programs.

This module provides the schedule half of the builder DSL:

- Context managers for schedules, sub-schedules, iterations, and conditionals
- Function calls for operations like playing pulses, recording, and setting frequency
- Token-based references for relative positioning within a schedule
- Decorators for modular composition of schedule blocks
- Measure function for simultaneous play + record operations

Every operation here requires an active :func:`build_schedule` context; sequences are
built with :mod:`eq1_pulse.builder` instead.

Examples

.. code-block:: python

    from eq1_pulse.builder.experimental import *

    with build_schedule() as sched:
        op1 = play("ch1", square_pulse(duration="10us", amplitude="100mV"))
        op2 = play("ch2", square_pulse(duration="10us", amplitude="100mV"),
                        ref_op=op1, ref_pt="start", rel_time="5us")
"""

from __future__ import annotations

import traceback
import warnings
from collections.abc import Callable
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal, Unpack, cast

from ...models.basic_types import LinSpace, Range
from ...models.channel_ops import (
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
from ...models.data_ops import Discriminate, PulseDecl, Store, StoreMode, StoreModeLiteral, VariableDecl
from ...models.experimental.schedule import (
    SchedConditional,
    SchedIteration,
    SchedRepetition,
    Schedule,
    ScheduledOperation,
)
from ...models.pulse_types import PulseType
from ...models.reference_types import PulseRef, VariableRef
from .._coerce import as_channel_ref, as_duration, as_frequency, as_phase, as_pulse_ref, as_threshold
from .._factories import _coerce_or_ref as _coerce_or_ref
from .._factories import (
    _convert_range_to_model,
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
from .._factories import _validate_or_pass_through as _validate_or_pass_through
from .._state import (
    _current_context,
    _generate_op_name,
    _in_schedule,
    _in_sequence,
    _pop_context,
    _push_context,
    _register_variable,
)
from .._state import _get_state as _get_state
from .utils import OperationToken, ScheduleParams, resolve_schedule_params

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from ...models.basic_types import AmplitudeLike, DurationLike, FrequencyLike, PhaseLike, ThresholdLike
    from ...models.data_ops import ComparisonModeLike, ComplexToRealProjectionModeLike
    from ...models.reference_types import ChannelRefLike, PulseRefLike, SymbolRefLike, VariableRefLike
    from .._expressions import ExprLike

__all__ = (
    "ScheduleBlock",
    "add_block",
    "arbitrary_pulse",
    "barrier",
    "build_schedule",
    "channel",
    "demod_integration",
    "discriminate",
    "external_pulse",
    "for_",
    "full_integration",
    "if_",
    "measure",
    "nested_schedule",
    "phase",
    "play",
    "pulse_decl",
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
    "var",
    "var_decl",
    "wait",
)


def _not_a_schedule_context(operation_name: str) -> RuntimeError:
    """Build the reciprocal-rejection error for an operation called outside a schedule.

    :param operation_name: Name of the operation for the error message, e.g. ``"play()"``

    :return: The error to raise
    """
    return RuntimeError(
        f"{operation_name} from eq1_pulse.builder.experimental requires a build_schedule() context. "
        "Sequences use eq1_pulse.builder."
    )


def _add_to_schedule(
    context: Schedule | SchedRepetition | SchedIteration | SchedConditional,
    operation: Any,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Add an operation to a schedule context.

    :param context: The schedule context to add to
    :param operation: The operation to add
    :param schedule_params: Additional scheduling parameters

    :return: Token for referencing this operation

    :raises RuntimeError: If context is not a schedule
    """
    # Resolve any operation tokens to names
    resolved_params = resolve_schedule_params(schedule_params)  # type: ignore[arg-type]

    # Generate operation name if not provided
    if "op_name" not in resolved_params:
        resolved_params["op_name"] = _generate_op_name()

    # ScheduledOperation expects 'name', not 'op_name'
    sched_params = {**resolved_params}
    sched_params["name"] = sched_params.pop("op_name")

    sched_op = ScheduledOperation(op=operation, **sched_params)  # type: ignore[arg-type]

    # Add to the appropriate schedule-like context
    if isinstance(context, SchedRepetition | SchedIteration | SchedConditional):
        context.body.items.append(sched_op)
    elif isinstance(context, Schedule):
        context.items.append(sched_op)
    else:
        raise RuntimeError(f"Cannot add scheduled operation to {type(context).__name__} context")

    return OperationToken(resolved_params["op_name"], sched_op)


# ============================================================================
# Context managers
# ============================================================================


def _reject_unconsumed_blocks(unconsumed: list[ScheduleBlock], context_kind: str) -> None:
    """Raise if any schedule blocks created in a context were never added to it.

    :param unconsumed: Blocks still outstanding when the context closed
    :param context_kind: Human-readable name of the context, for the error message

    :raises RuntimeError: If ``unconsumed`` is non-empty
    """
    if not unconsumed:
        return

    error_parts = [
        f"{context_kind} context closed with {len(unconsumed)} unconsumed ScheduleBlock(s). "
        "All @nested_schedule decorated function calls must be passed to add_block() "
        "with schedule parameters.\n"
    ]
    for i, block in enumerate(unconsumed, 1):
        error_parts.append(f"\nUnconsumed block #{i} created at:")
        error_parts.append(block._get_creation_info())

    raise RuntimeError("".join(error_parts))


@contextmanager
def _sub_schedule_with_token(
    **schedule_params: Unpack[ScheduleParams],
) -> Iterator[tuple[Schedule, OperationToken]]:
    """Open a nested sub-schedule, exposing both the schedule and its reference token.

    This is the shared implementation behind :func:`sub_schedule` and :func:`add_block`.

    :param schedule_params: Schedule timing parameters

    :yield: The nested schedule and the token referencing it in the parent

    :raises RuntimeError: If not called within a schedule context
    """
    context = _current_context("sub_schedule()")
    if not _in_schedule(context):
        raise RuntimeError("sub_schedule can only be used within a build_schedule() context")

    nested_sched = Schedule([])

    # Add it to the parent schedule with timing parameters
    token = _add_to_schedule(context, nested_sched, **schedule_params)

    # Push nested schedule as current context for operations inside it
    _push_context(nested_sched)
    try:
        yield nested_sched, token
    except BaseException:
        _pop_context()
        raise
    else:
        unconsumed = _get_state().unconsumed_blocks[-1]
        _pop_context()
        _reject_unconsumed_blocks(unconsumed, "sub_schedule")


@contextmanager
def build_schedule() -> Iterator[Schedule]:
    """Context manager for building a schedule.

    :yield: The schedule being built

    :raises RuntimeError: If a build_sequence() context is already active

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import *

        with build_schedule() as sched:
            op1 = play("ch1", square_pulse(duration="10us", amplitude="100mV"))
            op2 = play("ch2", square_pulse(duration="10us", amplitude="100mV"),
                            ref_op=op1, ref_pt="start", rel_time="5us")
    """
    state = _get_state()
    if state.context_stack and _in_sequence(state.context_stack[-1]):
        raise RuntimeError(
            "build_schedule() cannot be nested inside a build_sequence() context. "
            "Sequences use eq1_pulse.builder and cannot contain schedule operations."
        )
    warnings.warn(
        "build_schedule() and the Schedule representation are unused and will be removed. "
        "Use eq1_pulse.builder.build_sequence().",
        FutureWarning,
        stacklevel=3,
    )
    sched = Schedule([])
    _push_context(sched)
    try:
        yield sched
    except BaseException:
        _pop_context()
        raise
    else:
        unconsumed = _get_state().unconsumed_blocks[-1]
        _pop_context()
        _reject_unconsumed_blocks(unconsumed, "Schedule")


@contextmanager
def sub_schedule(**schedule_params: Unpack[ScheduleParams]) -> Iterator[OperationToken]:
    """Context manager for building a nested sub-schedule with timing parameters.

    This creates a sub-schedule that can be positioned relative to other operations
    in the parent schedule. Works in any schedule context, including the bodies of
    schedule-side ``repeat``, ``for_`` and ``if_`` blocks.

    :param schedule_params: Schedule timing parameters
        (``op_name``, ``ref_op``, ``ref_pt``, ``ref_pt_new``, ``rel_time``)

    :yield: Token referencing the sub-schedule, for use as ``ref_op`` of later operations

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import *

        with build_schedule() as main:
            # Create initialization sub-schedule
            with sub_schedule(op_name="init") as init:
                play("qubit", square_pulse(duration="100ns", amplitude="200mV"))
                wait("qubit", duration="50ns")

            # Create gate operation positioned after init, referring to it by token
            gate_op = play("qubit", square_pulse(duration="20ns", amplitude="150mV"),
                           ref_op=init, ref_pt="end", rel_time="10ns")

            # Create measurement block positioned after gate
            with sub_schedule(op_name="measure", ref_op=gate_op, ref_pt="end", rel_time="50ns"):
                play("drive", square_pulse(duration="1us", amplitude="50mV"))
                record("readout", var="result", duration="1us",
                       integration=full_integration())
    """
    with _sub_schedule_with_token(**schedule_params) as (_, token):
        yield token


@contextmanager
def repeat(count: int, **schedule_params: Unpack[ScheduleParams]) -> Iterator[SchedRepetition]:
    """Context manager for building a schedule repetition block.

    :param count: Number of times to repeat
    :param schedule_params:
        Additional scheduling parameters (``op_name``, ``ref_op``, ``ref_pt``, etc.)

    :yield: The repetition being built

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import *

        with build_schedule():
            op1 = play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
            with repeat(10, ref_op=op1, ref_pt="end"):
                play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
    """
    parent = _current_context("repeat()")
    if not _in_schedule(parent):
        raise _not_a_schedule_context("repeat()")

    sched_rep = SchedRepetition(count=count, body=Schedule([]))
    _add_to_schedule(parent, sched_rep, **schedule_params)
    _push_context(sched_rep)
    try:
        yield sched_rep
    except BaseException:
        _pop_context()
        raise
    else:
        unconsumed = _get_state().unconsumed_blocks[-1]
        _pop_context()
        _reject_unconsumed_blocks(unconsumed, "repeat")


@contextmanager
def for_(
    var: str | VariableRefLike | list[str | VariableRefLike],
    items: Iterable[Any] | Range | LinSpace | list[Iterable[Any] | Range | LinSpace],
    **schedule_params: Unpack[ScheduleParams],
) -> Iterator[SchedIteration]:
    """Context manager for building a schedule iteration (for loop).

    Supports both single and zipped iteration:

    - Single iteration: single variable over single iterable
    - Zipped iteration: multiple variables over corresponding iterables (like Python's zip())

    :param var: Variable reference(s) for the loop variable(s).
        Can be a single variable or list of variables for zipped iteration.
    :param items: Iterable(s) to iterate over.

        - For single iteration: Range, LinSpace, or any iterable
        - For zipped iteration: list of iterables, one per variable. A single iterable
          is broadcast across all of the variables.

    :param schedule_params:
        Additional scheduling parameters (``op_name``, ``ref_op``, ``ref_pt``, etc.)

    :yield: The iteration being built

    :raises RuntimeError: If not called within a schedule context
    :raises ValueError: If var/items length mismatch in zipped iteration

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import *

        with build_schedule():
            op1 = play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
            with for_("i", range(0, 5), ref_op=op1, ref_pt="end"):
                play("qubit", square_pulse(duration="20ns", amplitude="100mV"))
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
    if not _in_schedule(parent):
        raise _not_a_schedule_context("for_()")

    sched_iter = SchedIteration(var=validated_vars, items=validated_items, body=Schedule([]))
    _add_to_schedule(parent, sched_iter, **schedule_params)
    _push_context(sched_iter)
    try:
        yield sched_iter
    except BaseException:
        _pop_context()
        raise
    else:
        unconsumed = _get_state().unconsumed_blocks[-1]
        _pop_context()
        _reject_unconsumed_blocks(unconsumed, "for_")


@contextmanager
def if_(var: str | VariableRefLike, **schedule_params: Unpack[ScheduleParams]) -> Iterator[SchedConditional]:
    """Context manager for building a schedule conditional block.

    :param var: Variable reference for the condition
    :param schedule_params:
        Additional scheduling parameters (``op_name``, ``ref_op``, ``ref_pt``, etc.)

    :yield: The conditional being built

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import *

        with build_schedule():
            op1 = play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
            with if_("result", ref_op=op1, ref_pt="end"):
                play("qubit", square_pulse(duration="20ns", amplitude="100mV"))
    """
    # Validate variable reference
    validated_var = _validate_variable_ref(var)

    parent = _current_context("if_()")
    if not _in_schedule(parent):
        raise _not_a_schedule_context("if_()")

    sched_cond = SchedConditional(var=validated_var, body=Schedule([]))
    _add_to_schedule(parent, sched_cond, **schedule_params)
    _push_context(sched_cond)
    try:
        yield sched_cond
    except BaseException:
        _pop_context()
        raise
    else:
        unconsumed = _get_state().unconsumed_blocks[-1]
        _pop_context()
        _reject_unconsumed_blocks(unconsumed, "if_")


# ============================================================================
# Variable declaration
# ============================================================================


def var_decl(
    name: str,
    dtype: Literal["bool", "int", "float", "complex"],
    *,
    shape: tuple[int, ...] | None = None,
    unit: str | None = None,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Declare a variable for use in the current schedule context.

    Variables should be declared before they are used in iterations or conditionals.
    The declaration specifies the variable's data type, optional shape (for arrays),
    and optional unit for dimensional consistency.

    :param name: Name of the variable (must be a valid identifier)
    :param dtype: Data type of the variable ("bool", "int", "float", or "complex")
    :param shape: Optional shape for array variables (e.g., (10,) for 1D array)
    :param unit: Optional unit string (e.g., "mV", "ns", "GHz") for the variable
    :param op_name: Optional name for the operation
    :param rel_time: Relative time from the reference point
    :param ref_op: Name of or token for the reference operation
    :param ref_pt: Reference point on the reference operation
    :param ref_pt_new: Reference point on the new operation

    :return: Operation token

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import *

        with build_schedule():
            var_decl("result", "complex", unit="mV")
            # ... use the variable in scheduled operations
    """
    var_decl_obj = VariableDecl(name=name, dtype=dtype, shape=shape, unit=unit)

    # Register the variable as declared in the current context
    _register_variable(name)

    context = _current_context("var_decl()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("var_decl()")
    return _add_to_schedule(context, var_decl_obj, **schedule_params)


def pulse_decl(
    name: str,
    pulse: PulseType,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Declare a pulse for use in the current schedule context.

    Pulses can be declared and given a name, then referenced later using
    :func:`pulse_ref`. This allows reusing the same pulse definition multiple
    times without repeating the full definition.

    :param name: Name of the pulse (must be a valid identifier)
    :param pulse: The pulse definition (e.g., from :func:`square_pulse`, :func:`sine_pulse`)
    :param op_name: Optional name for the operation
    :param rel_time: Relative time from the reference point
    :param ref_op: Name of or token for the reference operation
    :param ref_pt: Reference point on the reference operation
    :param ref_pt_new: Reference point on the new operation

    :return: Operation token

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import *

        with build_schedule():
            pulse_decl("readout_pulse", square_pulse(duration="1us", amplitude="50mV"))
            play("readout", pulse_ref("readout_pulse"))
    """
    pulse_decl_obj = PulseDecl(name=name, pulse=pulse)

    context = _current_context("pulse_decl()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("pulse_decl()")
    return _add_to_schedule(context, pulse_decl_obj, **schedule_params)


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

        # Register this block against the innermost context, so that closing that
        # context can report it if it was never passed to add_block()
        _current_context("@nested_schedule function call")
        _get_state().unconsumed_blocks[-1].append(self)

    def _execute(self) -> None:
        """Execute the block's function and mark as consumed."""
        # Mark as consumed. The block was registered against whichever context was
        # innermost when it was created, which is the caller's frame rather than the
        # sub-schedule add_block() has since opened, so search outwards.
        state = _get_state()
        for blocks in reversed(state.unconsumed_blocks):
            if self in blocks:
                blocks.remove(self)
                break

        # Execute the function
        self._func(*self._args, **self._kwargs)

    def _get_creation_info(self) -> str:
        """Get formatted information about where this block was created."""
        # Format the traceback to show where the block was created
        return "".join(self._creation_traceback)


def add_block(block: ScheduleBlock, **schedule_params: Unpack[ScheduleParams]) -> OperationToken:
    """Add a schedule block to the current schedule with timing parameters.

    This function must be used with @nested_schedule decorated functions to
    add them to a schedule with positioning parameters.

    :param block: The ScheduleBlock returned by calling a @nested_schedule decorated function
    :param schedule_params: Schedule timing parameters
        (``op_name``, ``ref_op``, ``ref_pt``, ``ref_pt_new``, ``rel_time``)

    :return: Operation token for referencing this block

    :raises TypeError: If ``block`` is not a :class:`ScheduleBlock`
    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import *

        @nested_schedule
        def init_block(qubit: str):
            play(qubit, square_pulse(duration="100ns", amplitude="200mV"))

        with build_schedule():
            # Call the function to create a block, then add it with timing
            token = add_block(init_block("qubit0"), op_name="init")
            add_block(init_block("qubit1"), ref_op=token, ref_pt="end", rel_time="50ns")
    """
    if not isinstance(block, ScheduleBlock):
        raise TypeError("add_block() requires a ScheduleBlock from @nested_schedule decorated function")

    context = _current_context("add_block()")
    if not _in_schedule(context):
        raise RuntimeError("add_block() can only be used within a build_schedule() context")

    # Execute the block within a sub-schedule carrying the timing parameters
    with _sub_schedule_with_token(**schedule_params) as (_, token):
        block._execute()

    return token


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

        from eq1_pulse.builder.experimental import *

        @nested_schedule
        def initialization(qubit: str):
            '''Initialize qubit.'''
            play(qubit, square_pulse(duration="100ns", amplitude="200mV"))
            wait(qubit, duration="50ns")

        @nested_schedule
        def measurement_block(drive_ch: str, readout_ch: str, result_var: str):
            '''Perform readout measurement.'''
            play(drive_ch, square_pulse(duration="1us", amplitude="50mV"))
            record(readout_ch, result_var, duration="1us", integration=full_integration())

        # Use in schedule context - pass block to add_block with schedule parameters
        with build_schedule():
            var_decl("result", "complex", unit="mV")

            # Create block and add with timing parameters
            init_token = add_block(initialization("qubit0"), op_name="init")

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
    pulse: PulseType | str | PulseRefLike,
    *,
    scale_amp: float | complex | str | SymbolRefLike | ExprLike | None = None,
    cond: str | VariableRefLike | None = None,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Play a pulse on a channel.

    :param channel: Channel to play on
    :param pulse: Pulse to play
    :param scale_amp: Optional amplitude scaling
    :param cond: Optional condition variable
    :param schedule_params: Additional scheduling parameters

    :return: Operation token

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import *

        op = play("ch1", square_pulse(duration="10us", amplitude="100mV"),
                      ref_op=previous_op, ref_pt="end")
    """
    # scale_amp can be numeric or variable - only validate if it's a potential VariableRef type
    if scale_amp is not None and isinstance(scale_amp, str | dict | VariableRef):
        scale_amp = _validate_or_pass_through(scale_amp, param_name="scale_amp", context="play()")

    # cond is variable-only - use strict validation
    if cond is not None:
        cond = _validate_variable_ref(cond)

    channel = as_channel_ref(channel)
    if isinstance(pulse, PulseRef | str) or (isinstance(pulse, dict) and "pulse_name" in pulse):
        pulse = as_pulse_ref(pulse)

    op = Play(channel=channel, pulse=pulse, scale_amp=scale_amp, cond=cond)

    context = _current_context("play()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("play()")
    return _add_to_schedule(context, op, **schedule_params)


def wait(
    *channels: ChannelRefLike,
    duration: DurationLike | SymbolRefLike,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Add wait operation on a channel.

    Wait can only be applied to a single channel due to complex semantics
    (multi-channel wait would be equivalent to a sub-schedule where all channels
    idle, which contradicts the sequence definition). Use :mod:`eq1_pulse.builder`
    for multi-channel waits.

    :param channels: Channel to wait on. Must be exactly one.
    :param duration: Wait duration
    :param schedule_params: Additional scheduling parameters

    :return: Operation token

    :raises RuntimeError: If not called within a schedule context
    :raises RuntimeError: If multiple channels are specified

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import wait

        wait("ch1", duration="5us")
    """
    context = _current_context("wait()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("wait()")

    if len(channels) > 1:
        raise RuntimeError(
            f"Wait with multiple channels ({len(channels)} channels) is not allowed "
            "in schedule context. Multi-channel wait has complex semantics in schedules "
            "(equivalent to a subschedule with all channels idling), which contradicts "
            "the sequence definition. Use single-channel wait in schedules."
        )

    duration = _coerce_or_ref(duration, coerce=as_duration, param_name="duration", context="wait()")  # type: ignore[assignment]

    op = Wait(*(as_channel_ref(ch) for ch in channels), duration=duration)  # type: ignore[arg-type]

    return _add_to_schedule(context, op, **schedule_params)


def barrier(
    *channels: ChannelRefLike,
) -> None:
    """Reject a barrier operation: barriers are not supported in schedule contexts.

    The barrier operation only makes sense where relative timing between channels
    may vary. Schedules use explicit timing, making barriers unnecessary; use
    :mod:`eq1_pulse.builder` for barriers.

    :param channels: Channels that were to be synchronized

    :raises RuntimeError: Always — barriers are not supported in schedule contexts
    """
    context = _current_context("barrier()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("barrier()")

    raise RuntimeError(
        f"barrier() on {len(channels)} channel(s) is not supported in schedule contexts. "
        "Schedules use explicit timing, making barriers unnecessary. "
        "Use eq1_pulse.builder (sequences) instead."
    )


def set_frequency(
    channel: ChannelRefLike,
    frequency: FrequencyLike | SymbolRefLike,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Set channel frequency.

    :param channel: Channel to set frequency on
    :param frequency: Frequency to set
    :param schedule_params: Additional scheduling parameters

    :return: Operation token

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import set_frequency

        set_frequency("qubit", "5GHz")
    """
    channel = as_channel_ref(channel)
    frequency = _coerce_or_ref(frequency, coerce=as_frequency, param_name="frequency", context="set_frequency()")  # type: ignore[assignment]

    op = SetFrequency(channel=channel, frequency=frequency)

    context = _current_context("set_frequency()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("set_frequency()")
    return _add_to_schedule(context, op, **schedule_params)


def shift_frequency(
    channel: ChannelRefLike,
    frequency: FrequencyLike | SymbolRefLike,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Shift channel frequency.

    :param channel: Channel to shift frequency on
    :param frequency: Frequency shift amount
    :param schedule_params: Additional scheduling parameters

    :return: Operation token

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import shift_frequency

        shift_frequency("qubit", "100MHz")
    """
    channel = as_channel_ref(channel)
    frequency = _coerce_or_ref(frequency, coerce=as_frequency, param_name="frequency", context="shift_frequency()")  # type: ignore[assignment]

    op = ShiftFrequency(channel=channel, frequency=frequency)

    context = _current_context("shift_frequency()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("shift_frequency()")
    return _add_to_schedule(context, op, **schedule_params)


def set_phase(
    channel: ChannelRefLike,
    phase: PhaseLike | SymbolRefLike,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Set channel phase.

    :param channel: Channel to set phase on
    :param phase: Phase to set
    :param schedule_params: Additional scheduling parameters

    :return: Operation token

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import set_phase

        set_phase("qubit", "90deg")
    """
    channel = as_channel_ref(channel)
    phase = _coerce_or_ref(phase, coerce=as_phase, param_name="phase", context="set_phase()")  # type: ignore[assignment]

    op = SetPhase(channel=channel, phase=phase)

    context = _current_context("set_phase()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("set_phase()")
    return _add_to_schedule(context, op, **schedule_params)


def shift_phase(
    channel: ChannelRefLike,
    phase: PhaseLike | SymbolRefLike,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Shift channel phase.

    :param channel: Channel to shift phase on
    :param phase: Phase shift amount
    :param schedule_params: Additional scheduling parameters

    :return: Operation token

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import shift_phase

        shift_phase("qubit", "45deg")
    """
    channel = as_channel_ref(channel)
    phase = _coerce_or_ref(phase, coerce=as_phase, param_name="phase", context="shift_phase()")  # type: ignore[assignment]

    op = ShiftPhase(channel=channel, phase=phase)

    context = _current_context("shift_phase()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("shift_phase()")
    return _add_to_schedule(context, op, **schedule_params)


def record(
    channel: ChannelRefLike,
    var: str | VariableRefLike,
    *,
    duration: DurationLike,
    integration: FullIntegration | DemodIntegration,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Record (acquire) data from a channel.

    :param channel: Channel to record from
    :param var: Variable to store the result
    :param duration: Recording duration
    :param integration: Integration configuration (use :func:`full_integration` or :func:`demod_integration`)
    :param schedule_params: Additional scheduling parameters

    :return: Operation token

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import (
            build_schedule, record, var_decl,
            full_integration, demod_integration
        )

        with build_schedule() as sched:
            var_decl("result", "complex", unit="mV")
            record("readout", "result", duration="1us",
                   integration=full_integration())
    """
    # Validate variable reference
    validated_var = _validate_variable_ref(var)
    channel = as_channel_ref(channel)
    duration = as_duration(duration)

    op = Record(channel=channel, var=validated_var, duration=duration, integration=integration)  # type: ignore[arg-type]

    context = _current_context("record()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("record()")
    return _add_to_schedule(context, op, **schedule_params)


def discriminate(
    target: str | VariableRefLike,
    source: str | VariableRefLike,
    threshold: ThresholdLike,
    *,
    rotation: PhaseLike = 0,
    compare: ComparisonModeLike = ">=",
    project: ComplexToRealProjectionModeLike = "real",
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Discriminate a measurement result to a binary outcome.

    This operation applies a rotation, projects complex data to real, and compares
    against a threshold to produce a boolean result.

    :param target: Variable to store the discrimination result (boolean)
    :param source: Source variable containing the measurement data
    :param threshold: Threshold value for comparison
    :param rotation: Phase rotation to apply before projection (default: 0)
    :param compare: Comparison operator (default: ">=")
    :param project: Complex-to-real projection mode (default: "real")
    :param schedule_params: Additional scheduling parameters

    :return: Operation token

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import discriminate

        discriminate("bit", "measurement", threshold=0.5,
                         rotation="45deg", compare=">", project="abs")
    """
    # Validate variable references
    validated_target = _validate_variable_ref(target)
    validated_source = _validate_variable_ref(source)
    threshold = as_threshold(threshold)
    rotation = as_phase(rotation)

    op = Discriminate(
        target=validated_target,
        source=validated_source,
        threshold=threshold,
        rotation=rotation,  # type: ignore[arg-type]
        compare=compare,  # type: ignore[arg-type]
        project=project,  # type: ignore[arg-type]
    )

    context = _current_context("discriminate()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("discriminate()")
    return _add_to_schedule(context, op, **schedule_params)


def store(
    key: str,
    source: str | VariableRefLike,
    *,
    mode: StoreMode | StoreModeLiteral = "last",
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Store a variable value for later retrieval.

    This operation stores the value of a variable to persistent storage
    for analysis after the pulse program completes. Different storage modes
    allow for averaging, counting, or trace capture.

    :param key: Storage key for retrieving the data
    :param source: Source variable to store
    :param mode: Storage mode - how to aggregate multiple values
    :param schedule_params: Additional scheduling parameters

    :return: Operation token

    :raises RuntimeError: If not called within a schedule context

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import *

        with build_schedule():
            var_decl("measurement", "complex", unit="mV")
            var_decl("result", "complex", unit="mV")
            # ... perform measurement to populate measurement ...

            store("result", "measurement", mode="last")
    """
    # Validate variable reference
    validated_source = _validate_variable_ref(source)

    op = Store(key=key, source=validated_source, mode=mode)  # type: ignore[arg-type]

    context = _current_context("store()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("store()")
    return _add_to_schedule(context, op, **schedule_params)


def measure(
    channel: ChannelRefLike | tuple[ChannelRefLike, ChannelRefLike],
    *,
    result_var: str | VariableRefLike,
    duration: DurationLike,
    amplitude: AmplitudeLike,
    integration: FullIntegration | DemodIntegration,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken:
    """Perform a measurement (simultaneous play + record).

    This is a convenience function that creates a square pulse play operation
    and a record operation that execute simultaneously.

    :param channel: Channel for measurement. Can be a single channel (used for both
        drive and readout) or a tuple of (drive_channel, readout_channel)
    :param result_var: Variable to store the measurement result
    :param duration: Measurement duration
    :param amplitude: Measurement pulse amplitude
    :param integration: Integration configuration (use :func:`full_integration` or :func:`demod_integration`)
    :param schedule_params: Additional scheduling parameters

    :return: Token for the emitted play operation

    :raises RuntimeError: If not called within a schedule context

    .. note::

        This emits two operations: a play carrying ``op_name`` (or a generated name),
        and a record named ``"<that name>_record"`` anchored to the play's start. The
        returned token refers to the play; since both share a start and a duration,
        referencing either gives the same timing.

    Examples

    .. code-block:: python

        from eq1_pulse.builder.experimental import (
            build_schedule, measure, var_decl,
            full_integration, demod_integration
        )

        with build_schedule() as sched:
            var_decl("result", "complex", unit="mV")
            measure(("drive", "readout"), result_var="result",
                    duration="1us", amplitude="50mV",
                    integration=demod_integration(phase="0deg"))
    """
    context = _current_context("measure()")
    if not _in_schedule(context):
        raise _not_a_schedule_context("measure()")

    # Parse channel parameter
    if isinstance(channel, tuple):
        drive_channel, readout_channel = channel
    else:
        drive_channel = readout_channel = channel

    # Create measurement pulse
    meas_pulse = square_pulse(duration=duration, amplitude=amplitude)

    # The play carries the caller's timing parameters...
    play_token = play(drive_channel, meas_pulse, **schedule_params)

    # ...and the record is anchored to the play's start, so it needs none of
    # them. Reusing the caller's op_name here would give both operations the
    # same name and make ref_op="<that name>" ambiguous, so derive a distinct one.
    record_params: ScheduleParams = {
        "op_name": f"{play_token.name}_record",
        "ref_op": play_token.name,
        "ref_pt": "start",
        "ref_pt_new": "start",
        "rel_time": 0,
    }

    record(
        readout_channel,
        result_var,
        duration=duration,
        integration=integration,
        **record_params,
    )

    # Return the play's token: it carries the name the caller asked for, and the
    # two operations share a start and a duration, so every reference point of
    # the pair coincides.
    return play_token
