"""Tests for the OpenAPI schema generator module."""

import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import json
from tempfile import TemporaryDirectory

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
