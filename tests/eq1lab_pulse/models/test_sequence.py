"""Tests for sequence models."""

import pytest
from pydantic import ValidationError

from eq1_pulse.models.basic_types import Range
from eq1_pulse.models.channel_ops import Play
from eq1_pulse.models.pulse_types import SquarePulse
from eq1_pulse.models.sequence import (
    Conditional,
    Iteration,
    OpSequence,
    Repetition,
)


def test_op_sequence_init():
    """Test OpSequence initialization."""
    pulse = SquarePulse(duration={"ns": 100}, amplitude={"V": 1.0})
    play = Play(channel="ch1", pulse=pulse)
    seq = OpSequence([play])
    assert len(seq.items) == 1
    assert seq.items[0] == play


def test_op_sequence_init_from_list():
    """Test OpSequence initialization from list."""
    pulse = SquarePulse(duration={"ns": 100}, amplitude={"V": 1.0})
    play = Play(channel="ch1", pulse=pulse)
    seq = OpSequence([play])
    assert len(seq.items) == 1


def test_op_sequence_serialization():
    """Test OpSequence serialization."""
    pulse = SquarePulse(duration={"ns": 100}, amplitude={"V": 1.0})
    play = Play(channel="ch1", pulse=pulse)
    seq = OpSequence([play])
    serialized = seq.model_dump_json()
    deserialized = OpSequence.model_validate_json(serialized)
    assert deserialized == seq


def test_repetition():
    """Test Repetition model."""
    pulse = SquarePulse(duration={"ns": 100}, amplitude={"V": 1.0})
    play = Play(channel="ch1", pulse=pulse)
    body = OpSequence([play])
    rep = Repetition(count=3, body=body)
    assert rep.count == 3
    assert rep.body == body


def test_iteration():
    """Test Iteration model."""
    pulse = SquarePulse(duration={"ns": 100}, amplitude={"V": 1.0})
    play = Play(channel="ch1", pulse=pulse)
    body = OpSequence([play])
    range_obj = Range(start=0, stop=5, step=1)
    it = Iteration(var="i", items=range_obj, body=body)
    assert it.var.var == "i"
    assert it.items == range_obj
    assert it.body == body


def test_conditional():
    """Test Conditional model."""
    pulse = SquarePulse(duration={"ns": 100}, amplitude={"V": 1.0})
    play = Play(channel="ch1", pulse=pulse)
    body = OpSequence([play])
    cond = Conditional(var="flag", body=body)
    assert cond.var == "flag"
    assert cond.body == body


def test_nested_sequences():
    """Test nested operation sequences."""
    pulse1 = SquarePulse(duration={"ns": 100}, amplitude={"V": 1.0})
    pulse2 = SquarePulse(duration={"ns": 100}, amplitude={"V": 2.0})
    play1 = Play(channel="ch1", pulse=pulse1)
    play2 = Play(channel="ch2", pulse=pulse2)

    inner_seq = OpSequence([play1])
    rep = Repetition(count=2, body=inner_seq)
    outer_seq = OpSequence([rep, play2])

    assert len(outer_seq.items) == 2
    assert isinstance(outer_seq.items[0], Repetition)
    assert isinstance(outer_seq.items[1], Play)

    serialized = outer_seq.model_dump_json()

    assert serialized == (
        r'[{"op_type":"repeat","count":2,"body":'
        + r'[{"op_type":"play","channel":"ch1","pulse":{'
        + r'"pulse_type":"square","duration":{"ns":100},"amplitude":{"V":1.0}}}]},'
        + r'{"op_type":"play","channel":"ch2","pulse":{'
        + r'"pulse_type":"square","duration":{"ns":100},"amplitude":{"V":2.0}}}]'
    )
    deserialized = OpSequence.model_validate_json(serialized)
    assert deserialized == outer_seq


def test_sequence_validation():
    """Test sequence validation."""
    with pytest.raises(ValidationError):
        OpSequence(items=None)


def test_repetition_validation():
    with pytest.raises(ValidationError):
        Repetition(count=-1, body=OpSequence([]))
