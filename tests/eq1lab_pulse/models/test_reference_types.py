"""One wire form per reference: three tagged objects and one bare channel name.

``{"var": ...}``, ``{"ext": ...}`` and ``{"pulse_name": ...}`` are what the tagged references
validate and serialize, in both directions; ``"q0_drive"`` is what a channel does. Nothing accepts
a form it does not emit, which is what the schema-symmetry ledger next door measures.
"""

from typing import Annotated, Any

import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models.identifier_str import str_is_external_symbol
from eq1_pulse.models.reference_types import (
    ChannelRef,
    ChannelTarget,
    ExternalRef,
    PulseRef,
    Reference,
    ReferenceDiscriminator,
    SymbolRef,
    VariableRef,
)

TAGGED_REFERENCES: list[tuple[type[Reference], str, str]] = [
    (VariableRef, "var", "var1"),
    (ExternalRef, "ext", "q0[1].amp"),
    (PulseRef, "pulse_name", "pulse1"),
]


@pytest.mark.parametrize(("reference", "tag", "name"), TAGGED_REFERENCES, ids=lambda p: getattr(p, "__name__", p))
def test_tagged_reference_round_trips_as_its_object(reference, tag, name):
    """The tagged object is the wire form in both directions, and the constructor takes the name."""
    ref = reference(name)
    assert getattr(ref, tag) == name
    assert ref.model_dump() == {tag: name}
    assert reference.model_validate({tag: name}) == ref
    assert reference.model_validate_json(ref.model_dump_json()) == ref


@pytest.mark.parametrize(("reference", "tag", "name"), TAGGED_REFERENCES, ids=lambda p: getattr(p, "__name__", p))
def test_tagged_reference_rejects_the_bare_name(reference, tag, name):
    """A bare name is not a wire form: the constructor takes one, ``model_validate`` does not."""
    with pytest.raises(ValidationError):
        reference.model_validate(name)


@pytest.mark.parametrize(("reference", "tag", "name"), TAGGED_REFERENCES, ids=lambda p: getattr(p, "__name__", p))
def test_tagged_reference_rejects_extra_fields(reference, tag, name):
    """A tagged object is exactly one field wide; an extra key is not silently dropped."""
    with pytest.raises(ValidationError):
        reference.model_validate({tag: name, "unexpected": "value"})


@pytest.mark.parametrize(("reference", "tag", "name"), TAGGED_REFERENCES, ids=lambda p: getattr(p, "__name__", p))
def test_tagged_reference_schema_is_the_same_object_in_both_modes(reference, tag, name):
    """The default object schema is correct in both modes, so neither needs a hook."""
    schema = reference.model_json_schema()
    assert schema["type"] == "object"
    assert tag in schema["properties"]
    assert schema == reference.model_json_schema(mode="serialization")


def test_reference_compares_equal_to_its_bare_name():
    """The Python-level convenience the wire format no longer offers; plan §6 keeps it."""
    assert VariableRef("a") == "a"
    assert ExternalRef("q0.f01") == "q0.f01"
    assert PulseRef("pi") == "pi"
    assert VariableRef("a") != VariableRef("b")


def test_channel_ref_round_trips_as_the_bare_name():
    ref = ChannelRef("ch1")
    assert ref.root == "ch1"
    assert ref.model_dump() == "ch1"
    assert ref.model_dump_json() == '"ch1"'
    assert ChannelRef.model_validate("ch1") == ref
    assert ChannelRef.model_validate_json('"ch1"') == ref


def test_channel_ref_rejects_the_wrapped_form():
    """``{"channel": "ch1"}`` was only ever an input; the bare string is the wire form."""
    with pytest.raises(ValidationError):
        ChannelRef.model_validate({"channel": "ch1"})


def test_channel_ref_compares_equal_to_its_bare_name():
    """It leaves the :class:`Reference` hierarchy, so it carries this one member of its own."""
    assert ChannelRef("ch1") == "ch1"
    assert ChannelRef("ch1") == ChannelRef("ch1")
    assert ChannelRef("ch1") != ChannelRef("ch2")
    assert ChannelRef("ch1") != "ch2"


def test_channel_ref_schema_is_a_string_in_both_modes():
    """A root model publishes what it wraps -- here the identifier string -- and no object."""
    schema = ChannelRef.model_json_schema()
    assert schema["$defs"][schema["$ref"].rsplit("/", 1)[-1]] == {"type": "string"}
    assert "properties" not in schema
    assert schema == ChannelRef.model_json_schema(mode="serialization")


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


def test_symbol_ref_is_keyed_on_var_and_ext():
    adapter: TypeAdapter[SymbolRef] = TypeAdapter(SymbolRef)
    assert adapter.validate_python({"var": "amp"}) == VariableRef("amp")
    assert adapter.validate_python({"ext": "q0.f01"}) == ExternalRef("q0.f01")
    assert adapter.dump_python(VariableRef("amp")) == {"var": "amp"}
    assert adapter.dump_python(ExternalRef("q0.f01")) == {"ext": "q0.f01"}


def test_symbol_ref_has_no_bare_form_left():
    """Neither member has a shorthand, so there is no resolution order to depend on."""
    adapter: TypeAdapter[SymbolRef] = TypeAdapter(SymbolRef)
    with pytest.raises(ValidationError):
        adapter.validate_python("amp")


def test_channel_target_tells_the_two_forms_apart_by_json_type():
    adapter: TypeAdapter[ChannelTarget] = TypeAdapter(ChannelTarget)
    assert adapter.validate_python("q0_drive") == ChannelRef("q0_drive")
    assert adapter.validate_python({"ext": "q0.drive"}) == ExternalRef("q0.drive")
    assert adapter.dump_python(ChannelRef("q0_drive")) == "q0_drive"
    assert adapter.dump_python(ExternalRef("q0.drive")) == {"ext": "q0.drive"}


@pytest.mark.parametrize(
    ("union", "malformed"),
    [
        (SymbolRef, {"vr": "amp"}),
        (SymbolRef, "amp"),
        (ChannelTarget, {"channel": "ch1"}),
        (ChannelTarget, {"ex": "q0.drive"}),
        (ChannelTarget, 5),
    ],
)
def test_a_malformed_reference_produces_exactly_one_error(union, malformed):
    """Selection is a tag lookup, not a scoring pass, so a union does not report one error per member."""
    adapter: TypeAdapter[Any] = TypeAdapter(union)
    with pytest.raises(ValidationError) as excinfo:
        adapter.validate_python(malformed)

    assert len(excinfo.value.errors()) == 1
    assert excinfo.value.errors()[0]["type"].startswith("union_tag_")


def test_the_discriminator_reads_its_tags_off_the_members():
    """Adding a reference type means declaring it, with no tag table to keep in step."""
    assert ReferenceDiscriminator._tag_of(VariableRef) == "var"
    assert ReferenceDiscriminator._tag_of(ExternalRef) == "ext"
    assert ReferenceDiscriminator._tag_of(PulseRef) == "pulse_name"
    assert ReferenceDiscriminator._tag_of(ChannelRef) == ReferenceDiscriminator._BARE_TAG


def test_the_discriminator_needs_a_union():
    with pytest.raises(TypeError, match="union of reference models"):
        TypeAdapter(Annotated[VariableRef, ReferenceDiscriminator()])
