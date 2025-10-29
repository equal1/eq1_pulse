# OpenAPI Schema Generator for eq1_pulse Models

This module provides functionality to automatically generate OpenAPI 3.1.0 schemas from the Pydantic models in the `eq1_pulse.models` package.

This is an AI generated module for the `eq1_pulse`  based on the Speakeasy Pydantic guide, [available here](https://www.speakeasy.com/openapi/frameworks/pydantic):


## Overview

The OpenAPI schema generator discovers all Pydantic models in the eq1_pulse models package and creates a comprehensive OpenAPI schema that can be used for:

- SDK generation
- API documentation
- Client library generation
- Integration with API development tools

## Features

- Automatic Model Discovery: Recursively finds all Pydantic models in the models package
- OpenAPI 3.1.0 Compliant: Generates schemas compatible with the latest OpenAPI specification
- Save schemas as JSON or YAML
- Uses `#/components/schemas` references for inter-model relationships
- Groups models by category (basic types, pulse types, channel operations, etc.)
- Comprehensive documentation: went all the way to include model descriptions, field descriptions, and examples

## Installation

The module is part of the `eq1_pulse` package. To use YAML export, install ruamel.yaml:

```bash
pip install ruamel.yaml
```

## Usage

### Basic Usage

```python
from eq1_pulse.utilities.openapi_generator import generate_openapi_schema, save_openapi_schema

# Generate the schema
schema = generate_openapi_schema()

# Save to JSON
save_openapi_schema(schema, "openapi.json", format="json")

# Save to YAML (requires ruamel.yaml)
save_openapi_schema(schema, "openapi.yaml", format="yaml")
```

### Command-Line Usage

You can run the generator as a module:

```bash
python -m eq1_pulse.utilities.openapi_generator
```

This will generate both `openapi.json` and `openapi.yaml` files in the current directory.

### Example Script

See `examples/generate_openapi_example.py` for a complete example:

```bash
python examples/generate_openapi_example.py
```

### Advanced Usage

```python
from eq1_pulse.utilities.openapi_generator import (
    generate_openapi_schema,
    get_all_pydantic_models,
    save_openapi_schema,
)

# Discover all models
models = get_all_pydantic_models()
print(f"Found {len(models)} models")

# Generate custom schema
schema = generate_openapi_schema(
    title="My Custom API",
    version="2.0.0",
    description="Custom description for my API",
    include_tags=True,
)

# Save with custom path
save_openapi_schema(schema, "output/my_schema.yaml", format="yaml")
```

## Generated Schema Structure

The generated OpenAPI schema includes:

```yaml
openapi: 3.1.0
info:
  title: Equal1 Pulse Models API
  version: 1.0.0
  description: OpenAPI schema for Equal1 Pulse library models...
tags:
  - name: basic-types
    description: Basic types like Amplitude, Duration, Frequency, etc.
  - name: pulse-types
    description: Pulse type definitions (Square, Sine, Arbitrary, etc.)
  # ... more tags
components:
  schemas:
    SquarePulse:
      # Model definition
    SinePulse:
      # Model definition
    # ... all other models
```

## Integration with SDK Generators

The generated schema is compatible with various OpenAPI tools:
- [OpenAPI Generator](https://openapi-generator.tech/)
- [Swagger Codegen](https://swagger.io/tools/swagger-codegen/)
- [FastAPI](https://fastapi.tiangolo.com/) (can import the models directly)
- [Redoc](https://redocly.com/redoc/) (for documentation)

## Implementation Details

The generator uses Pydantic's `models_json_schema()` function to create JSON schemas for all models, then wraps them in the OpenAPI document structure. It:

1. **Discovers models**: Imports all modules in `eq1_pulse.models` and extracts Pydantic classes
2. **Filters base classes**: Excludes abstract base classes like `FrozenModel`, `NoExtrasModel`, etc.
3. **Generates schemas**: Uses Pydantic's schema generation with OpenAPI-compatible references
4. **Adds metadata**: Includes OpenAPI info, tags, and other metadata
5. **Exports**: Saves to JSON or YAML format

## References

- [Pydantic OpenAPI Guide](https://www.speakeasy.com/openapi/frameworks/pydantic)
- [OpenAPI 3.1.0 Specification](https://spec.openapis.org/oas/v3.1.0)
- [Pydantic JSON Schema Documentation](https://docs.pydantic.dev/latest/concepts/json_schema/)

## License

Same as the `eq1_pulse` package.
