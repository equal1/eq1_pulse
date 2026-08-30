"""Shared builder state: the context stack, variable tracking, and the operation counter.

This module is deliberately the one module aware of both context kinds (sequence and
schedule). A single shared context stack lets each builder (:mod:`eq1_pulse.builder.core`
and :mod:`eq1_pulse.builder.experimental.schedule`) reject the other's contexts with a
clear error, rather than silently producing a mixed model.

Context-kind detection uses each context model's ``_context_kind`` marker rather than
``isinstance`` against the concrete schedule classes: importing those unconditionally
would give the production, sequence-only builder a runtime dependency on the
experimental schedule model tree (and its deprecation warnings) merely from being
imported. The schedule classes are only needed here for type annotations, so they are
imported under ``TYPE_CHECKING``; the sequence classes are the production tree and are
imported normally, since :func:`_add_to_sequence` dispatches on them.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeGuard

from ..models.sequence import Conditional, Iteration, OpSequence, Repetition

if TYPE_CHECKING:
    from ..models.experimental.schedule import SchedConditional, SchedIteration, SchedRepetition, Schedule
    from ..models.sweeps import SweepSpec

type SequenceContext = OpSequence | Repetition | Iteration | Conditional
"""Contexts in which operations are ordered implicitly (sequence semantics)."""

type ScheduleContext = Schedule | SchedRepetition | SchedIteration | SchedConditional
"""Contexts in which operations carry explicit timing parameters (schedule semantics)."""

type BuilderContext = SequenceContext | ScheduleContext
"""Any context the builder can be inside of."""


def _in_schedule(context: Any) -> TypeGuard[ScheduleContext]:
    """Check whether a context has schedule semantics.

    This covers the top-level :class:`~eq1_pulse.models.experimental.schedule.Schedule` as well as
    the bodies of schedule-side control flow (``repeat``/``for_``/``if_``), which are
    :class:`~eq1_pulse.models.experimental.schedule.SchedRepetition`,
    :class:`~eq1_pulse.models.experimental.schedule.SchedIteration` and
    :class:`~eq1_pulse.models.experimental.schedule.SchedConditional` respectively.

    :param context: The context to test

    :return: :obj:`True` if operations in this context take schedule parameters
    """
    return getattr(context, "_context_kind", None) == "schedule"


def _in_sequence(context: Any) -> TypeGuard[SequenceContext]:
    """Check whether a context has sequence semantics.

    This covers the top-level :class:`~eq1_pulse.models.sequence.OpSequence` as well as the
    bodies of sequence-side control flow (``repeat``/``for_``/``if_``).

    :param context: The context to test

    :return: :obj:`True` if operations in this context are implicitly ordered
    """
    return getattr(context, "_context_kind", None) == "sequence"


@dataclass
class BuilderState:
    """State for the pulse builder.

    This class encapsulates all module-level state for the builder interface,
    allowing it to be stored in a ContextVar for thread and async safety.
    """

    context_stack: list[BuilderContext] = field(default_factory=list)
    op_counter: int = 0
    # Unconsumed schedule blocks, one list per entry of context_stack.
    # Kept as a parallel stack rather than keyed by id(context): ids are reused
    # after garbage collection, which let stale entries surface in unrelated builds.
    # Typed as Any rather than ScheduleBlock: core.ScheduleBlock and
    # experimental.schedule.ScheduleBlock are deliberately separate classes,
    # and this module must not import from either.
    unconsumed_blocks: list[list[Any]] = field(default_factory=list)
    # Declared variable names, one set per entry of context_stack.
    declared_variables: list[set[str]] = field(default_factory=list)
    # Declared external symbol names, one set per entry of context_stack.
    declared_externals: list[set[str]] = field(default_factory=list)
    # Declared pulse names, one set per entry of context_stack.
    declared_pulses: list[set[str]] = field(default_factory=list)
    # Declared sweeps, one mapping per entry of context_stack: the sweep's name against the
    # id of the sweep_group() declaring it, or None when it was declared on its own. The
    # group id is what the lock-step check compares; nothing else reads it.
    declared_sweeps: list[dict[str, int | None]] = field(default_factory=list)
    # The for_ consuming each sweep: its name against a description of the loop, recorded in
    # the frame where the sweep is *declared* rather than the innermost one, so that it lives
    # exactly as long as the declaration it qualifies.
    sweep_consumers: list[dict[str, str]] = field(default_factory=list)
    # Specifications collected by an open sweep_group(), and that group's id; None when no
    # group is open. A group is not a scope -- its members are declared in the surrounding
    # context -- so this is a single slot rather than a parallel stack.
    open_sweep_group: list[SweepSpec] | None = None
    open_sweep_group_id: int = 0
    # Source of the ids above. Never reset: two groups in one build must not collide, and the
    # ids are compared for equality only.
    sweep_group_counter: int = 0


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


def _push_context(context: BuilderContext) -> None:
    """Push a context onto the builder stack, together with its tracking state.

    Entering a top-level context (i.e. one with no enclosing context) resets the
    operation counter, so that building the same program twice in one process
    produces the same generated operation names.

    :param context: The context being entered
    """
    state = _get_state()
    if not state.context_stack:
        state.op_counter = 0
    state.context_stack.append(context)
    state.unconsumed_blocks.append([])
    state.declared_variables.append(set())
    state.declared_externals.append(set())
    state.declared_pulses.append(set())
    state.declared_sweeps.append({})
    state.sweep_consumers.append({})


def _pop_context() -> None:
    """Pop the innermost context off the builder stack, discarding its tracking state."""
    state = _get_state()
    state.context_stack.pop()
    state.unconsumed_blocks.pop()
    state.declared_variables.pop()
    state.declared_externals.pop()
    state.declared_pulses.pop()
    state.declared_sweeps.pop()
    state.sweep_consumers.pop()


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


def _register_variable(name: str) -> None:
    """Register a variable as declared in the current context.

    :param name: Variable name to register

    :raises RuntimeError: If variable is already declared in the current context
    """
    state = _get_state()
    if not state.context_stack:
        return  # No context active, skip registration

    # Check if already declared in current context (not parent contexts)
    current = state.declared_variables[-1]
    if name in current:
        raise RuntimeError(
            f"Variable '{name}' is already declared in the current context. "
            f"Each variable can only be declared once per context."
        )

    # Register in current context
    current.add(name)


def _is_variable_declared(name: str) -> bool:
    """Check if a variable has been declared in the current or parent contexts.

    Variables are scoped to the context where they are declared and all nested contexts.

    :param name: Variable name to check

    :return: :obj:`True` if variable is declared, :obj:`False` otherwise
    """
    state = _get_state()

    # Check from innermost to outermost context
    return any(name in declared for declared in reversed(state.declared_variables))


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


def _register_external(name: str) -> None:
    """Register an external symbol as declared in the current context.

    :param name: External symbol name to register

    :raises RuntimeError: If the external symbol is already declared in the current context
    """
    state = _get_state()
    if not state.context_stack:
        return  # No context active, skip registration

    # Check if already declared in current context (not parent contexts)
    current = state.declared_externals[-1]
    if name in current:
        raise RuntimeError(
            f"External symbol '{name}' is already declared in the current context. "
            f"Each external symbol can only be declared once per context."
        )

    # Register in current context
    current.add(name)


def _is_external_declared(name: str) -> bool:
    """Check if an external symbol has been declared in the current or parent contexts.

    External symbols are scoped to the context where they are declared and all nested contexts.

    :param name: External symbol name to check

    :return: :obj:`True` if the external symbol is declared, :obj:`False` otherwise
    """
    state = _get_state()

    # Check from innermost to outermost context
    return any(name in declared for declared in reversed(state.declared_externals))


def _check_external_declared(name: str) -> None:
    """Check if an external symbol has been declared and raise an error if not.

    :param name: External symbol name to check

    :raises RuntimeError: If the external symbol has not been declared in current or parent contexts
    """
    if not _is_external_declared(name):
        raise RuntimeError(
            f"External symbol '{name}' has not been declared. Use extern_decl('{name}', dtype, ...) "
            f"before referencing this symbol."
        )


def _register_pulse(name: str) -> None:
    """Register a pulse as declared in the current context.

    :param name: Pulse name to register

    :raises RuntimeError: If the pulse is already declared in the current context
    """
    state = _get_state()
    if not state.context_stack:
        return  # No context active, skip registration

    # Check if already declared in current context (not parent contexts)
    current = state.declared_pulses[-1]
    if name in current:
        raise RuntimeError(
            f"Pulse '{name}' is already declared in the current context. "
            f"Each pulse can only be declared once per context."
        )

    # Register in current context
    current.add(name)


def _is_pulse_declared(name: str) -> bool:
    """Check if a pulse has been declared in the current or parent contexts.

    Pulses are scoped to the context where they are declared and all nested contexts.

    :param name: Pulse name to check

    :return: :obj:`True` if the pulse is declared, :obj:`False` otherwise
    """
    state = _get_state()

    # Check from innermost to outermost context
    return any(name in declared for declared in reversed(state.declared_pulses))


def _check_pulse_declared(name: str) -> None:
    """Check if a pulse has been declared and raise an error if not.

    :param name: Pulse name to check

    :raises RuntimeError: If the pulse has not been declared in current or parent contexts
    """
    if not _is_pulse_declared(name):
        raise RuntimeError(
            f"Pulse '{name}' has not been declared. Use pulse_decl('{name}', ...) before referencing this pulse."
        )


def _register_sweep(name: str, group: int | None) -> None:
    """Register a sweep as declared in the current context.

    Sweeps have their own namespace, as external symbols do: they are read with ``sweep()``
    rather than ``var()``, so a variable of the same name is a different thing and not a clash.

    :param name: Sweep name to register
    :param group: Id of the ``sweep_group()`` declaring it, or :obj:`None` if declared on its own

    :raises RuntimeError: If the sweep is already declared in the current context
    """
    state = _get_state()
    if not state.context_stack:
        return  # No context active, skip registration

    # Check if already declared in current context (not parent contexts)
    current = state.declared_sweeps[-1]
    if name in current:
        raise RuntimeError(
            f"Sweep '{name}' is already declared in the current context. "
            f"Each sweep can only be declared once per context."
        )

    # Register in current context
    current[name] = group


def _is_sweep_declared(name: str) -> bool:
    """Check if a sweep has been declared in the current or parent contexts.

    Sweeps are scoped to the context where they are declared and all nested contexts.

    :param name: Sweep name to check

    :return: :obj:`True` if the sweep is declared, :obj:`False` otherwise
    """
    state = _get_state()

    # Check from innermost to outermost context
    return any(name in declared for declared in reversed(state.declared_sweeps))


def _check_sweep_declared(name: str) -> None:
    """Check if a sweep has been declared and raise an error if not.

    :param name: Sweep name to check

    :raises RuntimeError: If the sweep has not been declared in current or parent contexts
    """
    if not _is_sweep_declared(name):
        raise RuntimeError(
            f"Sweep '{name}' has not been declared. Use sweep_decl('{name}', dtype, ...) before referencing this sweep."
        )


def _sweep_group_of(name: str) -> int | None:
    """Return the id of the ``sweep_group()`` a declared sweep belongs to.

    :param name: Sweep name to look up; must already be declared

    :return: The group's id, or :obj:`None` if the sweep was declared on its own or is unknown
    """
    state = _get_state()

    # Innermost declaration wins, matching `_is_sweep_declared`'s search order
    for declared in reversed(state.declared_sweeps):
        if name in declared:
            return declared[name]
    return None


def _consume_sweep(name: str, consumer: str) -> None:
    """Record that *consumer* is the loop iterating a sweep, rejecting a second one.

    A sweep takes its position in the nesting order from the single ``for_`` that consumes it,
    so a second consumer leaves that position undefined. The record is kept in the frame where
    the sweep is declared rather than the innermost one, so that two sibling loops at different
    depths still see each other.

    :param name: Name of the sweep being consumed; must already be declared
    :param consumer: Description of the consuming loop, for the error message

    :raises RuntimeError: If another loop already consumes this sweep
    """
    state = _get_state()

    for index in range(len(state.declared_sweeps) - 1, -1, -1):
        if name not in state.declared_sweeps[index]:
            continue
        consumers = state.sweep_consumers[index]
        if name in consumers:
            raise RuntimeError(
                f"Sweep '{name}' is already iterated by {consumers[name]}, so a second loop over "
                f"it has no defined position in the nesting order. Iterate it once and reuse the "
                f"loop variable, or declare a second sweep."
            )
        consumers[name] = consumer
        return


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
