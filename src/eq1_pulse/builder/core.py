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
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Unpack, overload

from eq1_pulse.models import Phase

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
    "demod_integration",
    "discriminate",
    "external_pulse",
    "for_",
    "full_integration",
    "if_",
    "measure",
    "nested_schedule",
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
    "sub_schedule",
    "sub_sequence",
    "var",
    "var_decl",
    "wait",
)


@dataclass
class BuilderState:
    """State for the pulse builder.

    This class encapsulates all module-level state for the builder interface,
    allowing it to be stored in a ContextVar for thread and async safety.
    """

    context_stack: list[
        OpSequence
        | Schedule
        | Repetition
        | Iteration
        | Conditional
        | SchedRepetition
        | SchedIteration
        | SchedConditional
    ] = field(default_factory=list)
    op_counter: int = 0
    # Track unconsumed schedule blocks per context using defaultdict
    # Key is id(context), value is list of unconsumed blocks
    unconsumed_blocks: defaultdict[int, list[ScheduleBlock]] = field(default_factory=lambda: defaultdict(list))
    # Track declared variables per context using defaultdict
    # Key is id(context), value is set of declared variable names
    declared_variables: defaultdict[int, set[str]] = field(default_factory=lambda: defaultdict(set))


_state: ContextVar[BuilderState | None] = ContextVar("builder_state", default=None)


def _get_state() -> BuilderState:
    """Get the current builder state from context storage.

    If no state exists for the current context, a new state is initialized and set.

    :return: The current builder state
    """
    state = _state.get()
    if state is None:
        state = BuilderState()
        _state.set(state)
    return state


def _generate_op_name() -> str:
    """Generate a unique operation name.

    :return: Unique operation name
    """
    state = _get_state()
    state.op_counter += 1
    return f"op_{state.op_counter}"


def _current_context(operation_name: str = "") -> Any:
    """Get the current building context.

    :param operation_name: Optional operation name for more specific error messages

    :return: The current sequence or schedule being built

    :raises RuntimeError: If no context is active
    """
    state = _get_state()
    if not state.context_stack:
        if operation_name:
            msg = (
                f"No active building context for {operation_name}. "
                "Use build_sequence() or build_schedule() context manager first."
            )
        else:
            msg = "No active building context. Use build_sequence() or build_schedule() context manager first."
        raise RuntimeError(msg)
    return state.context_stack[-1]


def _add_to_sequence(
    context: OpSequence | Repetition | Iteration | Conditional,
    operation: Any,
    schedule_params: ScheduleParams | None = None,
    operation_name: str = "",
) -> None:
    """Add an operation to a sequence context.

    :param context: The sequence context to add to
    :param operation: The operation to add
    :param schedule_params: Schedule parameters to validate (should be empty)
    :param operation_name: Name of the operation for error messages

    :raises RuntimeError: If context is not a sequence
    :raises RuntimeError: If schedule parameters are provided
    """
    # Reject schedule parameters if any were provided
    if schedule_params:
        _reject_schedule_params(schedule_params, operation_name)

    if isinstance(context, Repetition | Iteration | Conditional):
        context.body.items.append(operation)
    elif isinstance(context, OpSequence):
        context.items.append(operation)
    else:
        raise RuntimeError(f"Cannot add sequence operation to {type(context).__name__} context")


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


def _register_variable(name: str) -> None:
    """Register a variable as declared in the current context.

    :param name: Variable name to register

    :raises RuntimeError: If variable is already declared in the current context
    """
    state = _get_state()
    if not state.context_stack:
        return  # No context active, skip registration

    # Check if already declared in current context (not parent contexts)
    context_id = id(_current_context())
    if name in state.declared_variables[context_id]:
        raise RuntimeError(
            f"Variable '{name}' is already declared in the current context. "
            f"Each variable can only be declared once per context."
        )

    # Register in current context
    state.declared_variables[context_id].add(name)


def _is_variable_declared(name: str) -> bool:
    """Check if a variable has been declared in the current or parent contexts.

    Variables are scoped to the context where they are declared and all nested contexts.

    :param name: Variable name to check

    :return: :obj:`True` if variable is declared, :obj:`False` otherwise
    """
    state = _get_state()
    if not state.context_stack:
        return False  # No context active

    # Check from innermost to outermost context
    for context in reversed(state.context_stack):
        context_id = id(context)
        if name in state.declared_variables[context_id]:
            return True

    return False


