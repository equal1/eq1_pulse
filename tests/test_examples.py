"""Execute every script in ``examples/`` to keep the reference material working.

The examples are the only executable documentation in the repository: the snippets in
``docs/`` and in docstrings are inert text. Running them here catches API drift that
would otherwise only surface when a user copies an example.
"""

import runpy
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
EXAMPLE_SCRIPTS = sorted(EXAMPLES_DIR.glob("*.py"))


@pytest.mark.parametrize("script", EXAMPLE_SCRIPTS, ids=lambda p: p.stem)
def test_example_runs(script: Path, capsys: pytest.CaptureFixture[str]):
    """Test that the example script runs to completion without raising."""
    sys.path.insert(0, str(script.parent))
    try:
        runpy.run_path(str(script), run_name="__main__")
    finally:
        sys.path.remove(str(script.parent))
    capsys.readouterr()  # examples print a lot; keep the test output readable


def test_examples_directory_is_not_empty():
    """Test that the parametrization above actually found scripts to run."""
    assert EXAMPLE_SCRIPTS, f"no example scripts found in {EXAMPLES_DIR}"
