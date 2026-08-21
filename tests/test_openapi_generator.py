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

    experimental_models = [model for model in get_all_pydantic_models() if "experimental" in model.__module__]
    assert experimental_models, "Expected at least one experimental model to check"

    for model in experimental_models:
        assert schemas[model.__name__].get("tags") == ["experimental"], (
            f"{model.__name__} is generated from {model.__module__} and should be tagged 'experimental'"
        )

    non_experimental_names = {model.__name__ for model in get_all_pydantic_models()} - {
        model.__name__ for model in experimental_models
    }
    for name in non_experimental_names:
        assert "tags" not in schemas.get(name, {}), f"{name} should not carry the 'experimental' tag"


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
    """A wrapped value model must not appear as ``{"value": ...}``; that form is never accepted.

    This is the regression guard for customising the schema via ``__get_pydantic_json_schema__``
    rather than by overriding ``model_json_schema()``: the latter is bypassed for nested models,
    so the generated document described the internal representation instead of the wire form.
    """
    for name in ("Duration", "Amplitude", "Frequency"):
        schema = generated_schemas[name]
        assert "properties" not in schema, f"{name} is described by its internal object shape"
        assert "anyOf" in schema, f"{name} should offer its accepted input forms"


def test_unit_models_accept_the_suffixed_string_form(generated_schemas):
    """``Seconds`` and friends accept ``"10s"`` as well as ``{"s": 10}``; both must be advertised."""
    schema = generated_schemas["Seconds"]
    branches = schema["anyOf"]
    assert any(branch.get("type") == "object" for branch in branches), "the object form is missing"
    assert any(branch.get("type") == "string" for branch in branches), "the string form is missing"


def test_bare_references_advertise_the_bare_form(generated_schemas):
    """A reference serializes bare, so the generated schema must accept the bare form."""
    for name in ("VariableRef", "ChannelRef", "PulseRef"):
        branches = generated_schemas[name]["anyOf"]
        assert len(branches) == 2, f"{name} should accept the bare value and the object form"
        assert any("$ref" in branch for branch in branches), f"{name} does not advertise the bare form"


def test_external_ref_stays_an_object(generated_schemas):
    """``ExternalRef`` keeps the wrapped form; a bare string is always a variable reference."""
    schema = generated_schemas["ExternalRef"]
    assert schema["type"] == "object"
    assert "ext" in schema["properties"]
    assert "anyOf" not in schema


def test_generated_schema_agrees_with_the_direct_call():
    """The same customisation must apply whether a model is asked directly or generated in bulk.

    Overriding ``model_json_schema()`` made these two disagree, which is what let the published
    document drift away from what the models actually accept.
    """
    from eq1_pulse.models.basic_types import Duration

    direct = Duration.model_json_schema()
    generated = generate_openapi_schema()["components"]["schemas"]["Duration"]

    def ref_names(schema):
        return [branch["$ref"].rsplit("/", 1)[-1] for branch in schema["anyOf"] if "$ref" in branch]

    assert ref_names(direct) == ref_names(generated)
    assert direct["anyOf"][0] == generated["anyOf"][0] == {"const": 0, "type": "integer"}


def test_serialization_mode_schema_can_be_generated():
    """``mode="serialization"`` used to raise ``KeyError`` on every reference model."""
    from eq1_pulse.models.reference_types import VariableRef

    assert VariableRef.model_json_schema(mode="serialization") is not None


def test_serialized_operations_validate_against_the_generated_schema():
    """What the models emit must validate against the document the generator publishes."""
    from eq1_pulse.models.channel_ops import Play, Wait

    schemas = json.loads(
        json.dumps(generate_openapi_schema()["components"]["schemas"]).replace("#/components/schemas/", "#/$defs/")
    )
    operations = [
        (Play(channel="ch1", pulse="p1"), "Play"),
        (Wait(channels=["ch1"], duration="10us"), "Wait"),
        (Wait(channels=["ch1"], duration={"ns": 100}), "Wait"),
    ]
    for operation, name in operations:
        document = json.loads(operation.model_dump_json())
        jsonschema.validate(document, {"$defs": schemas, **schemas[name]})
