"""Tests for the visitor infrastructure."""

from eq1_pulse.models import Amplitude, ChannelRef, Duration
from eq1_pulse.models.channel_ops import Play, Wait
from eq1_pulse.models.pulse_types import SquarePulse
from eq1_pulse.models.sequence import OpSequence, Repetition
from eq1_pulse.visitor.examples import ChannelCollectorSequence


def test_channel_collector_simple_sequence():
    """Test that ChannelCollector correctly identifies channels in a simple sequence."""
    ch1 = ChannelRef("qubit_0")
    ch2 = ChannelRef("qubit_1")
    us = Duration(us=1)
    V = Amplitude(V=1.0)

    seq = OpSequence(
        [
            Play(ch1, SquarePulse(duration=100 * us, amplitude=0.5 * V)),  # type: ignore
            Wait(ch2, duration=50 * us),
        ]
    )

    collector = ChannelCollectorSequence()
    collector.visit(seq)

    assert len(collector.channels) == 2
    assert "qubit_0" in collector.channels
    assert "qubit_1" in collector.channels


def test_channel_collector_with_repetition():
    """Test that ChannelCollector works with nested repetition structures."""
    ch1 = ChannelRef("qubit_0")
    ch2 = ChannelRef("qubit_1")
    us = Duration(us=1)
    V = Amplitude(V=1.0)

    inner_seq = OpSequence(
        [
            Play(ch1, pulse=SquarePulse(duration=100 * us, amplitude=0.5 * V)),
            Wait(ch2, duration=50 * us),
        ]
    )

    outer_seq = OpSequence(
        [
            Repetition(count=10, body=inner_seq),
        ]
    )

    collector = ChannelCollectorSequence()
    collector.visit(outer_seq)

    assert len(collector.channels) == 2
    assert "qubit_0" in collector.channels
    assert "qubit_1" in collector.channels


def test_channel_collector_multiple_nesting():
    """Test ChannelCollector with multiple levels of nesting."""
    ch1 = ChannelRef("qubit_0")
    ch2 = ChannelRef("qubit_1")
    ch3 = ChannelRef("readout")
    us = Duration(us=1)
    V = Amplitude(V=1.0)

    level2_seq = OpSequence(
        [
            Play(ch2, pulse=SquarePulse(duration=100 * us, amplitude=0.3 * V)),
        ]
    )

    level1_seq = OpSequence(
        [
            Play(ch1, pulse=SquarePulse(duration=100 * us, amplitude=0.5 * V)),
            Repetition(count=5, body=level2_seq),
        ]
    )

    root_seq = OpSequence(
        [
            Repetition(count=3, body=level1_seq),
            Wait(ch3, duration=200 * us),
        ]
    )

    collector = ChannelCollectorSequence()
    collector.visit(root_seq)

    assert len(collector.channels) == 3
    assert "qubit_0" in collector.channels
    assert "qubit_1" in collector.channels
    assert "readout" in collector.channels
