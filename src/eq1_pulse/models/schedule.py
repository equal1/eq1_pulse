"""Scheduling abstractions for quantum operations and time management.

Provides classes and utilities for scheduling quantum operations with precise
timing control, including:

- Time references and relative timing
- Operation scheduling and sequencing
- Control flow constructs like loops and conditionals
- Channel and data operation scheduling

"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal, TypedDict, Unpack, overload

from pydantic import ConfigDict, Discriminator, PlainSerializer

from .base_models import FrozenModel, LeanModel
from .basic_types import Time
from .channel_ops import ChannelOp
from .control_flow import ConditionalBase, IterationBase, RepetitionBase, SequenceBase
from .data_ops import DataOp

if TYPE_CHECKING:
    from .basic_types import LinSpaceLike, RangeLike, TimeDict
    from .nd_array import NumpyArrayLike
    from .reference_types import VariableRefLike


__all__ = (
    "RefPt",
    "RelTime",
    "SchedConditional",
    "SchedIteration",
    "SchedRepetition",
    "Schedulable",
    "Schedule",
    "ScheduledOperation",
)


class RelTime(Time):
    """A subclass of Time representing relative time between Schedulables."""

    if TYPE_CHECKING:

        @overload
        def __init__(self, _: Literal[0], /): ...

        @overload
        def __init__(self, /, *, s: float): ...

        @overload
        def __init__(self, /, *, ms: float): ...

        @overload
        def __init__(self, /, *, us: float): ...

        @overload
        def __init__(self, /, *, ns: int): ...

        def __init__(self, /, *args, **data): ...  # noqa: D107


class RefPt(StrEnum):
    """An enumeration of reference points for Schedulables.

    These represent the alignment points of the existing and the newly inserted schedulable.
    """

    Start = "start"
    End = "end"
    Center = "center"


type DiscriminableSchedulableOp = Annotated[
    ChannelOp | DataOp | SchedRepetition | SchedIteration | SchedConditional, Discriminator("op_type")
]
"""Schedulable operations that can be discriminated by the "op" field."""

type Schedulable = DiscriminableSchedulableOp | Schedule
"""A type representing a scheduled operation or a sub-schedule."""

if TYPE_CHECKING:
    type RelTimeLike = RelTime | Literal[0] | TimeDict
    type RefPtLike = RefPt | Literal["start", "end", "center"]

    class OpScheduleDict(TypedDict, total=False):
        name: str | None
        rel_time: RelTimeLike | None
        ref_op: str | None
        ref_pt: RefPtLike | None
        ref_pt_new: RefPtLike | None


class ScheduledOperation(LeanModel, FrozenModel):
    """A class representing a scheduled operation with timing and reference information.

    :param name: Optional name for the operation
    :param rel_time: Relative time from the reference point
    :param ref_op: Name of the reference operation
    :param ref_pt: Reference point on the reference operation
    :param ref_pt_new: Reference point on the new operation
    :param op: The schedulable operation
    """

    name: str | None = None
    rel_time: RelTime | None = None
    ref_op: str | None = None
    ref_pt: Annotated[RefPt, PlainSerializer(str)] | None = None
    ref_pt_new: Annotated[RefPt, PlainSerializer(str)] | None = None

    op: Schedulable

    def __init__(self, op: Schedulable, **data: Unpack[OpScheduleDict]):  # noqa: D107
        super().__init__(op=op, **data)  # type: ignore[call-arg, misc]


class Schedule(SequenceBase[ScheduledOperation]):
    """A collection of scheduled operations."""

    def __init__(self, items: Iterable[ScheduledOperation] = (), **data):  # noqa: D107
        super().__init__(items=items, **data)

    def add_op(self, op: Schedulable, **data: Unpack[OpScheduleDict]) -> ScheduledOperation:
        """Add a scheduled operation to the schedule.

        :param op: The operation to add
        :param name: Optional name for the operation. A unique name will be generated if not provided.
        :param rel_time: Relative time from the reference point
        :type rel_time: RelTime
        :param ref_op: Reference operation name
        :type ref_op: str | None
        :param ref_pt: Reference point on the reference operation
        :type ref_pt: RefPt | None
        :param ref_pt_new: Reference point on the new operation
        :type ref_pt_new: RefPt | None
        """
        item = ScheduledOperation(op=op, **data)
        self.items.append(item)
        return item

    @staticmethod
    def op(op: Schedulable, **data: Unpack[OpScheduleDict]) -> ScheduledOperation:
        """Create a scheduled operation.

        :param op: The operation to schedule
        :param name: Optional name for the operation
        :param rel_time: Relative time from the reference point
        :type rel_time: RelTime
        :param ref_op: Reference operation name
        :type ref_op: str | None
        :param ref_pt: Reference point on the reference operation
        :type ref_pt: RefPt | None
        :param ref_pt_new: Reference point on the new operation
        :type ref_pt_new: RefPt | None
        """
        return ScheduledOperation(op=op, **data)

    model_config = ConfigDict(extra="forbid")


if TYPE_CHECKING:
    type ScheduleLike = Schedule | Iterable[ScheduledOperation]


class SchedRepetition(RepetitionBase[Schedule]):
    """A class representing repeated schedule embedded in a schedule."""

    if TYPE_CHECKING:

        def __init__(self, /, *, count: int, body: ScheduleLike, **data):  # noqa: D107
            ...


class SchedIteration(IterationBase[Schedule]):
    """A class representing an iterated schedule in a schedule."""

    if TYPE_CHECKING:

        def __init__(  # noqa: D107
            self,
            /,
            *,
            var: VariableRefLike | list[VariableRefLike],
            items=LinSpaceLike
            | RangeLike
            | NumpyArrayLike
            | list[str]
            | list[LinSpaceLike | RangeLike | NumpyArrayLike | list[str]],
            body: ScheduleLike,
            **data,
        ): ...


class SchedConditional(ConditionalBase[Schedule]):
    """A class representing a conditional embedded in a schedule."""

    if TYPE_CHECKING:

        def __init__(self, /, *, var: VariableRefLike, body: ScheduleLike, **data):  # noqa: D107
            ...
