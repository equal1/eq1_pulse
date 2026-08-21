"""Local warning filters for the experimental (schedule) test tree.

The global ``always::FutureWarning`` filter in ``pyproject.toml`` exists so
``test_module_boundaries.py`` can assert on the warning count from outside this tree.
Nearly every test here builds at least one schedule, so silence the resulting noise
locally instead of touching that global config.
"""

import warnings

import pytest


@pytest.fixture(autouse=True)
def _ignore_build_schedule_future_warning():
    """Ignore the build_schedule() deprecation warning for tests under this directory."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        yield
