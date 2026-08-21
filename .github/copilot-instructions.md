# eq1_pulse Copilot Instructions

## Project Overview
**eq1_pulse** is a Python library (Python >=3.12) providing a uniform, portable intermediate representation (IR) for quantum pulse programs. It uses Pydantic models extensively for validation and serialization.

### Architecture: Three-Layer Model System
1. **Models Layer** (`src/eq1_pulse/models/`): Core Pydantic data models defining the pulse program IR
   - `base_models.py`: Base model hierarchy (`NoExtrasModel`, `FrozenModel`, `LeanModel`, `WrappedValueModel`)
   - `basic_types.py`: Fundamental types (`Duration`, `Frequency`, `Amplitude`, `Phase`, `Time`)
   - `pulse_types.py`: Pulse definitions (`SquarePulse`, `SinePulse`, `ArbitrarySampledPulse`, `ExternalPulse`)
   - `channel_ops.py`: Channel operations (`Play`, `Record`, `Wait`, `Barrier`, `SetFrequency`, `SetPhase`)
   - `data_ops.py`: Data operations (`VariableDecl`, `PulseDecl`, `Store`, `Discriminate`)
   - `control_flow.py`: Control structures (`Repetition`, `Iteration`, `Conditional`)
   - `sequence.py`: Implicit timing via `OpSequence` (earliest-possible-start-time scheduling)
   - `schedule.py`: Explicit timing via `Schedule` with relative positioning using reference points

2. **Builder Layer** (`src/eq1_pulse/builder/`): Context-manager-based DSL for constructing pulse programs
   - Global state in `_context_stack` tracks nested contexts (sequences/schedules)
   - `@contextmanager` decorators: `build_sequence()`, `build_schedule()`, `repeat()`, `for_()`, `if_()`
   - Operations return `OperationToken` in schedules for reference positioning (e.g., `ref_op=token, ref_pt="end"`)
   - Functions: `play()`, `record()`, `wait()`, `barrier()`, `measure()`, `set_frequency()`, etc.

3. **Utilities Layer** (`src/eq1_pulse/utilities/`): OpenAPI schema generation, unique naming

### Key Concepts
- **Sequences vs Schedules**: `OpSequence` has implicit timing; `Schedule` uses explicit relative timing with `RefPt` (start/end/center) and `RelTime`
- **OperationToken**: Returned by builder operations in schedule contexts; used for relative positioning instead of hardcoded names
- **Pulse Types**: NO Gaussian/DRAG pulses in models. Use `ArbitrarySampledPulse` or `ExternalPulse` instead
- **Type Coercion**: Models accept string/dict inputs (e.g., `"10us"`, `{"ns": 100}`) and auto-convert to proper types

## Development Workflow

### Environment Setup
```bash
conda activate eq1_pulse-dev  # REQUIRED before running any Python commands
# Create dev environment:
./setup/unix/create_dev_env.sh
```

### Running QA Checks
```bash
conda activate eq1_pulse-dev
./qa/run_all_qa.sh  # Runs pyright, mypy, pytest with coverage
```

### Individual Tools
```bash
conda run -n eq1_pulse-dev pyright src tests
conda run -n eq1_pulse-dev mypy src tests
conda run -n eq1_pulse-dev pytest tests  # Coverage in pyproject.toml
```

### Documentation
```bash
conda activate eq1_pulse-dev
cd docs && ./generate_html.sh  # Builds Sphinx HTML docs
cd docs && ./generate_pdf.sh   # Builds LaTeX/PDF docs
```

## Code Conventions

### Documentation (ReST/Sphinx)
- Use `:param name:` not `Args:`; `:return:` not `Returns:`; `:raises:` not `Raises:`
- Omit `:type:` directives (types inferred from annotations)
- Wrap Python keywords: `:obj:`None``, `:obj:`True``, `:obj:`False``
- Reference style: `:func:`func_name``, `:meth:`method_name``, `:class:`ClassName``, `:attr:`attr_name``
- Code blocks: Indent 4 spaces, preceded by `.. code-block:: python` with blank lines before/after
- Add blank line after section headers (Examples, Notes, etc.)

### Python Style
- Use `X | Y` in `isinstance()` calls, not `(X, Y)` (UP038 Ruff rule)
- Generic functions should use type parameters (UP047 Ruff rule)  -- instead of TypeVar; ParamSpec etc
- **CRITICAL: Blank lines MUST be completely empty** - NO spaces, tabs, or any whitespace on blank lines
   - ALSO STRIP ALL trailing whitespace
   - EXCEPT for Makefiles where it has semantic meaning
- **NO excessive blank lines**: Maximum 2 consecutive blank lines between top-level definitions; 1 blank line within functions/methods
- Line length: 120 chars (Ruff configured)
- Pydantic models: Inherit from base classes in `base_models.py`
- Use `TYPE_CHECKING` imports to avoid circular dependencies

## Markdown Conventions:
- When generating tables, please make sure the pipes (`|`) are aligned for better readability in raw markdown. Thank you please.

### Type Hints
- Models define `*Like` type aliases for flexible inputs (e.g., `DurationLike = Duration | dict[str, float] | str`)
- Use `@overload` for multiple constructor signatures in `TYPE_CHECKING` blocks
- Discriminated unions via `Discriminator("op_type")` or `Discriminator("pulse_type")`

## Testing
- Tests in `tests/` mirror `src/` structure
- `pytest.ini_options` in `pyproject.toml`: `pythonpath = "src"`, `addopts = "--cov=src"`
- Example files in `examples/` demonstrate builder API patterns

## CI/CD
- GitHub Actions: `.github/workflows/` (ruff, mypy, pyright, pytest, sphinx)
- Pre-commit hooks: ruff (lint+format), mypy, trailing whitespace, nb-clean
- Reusable workflow: `common-setup-workflow.yml` sets up Conda environment

## Common Pitfalls
- **Conda activation**: IDE may not auto-activate `eq1_pulse-dev`; manually activate before terminal commands
   - ***use `conda activate eq1_pulse-dev` if the prompt does not show `(eq1_pulse-dev)`***
- **Builder context**: Operations must be inside `build_sequence()` or `build_schedule()` context managers
- **Schedule positioning**: Use `OperationToken` return values as `ref_op`, not hardcoded strings
- **Pulse types**: Don't assume Gaussian/DRAG exist—use `ArbitrarySampledPulse` or `ExternalPulse`
- **DO NOT USE `git checkout`**: when you have uncommitted changes in-flight. Use `git stash` instead to avoid losing changes. Handle untracked files carefully, do not try to stash everything, but save away the work safely.
