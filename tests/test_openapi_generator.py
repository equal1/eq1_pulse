"""Tests for the OpenAPI schema generator module."""

import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import json
from tempfile import TemporaryDirectory

import jsonschema
import pytest
from pydantic import BaseModel

from eq1_pulse.utilities.openapi_generator import (
    generate_openapi_schema,
    get_all_pydantic_models,
    save_openapi_schema,
)


def test_get_all_pydantic_models():
    """Test that we can discover all Pydantic models."""
    models = get_all_pydantic_models()

    # Should find at least some models
    assert len(models) > 0, "Should discover at least one model"

    # All should be BaseModel subclasses
    for model in models:
        assert issubclass(model, BaseModel), f"{model.__name__} should be a BaseModel subclass"

    # Should not include base classes
    excluded_names = {"NoExtrasModel", "FrozenModel", "LeanModel"}
    model_names = {m.__name__ for m in models}
    assert not model_names & excluded_names, "Should not include base classes"


def test_generate_openapi_schema():
    """Test OpenAPI schema generation."""
    schema = generate_openapi_schema()

    # Check basic structure
    assert "openapi" in schema
    assert schema["openapi"] == "3.1.0"

    assert "info" in schema
    assert "title" in schema["info"]
    assert "version" in schema["info"]
    assert "description" in schema["info"]

    assert "components" in schema
    assert "schemas" in schema["components"]

    # Should have schemas for models
    assert len(schema["components"]["schemas"]) > 0

    # Should have tags
    assert "tags" in schema
    assert len(schema["tags"]) > 0

    # Should have empty paths
    assert "paths" in schema
    assert len(schema["paths"]) == 0


def test_generate_openapi_schema_custom_params():
    """Test OpenAPI schema generation with custom parameters."""
    schema = generate_openapi_schema(
        title="Custom Title",
        version="2.0.0",
        description="Custom description",
        include_tags=False,
    )

    assert schema["info"]["title"] == "Custom Title"
    assert schema["info"]["version"] == "2.0.0"
    assert schema["info"]["description"] == "Custom description"
    assert "tags" not in schema


def test_save_openapi_schema_json():
    """Test saving schema to JSON format."""
    schema = generate_openapi_schema()

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_schema.json"
        save_openapi_schema(schema, output_path, format="json")

        assert output_path.exists()

        # Verify it's valid JSON
        with output_path.open() as f:
            loaded_schema = json.load(f)

        assert loaded_schema["openapi"] == "3.1.0"
        assert "components" in loaded_schema


def test_experimental_schema_components_are_tagged():
    """Test that schemas generated from eq1_pulse.models.experimental carry the "experimental" tag.

    A top-level tag only documents that the tag exists; it must also be attached to the
    components those experimental models actually produce.
    """
    schema = generate_openapi_schema()
    schemas = schema["components"]["schemas"]

    experimental_names = {model.__name__ for model in get_all_pydantic_models() if "experimental" in model.__module__}
    assert experimental_names, "Expected at least one experimental model to check"

    for model_name in experimental_names:
        assert model_name in schemas, f"Expected a schema component for experimental model {model_name}"
        assert schemas[model_name].get("tags") == ["experimental"], (
            f"{model_name} is generated from an experimental model and should be tagged 'experimental'"
        )

    for name, component_schema in schemas.items():
        if "tags" not in component_schema:
            continue
        assert name in experimental_names, f"{name} should not carry the 'experimental' tag"


def test_save_openapi_schema_yaml():
    """Test saving schema to YAML format."""
    pytest.importorskip("ruamel.yaml")  # Skip if ruamel.yaml not installed

    schema = generate_openapi_schema()

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_schema.yaml"
        save_openapi_schema(schema, output_path, format="yaml")

        assert output_path.exists()

        # Verify it's valid YAML
        from ruamel.yaml import YAML

        yaml = YAML()
        with output_path.open() as f:
            loaded_schema = yaml.load(f)

        assert loaded_schema["openapi"] == "3.1.0"
        assert "components" in loaded_schema


def test_save_openapi_schema_invalid_format():
    """Test that invalid format raises ValueError."""
    schema = generate_openapi_schema()

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_schema.txt"

        with pytest.raises(ValueError, match="Unsupported format"):
            save_openapi_schema(schema, output_path, format="txt")


def test_schema_contains_expected_models():
    """Test that schema contains some expected model types."""
    schema = generate_openapi_schema()
    schemas = schema["components"]["schemas"]

    # Check for some expected model types (these should exist in the models package)
    expected_model_patterns = ["Pulse", "Operation", "Sequence"]

    # At least one schema name should contain one of these patterns
    schema_names = list(schemas.keys())
    found_patterns = []

    for pattern in expected_model_patterns:
        if any(pattern.lower() in name.lower() for name in schema_names):
            found_patterns.append(pattern)

    assert len(found_patterns) > 0, f"Expected to find models matching {expected_model_patterns}"


