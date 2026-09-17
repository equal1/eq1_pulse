"""Tests for the sweep declarations (parameter sweeps plan, task T2).

The wire forms asserted here are the ones plan §15 fixes as normative, transcribed from its
*Declarations* block:

.. code-block:: yaml

    - sweep_decl: {name: vg, dtype: float, unit: mV}

    - sweep_decl:
        name: t_pi
        dtype: float
        unit: ns
        default: {start: 0, stop: 200, num: 101}

    - sweep_decl:
        name: amp_seq
        dtype: float
        unit: mV
        default: [100, 0, 100, 50, 100, 25]

    - sweep_group:
        sweeps:
          - {name: i_amp, dtype: float, unit: mV}
          - {name: drive_freq, dtype: float, unit: MHz}

Each block appears below as the mapping it denotes, compared against ``model_dump()`` unabridged --
which is what catches a ``sweeps: list[SweepDecl]``, whose members would each carry a redundant
``sweep_decl:`` key their container already supplies.
"""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models.basic_types import LinSpace, Range
from eq1_pulse.models.data_ops import ValueLimits
from eq1_pulse.models.sweeps import SweepDecl, SweepGroup, SweepOp, SweepSpec


@pytest.fixture
def sweep_op_adapter() -> TypeAdapter[Any]:
    return TypeAdapter(SweepOp)


def test_sweep_decl_wire_form():
    """§15, first block: the minimal declaration."""
    decl = SweepDecl(name="vg", dtype="float", unit="mV")
    assert decl.model_dump() == {"sweep_decl": {"name": "vg", "dtype": "float", "unit": "mV"}}


def test_sweep_decl_linspace_default_wire_form():
    """§15, second block: a compact default stays compact."""
    decl = SweepDecl(name="t_pi", dtype="float", unit="ns", default={"start": 0, "stop": 200, "num": 101})
    assert decl.model_dump() == {
        "sweep_decl": {
            "name": "t_pi",
            "dtype": "float",
            "unit": "ns",
            "default": {"start": 0, "stop": 200, "num": 101},
        }
    }


def test_sweep_decl_array_default_wire_form():
    """§15, third block: an array default is the JSON array itself."""
    decl = SweepDecl(name="amp_seq", dtype="float", unit="mV", default=[100, 0, 100, 50, 100, 25])
    assert decl.model_dump() == {
        "sweep_decl": {
            "name": "amp_seq",
            "dtype": "float",
            "unit": "mV",
            "default": [100, 0, 100, 50, 100, 25],
        }
    }


def test_sweep_group_wire_form():
    """§15, fourth block, and §15 rule 3: ``sweep_decl:`` appears once per group, not per member."""
    group = SweepGroup(
        sweeps=[
            SweepSpec(name="i_amp", dtype="float", unit="mV"),
            SweepSpec(name="drive_freq", dtype="float", unit="MHz"),
        ]
    )
    assert group.model_dump() == {
        "sweep_group": {
            "sweeps": [
                {"name": "i_amp", "dtype": "float", "unit": "mV"},
                {"name": "drive_freq", "dtype": "float", "unit": "MHz"},
            ]
        }
    }


def test_sweep_spec_is_not_an_operation():
    """A specification is flat: it is the body of a declaration, not one itself."""
    assert SweepSpec(name="vg", dtype="float").model_dump() == {"name": "vg", "dtype": "float"}


def test_sweep_group_rejects_operations_as_members():
    """A member spelled as the whole operation is rejected rather than nested one level too deep."""
    with pytest.raises(ValidationError):
        SweepGroup.model_validate(
            {
                "sweep_group": {
                    "sweeps": [
                        {"sweep_decl": {"name": "i_amp", "dtype": "float"}},
                        {"sweep_decl": {"name": "drive_freq", "dtype": "float"}},
                    ]
                }
            }
        )


