"""Tests for the visitor infrastructure.

This module contains tests for the visitor pattern implementation
and example visitors.
"""

from eq1_pulse.models import Duration, OpSequence, Play, Schedule, Wait
from eq1_pulse.models.pulse_types import ExternalPulse
from eq1_pulse.visitor.examples import ChannelCollectorSchedule, ChannelCollectorSequence


class TestChannelCollectorSequence:
    """Tests for the ChannelCollectorSequence visitor."""

    def test_single_play(self):
        """Test collecting channels from a single Play operation."""
        seq = OpSequence(
            [
                Play(
                    "ch1",
                    ExternalPulse("pulses.gaussian", duration="100e-9s", amplitude="1.0V", params=dict(sigma="10e-9")),
                ),
            ]
        )

        collector = ChannelCollectorSequence()
        channels = collector.visit_OpSequence(seq)

        assert channels == {"ch1"}

    def test_multiple_channels(self):
        """Test collecting channels from multiple operations."""
        seq = OpSequence(
            [
                Play(
                    "ch1",
                    ExternalPulse("pulses.gaussian", duration="100e-9s", amplitude="1.0V", params=dict(sigma=10e-9)),
                ),
                Play(
                    "ch2",
                    ExternalPulse("pulses.gaussian", duration="100e-9s", amplitude="1.0V", params=dict(sigma=10e-9)),
                ),
                Play(
                    "ch1",
                    ExternalPulse("pulses.gaussian", duration="100e-9s", amplitude="1.0V", params=dict(sigma=10e-9)),
                ),  # Duplicate
            ]
        )

        collector = ChannelCollectorSequence()
        channels = collector.visit_OpSequence(seq)

        assert channels == {"ch1", "ch2"}

    def test_wait_multiple_channels(self):
        """Test collecting channels from Wait operation with multiple channels."""
        seq = OpSequence(
            [
                Wait("ch1", "ch2", "ch3", duration=Duration(s=100e-9)),
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
                Schedule.op(
                    Play(
                        "ch1",
                        ExternalPulse(
                            "pulses.gaussian", duration="100e-9s", amplitude="1.0V", params=dict(sigma=10e-9)
                        ),
                    )
                )
            ]
        )

        collector = ChannelCollectorSchedule()
        channels = collector.visit_Schedule(sched)

        assert channels == {"ch1"}

    def test_multiple_channels(self):
        """Test collecting channels from multiple operations in schedule."""
        sched = Schedule(
            [
                Schedule.op(
                    Play(
                        "ch1",
                        ExternalPulse(
                            "pulses.gaussian", duration="100e-9s", amplitude="1.0V", params=dict(sigma=10e-9)
                        ),
                    )
                ),
                Schedule.op(
                    Play(
                        "ch2",
                        ExternalPulse(
                            "pulses.gaussian", duration="100e-9s", amplitude="1.0V", params=dict(sigma=10e-9)
                        ),
                    )
                ),
            ]
        )

        collector = ChannelCollectorSchedule()
        channels = collector.visit_Schedule(sched)

        assert channels == {"ch1", "ch2"}