if __name__ == "__main__":
    # Run tests with pytest if available, otherwise run directly
    try:
        import pytest

        pytest.main([__file__, "-v"])
    except ImportError:
        print("Running tests without pytest...")
        test_get_all_pydantic_models()
        print("✓ test_get_all_pydantic_models passed")

        test_generate_openapi_schema()
        print("✓ test_generate_openapi_schema passed")

        test_generate_openapi_schema_custom_params()
        print("✓ test_generate_openapi_schema_custom_params passed")

        test_save_openapi_schema_json()
        print("✓ test_save_openapi_schema_json passed")

        try:
            test_save_openapi_schema_yaml()
            print("✓ test_save_openapi_schema_yaml passed")
        except ModuleNotFoundError:
            print("⊘ test_save_openapi_schema_yaml skipped (ruamel.yaml not installed)")

        test_save_openapi_schema_invalid_format()
        print("✓ test_save_openapi_schema_invalid_format passed")

        test_schema_contains_expected_models()
        print("✓ test_schema_contains_expected_models passed")

        print("\nAll tests passed!")


@pytest.fixture(scope="module")
def generated_schemas():
    """The ``components.schemas`` section of the generated OpenAPI document."""
    return generate_openapi_schema()["components"]["schemas"]


def test_wrapped_models_are_not_described_by_their_internal_shape(generated_schemas):
    """A quantity appears as its unit union, once -- not as ``{"value": ...}``, not twice.

    The wrapping used to be hand-rolled, and the schema hand-corrected to match. Both are gone:
    a quantity is a :class:`~pydantic.RootModel` over its unit union, so the published schema is
    that union. It is also the *same* union in both modes, which is why these have no
    ``-Input``/``-Output`` split left to have.
    """
    for name in ("Duration", "Amplitude", "Frequency"):
        schema = generated_schemas[name]
        assert "properties" not in schema, f"{name} is described by its internal object shape"
        assert "oneOf" in schema, f"{name} should offer its unit alternatives"
        assert f"{name}-Input" not in generated_schemas, f"{name} still differs between modes"


def test_unit_models_publish_only_the_object_form(generated_schemas):
    """``Seconds`` is ``{"s": 10}`` and nothing else; ``"10s"`` is not a wire form.

    The suffixed string used to be accepted here and advertised as a second, validation-only
    branch. It is now read only where it is authored -- ``Duration.parse("10s")`` and the
    quantity constructors -- so the schema has one branch, in both modes.
    """
    schema = generated_schemas["Seconds"]
    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"s"}
    assert "Seconds-Input" not in generated_schemas


def test_tagged_references_publish_one_object_definition(generated_schemas):
    """A tagged reference is its object, in both directions, so it needs no ``-Input``/``-Output`` split."""
    for name, tag in (("VariableRef", "var"), ("ExternalRef", "ext"), ("PulseRef", "pulse_name")):
        schema = generated_schemas[name]
        assert schema["type"] == "object"
        assert tag in schema["properties"]
        assert "anyOf" not in schema
        assert f"{name}-Input" not in generated_schemas, f"{name} still differs between modes"


def test_a_channel_publishes_the_bare_name_and_its_external_alternative(generated_schemas):
    """``ChannelRef`` is the channel name itself; a channel field offers it or an ``ExternalRef``."""
    assert generated_schemas["ChannelRef"]["$ref"].endswith("IdentifierStr")
    assert "ChannelRef-Input" not in generated_schemas

    branches = generated_schemas["ChannelTarget"]["oneOf"]
    assert [branch["$ref"].rsplit("/", 1)[-1] for branch in branches] == ["ChannelRef", "ExternalRef"]


def test_symbol_declarations_are_in_the_schema(generated_schemas):
    """``ValueLimits``, ``ParameterDecl`` and ``ExternalDecl`` are published; their shared base is not.

    ``SymbolDeclBase`` exists only to factor out common fields and is excluded the same way
    ``DataOpBase`` is -- it is never referenced by a discriminated union and has no wire form of
    its own.
    """
    for name in ("ValueLimits", "ParameterDecl", "ExternalDecl"):
        assert name in generated_schemas, f"{name} should be present in components.schemas"

    assert "SymbolDeclBase" not in generated_schemas, "SymbolDeclBase should not be published"


def test_variable_decl_schema_is_unchanged(generated_schemas):
    """Check that ``VariableDecl``'s schema survives its refactor onto ``SymbolDeclBase``.

    That base class was introduced for ``ParameterDecl``/``ExternalDecl`` to share; it must not
    change what ``VariableDecl`` itself publishes.
    """
    schema = generated_schemas["VariableDecl"]
    assert set(schema["properties"]) == {"op_type", "dtype", "shape", "unit", "name"}


