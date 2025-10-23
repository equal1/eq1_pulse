"""Tests for schedule module."""

import json

import numpy as np

from eq1_pulse.models.basic_types import Amplitude, Duration
from eq1_pulse.models.channel_ops import Play
from eq1_pulse.models.pulse_types import SquarePulse
from eq1_pulse.models.schedule import (
    RelTime,
    SchedConditional,
    SchedIteration,
    SchedRepetition,
    Schedule,
)

# Previous tests remain unchanged...


def test_nested_schedule():
    """Test nested Schedule operations."""
    outer_schedule = Schedule()
    inner_schedule = Schedule()
    op = Play(channel="chan1", pulse=SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0)))

    # Add ops to inner schedule
    inner_schedule.add_op(op, name="inner_op1")
    inner_schedule.add_op(op, name="inner_op2", rel_time=RelTime(ns=50), ref_op="inner_op1")

    # Add inner schedule to outer schedule
    outer_schedule.add_op(inner_schedule, name="nested")

    assert len(outer_schedule.items) == 1
    assert isinstance(outer_schedule.items[0].op, Schedule)
    assert len(outer_schedule.items[0].op.items) == 2


def test_schedule_repetition():
    """Test SchedRepetition operations."""
    schedule = Schedule()
    op = Play(channel="chan1", pulse=SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0)))
    schedule.add_op(op, name="op1")

    repetition = SchedRepetition(count=3, body=schedule)

    outer_schedule = Schedule()
    outer_schedule.add_op(repetition, name="repeat")

    assert len(outer_schedule.items) == 1
    assert isinstance(outer_schedule.items[0].op, SchedRepetition)
    assert outer_schedule.items[0].op.count == 3


def test_schedule_iteration():
    """Test SchedIteration operations."""
    schedule = Schedule()
    op = Play(channel="chan1", pulse=SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0)))
    schedule.add_op(op, name="op1")

    iteration = SchedIteration(var="i", items=[1, 2, 3], body=schedule)

    outer_schedule = Schedule()
    outer_schedule.add_op(iteration, name="iterate")

    assert len(outer_schedule.items) == 1
    assert isinstance(outer_schedule.items[0].op, SchedIteration)
    assert outer_schedule.items[0].op.var == "i"
    assert isinstance(outer_schedule.items[0].op.items, np.ndarray)
    assert np.array_equal(outer_schedule.items[0].op.items, [1, 2, 3])


def test_schedule_conditional():
    """Test SchedConditional operations."""
    schedule = Schedule()
    op = Play(channel="chan1", pulse=SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0)))
    schedule.add_op(op, name="op1")

    conditional = SchedConditional(var="x", body=schedule)

    outer_schedule = Schedule()
    outer_schedule.add_op(conditional, name="if_block")

    assert len(outer_schedule.items) == 1
    assert isinstance(outer_schedule.items[0].op, SchedConditional)
    assert outer_schedule.items[0].op.var == "x"


def test_schedule_conditional_list():
    """Test SchedConditional operations."""
    schedule = Schedule(
        [
            Schedule.op(
                SchedConditional(
                    var="x",
                    body=[
                        Schedule.op(
                            Play(
                                channel="chan1",
                                pulse=SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0)),
                            )
                        )
                    ],
                ),
                name="if_block",
            )
        ]
    )

    assert len(schedule.items) == 1
    assert isinstance(schedule.items[0].op, SchedConditional)
    assert schedule.items[0].op.var == "x"
    assert len(schedule.items[0].op.body) == 1
    assert isinstance(schedule.items[0].op.body[0].op, Play)
    assert schedule.items[0].op.body[0].op.channel == "chan1"

    assert schedule.model_dump() == [
        {
            "name": "if_block",
            "op": {
                "op_type": "if",
                "var": "x",
                "body": [
                    {
                        "op": {
                            "op_type": "play",
                            "channel": "chan1",
                            "pulse": {"pulse_type": "square", "duration": {"ns": 100}, "amplitude": {"V": 1.0}},
                        },
                    }
                ],
            },
        },
    ]


def test_complex_json_serialization():
    """Test complex Schedule JSON serialization."""
    # Create a complex nested schedule
    inner1 = Schedule()
    op = Play("chan1", SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0)))
    inner1.add_op(op, name="pulse0")

    inner2 = Schedule()
    op = Play("chan1", SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0)))
    inner2.add_op(op, name="pulse1")
    op = Play("chan2", SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0)))
    inner2.add_op(op, name="pulse2", rel_time=RelTime(0), ref_op="pulse1", ref_pt="start")

    outer = Schedule()
    outer.add_op(inner1, name="nested")
    outer.add_op(SchedRepetition(count=2, body=inner2), name="repeat")

    # Test serialization
    json_str = outer.model_dump_json()

    # Test deserialization
    new_schedule = Schedule.model_validate_json(json_str)
    assert new_schedule == outer

    expected_json = json.dumps(
        [
            {
                "name": "nested",
                "op": [
                    {
                        "name": "pulse0",
                        "op": {
                            "op_type": "play",
                            "channel": "chan1",
                            "pulse": {"pulse_type": "square", "duration": {"ns": 100}, "amplitude": {"V": 1.0}},
                        },
                    }
                ],
            },
            {
                "name": "repeat",
                "op": {
                    "op_type": "repeat",
                    "count": 2,
                    "body": [
                        {
                            "name": "pulse1",
                            "op": {
                                "op_type": "play",
                                "channel": "chan1",
                                "pulse": {"pulse_type": "square", "duration": {"ns": 100}, "amplitude": {"V": 1.0}},
                            },
                        },
                        {
                            "name": "pulse2",
                            "rel_time": {"s": 0.0},
                            "ref_op": "pulse1",
                            "ref_pt": "start",
                            "op": {
                                "op_type": "play",
                                "channel": "chan2",
                                "pulse": {"pulse_type": "square", "duration": {"ns": 100}, "amplitude": {"V": 1.0}},
                            },
                        },
                    ],
                },
            },
        ],
        separators=(",", ":"),
    )

    assert json_str == expected_json


def test_deep_nesting():
    """Test deeply nested schedules."""
    level1 = Schedule()
    level2 = Schedule()
    level3 = Schedule()
    op = Play("chan2", SquarePulse(duration=Duration(ns=100), amplitude=Amplitude(V=1.0)))

    level3.add_op(op, name="deepest")
    level2.add_op(level3, name="level3")
    level1.add_op(level2, name="level2")

    assert len(level1.items) == 1
    assert isinstance(level1[0].op, Schedule)
    assert isinstance(level1[0].op[0].op, Schedule)
    assert isinstance(level1[0].op[0].op[0].op.pulse, SquarePulse)  # type: ignore[attr-defined, union-attr]
    assert isinstance(level1[0].op[0].op[0].op.pulse, SquarePulse)  # type: ignore[attr-defined, union-attr]

    # Test deep nesting serialization and deserialization
    json_str = level1.model_dump_json()
    deserialized = Schedule.model_validate_json(json_str)

    # Verify the structure is preserved
    assert deserialized == level1

    # Verify the actual JSON string
    expected_json = json.dumps(
        [
            {
                "name": "level2",
                "op": [
                    {
                        "name": "level3",
                        "op": [
                            {
                                "name": "deepest",
                                "op": {
                                    "op_type": "play",
                                    "channel": "chan2",
                                    "pulse": {"pulse_type": "square", "duration": {"ns": 100}, "amplitude": {"V": 1.0}},
                                },
                            }
                        ],
                    }
                ],
            }
        ],
        separators=(",", ":"),
    )
    assert json_str == expected_json
