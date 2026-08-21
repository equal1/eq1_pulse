"""Rebuild-sweep test for the ``ValueRef`` widening (expressions plan, task 2).

Widening a field to :data:`~eq1_pulse.models.expressions.ValueRef` is only half the edit -- the
model that declares it needs a ``model_rebuild()`` once :class:`~.expressions.Expression` becomes
available, or the forward reference stays unresolved. A missed rebuild does not raise: it degrades
the union member silently to a plain :obj:`dict`. Each case below validates one representative model
per family from a plain dict containing an expression and asserts the field actually deserialized to
an :class:`~.expressions.Expression` node, not a dict standing in for one.
"""

from typing import Any

from pydantic import TypeAdapter

from eq1_pulse.models.channel_ops import ChannelOp, Wait
from eq1_pulse.models.data_ops import DataOp, Discriminate
from eq1_pulse.models.expressions import BinaryExpr, CompareExpr
from eq1_pulse.models.external_block import ExternalBlock
from eq1_pulse.models.pulse_types import PulseType, SquarePulse
from eq1_pulse.models.sequence import DiscriminableOp, OpSequenceItem

_EXPR_DOCUMENT = {
    "binary_op": {
        "op": "+",
        "lhs": {"symbol": {"var": "x"}},
        "rhs": {"value": 1},
    },
}


def test_pulse_types_rebuild_sweep():
    """SquarePulse.duration -- pulse_types.py's own model_rebuild sweep."""
    pulse: Any = TypeAdapter(PulseType).validate_python(
        {"pulse_type": "square", "duration": _EXPR_DOCUMENT, "amplitude": {"V": 0.5}}
    )
    assert isinstance(pulse, SquarePulse)
    assert isinstance(pulse.duration, BinaryExpr)


def test_channel_ops_rebuild_sweep():
    """Wait.duration -- channel_ops.py's own model_rebuild sweep."""
    op: Any = TypeAdapter(ChannelOp).validate_python({"wait": {"channels": ["ch1"], "duration": _EXPR_DOCUMENT}})
    assert isinstance(op, Wait)
    assert isinstance(op.duration, BinaryExpr)


def test_data_ops_rebuild_sweep():
    """Discriminate.threshold -- data_ops.py's own model_rebuild sweep."""
    op: Any = TypeAdapter(DataOp).validate_python(
        {
            "discriminate": {
                "target": "result",
                "source": "data",
                "threshold": _EXPR_DOCUMENT,
            }
        }
    )
    assert isinstance(op, Discriminate)
    assert isinstance(op.threshold, BinaryExpr)


def test_external_block_rebuild_sweep():
    """ExternalBlock.duration -- external_block.py's own model_rebuild sweep."""
    block = ExternalBlock.model_validate({"channels": {"a": "q0"}, "duration": _EXPR_DOCUMENT})
    assert isinstance(block.duration, BinaryExpr)


def test_control_flow_and_sequence_rebuild_sweep():
    """Repetition.count and Conditional.var -- control_flow.py's and sequence.py's model_rebuild sweep."""
    compare_document = {
        "compare_op": {
            "op": ">",
            "lhs": {"symbol": {"var": "x"}},
            "rhs": {"value": 1},
        },
    }
    rep: Any = TypeAdapter(DiscriminableOp).validate_python({"repeat": {"count": _EXPR_DOCUMENT, "body": []}})
    assert isinstance(rep.count, BinaryExpr)

    cond: Any = TypeAdapter(OpSequenceItem).validate_python({"if": {"var": compare_document, "body": []}})
    assert isinstance(cond.var, CompareExpr)
