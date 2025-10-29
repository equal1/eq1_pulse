"""Tests for visitor examples."""

from eq1_pulse.models import OpSequence, Play, Schedule, Wait
from eq1_pulse.models.basic_types import Amplitude, Duration
from eq1_pulse.models.pulse_types import SquarePulse
from eq1_pulse.visitor.examples import ChannelCollectorSchedule, ChannelCollectorSequence


class TestChannelCollectorSequence:
    """Tests for the ChannelCollectorSequence visitor."""

    def test_single_play(self):
        """Test collecting channels from a single Play operation."""
        seq = OpSequence(
            [
                Play("ch1", SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0))),
            ]
        )

        collector = ChannelCollectorSequence()
        channels = collector.visit_OpSequence(seq)

        assert channels == {"ch1"}

    def test_multiple_channels(self):
        """Test collecting channels from multiple operations."""
        seq = OpSequence(
            [
                Play("ch1", SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0))),
                Play("ch2", SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0))),
                Play("ch1", SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0))),  # Duplicate
            ]
        )

        collector = ChannelCollectorSequence()
        channels = collector.visit_OpSequence(seq)

        assert channels == {"ch1", "ch2"}

    def test_wait_multiple_channels(self):
        """Test collecting channels from Wait operation with multiple channels."""
        seq = OpSequence(
            [
                Wait("ch1", "ch2", "ch3", duration=Duration(ns=100)),
            ]
        )

        collector = ChannelCollectorSequence()
        channels = collector.visit_OpSequence(seq)

        assert channels == {"ch1", "ch2", "ch3"}


class TestChannelCollectorSchedule:
    """Tests for the ChannelCollectorSchedule visitor."""

    def test_single_play(self):
        """Test collecting channels from a single Play operation in schedule."""
        sched = Schedule(
            [
                Schedule.op(Play("ch1", SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0)))),
            ]
        )

        collector = ChannelCollectorSchedule()
        channels = collector.visit_Schedule(sched)

        assert channels == {"ch1"}

    def test_multiple_channels(self):
        """Test collecting channels from multiple operations in schedule."""
        sched = Schedule(
            [
                Schedule.op(Play("ch1", SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0)))),
                Schedule.op(Play("ch2", SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0)))),
            ]
        )

        collector = ChannelCollectorSchedule()
        channels = collector.visit_Schedule(sched)

        assert channels == {"ch1", "ch2"}
