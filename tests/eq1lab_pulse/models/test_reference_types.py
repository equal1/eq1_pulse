import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models.identifier_str import str_is_external_symbol
from eq1_pulse.models.reference_types import ChannelRef, ExternalRef, PulseRef, SymbolRef, VariableRef


def test_channel_ref():
    ref = ChannelRef("ch1")
    assert ref.channel == "ch1"


def test_channel_ref_serialization():
    ref = ChannelRef("ch1")
    assert ref.model_dump() == "ch1"  # type: ignore


def test_channel_ref_validation():
    ref = ChannelRef.model_validate("ch1")
    assert ref.channel == "ch1"


def test_channel_ref_json_validation():
    ref = ChannelRef.model_validate_json('"ch1"')
    assert ref.channel == "ch1"


def test_channel_ref_json_serialization():
    ref = ChannelRef("ch1")
    assert ref.model_dump_json() == '"ch1"'


def test_pulse_ref():
    ref = PulseRef("pulse1")
    assert ref.pulse_name == "pulse1"


def test_pulse_ref_serialization():
    ref = PulseRef("pulse1")
    assert ref.model_dump() == "pulse1"  # type: ignore


def test_pulse_ref_validation():
    ref = PulseRef.model_validate("pulse1")
    assert ref.pulse_name == "pulse1"


def test_pulse_ref_json_validation():
    ref = PulseRef.model_validate_json('"pulse1"')
    assert ref.pulse_name == "pulse1"


def test_pulse_ref_json_serialization():
    ref = PulseRef("pulse1")
    assert ref.model_dump_json() == '"pulse1"'


def test_variable_ref():
    ref = VariableRef("var1")
    assert ref.var == "var1"


def test_variable_ref_serialization():
    ref = VariableRef("var1")
    assert ref.model_dump() == "var1"  # type: ignore


def test_variable_ref_validation():
    ref = VariableRef.model_validate("var1")
    assert ref.var == "var1"


def test_variable_ref_json_validation():
    ref = VariableRef.model_validate_json('"var1"')
    assert ref.var == "var1"


def test_variable_ref_json_serialization():
    ref = VariableRef("var1")
    assert ref.model_dump_json() == '"var1"'


EXTERNAL_SYMBOLS_ACCEPTED = ["q0", "q0[1]", "q0.f01", "q0[1].amp", "chip.q0[3].readout.threshold"]
EXTERNAL_SYMBOLS_REJECTED = ["1q", "q0[]", "q0.", "q0[a]", 'q0["aux"]', "q0[-1]", "", "q0..f01"]


@pytest.mark.parametrize("symbol", EXTERNAL_SYMBOLS_ACCEPTED)
def test_external_symbol_grammar_accepts(symbol):
    assert str_is_external_symbol(symbol) == symbol
    assert ExternalRef(symbol).ext == symbol


@pytest.mark.parametrize("symbol", EXTERNAL_SYMBOLS_REJECTED)
def test_external_symbol_grammar_rejects(symbol):
    with pytest.raises(ValueError):
        str_is_external_symbol(symbol)

    with pytest.raises(ValidationError):
        ExternalRef(symbol)


def test_external_ref():
    ref = ExternalRef("q0[1].amp")
    assert ref.ext == "q0[1].amp"


def test_external_ref_serialization_is_wrapped():
    ref = ExternalRef("q0[1].amp")
    assert ref.model_dump() == {"ext": "q0[1].amp"}
    assert ref.model_dump_json() == '{"ext":"q0[1].amp"}'


def test_external_ref_validation():
    assert ExternalRef.model_validate({"ext": "q0.f01"}).ext == "q0.f01"
    assert ExternalRef.model_validate("q0.f01").ext == "q0.f01"


def test_external_ref_json_round_trip():
    ref = ExternalRef("chip.q0[3].readout.threshold")
    assert ExternalRef.model_validate_json(ref.model_dump_json()) == ref


def test_external_ref_json_schema_is_an_object():
    schema = ExternalRef.model_json_schema()
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "ext" in schema["properties"]


def test_variable_ref_serialization_is_still_bare():
    ref = VariableRef("amp")
    assert ref.model_dump() == "amp"  # type: ignore
    assert ref.model_dump_json() == '"amp"'


def test_symbol_ref_resolves_bare_string_to_a_variable():
    adapter: TypeAdapter[SymbolRef] = TypeAdapter(SymbolRef)
    ref = adapter.validate_python("amp")
    assert isinstance(ref, VariableRef)
    assert ref.var == "amp"


def test_symbol_ref_resolves_wrapped_form_to_an_external():
    adapter: TypeAdapter[SymbolRef] = TypeAdapter(SymbolRef)
    ref = adapter.validate_python({"ext": "q0.f01"})
    assert isinstance(ref, ExternalRef)
    assert ref.ext == "q0.f01"


def test_symbol_ref_union_serialization_is_unambiguous():
    adapter: TypeAdapter[SymbolRef] = TypeAdapter(SymbolRef)
    assert adapter.dump_python(VariableRef("amp")) == "amp"
    assert adapter.dump_python(ExternalRef("q0.f01")) == {"ext": "q0.f01"}
    assert adapter.validate_json(adapter.dump_json(ExternalRef("q0.f01"))) == ExternalRef("q0.f01")
