"""One wire form per reference: three tagged objects and one bare channel name.

``{"var": ...}``, ``{"ext": ...}`` and ``{"pulse_name": ...}`` are what the tagged references
validate and serialize, in both directions; ``"q0_drive"`` is what a channel does. Nothing accepts
a form it does not emit, which is what the schema-symmetry ledger next door measures.
"""

from typing import Annotated, Any

import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models.expressions import SymbolExpr, ValueRef
from eq1_pulse.models.identifier_str import str_is_external_symbol
from eq1_pulse.models.pulse_types import ExternalParamValue
from eq1_pulse.models.reference_types import (
    ChannelRef,
    ChannelTarget,
    ExternalRef,
    PulseRef,
    Reference,
    ReferenceDiscriminator,
    SymbolRef,
    VariableRef,
    VarName,
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


def test_var_name_is_bare_and_the_unions_stay_tagged():
    """The two spellings of a variable, and the line between them.

    A field typed exactly :class:`VariableRef` carries ``"iq"``; a union of references carries
    ``{"var": "iq"}``. The tag is not decoration in the union positions: an :class:`ExternalRef` is
    also spelled as a name, and ``ExternalParamValue`` has a plain :obj:`str` member whose value is
    the string itself, so a bare ``"iq"`` there is not decidable. Do not "fix" one to match the
    other.
    """
    bare: TypeAdapter[Any] = TypeAdapter(VarName)
    assert bare.validate_json('"iq"') == VariableRef("iq")
    assert bare.dump_python(VariableRef("iq")) == "iq"
    assert bare.dump_json(VariableRef("iq")) == b'"iq"'
    with pytest.raises(ValidationError):
        bare.validate_json('{"var": "iq"}')

    for union in (SymbolRef, ValueRef, ExternalParamValue):
        tagged: TypeAdapter[Any] = TypeAdapter(union)
        assert tagged.validate_json('{"var": "iq"}') == VariableRef("iq")
        assert tagged.dump_python(VariableRef("iq")) == {"var": "iq"}

    assert SymbolExpr(symbol=VariableRef("iq")).model_dump() == {"symbol": {"var": "iq"}}


def test_var_name_publishes_the_same_string_in_both_schema_modes():
    """The Python-side widening is authoring sugar and must not reach the schema.

    :obj:`VarName` accepts a :class:`VariableRef` and a ``{"var": ...}`` dict in Python so that
    authoring code and the builder keep working. Were that widening visible, the validation schema
    would describe an input the serialization schema never produces -- the asymmetry the ledger in
    ``test_schema_symmetry.py`` exists to catch.
    """
    adapter: TypeAdapter[Any] = TypeAdapter(VarName)
    validation = adapter.json_schema(mode="validation")
    serialization = adapter.json_schema(mode="serialization")
    assert validation == serialization
    # Referenced rather than spelled out, so a constraint added to IdentifierStr reaches every
    # position that accepts a name instead of being understated here as a bare string.
    assert validation == {"$defs": {"IdentifierStr": {"type": "string"}}, "$ref": "#/$defs/IdentifierStr"}

    assert adapter.validate_python(VariableRef("iq")) == VariableRef("iq")
    assert adapter.validate_python({"var": "iq"}) == VariableRef("iq")