def _check_variable_declared(name: str) -> None:
    """Check if a variable has been declared and raise an error if not.

    :param name: Variable name to check

    :raises RuntimeError: If variable has not been declared in current or parent contexts
    """
    if not _is_variable_declared(name):
        raise RuntimeError(
            f"Variable '{name}' has not been declared. Use var_decl('{name}', dtype, ...) "
            f"before referencing this variable."
        )


def _cleanup_context_variables(context: Any) -> None:
    """Clean up variable tracking for a context when it exits.

    :param context: The context to clean up
    """
    state = _get_state()
    context_id = id(context)
    if context_id in state.declared_variables:
        del state.declared_variables[context_id]


def _validate_variable_ref(var_ref: VariableRefLike) -> VariableRef:
    """Validate a variable reference and convert to VariableRef object.

    :param var_ref: Variable reference (string, dict, or VariableRef)

    :return: Validated VariableRef object

    :raises RuntimeError: If variable has not been declared
    """
    # Convert to VariableRef if needed
    if isinstance(var_ref, str):
        var_ref = VariableRef(var_ref)
    elif isinstance(var_ref, dict):
        var_ref = VariableRef(**var_ref)
    elif isinstance(var_ref, VariableRef):
        pass
    else:
        raise TypeError(f"Unexpected value passed into variable reference: {var_ref!r}")

    # Check if variable is declared
    _check_variable_declared(var_ref.var)

    # Return validated VariableRef
    return var_ref


def _reject_schedule_params(schedule_params: ScheduleParams, operation_name: str) -> None:
    """Reject schedule parameters when adding to sequence.

    Called just before adding an operation to a sequence context to ensure
    no schedule parameters were provided.

    :param schedule_params: Schedule parameters to check
    :param operation_name: Name of the operation for error messages

    :raises RuntimeError: If any schedule parameters are provided
    """
    provided_params = [key for key, value in schedule_params.items() if value is not None]

    if provided_params:
        params_str = ", ".join(f"'{p}'" for p in provided_params)
        raise RuntimeError(
            f"Schedule parameters ({params_str}) not allowed in sequence context for '{operation_name}'. "
            f"Use build_schedule() instead of build_sequence()."
        )


def _validate_or_pass_through[T](
    value: T | VariableRef,
    *,
    param_name: str,
    context: str,
) -> T | VariableRef:
    """Validate a parameter that can be a variable reference or literal value.

    - If value is :obj:`None`: pass through
    - If value is :class:`VariableRef`: validate it's declared, pass through
    - If value is dict with ``"var"`` key: convert to :class:`VariableRef` and validate
    - If value is dict without ``"var"`` key: pass through unchanged
    - If value is string AND identifier: treat as variable, validate, return :class:`VariableRef`
    - If value is string AND not identifier: pass through (e.g., ``"10us"``)
    - Otherwise: pass through unchanged (for model validation)

    This handles parameters like ``duration="10us"`` vs ``duration="my_var"`` vs ``duration=var("my_var")``.

    :param value: Parameter value
    :param param_name: Name of the parameter being validated (for error messages)
    :param context: Context/function name where validation occurs (for error messages)

    :return: :class:`VariableRef` if identifier string or dict with ``"var"``, else unchanged value

    :raises RuntimeError: If identifier string references undeclared variable
    """
    if value is None:
        return None  # type: ignore[return-value]

    if isinstance(value, VariableRef):
        _check_variable_declared(value.var)
        return value

    if isinstance(value, dict):
        if "var" in value:
            var_ref = VariableRef(**value)
            _check_variable_declared(var_ref.var)
            return var_ref
        # Dict without "var" key - pass through (e.g., {"ns": 100})
        return value  # type: ignore[return-value]

    if isinstance(value, str) and value.isidentifier():
        if not _is_variable_declared(value):
            raise RuntimeError(
                f"Parameter '{param_name}' in {context} references undeclared variable '{value}'. "
                f"Use var_decl('{value}', dtype, ...) before referencing this variable."
            )
        return VariableRef(value)

    return value


