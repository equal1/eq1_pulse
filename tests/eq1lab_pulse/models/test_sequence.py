"""Tests for sequence models."""

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models import (
    Conditional,
    ExternalBlock,
    ExternalRef,
    Iteration,
    LinSpace,
    OpSequence,
    OpSequenceItem,
    Play,
    PulseRef,
    Range,
    Repetition,
    SquarePulse,
    VariableRef,
)
from eq1_pulse.models.expressions import BinaryExpr, CompareExpr, LiteralExpr, SymbolExpr


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


def test_repetition_count_accepts_variable_and_external_ref():
    """Test Repetition.count accepts a VariableRef or an ExternalRef, in addition to a literal."""
    body = OpSequence([])
    rep = Repetition(count=VariableRef("n"), body=body)
    assert isinstance(rep.count, VariableRef)

    rep = Repetition(count=ExternalRef(ext="q0.reps"), body=body)
    assert isinstance(rep.count, ExternalRef)


def test_iteration():
    """Test Iteration model."""
    pulse = SquarePulse(duration={"ns": 100}, amplitude={"V": 1.0})
    play = Play(channel="ch1", pulse=pulse)
    body = OpSequence([play])
    range_obj = Range(start=0, stop=5, step=1)
    it = Iteration(var=VariableRef("i"), items=range_obj, body=body)
    assert it.var == "i"
    assert it.items == range_obj
    assert it.body == body


def test_conditional():
    """Test Conditional model."""
    pulse = SquarePulse(duration={"ns": 100}, amplitude={"V": 1.0})
    play = Play(channel="ch1", pulse=pulse)
    body = OpSequence([play])
    cond = Conditional(var=VariableRef("flag"), body=body)
    assert cond.var == "flag"
    assert cond.body == body


def test_conditional_accepts_external_ref():
    """Test Conditional model accepts an ExternalRef for its var field."""
    body = OpSequence([])
    cond = Conditional(var=ExternalRef(ext="q0.flag"), body=body)
    assert isinstance(cond.var, ExternalRef)


def test_iteration_rejects_external_ref():
    """Test Iteration model rejects an ExternalRef as its loop-binding var (a write site)."""
    with pytest.raises(ValidationError):
        Iteration(
            var=ExternalRef(ext="q0"),  # type: ignore[arg-type]
            items=Range(start=0, stop=5, step=1),
            body=OpSequence([]),
        )


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
    """A sequence's wire form is the array itself -- the old ``{"items": [...]}`` object is not one."""
    with pytest.raises(ValidationError):
        OpSequence.model_validate(None)
    with pytest.raises(ValidationError):
        OpSequence.model_validate({"items": []})


def test_repetition_validation():
    with pytest.raises(ValidationError):
        Repetition(count=-1, body=OpSequence([]))


def test_iteration_multiple_variables_validation_errors():
    with pytest.raises(ValidationError):
        Iteration(var=VariableRef("i"), items=[Range(start=0, stop=5, step=1)], body=OpSequence([]))

    with pytest.raises(ValidationError):
        Iteration(var=[VariableRef("i")], items=Range(start=0, stop=5, step=1), body=OpSequence([]))

    with pytest.raises(ValidationError):
        Iteration(var=[VariableRef("s")], items=["str"], body=OpSequence([]))

    with pytest.raises(ValidationError):
        Iteration(var=VariableRef("s"), items=[["str"]], body=OpSequence([]))

    with pytest.raises(ValidationError):
        Iteration(var=[VariableRef("i"), VariableRef("j")], items=[Range(start=0, stop=5, step=1)], body=OpSequence([]))

    with pytest.raises(ValidationError):
        Iteration(
            var=[VariableRef("i"), VariableRef("j")],
            items=[Range(start=0, stop=5, step=1), [1, 2]],
            body=OpSequence([]),
        )


def test_iteration_multiple_variables_construction():
    iter_obj = Iteration(
        var=[VariableRef("i"), VariableRef("j"), VariableRef("k"), VariableRef("s")],
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
            "var": [{"var": "i"}, {"var": "j"}, {"var": "k"}, {"var": "s"}],
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
            "var": [{"var": "i"}, {"var": "j"}, {"var": "k"}, {"var": "s"}],
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
        var=[VariableRef("i"), VariableRef("j"), VariableRef("k"), VariableRef("s")],
        items=[[0, 1, 2], Range(start=3, stop=5, step=1), LinSpace(start=10, stop=20, num=3), ["a", "b", "c"]],
        body=OpSequence([]),
    )
    serialized = iter_obj.model_dump_json()
    assert serialized == (
        '{"op_type":"for",'
        + '"var":[{"var":"i"},{"var":"j"},{"var":"k"},{"var":"s"}],'
        + '"items":['
        + '[0,1,2],{"start":3,"stop":5,"step":1},'
        + '{"start":10,"stop":20,"num":3},'
        + '["a","b","c"]'
        + '],"body":[]}'
    )


def test_sequence_external_param_references_round_trip_without_degrading():
    """A VariableRef, PulseRef, and ExternalRef in external params keep their own type through JSON."""
    block = ExternalBlock(
        channels={"a": "ch1"},
        duration={"ns": 100},
        params={
            "var": VariableRef("x"),
            "pulse": PulseRef("p1"),
            "ext": ExternalRef("q0.f01"),
        },
    )
    seq = OpSequence([block])
    serialized = seq.model_dump_json()
    deserialized = OpSequence.model_validate_json(serialized)
    assert deserialized == seq

    restored = deserialized.items[0]
    assert isinstance(restored, ExternalBlock)
    params = restored.params
    assert params is not None
    assert isinstance(params["var"], VariableRef)
    assert isinstance(params["pulse"], PulseRef)
    assert isinstance(params["ext"], ExternalRef)


def test_sequence_with_expressions_round_trips_through_json():
    """A sequence with a widened field holding an Expression round-trips through JSON, not just model_dump."""
    count = BinaryExpr(binary_op="+", left=SymbolExpr(symbol=VariableRef("n")), right=LiteralExpr(value=1))
    predicate = CompareExpr(compare_op=">", left=SymbolExpr(symbol=VariableRef("x")), right=LiteralExpr(value=1))
    pulse = SquarePulse(duration={"ns": 100}, amplitude={"V": 1.0})
    play = Play(channel="ch1", pulse=pulse)

    rep = Repetition(count=count, body=OpSequence([play]))
    cond = Conditional(var=predicate, body=OpSequence([play]))
    seq = OpSequence([rep, cond])

    dumped = seq.model_dump_json()
    restored = OpSequence.model_validate_json(dumped)
    assert restored == seq

    restored_rep = restored.items[0]
    assert isinstance(restored_rep, Repetition)
    assert isinstance(restored_rep.count, BinaryExpr)

    restored_cond = restored.items[1]
    assert isinstance(restored_cond, Conditional)
    assert isinstance(restored_cond.var, CompareExpr)
