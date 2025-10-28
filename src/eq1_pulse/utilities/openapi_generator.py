"""Generate OpenAPI schema from the eq1_pulse models package.

This module provides functionality to generate OpenAPI 3.1.0 schemas from the
Pydantic models defined in the eq1_pulse.models package. It follows the approach
outlined in the `Speakeasy Pydantic guide <https://www.speakeasy.com/openapi/frameworks/pydantic>`_
article.

The generated schema includes all model definitions with proper references,
descriptions, examples, and can be exported to YAML or JSON format.

.. code-block:: python

    from eq1_pulse.utilities.openapi_generator import generate_openapi_schema, save_openapi_schema

    # Generate the schema
    schema = generate_openapi_schema()

    # Save to YAML file
    save_openapi_schema(schema, "openapi.yaml", format="yaml")

    # Save to JSON file
    save_openapi_schema(schema, "openapi.json", format="json")
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from eq1_pulse import __version__ as _eq1_pulse_version

if TYPE_CHECKING:
    from typing import Literal

__all__ = (
    "generate_openapi_schema",
    "get_all_pydantic_models",
    "save_openapi_schema",
)


def get_all_pydantic_models() -> list[type[BaseModel]]:
    """Discover and return all Pydantic models from the eq1_pulse.models package.

    This function dynamically imports all modules in the models package and
    extracts Pydantic BaseModel subclasses, excluding abstract base classes
    and internal models.

    :return: List of Pydantic model classes found in the models package

    .. note::

        This function filters out base classes like :class:`NoExtrasModel`,
        :class:`FrozenModel`, etc., to only include concrete model definitions.

    Examples

    .. code-block:: python

        models = get_all_pydantic_models()
        print(f"Found {len(models)} models")
        for model in models:
            print(f"  - {model.__name__}")
    """
    # List of modules to import from the models package
    model_modules = [
        "arithmetic",
        "base_models",
        "basic_types",
        "channel_ops",
        "complex",
        "control_flow",
        "data_ops",
        "identifier_str",
        "nd_array",
        "pulse_types",
        "reference_types",
        "schedule",
        "sequence",
        "units",
    ]

    # Base classes to exclude from the schema
    excluded_base_classes = {
        "NoExtrasModel",
        "FrozenModel",
        "LeanModel",
        "FrozenLeanModel",
        "WrappedValueModel",
        "FrozenWrappedValueModel",
        "WrappedValueOrZeroModel",
        "OpBase",
        "PulseBase",
        "SequenceBase",
        "RepetitionBase",
        "IterationBase",
        "ConditionalBase",
    }

    pydantic_models = []

    for module_name in model_modules:
        try:
            module = importlib.import_module(f"eq1_pulse.models.{module_name}")

            # Get all classes from the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Check if it's a Pydantic model and not a base class
                if (
                    issubclass(obj, BaseModel)
                    and obj.__module__.startswith("eq1_pulse.models")
                    and name not in excluded_base_classes
                    and not name.startswith("_")
                    and obj not in pydantic_models
                ):
                    # Avoid duplicates
                    pydantic_models.append(obj)
        except ImportError as e:
            print(f"Warning: Could not import module {module_name}: {e}")

    return pydantic_models


def generate_openapi_schema(
    title: str = "Equal1 Pulse Models API",
    version: str = _eq1_pulse_version,
    description: str | None = None,
    include_tags: bool = True,
) -> dict[str, Any]:
    """Generate a complete OpenAPI 3.1.0 schema from eq1_pulse models.

    This function creates a comprehensive OpenAPI schema document that includes
    all Pydantic models from the eq1_pulse.models package. The schema uses the
    OpenAPI 3.1.0 format with proper component references.

    :param title: The title of the API in the OpenAPI document
    :param version: The version of the API
    :param description: Optional description of the API. If :obj:`None`, a default
        description will be used
    :param include_tags: Whether to include tags in the schema for grouping models

    :return: Dictionary representation of the OpenAPI schema

    Examples

    .. code-block:: python

        schema = generate_openapi_schema(
            title="My Pulse API",
            version="2.0.0",
            description="Custom API for pulse control"
        )

    .. note::

        The generated schema uses ``#/components/schemas`` for references,
        which is the standard OpenAPI format compatible with SDK generators
        like Speakeasy.
    """
    if description is None:
        description = (
            "OpenAPI schema for Equal1 Pulse library models. "
            "This schema defines all the Pydantic models used for pulse sequencing, "
            "channel operations, control flow, and data operations."
        )

    # Get all Pydantic models
    models_list = get_all_pydantic_models()

    if not models_list:
        raise ValueError("No Pydantic models found in eq1_pulse.models package")

    # Generate JSON schema for all models with OpenAPI-compatible references
    # models_json_schema expects a list of tuples (model, mode)
    models_with_mode: list[tuple[type[BaseModel], Literal["validation", "serialization"]]] = [
        (model, "validation") for model in models_list
    ]
    _, definitions = models_json_schema(
        models_with_mode,
        ref_template="#/components/schemas/{model}",
        title="Equal1 Pulse Models",
    )

    # Build the OpenAPI document structure
    openapi_doc: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {
            "title": title,
            "version": version,
            "description": description,
        },
        "components": {
            "schemas": definitions.get("$defs", {}),
        },
        "paths": {},
    }

    # Add tags if requested
    if include_tags:
        tags = [
            {"name": "basic-types", "description": "Basic types like Amplitude, Duration, Frequency, etc."},
            {"name": "pulse-types", "description": "Pulse type definitions (Square, Sine, Arbitrary, etc.)"},
            {"name": "channel-ops", "description": "Channel operations (Play, Record, Barrier, etc.)"},
            {"name": "control-flow", "description": "Control flow operations (Repetition, Iteration, Conditional)"},
            {"name": "data-ops", "description": "Data operations (Assignment, Arithmetic, etc.)"},
            {"name": "sequences", "description": "Operation sequences and schedules"},
            {"name": "reference-types", "description": "Reference types for variables and parameters"},
            {"name": "units", "description": "Unit types (Seconds, Volts, Hertz, etc.)"},
        ]
        openapi_doc["tags"] = tags

    return openapi_doc


def save_openapi_schema(
    schema: dict[str, Any],
    output_path: str | Path,
    format: str = "yaml",
) -> None:
    """Save the OpenAPI schema to a file in YAML or JSON format.

    :param schema: The OpenAPI schema dictionary to save
    :param output_path: Path where the schema file should be saved
    :param format: Output format, either ``"yaml"`` or ``"json"``

    :raises ValueError: If an unsupported format is specified
    :raises ImportError: If ruamel.yaml is not installed and YAML format is requested

    Examples

    .. code-block:: python

        schema = generate_openapi_schema()

        # Save as YAML
        save_openapi_schema(schema, "openapi.yaml", format="yaml")

        # Save as JSON
        save_openapi_schema(schema, "openapi.json", format="json")
    """
    output_path = Path(output_path)

    if format.lower() == "yaml":
        try:
            from ruamel.yaml import YAML
        except ImportError as e:
            raise ImportError(
                "ruamel.yaml is required to save schema in YAML format. Install it with: pip install ruamel.yaml"
            ) from e

        yaml = YAML()
        yaml.default_flow_style = False
        yaml.preserve_quotes = True
        yaml.width = 4096  # Prevent line wrapping

        with output_path.open("w") as f:
            yaml.dump(schema, f)
    elif format.lower() == "json":
        with output_path.open("w") as f:
            json.dump(schema, f, indent=2)
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'yaml' or 'json'.")


def main() -> None:
    """Generate and save the OpenAPI schema for eq1_pulse models.

    This is a convenience function that can be run as a script to generate
    both YAML and JSON versions of the OpenAPI schema.

    Examples

    .. code-block:: bash

        python -m eq1_pulse.utilities.openapi_generator
    """
    print("Generating OpenAPI schema for eq1_pulse models...")

    # Generate the schema
    schema = generate_openapi_schema()

    # Get the number of models
    num_models = len(schema.get("components", {}).get("schemas", {}))
    print(f"Found {num_models} model schemas")

    # Save to YAML
    yaml_path = Path("openapi.yaml")
    try:
        save_openapi_schema(schema, yaml_path, format="yaml")
        print(f"✓ Saved OpenAPI schema to {yaml_path}")
    except ImportError:
        print("✗ Could not save YAML (ruamel.yaml not installed)")

    # Save to JSON
    json_path = Path("openapi.json")
    save_openapi_schema(schema, json_path, format="json")
    print(f"✓ Saved OpenAPI schema to {json_path}")

    print("\nSchema generation complete!")


if __name__ == "__main__":
    main()
