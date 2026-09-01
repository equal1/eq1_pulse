"""Sweep declarations: named lists of values a program is invoked over.

A sweep is the list-valued sibling of a parameter. :class:`~.data_ops.ParameterDecl` declares one
value supplied at submission time; :class:`SweepDecl` declares a *list* of them, and the program is
run once per item. Everything else is the same: the same provenance -- always caller-supplied, with
a ``default`` to fall back on -- the same lexical scoping, and the same ``dtype``/``shape``/``unit``
description of what the values are.

This module holds **declarations only**. Reading a sweep is an expression leaf, and a transform
of one is an ordinary expression over it; both live in :mod:`~.expressions`, so there is no
transform model here, no name to bind and no declaration operation for one. That split is what
keeps this module a leaf: it imports :mod:`~.basic_types`, :mod:`~.data_ops` and
:mod:`~.nd_array`, and none of the operation modules imports it back.

Two operations declare sweeps, and there is no third:

:class:`SweepDecl`
    one sweep, at top level.

:class:`SweepGroup`
    two or more sweeps advanced in lock-step, eq1lab's ``TogetherSweep`` flattened onto the
    declarations. It carries full :class:`SweepSpec` bodies rather than names, because members keep
    their own ``dtype``, ``unit`` and ``limits`` -- a voltage and a frequency routinely move
    together -- and a group is one object, so it occupies exactly one level of nesting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from .base_models import LeanModel
from .basic_types import LinSpace, OpBase, OperationDiscriminator, Range
from .data_ops import DataOpBase, ValueLimits, VariableDTypeType
from .identifier_str import IdentifierStr
from .nd_array import NumpyIterableArray

if TYPE_CHECKING:
    from .basic_types import LinSpaceLike, RangeLike
    from .nd_array import NumpyArrayLike

__all__ = (
    "SweepDecl",
    "SweepGroup",
    "SweepOp",
    "SweepSpec",
    "SweepValue",
    "SweepValueLike",
)


type SweepValue = LinSpace | Range | NumpyIterableArray
"""The values of a sweep: the list-valued counterpart of :data:`~.data_ops.SymbolValue`.

Its members are decidable by wire shape with no tag, exactly as :data:`~.data_ops.SymbolValue`'s
are -- ``{start, stop, num}`` is a :class:`~.basic_types.LinSpace`, ``{start, stop, step}`` a
:class:`~.basic_types.Range`, and a JSON array an array:

======================================  ======  ================================================
Wire                                    Size    For
======================================  ======  ================================================
``{start, stop, num}``                  O(1)    the common case -- an evenly spaced scan
``{start, stop, step}``                 O(1)    a scan specified by resolution rather than count
``[...]``                               O(n)    irregular, measured, or repeating items
======================================  ======  ================================================

:class:`~.basic_types.LinSpace` and :class:`~.basic_types.Range` are reused unchanged, and both are
explicitly unitless -- the unit is on the declaration, which is what :attr:`SweepSpec.unit`
continues.

:data:`~.nd_array.NumpyIterableArray` is the same set :mod:`~.control_flow` iterates over, imported
rather than restated now that it lives in :mod:`~.nd_array` -- a leaf module itself, so importing it
here does not cost this module its own leaf property.
"""

type SweepValueLike = LinSpaceLike | RangeLike | NumpyArrayLike
"""Acceptable input types for :data:`SweepValue`."""


class SweepSpec(LeanModel):
    """The body of a sweep declaration: everything about a sweep except its being an operation.

    Split out of :class:`SweepDecl` so :attr:`SweepGroup.sweeps` can hold specifications without
    repeating ``sweep_decl:`` on every member of a container that already says they are sweeps --
    :class:`~.basic_types.OpBase` lifts every operation to ``{op_type: payload}`` unconditionally,
    so a list of *operations* is a list of single-key wrappers.

    ``dtype``, ``shape`` and ``unit`` are restated here rather than inherited from
    :class:`~.data_ops.SymbolDeclBase`: that class is an :class:`~.basic_types.OpBase` descendant,
    and inheriting it is exactly the thing this split exists to avoid.
    """

    # numpy arrays are a `SweepValue` member, and pydantic needs to be told they are welcome.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: IdentifierStr
    """Name of the sweep. Must be a valid identifier."""
    dtype: VariableDTypeType
    """Data type of the sweep's items."""
    shape: tuple[int, ...] | None = None
    """The length the sweep's values must have, as a one-entry tuple, or :obj:`None` to accept any.

    Left unset -- the usual case, and the point of it being optional -- a sweep takes whatever
    length the caller supplies. It is a tuple rather than an :obj:`int` because it is the same
    ``shape`` :attr:`~.data_ops.SymbolDeclBase.shape` carries, describing the declared symbol as a
    whole, and a sweep's symbol is the list.
    """
    unit: str | None = None
    """Unit of the sweep's items. This is a string that represents the unit of measurement.

    Declared and never enforced, exactly as :attr:`~.data_ops.SymbolDeclBase.unit` is: the values
    are unitless on the wire, and it is the consuming framework that decides what ``"mV"`` means.
    """
    default: SweepValue | None = None
    """The values used if none are supplied at invocation, or :obj:`None` if the sweep is required."""
    limits: ValueLimits | None = None
    """Declared bounds on each of the sweep's items, or :obj:`None` if unbounded."""

    if TYPE_CHECKING:

        def __init__(  # noqa: D107
            self,
            *,
            name: str,
            dtype: VariableDTypeType,
            shape: tuple[int, ...] | None = None,
            unit: str | None = None,
            default: SweepValueLike | None = None,
            limits: ValueLimits | None = None,
            **data,
        ): ...


