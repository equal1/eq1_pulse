"""Module containing operation sequence models and related types for pulse sequencing.

This module defines the core classes and types needed for representing and
manipulating sequences of operations in pulse programming.

The timing of the operations in a sequence is implicit, scheduling is done by
earliest possible start time.
The same channel can not execute two Play/Record/Barrier operations at the same time, the only
exception being a Play and its corresponding Record (constituting a Measurement operation).

Because scheduling is per-channel, operations on different channels already have
independent timelines; a Play and Record on different channels are never "linked" by
the model, and nothing in a sequence guarantees they start in lock-step. This only
becomes an actual concern for the same-channel Play/Record exception above, where the
two operations must be treated as one atomic measurement rather than two ops that
happen to share a channel and start time.

:class:`~.channel_ops.Wait` is the more primitive counterpart of OpenQASM's multi-resource
``delay``, which conflates a barrier with a delay. The composite decomposes exactly:

.. code-block:: text

    import:   delay[d] a, b;   ->   barrier(a, b) ; wait(a, b, d)
    export:   wait(a, b, d)    ->   delay[d] a;  delay[d] b;

See :class:`~.channel_ops.Wait` for why both identities hold.
"""

# ruff: noqa: D107
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal, overload

from pydantic import Discriminator

from .basic_types import LinSpace, OpBase, Range
from .channel_ops import ChannelOp
from .control_flow import ConditionalBase, IterationBase, RepetitionBase, SequenceBase
from .data_ops import DataOp
from .external_block import ExternalBlock
from .nd_array import NumpyArray

if TYPE_CHECKING:
    from .basic_types import LinSpaceLike, RangeLike
    from .nd_array import NumpyArrayLike
    from .reference_types import SymbolRefLike, VariableRefLike

type DiscriminableOp = Annotated[
    ChannelOp | DataOp | ExternalBlock | Repetition | Iteration | Conditional, Discriminator("op_type")
]
"""All operations that can be discriminated by the "op_type" field."""

type OpSequenceItem = DiscriminableOp | OpSequence
"""A type alias for an operation sequence item."""


class OpSequence(SequenceBase[OpSequenceItem]):
    """A sequence of operation items that can be serialized as a list.

    This class represents an ordered collection of operation sequence items that
    will be serialized as a list when converted to JSON or other formats.

    :ivar items: List of operation sequence items
    """

    # Lets eq1_pulse.builder._state detect context kind without importing this class.
    _context_kind: ClassVar[Literal["sequence"]] = "sequence"

    if TYPE_CHECKING:  # mypy food
        items: list[OpSequenceItem]
        """List of operation sequence items."""

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

    _context_kind: ClassVar[Literal["sequence"]] = "sequence"

    if TYPE_CHECKING:

        def __init__(self, /, *, count: int, body: OpSequenceLike, **data): ...


class Iteration(IterationBase[OpSequence]):
    """Represents an iteration over a sequence of operations.

    :ivar op_type: Operation type, always "for"
    :ivar var: The variable reference for the iterated value.
    :ivar items: The range or array over which to iterate.
    :ivar body: The sequence of operations to execute in each iteration
    """

    _context_kind: ClassVar[Literal["sequence"]] = "sequence"

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

    _context_kind: ClassVar[Literal["sequence"]] = "sequence"

    if TYPE_CHECKING:

        def __init__(self, /, *, var: SymbolRefLike, body: OpSequenceLike, **data): ...


__all__ = (
    "Conditional",
    "DiscriminableOp",
    "ExternalBlock",
    "Iteration",
    "LinSpace",
    "NumpyArray",
    "OpBase",
    "OpSequence",
    "OpSequenceItem",
    "Range",
    "Repetition",
)
