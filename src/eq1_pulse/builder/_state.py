"""Shared builder state: the context stack, variable tracking, and the operation counter.

This module is deliberately the one module aware of both context kinds (sequence and
schedule). A single shared context stack lets each builder (:mod:`eq1_pulse.builder.core`
and :mod:`eq1_pulse.builder.experimental.schedule`) reject the other's contexts with a
clear error, rather than silently producing a mixed model.

Context-kind detection uses each context model's ``_context_kind`` marker rather than
``isinstance`` against the concrete schedule classes: importing those unconditionally
would give the production, sequence-only builder a runtime dependency on the
experimental schedule model tree (and its deprecation warnings) merely from being
imported. The concrete classes are only needed here for type annotations, so they are
imported under ``TYPE_CHECKING``.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeGuard

if TYPE_CHECKING:
    from ..models.experimental.schedule import SchedConditional, SchedIteration, SchedRepetition, Schedule
    from ..models.sequence import Conditional, Iteration, OpSequence, Repetition

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


def _pop_context() -> None:
    """Pop the innermost context off the builder stack, discarding its tracking state."""
    state = _get_state()
    state.context_stack.pop()
    state.unconsumed_blocks.pop()
    state.declared_variables.pop()
    state.declared_externals.pop()


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
