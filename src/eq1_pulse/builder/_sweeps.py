"""Builder support for parameter sweeps: the reference, the declarations, and the three checks.

A small module by design. The arithmetic over sweeps is :mod:`~eq1_pulse.builder._expressions`'s --
a sweep is an operand of the ordinary expression grammar, so ``sweep("d") * ext("m11") + ext("o1")``
runs :class:`~eq1_pulse.builder._expressions.Expr`'s own operators and there is nothing to fold.
What is left is one constructor, two declaration functions and three build-time checks:

**undeclared sweep**
    ``sweep("x")`` with no :func:`sweep_decl` in scope, wherever in a tree it appears.

**at most one consuming loop**
    a sweep read by two loops' ``items`` has no well-defined position in the nesting order.

**lock-step**
    every sweep a *single* expression reads -- and every sweep a *single zipped loop* iterates,
    which is one level of nesting just as an expression is -- must be the same sweep, or a member
    of one :func:`sweep_group`.

All three are local; none is a traversal of the program. There is no cycle check to write either:
an expression tree is finite and acyclic by construction, and a transform is anonymous, so it has
no name for another to reference.

Like :mod:`~eq1_pulse.builder._state`, :mod:`~eq1_pulse.builder._factories` and
:mod:`~eq1_pulse.builder._expressions`, this module does not import
:mod:`~eq1_pulse.builder.core`; the dependency runs the other way, and ``core`` re-exports what is
public here.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal, cast

from ..models.expressions import (
    BinaryExpr,
    CallExpr,
    CompareExpr,
    ExprBase,
    IndexExpr,
    LenExpr,
    LogicalExpr,
    NotExpr,
    SweepExpr,
    UnaryExpr,
    sweep_names_in,
)
from ..models.sweeps import SweepDecl, SweepGroup, SweepSpec
from ._expressions import Expr
from ._state import (
    _add_to_sequence,
    _check_sweep_declared,
    _consume_sweep,
    _current_context,
    _get_state,
    _in_sequence,
    _not_a_sequence_context,
    _register_sweep,
    _sweep_group_of,
    _unregister_sweep,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ..models.data_ops import ValueLimits
    from ..models.expressions import Expression
    from ..models.sweeps import SweepValueLike

__all__ = (
    "sweep",
    "sweep_decl",
    "sweep_group",
)


def sweep(name: str) -> Expr:
    """Reference a declared sweep, as an expression.

    The whole entry point: there is no ``Sweep`` wrapper class, because
    :class:`~eq1_pulse.builder._expressions.Expr` already is one and its operators already build
    every tree this feature needs. ``sweep("vg") * ext("gate.gain")`` is an ordinary
    :class:`~.expressions.BinaryExpr`, and an anonymous transform is written where it is read.

    The name is not checked here -- a reference is checked where it is *used*, by the builder
    function receiving the expression, so that a fragment can be assembled before the context that
    declares its sweeps exists.

    :param name: Name of the declared sweep to read.

    :return: An :class:`~eq1_pulse.builder._expressions.Expr` wrapping a
        :class:`~.expressions.SweepExpr`.

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence():
            sweep_decl("vg", "float", unit="mV")
            var_decl("v", "float", unit="mV")
            with for_("v", sweep("vg")):
                play("gate", step_pulse(duration="40ns", amplitude=var("v")))
    """
    return Expr(SweepExpr(sweep=name))


def sweep_decl(
    name: str,
    dtype: Literal["bool", "int", "float", "complex"],
    *,
    shape: tuple[int, ...] | None = None,
    unit: str | None = None,
    default: SweepValueLike | None = None,
    limits: ValueLimits | None = None,
) -> None:
    """Declare a sweep: a named list of values the program is invoked over, one run per item.

    A sweep is the list-valued sibling of a parameter. Its values are always caller-supplied, with
    ``default`` as the fallback; ``shape`` left unset -- the usual case -- accepts whatever length
    the caller supplies. Sweeps are scoped to the surrounding context and its children, and live in
    their own namespace, so a variable of the same name is a different thing.

    Called inside a :func:`sweep_group` body, the declaration joins that group instead of standing
    on its own, and the group is emitted as one operation when its body ends.

    ``limits`` is declared and never enforced by eq1_pulse itself; see
    :class:`~eq1_pulse.models.ValueLimits`.

    :param name: Name of the sweep (must be a valid identifier)
    :param dtype: Data type of the sweep's items ("bool", "int", "float", or "complex")
    :param shape: The length the values must have, as a one-entry tuple, or :obj:`None` for any
    :param unit: Optional unit string (e.g., "mV", "ns", "GHz") for the sweep's items
    :param default: Values used if none are supplied at invocation, or :obj:`None` if required
    :param limits: Declared bounds on each item, or :obj:`None` if unbounded

    :raises RuntimeError: If not called within a sequence context, or the sweep is already declared
        in the current context

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *
        from eq1_pulse.models import LinSpace

        with build_sequence():
            # Always supplied at invocation: {"vg": {"start": -400, "stop": 400, "num": 201}}
            sweep_decl("vg", "float", unit="mV")

            # With a fallback default
            sweep_decl("t_pi", "float", unit="ns", default=LinSpace(start=0, stop=200, num=101))

            # Repeating items: a list, not an axis
            sweep_decl("amp_seq", "float", unit="mV", default=[100, 0, 100, 50, 100, 25])
    """
    context = _current_context("sweep_decl()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("sweep_decl()")

    state = _get_state()
    if state.open_sweep_group is not None:
        # Inside sweep_group(): the member is the bare specification, and the group -- not this
        # call -- is the operation that reaches the sequence.
        state.open_sweep_group.append(
            SweepSpec(name=name, dtype=dtype, shape=shape, unit=unit, default=default, limits=limits)
        )
        _register_sweep(name, state.open_sweep_group_id)
        return

    _register_sweep(name, None)
    _add_to_sequence(
        context,
        SweepDecl(name=name, dtype=dtype, shape=shape, unit=unit, default=default, limits=limits),
    )


@contextmanager
def sweep_group() -> Iterator[None]:
    """Context manager declaring independent sweeps that advance in lock-step.

    Every :func:`sweep_decl` in the body becomes a member of one
    :class:`~eq1_pulse.models.sweeps.SweepGroup`, which occupies a single level of nesting and is
    emitted when the body ends. Members keep their own ``dtype``, ``unit`` and ``limits`` -- a
    voltage and a frequency routinely move together -- and must share a length.

    A group is *only* for independently declared sweeps that must advance together. A transform is
    implicitly lock-step with the sweeps it reads, so it needs no group and has none.

    Unlike :func:`~eq1_pulse.builder.core.sub_sequence`, a group is not a scope: its members are
    declared in the surrounding context and outlive the ``with`` block, exactly as they would had
    they been written as bare :func:`sweep_decl` calls.

    :yield: Nothing. The group is built from the body's declarations, so there is no object to
        hand out until the body has run.

    :raises RuntimeError: If not called within a sequence context, if a group is already open, or
        if the body declares fewer than two sweeps

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence():
            with sweep_group():
                sweep_decl("i_amp", "float", unit="mV")
                sweep_decl("drive_freq", "float", unit="MHz")

            var_decl("a", "float", unit="mV")
            var_decl("f", "float", unit="MHz")
            with for_(["a", "f"], [sweep("i_amp"), sweep("drive_freq")]):
                set_frequency("q0_drive", var("f"))
                play("q0_drive", square_pulse(duration="40ns", amplitude=var("a")))
    """
    context = _current_context("sweep_group()")
    if not _in_sequence(context):
        raise _not_a_sequence_context("sweep_group()")

    state = _get_state()
    if state.open_sweep_group is not None:
        raise RuntimeError(
            "sweep_group() cannot be nested: a group is one level of nesting, and sweeps in two "
            "groups are not in lock-step with each other."
        )

    state.sweep_group_counter += 1
    group_id = state.sweep_group_counter
    state.open_sweep_group = []
    state.open_sweep_group_id = group_id
    emitted = False
    try:
        yield
        specs = state.open_sweep_group or []
        if len(specs) < 2:
            raise RuntimeError(
                f"sweep_group() needs at least two sweep_decl() calls in its body, got {len(specs)}. "
                "A group of one is an ordinary sweep_decl()."
            )
        _add_to_sequence(context, SweepGroup(sweeps=specs))
        emitted = True
    finally:
        specs = state.open_sweep_group or []
        state.open_sweep_group = None
        state.open_sweep_group_id = 0
        if not emitted:
            # Nothing reached the sequence, so nothing may stay declared: a member left registered
            # by a group that raised would let a later sweep("x") validate against a sweep the
            # program does not declare.
            for spec in specs:
                _unregister_sweep(spec.name, group_id)


def _check_sweep_reads(node: Expression) -> None:
    """Check every sweep *node* reads: each declared, and all of one expression's in lock-step.

    Two of the module's three checks, run wherever an expression enters the builder.

    The walk is over *lock-step scopes* rather than over nodes. :class:`~.expressions.IndexExpr`
    and :class:`~.expressions.LenExpr` each take a sweep and return a scalar, so a sweep under one
    is not read by the enclosing tree at all -- ``sweep("d1")[i] + sweep("d2")[j]`` combines two
    scalars and is fine however the two sweeps are declared. Their operands are therefore scopes of
    their own, checked in turn, which is also what keeps the undeclared-sweep check honest for
    ``sweep("nope")[0]``.

    :param node: The root of the expression tree to check

    :raises RuntimeError: If a sweep is undeclared, or one scope reads sweeps that are neither the
        same sweep nor members of one group
    """
    scopes: list[Expression] = [node]
    while scopes:
        names: set[str] = set()
        stack: list[Expression] = [scopes.pop()]
        while stack:
            current = stack.pop()
            if isinstance(current, SweepExpr):
                names.add(current.sweep)
            elif isinstance(current, IndexExpr):
                # The operand opens a scope of its own; the indices are scalars in this one.
                scopes.append(current.operand)
                stack.extend(current.indices)
            elif isinstance(current, LenExpr):
                scopes.append(current.operand)
            elif isinstance(current, UnaryExpr | NotExpr):
                stack.append(current.rhs)
            elif isinstance(current, BinaryExpr | CompareExpr | LogicalExpr):
                stack.append(current.lhs)
                stack.append(current.rhs)
            elif isinstance(current, CallExpr):
                stack.extend(current.args)
        _check_lock_step(names)


def _lock_step_offenders(names: set[str]) -> tuple[str, str] | None:
    """Check that *names* are declared, and return the first pair that does not advance together.

    The rule both callers apply: sweeps advance together when they are the same sweep, or members of
    one :func:`sweep_group`. What differs is only what was found combining them, and so the message.

    :param names: The sweep names one lock-step scope reads

    :return: The offending pair, or :obj:`None` if every name advances with the others
    :raises RuntimeError: If a name is undeclared
    """
    ordered = sorted(names)
    for name in ordered:
        _check_sweep_declared(name)

    if len(ordered) < 2:
        return None

    first = ordered[0]
    group = _sweep_group_of(first)
    for other in ordered[1:]:
        if group is None or _sweep_group_of(other) != group:
            return first, other
    return None


def _check_lock_step(names: set[str]) -> None:
    """Check that the sweeps read by one expression are declared and advance together.

    :param names: The sweep names one lock-step scope reads

    :raises RuntimeError: If a name is undeclared, or two of them are neither the same sweep nor
        members of one :func:`sweep_group`
    """
    offenders = _lock_step_offenders(names)
    if offenders is None:
        return

    first, other = offenders
    raise RuntimeError(
        f"Sweeps '{first}' and '{other}' are read by one expression but do not advance "
        f"together. Only the same sweep, or sweeps declared side by side in one "
        f"sweep_group(), may be combined in a single expression. To combine sweeps from "
        f"different nesting levels, give each its own for_() and do the arithmetic on the "
        f"loop variables in the body."
    )


def _check_zipped_lock_step(items: Any) -> None:
    """Check that the sweeps a zipped loop iterates advance together.

    The same rule :func:`_check_lock_step` applies within one expression, applied *across* a zipped
    loop's items: one loop is one level of nesting, and a level has one length, so its items must
    read members of one group (plan section 7). Independently declared sweeps are two levels and
    belong in two nested loops -- the models cannot catch it, since neither item has a length until
    the program is invoked.

    :param items: The loop's already-validated items, one or a list of them

    :raises RuntimeError: If two items read sweeps that are neither the same sweep nor members of
        one :func:`sweep_group`
    """
    if not isinstance(items, list) or len(items) < 2:
        return

    names: set[str] = set()
    for item in items:
        if isinstance(item, ExprBase):
            names |= sweep_names_in(cast("Expression", item))

    offenders = _lock_step_offenders(names)
    if offenders is None:
        return

    first, other = offenders
    raise RuntimeError(
        f"Sweeps '{first}' and '{other}' are zipped by one for_() but do not advance together. "
        f"A zipped loop is a single level of nesting, so its items must read the same sweep, or "
        f"sweeps declared side by side in one sweep_group(). To iterate them independently, give "
        f"each its own for_() and nest the two loops."
    )


def _consume_sweeps(items: Any, consumer: str) -> None:
    """Record *consumer* as the loop iterating every sweep its items read.

    A loop consumes every sweep its ``items`` trees read, so an inline transform consumes its bases
    exactly as a bare reference does, and index iteration -- ``indices(len_(sweep("vg")))`` --
    consumes nothing, since a :class:`~.expressions.LenExpr` reads no sweep through itself.

    :param items: The loop's already-validated items, one or a list of them
    :param consumer: Description of the loop, for the error message a second consumer gets

    :raises RuntimeError: If any of those sweeps is already consumed by another loop
    """
    candidates = items if isinstance(items, list) else [items]
    names: set[str] = set()
    for item in candidates:
        if isinstance(item, ExprBase):
            names |= sweep_names_in(cast("Expression", item))

    for name in sorted(names):
        _consume_sweep(name, consumer)
