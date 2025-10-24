"""Tests for sequence models."""

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models import (
    Conditional,
    Iteration,
    LinSpace,
    OpSequence,
    OpSequenceItem,
    Play,
    Range,
    Repetition,
    SquarePulse,
    VariableRef,
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
    assert it.var == "i"
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


def test_iteration_multiple_variables_validation_errors():
    with pytest.raises(ValidationError):
        Iteration(var="i", items=[Range(start=0, stop=5, step=1)], body=OpSequence([]))

    with pytest.raises(ValidationError):
        Iteration(var=["i"], items=Range(start=0, stop=5, step=1), body=OpSequence([]))

    with pytest.raises(ValidationError):
        Iteration(var=["s"], items=["str"], body=OpSequence([]))

    with pytest.raises(ValidationError):
        Iteration(var="s", items=[["str"]], body=OpSequence([]))

    with pytest.raises(ValidationError):
        Iteration(var=["i", "j"], items=[Range(start=0, stop=5, step=1)], body=OpSequence([]))

    with pytest.raises(ValidationError):
        Iteration(var=["i", "j"], items=[Range(start=0, stop=5, step=1), [1, 2]], body=OpSequence([]))


def test_iteration_multiple_variables_construction():
    iter_obj = Iteration(
        var=["i", "j", "k", "s"],
        items=[[0, 1, 2], Range(start=3, stop=5, step=1), LinSpace(start=10, stop=20, num=3), ["a", "b", "c"]],
        body=OpSequence([]),
    )
    assert isinstance(iter_obj, Iteration)
    assert iter_obj.var == [VariableRef("i"), VariableRef("j"), VariableRef("k"), VariableRef("s")]
    assert isinstance(iter_obj.items, list)
    assert len(iter_obj.items) == 4
    assert isinstance(iter_obj.items[0], np.ndarray)
    assert isinstance(iter_obj.items[1], Range)
    assert isinstance(iter_obj.items[2], LinSpace)
    assert isinstance(iter_obj.items[3], list)


def test_iteration_multiple_variables_validation():
    iter_obj: OpSequenceItem = TypeAdapter(OpSequenceItem).validate_python(
        {
            "op_type": "for",
            "var": ["i", "j", "k", "s"],
            "items": [
                [0, 1, 2],
                {"start": 3, "stop": 5, "step": 1},
                {"start": 10, "stop": 20, "num": 3},
                ["a", "b", "c"],
            ],
            "body": [],
        }
    )
    assert isinstance(iter_obj, Iteration)
    assert iter_obj.var == [VariableRef("i"), VariableRef("j"), VariableRef("k"), VariableRef("s")]
    assert isinstance(iter_obj.items, list)
    assert len(iter_obj.items) == 4
    assert isinstance(iter_obj.items[0], np.ndarray)
    assert isinstance(iter_obj.items[1], Range)
    assert isinstance(iter_obj.items[2], LinSpace)
    assert isinstance(iter_obj.items[3], list)


def test_iteration_multiple_variables_validate_json():
    iter_obj: OpSequenceItem = TypeAdapter(OpSequenceItem).validate_json(
        r"""{
            "op_type": "for",
            "var": ["i", "j", "k", "s"],
            "items": [
                [0, 1, 2],
                {"start": 3, "stop": 5, "step": 1},
                {"start": 10, "stop": 20, "num": 3},
                ["a", "b", "c"]
            ],
            "body": []
        }"""
    )
    assert isinstance(iter_obj, Iteration)
    assert iter_obj.var == [VariableRef("i"), VariableRef("j"), VariableRef("k"), VariableRef("s")]
    assert isinstance(iter_obj.items, list)
    assert len(iter_obj.items) == 4
    assert isinstance(iter_obj.items[0], np.ndarray)
    assert issubclass(iter_obj.items[0].dtype.type, np.integer)
    assert isinstance(iter_obj.items[1], Range)
    assert isinstance(iter_obj.items[2], LinSpace)
    assert isinstance(iter_obj.items[3], list)


def test_iteration_multiple_variables_serialize_json():
    iter_obj = Iteration(
        var=["i", "j", "k", "s"],
        items=[[0, 1, 2], Range(start=3, stop=5, step=1), LinSpace(start=10, stop=20, num=3), ["a", "b", "c"]],
        body=OpSequence([]),
    )
    serialized = iter_obj.model_dump_json()
    assert serialized == (
        '{"op_type":"for",'
        + '"var":["i","j","k","s"],'
        + '"items":['
        + '[0,1,2],{"start":3,"stop":5,"step":1},'
        + '{"start":10,"stop":20,"num":3},'
        + '["a","b","c"]'
        + '],"body":[]}'
    )
