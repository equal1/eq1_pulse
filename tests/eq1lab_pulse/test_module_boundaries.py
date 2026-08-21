"""Enforce the boundary between the sequence and schedule builders.

Covers the acceptance gates for the sequence/schedule builder split:

- G3, import direction: nothing outside an ``experimental`` package may import from one.
- G4, mixing rejection: each builder must refuse the other's contexts, with a message
  that points at the correct module.
- G6, warning count: entering ``build_schedule()`` emits exactly one ``FutureWarning``,
  regardless of how many operations the schedule contains.
"""

import ast
import warnings
from collections.abc import Iterator
from pathlib import Path

import pytest

from eq1_pulse.builder import build_sequence
from eq1_pulse.builder import play as sequence_play
from eq1_pulse.builder import repeat as sequence_repeat
from eq1_pulse.builder.experimental import build_schedule, square_pulse
from eq1_pulse.builder.experimental import play as schedule_play
from eq1_pulse.builder.experimental import repeat as schedule_repeat

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "eq1_pulse"

# The deprecated compatibility shim is the one permitted exception to G3: its entire
# purpose is to redirect old imports to eq1_pulse.models.experimental.schedule.
_ALLOWLISTED_IMPORTERS = {SRC_ROOT / "models" / "schedule.py"}


def _is_under_experimental(path: Path) -> bool:
    """Check whether ``path`` lives inside an ``experimental`` package.

    :param path: Source file path to check

    :return: :obj:`True` if any directory component of the path (excluding the
        filename itself) is named ``experimental``
    """
    return "experimental" in path.relative_to(SRC_ROOT).parts[:-1]


def _imported_module_names(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Collect every dotted name an import statement could resolve to.

    Covers both ``import a.b.c`` and ``from a.b import c`` forms, absolute and
    relative alike; relative imports are reported with their ``.`` prefix intact so
    that later split-and-scan still works on the dotted parts that matter.

    :param node: The AST import node

    :return: Dotted names to scan for an ``experimental`` component
    """
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]

    module = node.module or ""
    prefix = "." * node.level
    full_module = f"{prefix}{module}"
    names = [full_module] if module else [prefix]
    names.extend(f"{full_module}.{alias.name}" if module else f"{prefix}{alias.name}" for alias in node.names)
    return names


def _is_type_checking_guard(test: ast.expr) -> bool:
    """Check whether an ``if`` condition is a ``TYPE_CHECKING`` guard.

    Matches both the bare ``TYPE_CHECKING`` and qualified ``typing.TYPE_CHECKING`` forms.

    :param test: The condition expression of an ``ast.If`` node

    :return: :obj:`True` if the condition is a ``TYPE_CHECKING`` guard
    """
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _walk_skipping_type_checking(tree: ast.AST) -> Iterator[ast.AST]:
    """Walk an AST like :func:`ast.walk`, but do not descend into ``TYPE_CHECKING`` bodies.

    Imports gated behind ``if TYPE_CHECKING:`` are never executed, so they carry none of
    the runtime coupling that the G3 gate is meant to catch.

    :param tree: The AST node to walk

    :yield: Every descendant node, excluding those nested under a ``TYPE_CHECKING`` guard's body
    """
    stack = [tree]
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, ast.If) and _is_type_checking_guard(node.test):
            stack.extend(node.orelse)
        else:
            stack.extend(ast.iter_child_nodes(node))


def test_no_module_outside_experimental_imports_experimental():
    """G3: only modules inside an ``experimental`` package may import from one.

    ``TYPE_CHECKING``-only imports are exempt: they are never evaluated at runtime, so
    they carry none of the runtime coupling (eager loading, deprecation warnings) that
    this gate guards against.
    """
    offenders: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if _is_under_experimental(path) or path in _ALLOWLISTED_IMPORTERS:
            continue

        tree = ast.parse(path.read_text(), filename=str(path))
        for node in _walk_skipping_type_checking(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                for name in _imported_module_names(node):
                    if "experimental" in name.split("."):
                        offenders.append(f"{path.relative_to(SRC_ROOT)}: {name}")

    assert not offenders, (
        f"Modules outside 'experimental' importing from it (only {_ALLOWLISTED_IMPORTERS} is permitted to): {offenders}"
    )


class TestMixingRejection:
    """G4: each builder must reject the other's contexts."""

    def test_build_schedule_inside_build_sequence_raises(self):
        """Entering build_schedule() while a sequence context is active raises."""
        with build_sequence():
            with pytest.raises(RuntimeError, match="cannot be nested inside a build_sequence"):
                with build_schedule():
                    pass

    def test_build_sequence_inside_build_schedule_raises(self):
        """Entering build_sequence() while a schedule context is active raises."""
        with pytest.warns(FutureWarning):
            with build_schedule():
                with pytest.raises(RuntimeError, match="cannot be nested inside a build_schedule"):
                    with build_sequence():
                        pass

    def test_sequence_play_inside_schedule_context_raises(self):
        """eq1_pulse.builder.play() called while a schedule context is active raises."""
        with pytest.warns(FutureWarning):
            with build_schedule():
                with pytest.raises(RuntimeError, match="requires a build_sequence"):
                    sequence_play("ch1", square_pulse(duration="10ns", amplitude="10mV"))

    def test_experimental_play_inside_sequence_context_raises(self):
        """eq1_pulse.builder.experimental.play() called while a sequence context is active raises."""
        with build_sequence():
            with pytest.raises(RuntimeError, match="requires a build_schedule"):
                schedule_play("ch1", square_pulse(duration="10ns", amplitude="10mV"))

    def test_sequence_repeat_inside_schedule_context_raises(self):
        """eq1_pulse.builder.repeat() called while a schedule context is active raises."""
        with pytest.warns(FutureWarning):
            with build_schedule():
                with pytest.raises(RuntimeError, match="requires a build_sequence"):
                    with sequence_repeat(1):
                        pass

    def test_experimental_repeat_inside_sequence_context_raises(self):
        """eq1_pulse.builder.experimental.repeat() called while a sequence context is active raises."""
        with build_sequence():
            with pytest.raises(RuntimeError, match="requires a build_schedule"):
                with schedule_repeat(1):
                    pass


def test_build_schedule_emits_exactly_one_future_warning():
    """G6: a 20-operation schedule build emits exactly one FutureWarning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with build_schedule():
            for _ in range(20):
                schedule_play("ch1", square_pulse(duration="10ns", amplitude="10mV"))

    future_warnings = [w for w in caught if issubclass(w.category, FutureWarning)]
    assert len(future_warnings) == 1
