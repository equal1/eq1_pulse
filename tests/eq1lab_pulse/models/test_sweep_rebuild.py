"""Rebuild-sweep test for the sweeps plan's task 3 (control_flow.py, sequence.py).

Widening :data:`~eq1_pulse.models.control_flow.IterableSequence` to admit
:data:`~eq1_pulse.models.expressions.SweepSource` and :class:`~eq1_pulse.models.control_flow.Indices`,
and adding :data:`~eq1_pulse.models.sweeps.SweepOp` to
:data:`~eq1_pulse.models.sequence.DiscriminableOp`, is only half the edit -- every model that
transitively mentions the new union members needs a ``model_rebuild()`` once the forward reference
resolves, or it degrades silently to a plain :obj:`dict`. Each case below validates one representative
model from a plain dict containing a sweep expression and asserts the field actually deserialized to
the model, not a dict standing in for one.
"""

from typing import Any

from pydantic import TypeAdapter

from eq1_pulse.models.control_flow import Indices
from eq1_pulse.models.expressions import BinaryExpr, LenExpr, SweepExpr
from eq1_pulse.models.sequence import DiscriminableOp, Iteration, OpSequenceItem
from eq1_pulse.models.sweeps import SweepDecl, SweepGroup


def test_iteration_items_rebuild_sweep_bare_reference():
    """``Iteration.items`` accepts a bare ``{"sweep": ...}``, not a dict standing in for one."""
    op: Any = TypeAdapter(OpSequenceItem).validate_python({"for": {"var": "v", "items": {"sweep": "vg"}, "body": []}})
    assert isinstance(op, Iteration)
    assert isinstance(op.items, SweepExpr)


def test_iteration_items_rebuild_sweep_indices():
    """``Iteration.items`` accepts ``Indices``, not a dict standing in for one.

    ``Indices.count`` is a ``ValueRef`` -- a scalar -- so it takes ``len_(sweep(...))``, not a bare
    sweep reference.
    """
    op: Any = TypeAdapter(OpSequenceItem).validate_python(
        {"for": {"var": "i", "items": {"count": {"len_op": {"operand": {"sweep": "vg"}}}}, "body": []}}
    )
    assert isinstance(op, Iteration)
    assert isinstance(op.items, Indices)
    assert isinstance(op.items.count, LenExpr)


def test_iteration_items_rebuild_sweep_transform():
    """``Iteration.items`` accepts a tree over a sweep, not a dict standing in for one."""
    op: Any = TypeAdapter(OpSequenceItem).validate_python(
        {
            "for": {
                "var": "p",
                "items": {"binary_op": {"op": "*", "lhs": {"sweep": "vg"}, "rhs": {"value": 2}}},
                "body": [],
            }
        }
    )
    assert isinstance(op, Iteration)
    assert isinstance(op.items, BinaryExpr)


def test_discriminable_op_rebuild_sweep_decl():
    """``DiscriminableOp`` selects ``SweepDecl``, not a dict standing in for one."""
    op: Any = TypeAdapter(DiscriminableOp).validate_python(
        {"sweep_decl": {"name": "vg", "dtype": "float", "unit": "mV"}}
    )
    assert isinstance(op, SweepDecl)


def test_discriminable_op_rebuild_sweep_group():
    """``DiscriminableOp`` selects ``SweepGroup``, not a dict standing in for one."""
    op: Any = TypeAdapter(DiscriminableOp).validate_python(
        {
            "sweep_group": {
                "sweeps": [
                    {"name": "i_amp", "dtype": "float", "unit": "mV"},
                    {"name": "drive_freq", "dtype": "float", "unit": "MHz"},
                ]
            }
        }
    )
    assert isinstance(op, SweepGroup)
