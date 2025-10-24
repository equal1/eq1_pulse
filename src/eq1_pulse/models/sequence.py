"""Module containing operation sequence models and related types for pulse sequencing.

This module defines the core classes and types needed for representing and
manipulating sequences of operations in pulse programming.

The timing of the operations in a sequence is implicit, scheduling is done by
earliest possible start time.
The same channel can not execute two Play/Record/Barrier operations at the same time, the only
exception being a Play and its corresponding Record (constituting a Measurement operation).
"""

# ruff: noqa: D107
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Annotated, overload

from pydantic import Discriminator

from .basic_types import LinSpace, OpBase, Range
from .channel_ops import ChannelOp
from .control_flow import ConditionalBase, IterationBase, RepetitionBase, SequenceBase
from .data_ops import DataOp
from .nd_array import NumpyArray

if TYPE_CHECKING:
    from .basic_types import LinSpaceLike, RangeLike
    from .nd_array import NumpyArrayLike
    from .reference_types import VariableRefLike

type DiscriminableOp = Annotated[ChannelOp | DataOp | Repetition | Iteration | Conditional, Discriminator("op_type")]
"""All operations that can be discriminated by the "op_type" field."""

type OpSequenceItem = DiscriminableOp | OpSequence
"""A type alias for an operation sequence item."""


class OpSequence(SequenceBase[OpSequenceItem]):
    """A sequence of operation items that can be serialized as a list.

    This class represents an ordered collection of operation sequence items that
    will be serialized as a list when converted to JSON or other formats.

    :ivar items: List of operation sequence items
    """

    if TYPE_CHECKING:  # mypy food
        items: list[OpSequenceItem]

        @overload
        def __init__(self, items: Iterable[OpSequenceItem], **data): ...

        @overload
        def __init__(self, **data): ...

        def __init__(self, *args, **data): ...


if TYPE_CHECKING:
    type OpSequenceLike = Iterable[OpSequenceItem] | OpSequence


class Repetition(RepetitionBase[OpSequence]):
    """Represents a repeated sequence of operations.

    :ivar op_type: Operation type, always "repeat"
    :ivar count: Number of times to repeat the sequence
    :ivar body: The sequence of operations to repeat
    """

    if TYPE_CHECKING:

        def __init__(self, /, *, count: int, body: OpSequenceLike, **data): ...


class Iteration(IterationBase[OpSequence]):
    """Represents an iteration over a sequence of operations.

    :ivar op_type: Operation type, always "for"
    :ivar var: The variable reference for the iterated value.
    :ivar items: The range or array over which to iterate.
    :ivar body: The sequence of operations to execute in each iteration
    """

    if TYPE_CHECKING:

        def __init__(
            self,
            /,
            *,
            var: VariableRefLike | list[VariableRefLike],
            items=LinSpaceLike
            | RangeLike
            | NumpyArrayLike
            | list[str]
            | list[LinSpaceLike | RangeLike | NumpyArrayLike | list[str]],
            body: OpSequenceLike,
            **data,
        ): ...


class Conditional(ConditionalBase[OpSequence]):
    """Represents a conditional sequence of operations.

    :ivar op_type: Operation type, always "if"
    :ivar var: The variable reference for the condition.
    :ivar body: The sequence of operations to execute if the condition is met
    """

    if TYPE_CHECKING:

        def __init__(self, /, *, var: VariableRefLike, body: OpSequenceLike, **data): ...


__all__ = (
    "Conditional",
    "DiscriminableOp",
    "Iteration",
    "LinSpace",
    "NumpyArray",
    "OpBase",
    "OpSequence",
    "OpSequenceItem",
    "Range",
    "Repetition",
)
