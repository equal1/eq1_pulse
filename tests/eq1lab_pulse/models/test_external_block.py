"""Tests for the ExternalBlock model."""

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models.basic_types import Amplitude, Duration, Frequency, Magnitude, Phase, Voltage
from eq1_pulse.models.expressions import BinaryExpr, LiteralExpr, SymbolExpr
from eq1_pulse.models.external_block import ExternalBlock
from eq1_pulse.models.pulse_types import SquarePulse
from eq1_pulse.models.reference_types import ChannelRef, ExternalRef, PulseRef, VariableRef
from eq1_pulse.models.sequence import DiscriminableOp, OpSequence


def test_external_block_creation_minimal():
    """Test creating an external block with only the required channels field."""
    block = ExternalBlock(channels={"drive": "q0"})
    assert block.op_type == "external_block"
    assert block.program is None
    assert block.channels == {"drive": ChannelRef("q0")}
    assert block.params is None
    assert block.results is None
    assert block.duration is None


def test_external_block_role_keyed_channels():
    """Test that channels are keyed by role, and the reservation set is channels.values()."""
    block = ExternalBlock(
        program="eq1.cal.measure",
        channels={"drive": "q0", "readout": "q0_ro"},
    )
    assert block.channels["drive"] == ChannelRef("q0")
    assert block.channels["readout"] == ChannelRef("q0_ro")
    assert sorted(block.channels.values(), key=repr) == [ChannelRef("q0"), ChannelRef("q0_ro")]


def test_external_block_timed():
    """Test creating a timed (hard duration) external block."""
    block = ExternalBlock(
        program="eq1.cal.cz",
        channels={"a": "q0", "b": "q1"},
        duration=Duration(s=100e-9),
    )
    assert isinstance(block.duration, Duration)
    assert block.duration.s == 100e-9


def test_external_block_flex():
    """Test creating a flex (duration=None) external block without runtime-variable params."""
    block = ExternalBlock(
        program="eq1.cal.cz",
        channels={"a": "q0", "b": "q1"},
        params={"amp": Voltage(V=0.5)},
    )
    assert block.duration is None
    assert block.params == {"amp": Voltage(V=0.5)}


def test_external_block_empty_program_pure_reservation():
    """Test that program=None with a duration models a pure channel reservation."""
    block = ExternalBlock(channels={"a": "q0"}, duration=Duration(s=50e-9))
    assert block.program is None
    assert isinstance(block.duration, Duration)


@pytest.mark.parametrize(
    ("value", "expected_type"),
    [
        (Voltage(V=0.5), Voltage),
        (Duration(s=1e-6), Duration),
        (Frequency(Hz=1e6), Frequency),
        (Phase(rad=1.0), Phase),
        (Magnitude(V=0.1), Magnitude),
        (VariableRef(var="x"), VariableRef),
        (PulseRef(pulse_name="p1"), PulseRef),
        (True, bool),
        (3, int),
        (1.5, float),
        (1 + 2j, complex),
        ("foo", str),
    ],
)
def test_external_block_params_value_types(value: Any, expected_type: type):
    """Test that each ExternalParamValue member type is accepted in params."""
    block = ExternalBlock(channels={"a": "q0"}, duration=Duration(s=1e-6), params={"p": value})
    assert block.params is not None
    assert isinstance(block.params["p"], expected_type)


def test_external_block_params_pulse_type_value():
    """Test that an inline pulse can be passed as a params value."""
    pulse = SquarePulse(duration=Duration(s=1e-6), amplitude=Amplitude(V=0.5))
    block = ExternalBlock(channels={"a": "q0"}, duration=Duration(s=1e-6), params={"drive_pulse": pulse})
    assert block.params is not None
    assert block.params["drive_pulse"] == pulse


def test_external_block_results_binding():
    """Test that results binds output variables."""
    block = ExternalBlock(
        program="eq1.cal.measure",
        channels={"readout": "q0_ro"},
        duration=Duration(s=1e-6),
        results={"outcome": VariableRef(var="m0")},
    )
    assert block.results == {"outcome": VariableRef(var="m0")}


def test_external_block_flex_duration_with_runtime_variable_param_rejected():
    """Test that flex duration combined with a runtime-variable param is rejected."""
    with pytest.raises(ValidationError, match="flex duration"):
        ExternalBlock(
            program="eq1.cal.cz",
            channels={"a": "q0", "b": "q1"},
            params={"amp": VariableRef(var="amp")},
        )


def test_external_block_flex_duration_with_only_compile_time_params_allowed():
    """Test that flex duration is fine as long as no param is a runtime variable."""
    block = ExternalBlock(
        program="eq1.cal.cz",
        channels={"a": "q0", "b": "q1"},
        params={"amp": Voltage(V=0.5), "label": "foo"},
    )
    assert block.duration is None


def test_external_block_json_round_trip():
    """Test that an ExternalBlock round-trips through JSON serialization."""
    block = ExternalBlock(
        program="eq1.cal.measure",
        channels={"drive": "q0", "readout": "q0_ro"},
        params={"amp": Voltage(V=0.5)},
        results={"outcome": VariableRef(var="m0")},
        duration=Duration(s=1e-6),
    )
    dumped = block.model_dump_json()
    restored = ExternalBlock.model_validate_json(dumped)
    assert restored == block


def test_external_block_discriminated_union_dispatch():
    """Test that ExternalBlock dispatches correctly by op_type in DiscriminableOp."""
    block = ExternalBlock(channels={"drive": "q0"}, duration=Duration(s=1e-6))
    dispatched: Any = TypeAdapter(DiscriminableOp).validate_python(block.model_dump())
    assert isinstance(dispatched, ExternalBlock)
    assert dispatched == block


def test_external_block_nested_in_op_sequence_round_trip():
    """Test that an ExternalBlock nested inside an OpSequence round-trips."""
    block = ExternalBlock(channels={"drive": "q0"}, duration=Duration(s=1e-6))
    seq = OpSequence([block])
    dumped = seq.model_dump_json()
    restored = OpSequence.model_validate_json(dumped)
    assert restored == seq
    assert isinstance(restored.items[0], ExternalBlock)


def test_external_block_channels_accept_an_external_ref():
    """A channel name can itself be late-bound: the calibration store says which line drives ``q0``.

    That is an :class:`ExternalRef`, keeping the ``{"ext": ...}`` object it has everywhere else, so
    the field is the two-member :obj:`ChannelTarget` union and the two forms may be mixed.
    """
    block = ExternalBlock(
        channels={"drive": ExternalRef("q0.drive"), "readout": "q0_ro"},
        duration=Duration(s=1e-6),
    )
    assert block.channels == {"drive": ExternalRef("q0.drive"), "readout": ChannelRef("q0_ro")}
    assert block.model_dump()["channels"] == {"drive": {"ext": "q0.drive"}, "readout": "q0_ro"}
    assert ExternalBlock.model_validate_json(block.model_dump_json()) == block


def test_external_block_duration_accepts_expression():
    """``ExternalBlock.duration`` accepts an ``Expression``, not just a bare ``SymbolRef``."""
    duration = BinaryExpr(binary_op="+", lhs=SymbolExpr(symbol=VariableRef("d")), rhs=LiteralExpr(value={"ns": 10}))
    block = ExternalBlock(channels={"a": "q0"}, duration=duration)
    assert isinstance(block.duration, BinaryExpr)

    restored = ExternalBlock.model_validate(block.model_dump())
    assert isinstance(restored.duration, BinaryExpr)
