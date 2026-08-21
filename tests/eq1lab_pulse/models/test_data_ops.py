from collections.abc import Callable
from typing import Any

import pytest
from pydantic import TypeAdapter

from eq1_pulse.models.basic_types import Amplitude
from eq1_pulse.models.data_ops import (
    ComparisonMode,
    ComplexToRealProjectionMode,
    DataOp,
    Discriminate,
    ExternalDecl,
    ParameterDecl,
    PulseDecl,
    Store,
    StoreMode,
    ValueLimits,
    VariableDecl,
)
from eq1_pulse.models.pulse_types import SquarePulse
from eq1_pulse.models.reference_types import ExternalRef, VariableRef


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


def test_discriminate_target_rejects_external_ref():
    with pytest.raises(ValueError):
        Discriminate(
            target=ExternalRef("q0"),  # type: ignore[arg-type]
            source="data",
            threshold={"V": 0.5},
            rotation={"rad": 0.0},
            compare=">=",
            project="real",
        )


def test_store_creation(store: Store):
    assert store.key == "test_key"
    assert store.source.var == "data"
    assert store.mode == StoreMode.Last


def test_variable_decl_serialization_unchanged():
    assert VariableDecl(name="x", dtype="float", unit="mV").model_dump() == {
        "op_type": "var_decl",
        "name": "x",
        "dtype": "float",
        "unit": "mV",
    }


def test_variable_decl_without_optional_fields():
    decl = VariableDecl(name="x", dtype="int")
    assert decl.shape is None
    assert decl.unit is None
    assert decl.model_dump() == {"op_type": "var_decl", "name": "x", "dtype": "int"}


def test_parameter_decl_without_optional_fields():
    decl = ParameterDecl(name="amp", dtype="float")
    assert decl.default is None
    assert decl.limits is None
    assert decl.model_dump() == {"op_type": "param_decl", "name": "amp", "dtype": "float"}


def test_parameter_decl_with_optional_fields():
    decl = ParameterDecl(
        name="amp",
        dtype="float",
        shape=(2,),
        unit="mV",
        default=100,
        limits=ValueLimits(minimum=0, maximum=1000),
    )
    assert decl.shape == (2,)
    assert decl.unit == "mV"
    assert decl.default == 100
    assert decl.limits is not None
    assert decl.limits.minimum == 0
    assert decl.limits.maximum == 1000


def test_parameter_decl_round_trip():
    decl = ParameterDecl(name="amp", dtype="float", unit="mV", default=100, limits=ValueLimits(maximum=1000))
    loaded = ParameterDecl.model_validate(decl.model_dump())
    assert loaded.model_dump() == decl.model_dump()


def test_external_decl_without_optional_fields():
    decl = ExternalDecl(name="q0.f01", dtype="float")
    assert decl.default is None
    assert decl.limits is None
    assert decl.model_dump() == {"op_type": "extern_decl", "name": "q0.f01", "dtype": "float"}


def test_external_decl_with_optional_fields():
    decl = ExternalDecl(
        name="q0[1].amp",
        dtype="float",
        unit="mV",
        default=50,
        limits=ValueLimits(allowed=[10, 20, 50]),
    )
    assert decl.name == "q0[1].amp"
    assert decl.default == 50
    assert decl.limits is not None
    assert decl.limits.allowed == [10, 20, 50]


def test_value_limits_accepts_dimensional_and_scalar_bounds():
    limits = ValueLimits(minimum={"mV": 0}, maximum="1V", allowed=[True, False])
    assert isinstance(limits.minimum, Amplitude)
    assert limits.minimum.mV == 0
    assert isinstance(limits.maximum, Amplitude)
    assert limits.maximum.V == 1
    assert limits.allowed == [True, False]


def test_value_limits_default_elision():
    assert ValueLimits().model_dump() == {}
    assert ValueLimits(minimum=0).model_dump() == {"minimum": 0}


def test_parameter_decl_limits_elided_when_none():
    assert ParameterDecl(name="amp", dtype="float").model_dump() == {
        "op_type": "param_decl",
        "name": "amp",
        "dtype": "float",
    }


@pytest.mark.parametrize(
    "op",
    [
        pytest.param(lambda: VariableDecl(name="test", dtype="complex"), id="var_decl"),
        pytest.param(lambda: ParameterDecl(name="amp", dtype="float", default=1.0), id="param_decl"),
        pytest.param(lambda: ExternalDecl(name="q0.f01", dtype="float", default=1.0), id="extern_decl"),
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
    assert type(loaded) is type(instance)