class SweepDecl(SweepSpec, DataOpBase):
    """Sweep declaration operation: one named list of values, supplied at invocation.

    :class:`SweepSpec` plus ``op_type`` and nothing else. This is the form used at top level; a
    member of a :class:`SweepGroup` is the bare specification.

    Sweep declarations are scoped to the surrounding context and its children, exactly as
    :class:`~.data_ops.ParameterDecl` is.
    """

    # Declared first, and it must stay first: `LeanModel` reads the first single-valued `Literal`
    # field as the discriminator and never elides it, and `OpBase` lifts it to the sole wire key.
    op_type: Literal["sweep_decl"] = "sweep_decl"
    """The operation type discriminator for sweep declarations. It is always "sweep_decl"."""

    if TYPE_CHECKING:

        def __init__(  # noqa: D107
            self,
            *,
            name: str,
            dtype: VariableDTypeType,
            shape: tuple[int, ...] | None = None,
            unit: str | None = None,
            default: SweepValueLike | None = None,
            limits: ValueLimits | None = None,
            **data,
        ): ...


class SweepGroup(OpBase):
    """Independent sweeps advanced in lock-step. Occupies one level of nesting.

    The declarations of eq1lab's ``TogetherSweep``: two or more sweeps whose items are consumed
    together, one item from each per iteration. Members are full :class:`SweepSpec` bodies rather
    than names, because each keeps its own ``dtype``, ``unit`` and ``limits``.

    A group is *only* for independently declared sweeps that must advance together. A transform is
    implicitly lock-step with the sweeps it reads, so it needs no group and has none.
    """

    op_type: Literal["sweep_group"] = "sweep_group"
    """The operation type discriminator for sweep groups. It is always "sweep_group"."""

    sweeps: list[SweepSpec] = Field(min_length=2)
    """The sweeps advanced together. A group of one is a :class:`SweepDecl`, so there are at least two."""

    @model_validator(mode="after")
    def _validate_default_lengths(self) -> Self:
        """Check that the members' defaults, where all of them are concrete, are the same length.

        Lock-step is a statement about the values actually advanced together, and those are the
        supplied ones -- so this checks the *defaults* only when every member has one, and leaves
        an invocation's own values to the invocation checker. Which expressions may read which
        sweeps needs declaration scope no field validator has, and is checked by the builder.

        :return: This group, unchanged.
        :raises ValueError: If every member declares a default and the defaults differ in length.
        """
        lengths: list[tuple[str, int]] = []
        for sweep in self.sweeps:
            if sweep.default is None:
                return self
            lengths.append((sweep.name, len(sweep.default)))

        if len({length for _, length in lengths}) > 1:
            raise ValueError(
                "sweeps advanced in lock-step must have defaults of equal length, got "
                + ", ".join(f"{name}: {length}" for name, length in lengths)
            )
        return self


type SweepOp = Annotated[SweepDecl | SweepGroup, OperationDiscriminator()]
"""Sweep operation type.

The two operations that declare sweeps, and there is no third: a transform is a value rather than a
declaration, so it has no operation of its own. Each is spelled as the single-key object
``{op_type: payload}`` -- ``{"sweep_decl": {...}}`` -- and
:class:`~.basic_types.OperationDiscriminator` selects the member by that sole key.
"""