# ============================================================================
# Basic model builders
# ============================================================================


@overload
def phase(_0: Literal[0], /) -> Phase: ...


@overload
def phase(_s: str, /) -> Phase: ...


@overload
def phase(*, deg: float) -> Phase: ...


@overload
def phase(*, rad: float) -> Phase: ...


@overload
def phase(*, turns: float) -> Phase: ...


@overload
def phase(*, half_turns: float) -> Phase: ...


def phase(*args, **kwargs) -> Phase:
    """Construct a phase object.

    :param deg: Phase in degrees
    :param rad: Phase in radians
    :param turns: Phase in turns
    :param half_turns: Phase in half-turns
    :param _0: The literal zero
    :param _s: The string representation (value + unit) only as positional
    :return: The constructed phase object
        Use the result to matrix-multiply (`@`)
    """
    match len(args):
        case 0:
            if not len(kwargs):
                raise TypeError("not enough arguments")
            return Phase(**kwargs)
        case 1:
            if len(kwargs):
                raise TypeError("keyword arguments cannot follow positional argument")
            return Phase.model_validate(*args)
        case _:
            raise TypeError("at most one positional argument is allowed")


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
    state = _get_state()
    state.context_stack.append(seq)
    try:
        yield seq
    finally:
        state.context_stack.pop()
        _cleanup_context_variables(seq)


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
    state = _get_state()
    if not state.context_stack:
        raise RuntimeError("sub_sequence can only be used within a build_sequence() context")

    context = _current_context()
    if not isinstance(context, OpSequence | Repetition | Iteration | Conditional):
        raise RuntimeError("sub_sequence can only be used within a sequence context (not in schedules)")

    # Create the nested sequence
    nested_seq = OpSequence(items=[])

    # Add it to the parent sequence
    _add_to_sequence(context, nested_seq)

    # Push nested sequence as current context for operations inside it
    state.context_stack.append(nested_seq)
    try:
        yield nested_seq
    finally:
        state.context_stack.pop()
        _cleanup_context_variables(nested_seq)


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
    state = _get_state()
    state.context_stack.append(sched)
    sched_id = id(sched)
    try:
        yield sched
    finally:
        # Check for unconsumed schedule blocks before popping context
        unconsumed = state.unconsumed_blocks[sched_id]
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
            del state.unconsumed_blocks[sched_id]
            state.context_stack.pop()
            _cleanup_context_variables(sched)
            raise RuntimeError("".join(error_parts))
        # Clean up empty list
        if sched_id in state.unconsumed_blocks:
            del state.unconsumed_blocks[sched_id]
        state.context_stack.pop()
        _cleanup_context_variables(sched)


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
            with sub_schedule(op_name="init") as init:
                play("qubit", square_pulse(duration="100ns", amplitude="200mV"))
                wait("qubit", duration="50ns")

            # Create gate operation positioned after init
            gate_op = play("qubit", square_pulse(duration="20ns", amplitude="150mV"),
                          ref_op="init", ref_pt="end", rel_time="10ns")

            # Create measurement block positioned after gate
            with sub_schedule(op_name="measure", ref_op=gate_op, ref_pt="end", rel_time="50ns"):
                play("drive", square_pulse(duration="1us", amplitude="50mV"))
                record("readout", var="result", duration="1us")
    """
    # Must be called within a schedule context
    state = _get_state()
    context = _current_context("sub_schedule()") if state.context_stack else None
    if context is None or not isinstance(context, Schedule):
        raise RuntimeError("sub_schedule can only be used within a build_schedule() context")

    # Create the nested schedule
    nested_sched = Schedule(items=[])

    # Add it to the parent schedule with timing parameters
    token = _add_to_schedule(context, nested_sched, **schedule_params)

    # Push nested schedule as current context for operations inside it
    state.context_stack.append(nested_sched)
    sched_id = id(nested_sched)
    try:
        yield nested_sched
    finally:
        # Check for unconsumed schedule blocks before popping context
        unconsumed = state.unconsumed_blocks[sched_id]
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
            del state.unconsumed_blocks[sched_id]
            state.context_stack.pop()
            _cleanup_context_variables(nested_sched)
            raise RuntimeError("".join(error_parts))
        # Clean up empty list
        if sched_id in state.unconsumed_blocks:
            del state.unconsumed_blocks[sched_id]
        state.context_stack.pop()
        _cleanup_context_variables(nested_sched)

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

    :raises RuntimeError: If schedule parameters are provided in a sequence context

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
    state = _get_state()
    parent = _current_context("repeat()")

    # Schedule context - create SchedRepetition
    if isinstance(parent, Schedule | SchedRepetition | SchedIteration | SchedConditional):
        sched_body = Schedule(items=[])
        sched_rep = SchedRepetition(count=count, body=sched_body)
        _add_to_schedule(parent, sched_rep, **schedule_params)
        state.context_stack.append(sched_rep)
        try:
            yield sched_rep  # type: ignore[misc]
        finally:
            state.context_stack.pop()
            _cleanup_context_variables(sched_rep)
        return

    # Sequence context - create Repetition
    if isinstance(parent, OpSequence | Repetition | Iteration | Conditional):
        # Check that no schedule parameters were provided in sequence context
        _reject_schedule_params(schedule_params, "repeat")
        seq_body = OpSequence(items=[])
        rep = Repetition(count=count, body=seq_body)
        if isinstance(parent, OpSequence):
            parent.items.append(rep)
        else:
            parent.body.items.append(rep)
        state.context_stack.append(rep)
        try:
            yield rep  # type: ignore[misc]
        finally:
            state.context_stack.pop()
            _cleanup_context_variables(rep)
        return

    msg = f"repeat() cannot be used in context of type {type(parent).__name__}"
    raise RuntimeError(msg)


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

    :raises RuntimeError: If schedule parameters are provided in a sequence context

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
    # Validate variable reference(s)
    validated_vars: list[VariableRefLike] | VariableRefLike = (
        [_validate_variable_ref(v) for v in var] if isinstance(var, list) else _validate_variable_ref(var)
    )

    parent = _current_context("for_()")
    body = OpSequence(items=[])
    iter_obj = Iteration(var=validated_vars, items=items, body=body)

    state = _get_state()
    if isinstance(parent, OpSequence):
        _reject_schedule_params(schedule_params, "for_")
        parent.items.append(iter_obj)
    elif isinstance(parent, Repetition | Iteration | Conditional):
        _reject_schedule_params(schedule_params, "for_")
        parent.body.items.append(iter_obj)
    elif isinstance(parent, Schedule | SchedRepetition | SchedIteration | SchedConditional):
        # For schedules, we need SchedIteration not Iteration
        sched_iter = SchedIteration(var=validated_vars, items=items, body=Schedule(items=[]))
        _add_to_schedule(parent, sched_iter, **schedule_params)
        state.context_stack.append(sched_iter)
        try:
            yield sched_iter  # type: ignore[misc]
        finally:
            state.context_stack.pop()
            _cleanup_context_variables(sched_iter)
        return
    else:
        msg = f"for_() cannot be used in context of type {type(parent).__name__}"
        raise RuntimeError(msg)

    state.context_stack.append(iter_obj)
    try:
        yield iter_obj
    finally:
        state.context_stack.pop()
        _cleanup_context_variables(iter_obj)


@contextmanager
def if_(var: VariableRefLike, **schedule_params: Unpack[ScheduleParams]) -> Iterator[Conditional]:
    """Context manager for building a conditional block.

    :param var: Variable reference for the condition
    :param schedule_params:
        Additional scheduling parameters (name, ref_op, ref_pt, etc.) - only used in schedule context

    :yield: The conditional being built

    :raises RuntimeError: If schedule parameters are provided in a sequence context

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
    # Validate variable reference
    validated_var = _validate_variable_ref(var)

    parent = _current_context("if_()")
    body = OpSequence(items=[])
    cond = Conditional(var=validated_var, body=body)

    state = _get_state()
    if isinstance(parent, OpSequence):
        _reject_schedule_params(schedule_params, "if_")
        parent.items.append(cond)
    elif isinstance(parent, Repetition | Iteration | Conditional):
        _reject_schedule_params(schedule_params, "if_")
        parent.body.items.append(cond)
    elif isinstance(parent, Schedule | SchedRepetition | SchedIteration | SchedConditional):
        # For schedules, we need SchedConditional not Conditional
        sched_cond = SchedConditional(var=validated_var, body=Schedule(items=[]))
        _add_to_schedule(parent, sched_cond, **schedule_params)
        state.context_stack.append(sched_cond)
        try:
            yield sched_cond  # type: ignore[misc]
        finally:
            state.context_stack.pop()
            _cleanup_context_variables(sched_cond)
        return
    else:
        msg = f"if_() cannot be used in context of type {type(parent).__name__}"
        raise RuntimeError(msg)

    state.context_stack.append(cond)
    try:
        yield cond
    finally:
        state.context_stack.pop()
        _cleanup_context_variables(cond)


