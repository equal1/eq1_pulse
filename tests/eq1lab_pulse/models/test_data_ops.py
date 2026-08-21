from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models.basic_types import Amplitude, ComplexVoltage, Phase, Threshold, Voltage
from eq1_pulse.models.data_ops import (
    Assign,
    ComparisonMode,
    ComplexToRealProjectionMode,
    DataOp,
    Discriminate,
    ExternalDecl,
    ParameterDecl,
    PulseDecl,
    Store,
    StoreMode,
    SymbolValue,
    ValueLimits,
    VariableDecl,
)
from eq1_pulse.models.expressions import BinaryExpr, LiteralExpr, SymbolExpr
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
        target=VariableRef("result"),
        source=VariableRef("data"),
        threshold={"V": 0.5},
        rotation={"rad": 0.0},
        compare=">=",
        project="real",
    )


@pytest.fixture
def store() -> Store:
    return Store(key="test_key", source=VariableRef("data"), mode=StoreMode.Last)


@pytest.fixture
def assign() -> Assign:
    return Assign(target=VariableRef("count"), value=0)


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
    assert isinstance(discriminate.threshold, Threshold)
    assert isinstance(discriminate.rotation, Phase)
    assert discriminate.threshold.V == 0.5
    assert discriminate.rotation.rad == 0.0
    assert discriminate.compare == ComparisonMode.GreaterEqual
    assert discriminate.project == ComplexToRealProjectionMode.RealPart


def test_discriminate_target_rejects_external_ref():
    with pytest.raises(ValueError):
        Discriminate(
            target=ExternalRef("q0"),  # type: ignore[arg-type]
            source=VariableRef("data"),
            threshold={"V": 0.5},
            rotation={"rad": 0.0},
            compare=">=",
            project="real",
        )


def test_discriminate_threshold_and_rotation_accept_variable_and_external_ref():
    disc = Discriminate(
        target=VariableRef("result"),
        source=VariableRef("data"),
        threshold=VariableRef("thr"),
        rotation=ExternalRef("q0.rot"),
    )
    assert isinstance(disc.threshold, VariableRef)
    assert isinstance(disc.rotation, ExternalRef)

    disc = Discriminate(
        target=VariableRef("result"),
        source=VariableRef("data"),
        threshold=ExternalRef("q0.thr"),
        rotation=VariableRef("rot"),
    )
    assert isinstance(disc.threshold, ExternalRef)
    assert isinstance(disc.rotation, VariableRef)

    # Still accepts its literal form.
    disc = Discriminate(
        target=VariableRef("result"), source=VariableRef("data"), threshold={"V": 0.5}, rotation={"rad": 0.0}
    )
    assert isinstance(disc.threshold, Threshold)
    assert isinstance(disc.rotation, Phase)
    assert disc.threshold.V == 0.5
    assert disc.rotation.rad == 0.0


def test_discriminate_threshold_accepts_expression():
    """``Discriminate.threshold`` accepts an ``Expression``, not just a bare ``SymbolRef``."""
    threshold = BinaryExpr(binary_op="+", lhs=SymbolExpr(symbol=VariableRef("t")), rhs=LiteralExpr(value={"V": 0.1}))
    disc = Discriminate(target=VariableRef("result"), source=VariableRef("data"), threshold=threshold)
    assert isinstance(disc.threshold, BinaryExpr)

    document = disc.model_dump()
    reloaded: Any = TypeAdapter(DataOp).validate_python(document)
    assert isinstance(reloaded, Discriminate)
    assert isinstance(reloaded.threshold, BinaryExpr)


def test_store_creation(store: Store):
    assert store.key == "test_key"
    assert store.source.var == "data"
    assert store.mode == StoreMode.Last


def test_assign_creation(assign: Assign):
    assert assign.target.var == "count"
    assert assign.value == 0


def test_assign_accepts_variable_and_external_ref():
    written = Assign(target=VariableRef("count"), value=VariableRef("other"))
    assert isinstance(written.value, VariableRef)

    written = Assign(target=VariableRef("count"), value=ExternalRef("q0.n"))
    assert isinstance(written.value, ExternalRef)


def test_assign_accepts_expression():
    """``Assign.value`` accepts an ``Expression``, not just a bare ``SymbolValue``/``SymbolRef``."""
    value = BinaryExpr(binary_op="+", lhs=SymbolExpr(symbol=VariableRef("count")), rhs=LiteralExpr(value=1))
    written = Assign(target=VariableRef("count"), value=value)
    assert isinstance(written.value, BinaryExpr)

    document = written.model_dump()
    reloaded: Any = TypeAdapter(DataOp).validate_python(document)
    assert isinstance(reloaded, Assign)
    assert isinstance(reloaded.value, BinaryExpr)


def test_assign_serialization():
    assert Assign(target=VariableRef("count"), value=0).model_dump() == {"assign": {"target": "count", "value": 0}}


def test_variable_decl_serialization_unchanged():
    assert VariableDecl(name="x", dtype="float", unit="mV").model_dump() == {
        "var_decl": {"name": "x", "dtype": "float", "unit": "mV"}
    }


