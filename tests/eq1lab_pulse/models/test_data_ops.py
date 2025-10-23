from collections.abc import Callable
from typing import Any

import pytest
from pydantic import TypeAdapter

from eq1_pulse.models.data_ops import (
    ComparisonMode,
    ComplexToRealProjectionMode,
    DataOp,
    Discriminate,
    PulseDecl,
    Store,
    StoreMode,
    VariableDecl,
)
from eq1_pulse.models.pulse_types import SquarePulse
from eq1_pulse.models.reference_types import VariableRef


@pytest.fixture
def var_decl() -> VariableDecl:
    return VariableDecl(name="test_var", dtype="complex")


@pytest.fixture
def square_pulse() -> SquarePulse:
    return SquarePulse(duration={"ns": 100}, amplitude={"V": 1.0})


@pytest.fixture
def pulse_decl(square_pulse: SquarePulse) -> PulseDecl:
    return PulseDecl(
        name="test_pulse",
        pulse=square_pulse,
    )


@pytest.fixture
def discriminate() -> Discriminate:
    return Discriminate(
        target="result",
        source="data",
        threshold={"V": 0.5},
        rotation={"rad": 0.0},
        compare=">=",
        project="real",
    )


@pytest.fixture
def store() -> Store:
    return Store(key="test_key", source=VariableRef("data"), mode=StoreMode.Last)


def test_variable_decl_creation(var_decl: VariableDecl):
    assert var_decl.name == "test_var"
    assert var_decl.dtype == "complex"
    assert var_decl.shape is None


def test_pulse_decl_creation(pulse_decl: PulseDecl):
    assert pulse_decl.name == "test_pulse"
    assert isinstance(pulse_decl.pulse, SquarePulse)


def test_discriminate_creation(discriminate: Discriminate):
    assert discriminate.target.var == "result"
    assert discriminate.source.var == "data"
    assert discriminate.threshold.V == 0.5
    assert discriminate.rotation.rad == 0.0
    assert discriminate.compare == ComparisonMode.GreaterEqual
    assert discriminate.project == ComplexToRealProjectionMode.RealPart


def test_store_creation(store: Store):
    assert store.key == "test_key"
    assert store.source.var == "data"
    assert store.mode == StoreMode.Last


@pytest.mark.parametrize(
    "op",
    [
        pytest.param(lambda: VariableDecl(name="test", dtype="complex"), id="var_decl"),
        pytest.param(
            lambda: PulseDecl(name="test", pulse=SquarePulse(duration={"ns": 100}, amplitude={"V": 1.0})),
            id="pulse_decl",
        ),
        pytest.param(
            lambda: Discriminate(target="result", source="data", threshold={"mV": 500}),
            id="discriminate",
        ),
        pytest.param(lambda: Store(key="test", source=VariableRef("data"), mode=StoreMode.Last), id="store"),
    ],
)
def test_json_serialization(op: Callable[[], DataOp]):
    instance = op()
    json_data = instance.model_dump_json()
    adapter: Any = TypeAdapter(DataOp)
    loaded = adapter.validate_json(json_data)
    assert loaded.model_dump() == instance.model_dump()
