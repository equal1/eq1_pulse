"""Example visitor implementations demonstrating the visitor infrastructure.

This module provides concrete visitor implementations that can be used as
examples or utilities for working with pulse models.
"""

# ruff: noqa: D102
from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ScheduleVisitor, SequenceVisitor

if TYPE_CHECKING:
    from ..models.channel_ops import (
        Barrier,
        CompensateDC,
        Play,
        Record,
        SetFrequency,
        SetPhase,
        ShiftFrequency,
        ShiftPhase,
        Trace,
        Wait,
    )
    from ..models.reference_types import ChannelRef
    from ..models.schedule import (
        SchedConditional,
        SchedIteration,
        SchedRepetition,
        Schedule,
        ScheduledOperation,
    )
    from ..models.sequence import Conditional, Iteration, OpSequence, Repetition

__all__ = (
    "ChannelCollectorSchedule",
    "ChannelCollectorSequence",
)


class ChannelCollectorSequence(SequenceVisitor[set[str]]):
    """Visitor that collects all unique channel names used in a sequence.

    This visitor traverses a sequence and collects the names of all channels
    referenced in channel operations.

    Example
    -------

    .. code-block:: python

        from eq1_pulse.models import OpSequence, Play
        from eq1_pulse.models.pulse_types import Gaussian
        from eq1_pulse.visitor.examples import ChannelCollectorSequence

        seq = OpSequence([
            Play("ch1", Gaussian(duration=100e-9, sigma=10e-9)),
            Play("ch2", Gaussian(duration=100e-9, sigma=10e-9)),
        ])

        collector = ChannelCollectorSequence()
        channels = collector.visit(seq)
        print(channels)  # {'ch1', 'ch2'}
    """

    def __init__(self):
        """Initialize the channel collector."""
        self.channels: set[str] = set()

    def _add_channel(self, channel: ChannelRef) -> set[str]:
        """Add a channel reference to the collection.

        :param channel: The channel reference to add

        :return: The current set of channels
        """
        self.channels.add(channel.channel)
        return self.channels.copy()

    def _add_channels(self, channels: list[ChannelRef]) -> set[str]:
        """Add multiple channel references to the collection.

        :param channels: The channel references to add

        :return: The current set of channels
        """
        for channel in channels:
            self.channels.add(channel.channel)
        return self.channels.copy()

    # Channel operations
    def visit_Play(self, node: Play) -> set[str]:
        return self._add_channel(node.channel)

    def visit_Wait(self, node: Wait) -> set[str]:
        return self._add_channels(node.channels)

    def visit_Barrier(self, node: Barrier) -> set[str]:
        return self._add_channels(node.channels)

    def visit_SetFrequency(self, node: SetFrequency) -> set[str]:
        return self._add_channel(node.channel)

    def visit_ShiftFrequency(self, node: ShiftFrequency) -> set[str]:
        return self._add_channel(node.channel)

    def visit_SetPhase(self, node: SetPhase) -> set[str]:
        return self._add_channel(node.channel)

    def visit_ShiftPhase(self, node: ShiftPhase) -> set[str]:
        return self._add_channel(node.channel)

    def visit_Record(self, node: Record) -> set[str]:
        return self._add_channel(node.channel)

    def visit_Trace(self, node: Trace) -> set[str]:
        return self._add_channel(node.channel)

    def visit_CompensateDC(self, node: CompensateDC) -> set[str]:
        return self._add_channel(node.channel)

    # Data operations don't use channels
    def generic_visit(self, node) -> set[str]:
        return self.channels.copy()

    def combine_sequence_results(self, node: OpSequence, results: list[set[str]]) -> set[str]:
        return self.channels.copy()

    def combine_repetition(self, node: Repetition, body_result: set[str]) -> set[str]:
        return self.channels.copy()

    def combine_iteration(self, node: Iteration, body_result: set[str]) -> set[str]:
        return self.channels.copy()

    def combine_conditional(self, node: Conditional, body_result: set[str]) -> set[str]:
        return self.channels.copy()


class ChannelCollectorSchedule(ScheduleVisitor[set[str]]):
    """Visitor that collects all unique channel names used in a schedule.

    This visitor traverses a schedule and collects the names of all channels
    referenced in channel operations.

    Example
    -------

    .. code-block:: python

        from eq1_pulse.models import Schedule, Play
        from eq1_pulse.models.pulse_types import Gaussian
        from eq1_pulse.visitor.examples import ChannelCollectorSchedule

        sched = Schedule([
            Schedule.op(Play("ch1", Gaussian(duration=100e-9, sigma=10e-9))),
            Schedule.op(Play("ch2", Gaussian(duration=100e-9, sigma=10e-9))),
        ])

        collector = ChannelCollectorSchedule()
        channels = collector.visit(sched)
        print(channels)  # {'ch1', 'ch2'}
    """

    def __init__(self):
        """Initialize the channel collector."""
        self.channels: set[str] = set()

    def _add_channel(self, channel: ChannelRef) -> set[str]:
        """Add a channel reference to the collection.

        :param channel: The channel reference to add

        :return: The current set of channels
        """
        self.channels.add(channel.channel)
        return self.channels.copy()

    def _add_channels(self, channels: list[ChannelRef]) -> set[str]:
        """Add multiple channel references to the collection.

        :param channels: The channel references to add

        :return: The current set of channels
        """
        for channel in channels:
            self.channels.add(channel.channel)
        return self.channels.copy()

    # Channel operations
    def visit_Play(self, node: Play) -> set[str]:
        return self._add_channel(node.channel)

    def visit_Wait(self, node: Wait) -> set[str]:
        return self._add_channels(node.channels)

    def visit_Barrier(self, node: Barrier) -> set[str]:
        return self._add_channels(node.channels)

    def visit_SetFrequency(self, node: SetFrequency) -> set[str]:
        return self._add_channel(node.channel)

    def visit_ShiftFrequency(self, node: ShiftFrequency) -> set[str]:
        return self._add_channel(node.channel)

    def visit_SetPhase(self, node: SetPhase) -> set[str]:
        return self._add_channel(node.channel)

    def visit_ShiftPhase(self, node: ShiftPhase) -> set[str]:
        return self._add_channel(node.channel)

    def visit_Record(self, node: Record) -> set[str]:
        return self._add_channel(node.channel)

    def visit_Trace(self, node: Trace) -> set[str]:
        return self._add_channel(node.channel)

    def visit_CompensateDC(self, node: CompensateDC) -> set[str]:
        return self._add_channel(node.channel)

    # Data operations don't use channels
    def generic_visit(self, node) -> set[str]:
        return self.channels.copy()

    def combine_schedule_results(self, node: Schedule, results: list[set[str]]) -> set[str]:
        return self.channels.copy()

    def combine_scheduled_operation(self, node: ScheduledOperation, op_result: set[str]) -> set[str]:
        return op_result

    def combine_sched_repetition(self, node: SchedRepetition, body_result: set[str]) -> set[str]:
        return self.channels.copy()

    def combine_sched_iteration(self, node: SchedIteration, body_result: set[str]) -> set[str]:
        return self.channels.copy()

    def combine_sched_conditional(self, node: SchedConditional, body_result: set[str]) -> set[str]:
        return self.channels.copy()
