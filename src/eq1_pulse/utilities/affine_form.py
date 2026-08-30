"""Recognise the affine subset of sweep-valued expressions, for consumers that can transport it.

An affine transform of a compact base is compact::

    scale * LinSpace(start, stop, num) + offset
        == LinSpace(scale*start + offset, scale*stop + offset, num)

and so is a linear combination of bases of equal length -- which is exactly what a
:class:`~eq1_pulse.models.sweeps.SweepGroup` guarantees, and why the sweeps read by one expression
must be lock-step. :func:`affine_form` recognises a tree of that shape and hands back the
``sum(scale_i * sweep_i) + offset`` decomposition, so a generator can upload three numbers instead of
one float per item.

**A :obj:`None` result is correct and common, and it is not a failure.** It means *evaluate this
one elementwise*: walk the tree once per item and send the values. ``sweep("amp") * sweep("scale")``
is a legal, ordinary, elementwise product that no linear combination describes; so are every
:class:`~eq1_pulse.models.expressions.CallExpr`, every comparison, and ``%``. A consumer that never
calls this module and always evaluates elementwise is correct everywhere; one that calls it is
cheaper on the subset where the answer is not :obj:`None`.

Advisory, like every other checker in this package: nothing in ``models/`` or ``builder/`` calls it,
no validator runs it, and it neither evaluates nor simplifies what it returns. Scales and offsets
come back as :data:`~eq1_pulse.models.expressions.Expression` trees because they may read externals
that have no value until invocation -- the scale of ``sweep("d") * ext("vg.m11")`` is
``{"symbol": {"ext": "vg.m11"}}`` -- and literal arithmetic is left unfolded for the same reason it
is left unevaluated: this function decomposes, and a consumer that wants numbers evaluates.

Subtrees of the input are shared with the result rather than copied, so the decomposition of a tree
that is later mutated is stale. Nothing in the IR mutates an expression in place.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.expressions import BinaryExpr, Expression, LiteralExpr, SweepExpr, UnaryExpr, sweep_names_in

__all__ = ("AffineForm", "affine_form")


@dataclass(frozen=True)
class AffineForm:
    """The decomposition of an expression into ``sum(scale_i * sweep_i) + offset``.

    A plain frozen dataclass rather than a model: it is the *result of an analysis*, never a part of
    a program, so it has no wire form to keep and nothing validates it.
    """

    terms: dict[str, Expression]
    """The scale each sweep is read with, keyed by sweep name.

    One entry per **distinct** sweep, whatever the tree's shape: ``sweep("a") + sweep("a")`` is one
    term whose scale is the sum of the two, not two entries. Empty when the tree reads no sweep at
    all, which is the honest decomposition of a rank-0 tree.
    """
    offset: Expression
    """What is added once, independently of the item: the whole rank-0 part of the tree.

    :class:`~eq1_pulse.models.expressions.IndexExpr` and
    :class:`~eq1_pulse.models.expressions.LenExpr` land here, sweep and all, because both produce a
    scalar however deep a sweep sits inside them.
    """


@dataclass(frozen=True)
class _Partial:
    """A decomposition mid-walk, with its implicit values still implicit.

    A scale of :obj:`None` is an untouched sweep -- scale one -- and an offset of :obj:`None` is one
    nothing has been added to yet. Keeping both implicit until :func:`affine_form` materialises them
    is what stops ``sweep("vg") * 2`` coming back with the scale ``1 * 2`` and the offset ``0 * 2``:
    the recogniser writes no node for arithmetic the author did not write. It is *not* folding --
    the arithmetic the author did write is left exactly as they wrote it.
    """

    terms: dict[str, Expression | None]
    """The scale each sweep is read with, or :obj:`None` for an implicit scale of one."""
    offset: Expression | None
    """What is added once, or :obj:`None` if nothing has been."""


def _explicit(scale: Expression | None) -> Expression:
    """Return *scale*, or the literal one that an implicit scale stands for.

    :param scale: A scale from a :class:`_Partial`, possibly implicit
    :return: The same scale, spelled out
    """
    return LiteralExpr(value=1) if scale is None else scale


def _negated(form: _Partial) -> _Partial:
    """Return *form* with every scale and its offset negated.

    :param form: The decomposition to negate
    :return: The decomposition of ``-form``
    """
    return _Partial(
        terms={name: UnaryExpr(unary_op="-", rhs=_explicit(scale)) for name, scale in form.terms.items()},
        offset=None if form.offset is None else UnaryExpr(unary_op="-", rhs=form.offset),
    )


def _summed(left: _Partial, right: _Partial) -> _Partial:
    """Return the decomposition of ``left + right``, canonicalised by sweep name.

    A sweep read by both sides yields **one** term whose scale is the sum of the two scales, which
    is the canonicalisation this module exists to perform: a consumer wants one scale per sweep, and
    a tree is free to read the same sweep twice.

    :param left: The left decomposition
    :param right: The right decomposition
    :return: Their sum
    """
    terms = dict(left.terms)
    for name, scale in right.terms.items():
        if name in terms:
            terms[name] = BinaryExpr(binary_op="+", lhs=_explicit(terms[name]), rhs=_explicit(scale))
        else:
            terms[name] = scale
    if left.offset is None:
        offset = right.offset
    elif right.offset is None:
        offset = left.offset
    else:
        offset = BinaryExpr(binary_op="+", lhs=left.offset, rhs=right.offset)
    return _Partial(terms=terms, offset=offset)


def _scaled(form: _Partial, factor: Expression) -> _Partial:
    """Return the decomposition of ``form * factor``, for a rank-0 *factor*.

    :param form: The decomposition being scaled
    :param factor: The rank-0 tree multiplying it
    :return: The scaled decomposition
    """
    return _Partial(
        terms={
            name: factor if scale is None else BinaryExpr(binary_op="*", lhs=scale, rhs=factor)
            for name, scale in form.terms.items()
        },
        offset=None if form.offset is None else BinaryExpr(binary_op="*", lhs=form.offset, rhs=factor),
    )


def _divided(form: _Partial, divisor: Expression) -> _Partial:
    """Return the decomposition of ``form / divisor``, for a rank-0 *divisor*.

    :param form: The decomposition being divided
    :param divisor: The rank-0 tree dividing it
    :return: The divided decomposition
    """
    return _Partial(
        terms={
            name: BinaryExpr(binary_op="/", lhs=_explicit(scale), rhs=divisor) for name, scale in form.terms.items()
        },
        offset=None if form.offset is None else BinaryExpr(binary_op="/", lhs=form.offset, rhs=divisor),
    )


def _recognise_binary(expression: BinaryExpr) -> _Partial | None:
    """Decompose a sweep-reading :class:`~eq1_pulse.models.expressions.BinaryExpr`, or fail.

    :param expression: The node to decompose, known to read a sweep
    :return: Its decomposition, or :obj:`None` if it is not affine
    """
    lhs, rhs = expression.lhs, expression.rhs
    if expression.binary_op in {"+", "-"}:
        left = _recognise(lhs)
        right = _recognise(rhs)
        if left is None or right is None:
            return None
        return _summed(left, right if expression.binary_op == "+" else _negated(right))
    if expression.binary_op == "*":
        # One side must be rank-0 to be a scale; a product of two sweeps is elementwise and has no
        # linear combination describing it.
        if not sweep_names_in(lhs):
            scaled = _recognise(rhs)
            return None if scaled is None else _scaled(scaled, lhs)
        if not sweep_names_in(rhs):
            scaled = _recognise(lhs)
            return None if scaled is None else _scaled(scaled, rhs)
        return None
    if expression.binary_op == "/":
        # Only a sweep divided by a scalar: a scalar over a sweep is not affine in the sweep.
        if sweep_names_in(rhs):
            return None
        divided = _recognise(lhs)
        return None if divided is None else _divided(divided, rhs)
    return None  # "%" -- elementwise, and not affine.


def _recognise(expression: Expression) -> _Partial | None:
    """Decompose *expression*, leaving implicit scales and offsets implicit.

    Recursive, and safe to be: a tree that has validated is at most
    :data:`~eq1_pulse.models.expressions.MAX_EXPRESSION_DEPTH` levels deep.

    :param expression: The tree to decompose
    :return: Its decomposition, or :obj:`None` if it is not affine
    """
    if not sweep_names_in(expression):
        # The whole rank-0 part of a tree is offset, at any depth: literals, symbols, calls,
        # comparisons, and both of the nodes that take a sweep and give back a scalar.
        return _Partial(terms={}, offset=expression)
    if isinstance(expression, SweepExpr):
        return _Partial(terms={expression.sweep: None}, offset=None)
    if isinstance(expression, UnaryExpr):
        # Negation is the only unary operator.
        inner = _recognise(expression.rhs)
        return None if inner is None else _negated(inner)
    if isinstance(expression, BinaryExpr):
        return _recognise_binary(expression)
    # Everything left reads a sweep through a node no linear combination survives: a call, a
    # comparison, or a boolean connective.
    return None


def affine_form(expression: Expression) -> AffineForm | None:
    """Decompose *expression* into ``sum(scale_i * sweep_i) + offset``, if it has that shape.

    Recognised, and nothing else: a bare sweep; ``+`` and ``-`` of two recognisable operands, or of
    one and a rank-0 tree; ``*`` of a recognisable operand and a rank-0 tree, either way round; ``/``
    of a recognisable operand by a rank-0 tree, never the reverse; and unary ``-``. A tree reading no
    sweep decomposes to no terms and an offset of itself.

    Everything else is :obj:`None`, which is a normal answer meaning *evaluate this elementwise* --
    see the module docstring. Nothing is evaluated or folded here: ``sweep("a") / 2`` comes back with
    the scale ``1 / 2`` as a tree, because a scale may equally be ``ext("vg.m11")``, which has no
    value until the program is invoked.

    :param expression: The tree to decompose, sweep-valued or not
    :return: The decomposition, or :obj:`None` if *expression* is not affine in the sweeps it reads

    Examples

    .. code-block:: python

        from eq1_pulse.builder import ext, sweep
        from eq1_pulse.utilities.affine_form import affine_form

        form = affine_form((sweep("detuning") * ext("vg.m11") + ext("vg.o1")).unwrap())
        assert form is not None
        form.terms  # {"detuning": <ext vg.m11>}
        form.offset  # <ext vg.o1>
    """
    partial = _recognise(expression)
    if partial is None:
        return None
    return AffineForm(
        terms={name: _explicit(scale) for name, scale in partial.terms.items()},
        offset=LiteralExpr(value=0) if partial.offset is None else partial.offset,
    )