def test_variable_decl_without_optional_fields():
    decl = VariableDecl(name="x", dtype="int")
    assert decl.shape is None
    assert decl.unit is None
    assert decl.model_dump() == {"var_decl": {"name": "x", "dtype": "int"}}


def test_parameter_decl_without_optional_fields():
    decl = ParameterDecl(name="amp", dtype="float")
    assert decl.default is None
    assert decl.limits is None
    assert decl.model_dump() == {"param_decl": {"name": "amp", "dtype": "float"}}


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
    assert decl.model_dump() == {"extern_decl": {"name": "q0.f01", "dtype": "float"}}


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
    limits = ValueLimits(minimum={"mV": 0}, maximum={"V": 1}, allowed=[True, False])
    assert isinstance(limits.minimum, Voltage)
    assert limits.minimum.mV == 0
    assert isinstance(limits.maximum, Voltage)
    assert limits.maximum.V == 1
    assert limits.allowed == [True, False]


def test_symbol_value_numpy_complex_forms_are_tagged_as_complex():
    """A 2-element numpy array or a numpy complex scalar is recognized as the complex tag.

    :func:`~eq1_pulse.models.complex.validate_complex_tuple` accepts both, so the discriminator
    must route them there instead of falling through to :obj:`None`.
    """
    adapter: TypeAdapter[Any] = TypeAdapter(SymbolValue)
    assert adapter.validate_python(np.array([1.0, 2.0])) == 1 + 2j
    assert adapter.validate_python(np.complex128(1 + 2j)) == 1 + 2j


def test_symbol_value_amplitude_instance_survives_as_amplitude():
    """An Amplitude instance is tagged by its type, so it stays an Amplitude.

    :class:`~.basic_types.Amplitude` derives from :class:`~.basic_types.ComplexVoltage`, which is not
    a :class:`~.basic_types.Voltage` subclass; before the complex-voltage member was added the union
    rejected it, and with it :data:`~.expressions.LiteralExpr`'s most common value.
    """
    value: Any = TypeAdapter(SymbolValue).validate_python(Amplitude(mV=1 + 2j))
    assert isinstance(value, Amplitude)
    assert value.mV == 1 + 2j


def test_symbol_value_complex_voltage_wire_form():
    """A ``(real, imag)`` pair under a voltage unit key is a ComplexVoltage and dumps back unchanged."""
    adapter: TypeAdapter[Any] = TypeAdapter(SymbolValue)
    value = adapter.validate_python({"mV": [1, 2]})
    assert isinstance(value, ComplexVoltage)
    assert value.mV == 1 + 2j
    assert adapter.dump_python(value) == {"mV": (1.0, 2.0)}


def test_symbol_value_real_voltage_key_is_still_a_voltage():
    """A real number under the same unit key still resolves to the real dimension."""
    value: Any = TypeAdapter(SymbolValue).validate_python({"mV": 100})
    assert type(value) is Voltage
    assert value.mV == 100


def test_symbol_value_real_amplitude_narrows_to_voltage_on_the_way_back():
    """A real-valued Amplitude dumps ``{"mV": 100}`` and revalidates as a Voltage.

    The document round-trips unchanged and only the type narrows -- the same narrowing
    :class:`~.basic_types.Duration` gets to :class:`~.basic_types.Time`, for the same reason: on the
    wire a real complex voltage and a real voltage are one document. Intended, not a defect.
    """
    adapter: TypeAdapter[Any] = TypeAdapter(SymbolValue)
    document = adapter.dump_python(adapter.validate_python(Amplitude(mV=100)))
    assert document == {"mV": 100}
    assert type(adapter.validate_python(document)) is Voltage
    assert adapter.dump_python(adapter.validate_python(document)) == document


def test_symbol_value_unit_typo_reports_one_error():
    """An unknown unit key is one union_tag_not_found, not one error per member.

    The complex-voltage member is decided by value shape rather than by its own unit key, so it adds
    no second way for a typo to be reported.
    """
    with pytest.raises(ValidationError) as excinfo:
        TypeAdapter(SymbolValue).validate_python({"usec": 3})
    assert [error["type"] for error in excinfo.value.errors()] == ["union_tag_not_found"]


def test_value_limits_default_elision():
    assert ValueLimits().model_dump() == {}
    assert ValueLimits(minimum=0).model_dump() == {"minimum": 0}


def test_parameter_decl_limits_elided_when_none():
    assert ParameterDecl(name="amp", dtype="float").model_dump() == {"param_decl": {"name": "amp", "dtype": "float"}}


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
            lambda: Discriminate(target=VariableRef("result"), source=VariableRef("data"), threshold={"mV": 500}),
            id="discriminate",
        ),
        pytest.param(lambda: Store(key="test", source=VariableRef("data"), mode=StoreMode.Last), id="store"),
        pytest.param(lambda: Assign(target=VariableRef("count"), value=0), id="assign"),
    ],
)
def test_json_serialization(op: Callable[[], DataOp]):
    instance = op()
    json_data = instance.model_dump_json()
    adapter: Any = TypeAdapter(DataOp)
    loaded = adapter.validate_json(json_data)
    assert loaded.model_dump() == instance.model_dump()
    assert type(loaded) is type(instance)