def test_no_component_schema_has_an_input_output_suffix(generated_schemas):
    """``components.schemas`` has no ``-Input``/``-Output`` names.

    ``models_json_schema()`` only splits a model into ``<Model>-Input``/``<Model>-Output`` when its
    validation and serialization schemas disagree; the schema-symmetry invariant
    (:func:`tests.eq1lab_pulse.models.test_schema_symmetry`) means that never happens.
    """
    for name in generated_schemas:
        assert not name.endswith("-Input"), f"{name} should not need an -Input split"
        assert not name.endswith("-Output"), f"{name} should not need an -Output split"


def test_generated_schema_agrees_with_the_direct_call():
    """The same customisation must apply whether a model is asked directly or generated in bulk.

    Overriding ``model_json_schema()`` made these two disagree, which is what let the published
    document drift away from what the models actually accept.
    """
    from eq1_pulse.models.basic_types import Duration

    direct = Duration.model_json_schema()
    generated = generate_openapi_schema()["components"]["schemas"]["Duration"]

    def ref_names(schema):
        return [branch["$ref"].rsplit("/", 1)[-1] for branch in schema["oneOf"] if "$ref" in branch]

    assert ref_names(direct) == ref_names(generated) == ["Seconds", "Milliseconds", "Microseconds", "Nanoseconds"]


def test_serialization_mode_schema_is_no_longer_empty():
    """``mode="serialization"`` used to raise ``KeyError``, then to collapse to ``{}``.

    :meth:`~eq1_pulse.models.base_models.LeanModel.__get_pydantic_json_schema__` now rebuilds it
    from the field annotations, independent of the plain ``@model_serializer``'s undeclared return
    type. (The reference types this used to be checked on no longer need the fix at all: since
    task 5 they carry no model serializer to defeat the default schema.)
    """
    from eq1_pulse.models.channel_ops import Wait

    schema = Wait.model_json_schema(mode="serialization")
    assert schema["type"] == "object"
    assert set(schema["properties"]) == set(Wait.model_fields)


def test_serialized_models_validate_against_the_generated_schema():
    """What the models emit must validate against the *output* schema the generator publishes."""
    from eq1_pulse.models.basic_types import Amplitude, Duration
    from eq1_pulse.models.channel_ops import Play, Wait
    from eq1_pulse.models.external_block import ExternalBlock
    from eq1_pulse.models.pulse_types import ExternalPulse
    from eq1_pulse.models.reference_types import PulseRef, VariableRef

    schemas = json.loads(
        json.dumps(generate_openapi_schema()["components"]["schemas"]).replace("#/components/schemas/", "#/$defs/")
    )
    models = [
        (Play(channel="ch1", pulse=PulseRef("p1")), "Play"),
        (Wait(channels=["ch1"], duration=Duration("10us")), "Wait"),
        (Wait(channels=["ch1"], duration={"ns": 100}), "Wait"),
        (
            ExternalPulse(
                function="eq1.pulses.drag",
                duration=Duration("10us"),
                amplitude=Amplitude("100mV"),
                params={
                    "detuning": "5GHz",
                    "phase_offset": 0.5 - 0.25j,
                    "scale": VariableRef(var="scale"),
                    "template": PulseRef(pulse_name="template"),
                },
            ),
            "ExternalPulse",
        ),
        (
            ExternalBlock(
                program="eq1.cal.measure",
                channels={"readout": "ch1"},
                params={"template": PulseRef(pulse_name="template")},
                results={"outcome": VariableRef(var="result")},
                duration=Duration("10us"),
            ),
            "ExternalBlock",
        ),
    ]
    for model, name in models:
        document = json.loads(model.model_dump_json())
        output_schema = schemas[name]
        jsonschema.validate(document, {"$defs": schemas, **output_schema})


def test_serialized_opsequence_validates_against_the_generated_schema():
    """The top-level program container must validate against its own published schema too.

    ``test_serialized_models_validate_against_the_generated_schema`` above checks five individual
    operation and pulse models and never :class:`~eq1_pulse.models.sequence.OpSequence`, which is
    how the defect this guards survived the last pass over this area: the container serialized to
    a bare JSON array while its schema described a ``{"items": [...]}`` object.
    """
    from eq1_pulse.builder import build_sequence, play, wait
    from eq1_pulse.models.sequence import OpSequence

    with build_sequence() as seq:
        wait("ch1", duration="10us")
        play("ch1", "p1")

    document = json.loads(seq.model_dump_json())
    jsonschema.validate(document, OpSequence.model_json_schema())