@pytest.mark.parametrize(
    "op",
    [
        pytest.param(lambda: SweepDecl(name="vg", dtype="float", unit="mV"), id="sweep_decl"),
        pytest.param(
            lambda: SweepDecl(name="t_pi", dtype="float", default=LinSpace(start=0, stop=200, num=101)),
            id="sweep_decl_linspace",
        ),
        pytest.param(
            lambda: SweepDecl(name="vg", dtype="float", default=Range(start=0, stop=10, step=2)),
            id="sweep_decl_range",
        ),
        pytest.param(
            lambda: SweepDecl(name="amp_seq", dtype="float", default=[100, 0, 100, 50]),
            id="sweep_decl_int_array",
        ),
        pytest.param(
            lambda: SweepDecl(name="iq", dtype="complex", default=[1 + 2j, 3 + 4j]),
            id="sweep_decl_complex_array",
        ),
        pytest.param(
            lambda: SweepDecl(
                name="vg",
                dtype="float",
                shape=(101,),
                unit="mV",
                default=LinSpace(start=0, stop=100, num=101),
                limits=ValueLimits(minimum=0, maximum=200),
            ),
            id="sweep_decl_every_field",
        ),
        pytest.param(
            lambda: SweepGroup(
                sweeps=[
                    SweepSpec(name="i_amp", dtype="float", unit="mV"),
                    SweepSpec(name="drive_freq", dtype="float", unit="MHz"),
                ]
            ),
            id="sweep_group",
        ),
    ],
)
def test_round_trip(op: Callable[[], SweepDecl | SweepGroup], sweep_op_adapter: TypeAdapter[Any]):
    """Every operation survives ``model_dump`` -> ``model_validate`` and the JSON path too."""
    instance = op()
    document = instance.model_dump()

    from_python = sweep_op_adapter.validate_python(document)
    assert type(from_python) is type(instance)
    assert from_python.model_dump() == document

    from_json = sweep_op_adapter.validate_json(instance.model_dump_json())
    assert type(from_json) is type(instance)
    assert from_json.model_dump() == document


def test_sweep_op_discriminates_by_sole_key(sweep_op_adapter: TypeAdapter[Any]):
    """Both operations are selected by the one key their wire object carries."""
    decl = sweep_op_adapter.validate_python({"sweep_decl": {"name": "vg", "dtype": "float"}})
    group = sweep_op_adapter.validate_python(
        {"sweep_group": {"sweeps": [{"name": "i", "dtype": "float"}, {"name": "q", "dtype": "float"}]}}
    )
    assert type(decl) is SweepDecl
    assert type(group) is SweepGroup


def test_sweep_op_rejects_the_flat_form(sweep_op_adapter: TypeAdapter[Any]):
    """A flat object carries no sole key, so it is one ``union_tag_not_found``."""
    with pytest.raises(ValidationError) as excinfo:
        sweep_op_adapter.validate_python({"op_type": "sweep_decl", "name": "vg", "dtype": "float"})
    assert [error["type"] for error in excinfo.value.errors()] == ["union_tag_not_found"]


def test_sweep_group_needs_two_members():
    """A group of one is a declaration, so two is the minimum."""
    with pytest.raises(ValidationError):
        SweepGroup(sweeps=[SweepSpec(name="i_amp", dtype="float")])


def test_sweep_group_rejects_mismatched_concrete_defaults():
    """Lock-step members whose defaults are all concrete must be the same length."""
    with pytest.raises(ValidationError) as excinfo:
        SweepGroup(
            sweeps=[
                SweepSpec(name="i_amp", dtype="float", default=LinSpace(start=0, stop=1, num=11)),
                SweepSpec(name="drive_freq", dtype="float", default=LinSpace(start=0, stop=1, num=21)),
            ]
        )
    message = str(excinfo.value)
    assert "i_amp: 11" in message
    assert "drive_freq: 21" in message


def test_sweep_group_accepts_matching_concrete_defaults():
    """Equal lengths pass, across the three ``SweepValue`` spellings."""
    group = SweepGroup(
        sweeps=[
            SweepSpec(name="i_amp", dtype="float", default=LinSpace(start=0, stop=10, num=6)),
            SweepSpec(name="drive_freq", dtype="float", default=Range(start=0, stop=10, step=2)),
            SweepSpec(name="amp_seq", dtype="float", default=[1, 2, 3, 4, 5, 6]),
        ]
    )
    assert len(group.sweeps) == 3


@pytest.mark.parametrize(
    "defaults",
    [
        pytest.param((None, None), id="none_supplied"),
        pytest.param((LinSpace(start=0, stop=1, num=11), None), id="one_supplied"),
        pytest.param((None, LinSpace(start=0, stop=1, num=21)), id="the_other_supplied"),
    ],
)
def test_sweep_group_unsupplied_defaults_are_not_checked(defaults: tuple[LinSpace | None, LinSpace | None]):
    """The lengths that matter are the supplied ones; a group with any default missing is unchecked."""
    group = SweepGroup(
        sweeps=[
            SweepSpec(name="i_amp", dtype="float", default=defaults[0]),
            SweepSpec(name="drive_freq", dtype="float", default=defaults[1]),
        ]
    )
    assert len(group.sweeps) == 2


def test_lean_model_elision():
    """``shape``, ``limits`` and an absent ``default`` never reach the wire."""
    document = SweepDecl(name="vg", dtype="float").model_dump()
    assert document == {"sweep_decl": {"name": "vg", "dtype": "float"}}

    spec = SweepSpec(name="vg", dtype="float", shape=None, unit=None, default=None, limits=None).model_dump()
    assert spec == {"name": "vg", "dtype": "float"}


def test_sweep_name_must_be_an_identifier():
    with pytest.raises(ValidationError):
        SweepDecl(name="not an identifier", dtype="float")