# ============================================================================
# Pulse creation helpers
# ============================================================================


def square_pulse(
    *,
    duration: DurationLike | VariableRefLike,
    amplitude: AmplitudeLike | VariableRefLike,
    rise_time: DurationLike | VariableRefLike | None = None,
    fall_time: DurationLike | VariableRefLike | None = None,
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
    duration = _validate_or_pass_through(duration, param_name="duration", context="square_pulse()")
    amplitude = _validate_or_pass_through(amplitude, param_name="amplitude", context="square_pulse()")
    rise_time = _validate_or_pass_through(rise_time, param_name="rise_time", context="square_pulse()")
    fall_time = _validate_or_pass_through(fall_time, param_name="fall_time", context="square_pulse()")

    return SquarePulse(
        duration=duration,
        amplitude=amplitude,
        rise_time=rise_time,
        fall_time=fall_time,
    )


def sine_pulse(
    *,
    duration: DurationLike | VariableRefLike,
    amplitude: AmplitudeLike | VariableRefLike,
    frequency: FrequencyLike | VariableRefLike,
    to_frequency: FrequencyLike | VariableRefLike | None = None,
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
    duration = _validate_or_pass_through(duration, param_name="duration", context="sine_pulse()")
    amplitude = _validate_or_pass_through(amplitude, param_name="amplitude", context="sine_pulse()")
    frequency = _validate_or_pass_through(frequency, param_name="frequency", context="sine_pulse()")
    to_frequency = _validate_or_pass_through(to_frequency, param_name="to_frequency", context="sine_pulse()")

    return SinePulse(
        duration=duration,
        amplitude=amplitude,
        frequency=frequency,
        to_frequency=to_frequency,
    )


def external_pulse(
    function: str,
    *,
    duration: DurationLike | VariableRefLike,
    amplitude: AmplitudeLike | VariableRefLike,
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
    duration = _validate_or_pass_through(duration, param_name="duration", context="external_pulse()")
    amplitude = _validate_or_pass_through(amplitude, param_name="amplitude", context="external_pulse()")

    # Validate top-level params dict values (if params provided)
    if params is not None:
        validated_params = {}
        for key, value in params.items():
            validated_params[key] = _validate_or_pass_through(
                value, param_name=f"params['{key}']", context="external_pulse()"
            )
        params = validated_params

    return ExternalPulse(
        function=function,
        duration=duration,
        amplitude=amplitude,
        params=params,  # type: ignore[arg-type]
    )


def arbitrary_pulse(
    samples: list[float] | list[complex],
    *,
    duration: DurationLike | VariableRefLike,
    amplitude: AmplitudeLike | VariableRefLike,
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
    duration = _validate_or_pass_through(duration, param_name="duration", context="arbitrary_pulse()")
    amplitude = _validate_or_pass_through(amplitude, param_name="amplitude", context="arbitrary_pulse()")

    return ArbitrarySampledPulse(
        samples=samples,
        duration=duration,
        amplitude=amplitude,
        interpolation=interpolation,
        time_points=time_points,
    )


# ============================================================================
# Integration helpers
# ============================================================================


def full_integration() -> FullIntegration:
    """Create a full integration configuration.

    Full integration performs a simple accumulation of the measured signal
    over the acquisition window.

    :return: Full integration configuration object

    Examples

    .. code-block:: python

        from eq1_pulse.builder import full_integration, record

        # Use full integration for recording
        record("readout", var="result", duration="1us", integration=full_integration())
    """
    return FullIntegration()


def demod_integration(
    *,
    phase: PhaseLike | None = None,
    scale_cos: float = 1.0,
    scale_sin: float = 1.0,
) -> DemodIntegration:
    """Create a demodulation integration configuration.

    Demodulation integration multiplies the measured signal with the channel's
    output signal (at the channel's frequency and phase) before integration.
    This is useful for extracting the in-phase and quadrature components.

    :param phase: Optional phase rotation to apply to the result
    :param scale_cos: Scaling factor for the real (cosine) part (default: 1.0)
    :param scale_sin: Scaling factor for the imaginary (sine) part (default: 1.0)

    :return: Demodulation integration configuration object

    Examples

    .. code-block:: python

        from eq1_pulse.builder import demod_integration, record

        # Basic demodulation
        record("readout", var="result", duration="1us",
               integration=demod_integration())

        # With phase rotation
        record("readout", var="result", duration="1us",
               integration=demod_integration(phase="45deg"))

        # With scaling (e.g., to flip sign of imaginary part)
        record("readout", var="result", duration="1us",
               integration=demod_integration(scale_cos=1.0, scale_sin=-1.0))
    """
    return DemodIntegration(
        phase=phase,  # type: ignore[arg-type]
        scale_cos=scale_cos,
        scale_sin=scale_sin,
    )


# ============================================================================
# Reference helpers
# ============================================================================


def var(name: str) -> VariableRef:
    """Create a variable reference.

    :param name: Variable name

    :return: Variable reference

    :raises RuntimeError: If variable has not been declared in current or parent contexts

    Examples

    .. code-block:: python

        from eq1_pulse.builder import var

        freq_var = var("frequency")
    """
    _check_variable_declared(name)
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
    **kwargs: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Declare a variable for use in the current context.

    Variables should be declared before they are used in iterations or conditionals.
    The declaration specifies the variable's data type, optional shape (for arrays),
    and optional unit for dimensional consistency.

    :param name: Name of the variable (must be a valid identifier)
    :param dtype: Data type of the variable ("bool", "int", "float", or "complex")
    :param shape: Optional shape for array variables (e.g., (10,) for 1D array)
    :param unit: Optional unit string (e.g., "mV", "ns", "GHz") for the variable
    :param op_name: Optional name for the operation (schedules only)
    :param rel_time: Relative time from the reference point (schedules only)
    :param ref_op: Name of or token for the reference operation (schedules only)
    :param ref_pt: Reference point on the reference operation (schedules only)
    :param ref_pt_new: Reference point on the new operation (schedules only)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    :raises RuntimeError: If schedule parameters are provided in a sequence context

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

        # In schedule context
        with build_schedule():
            var_decl("result", "complex", unit="mV")
            # ... use the variable in scheduled operations
    """
    var_decl_obj = VariableDecl(name=name, dtype=dtype, shape=shape, unit=unit)

    # Register the variable as declared in the current context
    _register_variable(name)

    context = _current_context("var_decl()")
    if isinstance(context, Schedule | SchedRepetition | SchedIteration | SchedConditional):
        return _add_to_schedule(context, var_decl_obj, **kwargs)
    else:
        _add_to_sequence(context, var_decl_obj, kwargs, "var_decl")
        return None


def pulse_decl(
    name: str,
    pulse: PulseType,
    **kwargs: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Declare a pulse for use in the current context.

    Pulses can be declared and given a name, then referenced later using
    :func:`pulse_ref`. This allows reusing the same pulse definition multiple
    times without repeating the full definition.

    :param name: Name of the pulse (must be a valid identifier)
    :param pulse: The pulse definition (e.g., from :func:`square_pulse`, :func:`sine_pulse`)
    :param op_name: Optional name for the operation (schedules only)
    :param rel_time: Relative time from the reference point (schedules only)
    :param ref_op: Name of or token for the reference operation (schedules only)
    :param ref_pt: Reference point on the reference operation (schedules only)
    :param ref_pt_new: Reference point on the new operation (schedules only)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    :raises RuntimeError: If schedule parameters are provided in a sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence():
            # Declare a pulse with a name
            pulse_decl("my_square", square_pulse(duration="100ns", amplitude="200mV"))

            # Use the pulse reference later
            play("qubit", pulse_ref("my_square"))
            play("qubit", pulse_ref("my_square"))  # Reuse the same pulse

        # In schedule context
        with build_schedule():
            pulse_decl("readout_pulse", square_pulse(duration="1us", amplitude="50mV"))
            play("readout", pulse_ref("readout_pulse"))
    """
    pulse_decl_obj = PulseDecl(name=name, pulse=pulse)

    context = _current_context("pulse_decl()")
    if isinstance(context, Schedule | SchedRepetition | SchedIteration | SchedConditional):
        return _add_to_schedule(context, pulse_decl_obj, **kwargs)
    else:
        _add_to_sequence(context, pulse_decl_obj, kwargs, "pulse_decl")
        return None


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
        state = _get_state()
        context = _current_context()
        state.unconsumed_blocks[id(context)].append(self)

    def _execute(self) -> None:
        """Execute the block's function and mark as consumed."""
        # Remove from unconsumed list (find the context this belongs to)
        state = _get_state()
        for blocks in state.unconsumed_blocks.values():
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
        state = _get_state()
        if state.context_stack:
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
    scale_amp: float | complex | VariableRefLike | None = None,
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

    :raises RuntimeError: If schedule parameters are provided in a sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        # In sequence
        play("ch1", square_pulse(duration="10us", amplitude="100mV"))

        # In schedule with positioning
        op = play("ch1", square_pulse(duration="10us", amplitude="100mV"),
                      ref_op=previous_op, ref_pt="end")
    """
    # scale_amp can be numeric or variable - only validate if it's a potential VariableRef type
    if scale_amp is not None and isinstance(scale_amp, str | dict | VariableRef):
        scale_amp = _validate_or_pass_through(scale_amp, param_name="scale_amp", context="play()")

    # cond is variable-only - use strict validation
    if cond is not None:
        cond = _validate_variable_ref(cond)

    op = Play(channel=channel, pulse=pulse, scale_amp=scale_amp, cond=cond)

    context = _current_context("play()")
    if isinstance(context, Schedule | SchedRepetition | SchedIteration | SchedConditional):
        return _add_to_schedule(context, op, **schedule_params)
    else:
        _add_to_sequence(context, op, schedule_params, "play")
        return None


def wait(
    *channels: ChannelRefLike,
    duration: DurationLike | VariableRefLike,
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
    :raises RuntimeError: If schedule parameters are provided in a sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import wait

        # Single channel (works in both sequences and schedules)
        wait("ch1", duration="5us")

        # Multiple channels (only works in sequences)
        with build_sequence():
            wait("ch1", "ch2", duration="10us")
    """
    context = _current_context("wait()")

    # Validate multi-channel wait in schedules
    if isinstance(context, Schedule | SchedRepetition | SchedIteration | SchedConditional) and len(channels) > 1:
        raise RuntimeError(
            f"Wait with multiple channels ({len(channels)} channels) is not allowed "
            "in schedule context. Multi-channel wait has complex semantics in schedules "
            "(equivalent to a subschedule with all channels idling), which contradicts "
            "the sequence definition. Use single-channel wait in schedules."
        )

    duration = _validate_or_pass_through(duration, param_name="duration", context="wait()")

    op = Wait(*channels, duration=duration)  # type: ignore[arg-type]

    if isinstance(context, Schedule | SchedRepetition | SchedIteration | SchedConditional):
        return _add_to_schedule(context, op, **schedule_params)
    else:
        _add_to_sequence(context, op, schedule_params, "wait")
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

    context = _current_context("barrier()")
    if isinstance(context, Schedule):
        raise RuntimeError(
            "Barrier operations are not supported in schedule contexts. "
            "Schedules use explicit timing, making barriers unnecessary. "
            "Use sequence context instead."
        )
    else:
        _add_to_sequence(context, op)


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

    :raises RuntimeError: If schedule parameters are provided in a sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import set_frequency

        set_frequency("qubit", "5GHz")
    """
    frequency = _validate_or_pass_through(frequency, param_name="frequency", context="set_frequency()")

    op = SetFrequency(channel=channel, frequency=frequency)

    context = _current_context("set_frequency()")
    if isinstance(context, Schedule):
        return _add_to_schedule(context, op, **schedule_params)
    else:
        _add_to_sequence(context, op, schedule_params, "set_frequency")
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

    :raises RuntimeError: If schedule parameters are provided in a sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import shift_frequency

        shift_frequency("qubit", "100MHz")
    """
    frequency = _validate_or_pass_through(frequency, param_name="frequency", context="shift_frequency()")

    op = ShiftFrequency(channel=channel, frequency=frequency)

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(context, op, **schedule_params)
    else:
        _add_to_sequence(context, op, schedule_params, "set_frequency")
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

    :raises RuntimeError: If schedule parameters are provided in a sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import set_phase

        set_phase("qubit", "90deg")
    """
    phase = _validate_or_pass_through(phase, param_name="phase", context="set_phase()")

    op = SetPhase(channel=channel, phase=phase)

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(context, op, **schedule_params)
    else:
        _add_to_sequence(context, op, schedule_params, "set_frequency")
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

    :raises RuntimeError: If schedule parameters are provided in a sequence context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import shift_phase

        shift_phase("qubit", "45deg")
    """
    phase = _validate_or_pass_through(phase, param_name="phase", context="shift_phase()")

    op = ShiftPhase(channel=channel, phase=phase)

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(context, op, **schedule_params)
    else:
        _add_to_sequence(context, op, schedule_params, "set_frequency")
        return None


def record(
    channel: ChannelRefLike,
    var: VariableRefLike,
    *,
    duration: DurationLike,
    integration: FullIntegration | DemodIntegration,
    **schedule_params: Unpack[ScheduleParams],
) -> OperationToken | None:
    """Record (acquire) data from a channel.

    :param channel: Channel to record from
    :param var: Variable to store the result
    :param duration: Recording duration
    :param integration: Integration configuration (use :func:`full_integration` or :func:`demod_integration`)
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    :raises RuntimeError: If schedule parameters are provided in a sequence context

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

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(context, op, **schedule_params)
    else:
        _add_to_sequence(context, op, schedule_params, "set_frequency")
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

    :raises RuntimeError: If schedule parameters are provided in a sequence context

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

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(context, op, **schedule_params)
    else:
        _add_to_sequence(context, op, schedule_params, "set_frequency")
        return None


def store(
    key: str,
    source: VariableRefLike,
    *,
    mode: StoreMode | StoreModeLiteral = "last",
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

    :raises RuntimeError: If schedule parameters are provided in a sequence context

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

            with repeat(range(100)):
                measure("drive", result_var="m", duration="1us", amplitude="50mV")
                store("avg_result", "m", mode="average")
    """
    # Validate variable reference
    validated_source = _validate_variable_ref(source)

    op = Store(key=key, source=validated_source, mode=mode)  # type: ignore[arg-type]

    context = _current_context()
    if isinstance(context, Schedule):
        return _add_to_schedule(context, op, **schedule_params)
    else:
        _add_to_sequence(context, op, schedule_params, "set_frequency")
        return None


def measure(
    channel: ChannelRefLike | tuple[ChannelRefLike, ChannelRefLike],
    *,
    result_var: VariableRefLike,
    duration: DurationLike,
    amplitude: AmplitudeLike,
    integration: FullIntegration | DemodIntegration,
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
    :param integration: Integration configuration (use :func:`full_integration` or :func:`demod_integration`)
    :param schedule_params: Additional scheduling parameters (for schedules)

    :return: Operation token if in schedule context, :obj:`None` if in sequence context

    :raises RuntimeError: If schedule parameters are provided in a sequence context

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
    context = _current_context()

    # Check if schedule params provided in sequence context
    if isinstance(context, OpSequence | Repetition | Iteration | Conditional):
        _reject_schedule_params(schedule_params, "measure")

    # Parse channel parameter
    if isinstance(channel, tuple):
        drive_channel, readout_channel = channel
    else:
        drive_channel = readout_channel = channel

    # Create measurement pulse
    meas_pulse = square_pulse(duration=duration, amplitude=amplitude)

    if isinstance(context, Schedule | SchedRepetition | SchedIteration | SchedConditional):
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
        )
        return None
