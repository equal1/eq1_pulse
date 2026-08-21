"""Check that the code in documentation matches the real builder API.

Neither the ``.. code-block:: python`` snippets in ``docs/`` nor the ones in docstrings
are executed by Sphinx or by pytest, so they drift away from the signatures they
describe. This does not run them -- most are deliberate fragments -- but it does parse
every snippet and bind each builder call against the real signature, which catches the
mismatches that make a copy-pasted example raise immediately.
"""

import ast
import inspect
import re
from pathlib import Path

import pytest

import eq1_pulse.builder as builder
import eq1_pulse.builder.experimental as experimental_builder

REPO_ROOT = Path(__file__).parent.parent
DOC_ROOT = REPO_ROOT / "docs" / "source"
SRC_ROOT = REPO_ROOT / "src"
EXPERIMENTAL_ROOT = SRC_ROOT / "eq1_pulse" / "builder" / "experimental"

CODE_BLOCK_RE = re.compile(r"^(\s*)\.\. code-block:: python\s*$")


def _signature_of(obj: object) -> inspect.Signature | None:
    """Return the signature of a builder export, or :obj:`None` if it has none.

    :param obj: The exported object

    :return: Its signature, or :obj:`None` for classes and builtins without one
    """
    try:
        return inspect.signature(inspect.unwrap(obj))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _signatures_of(module: object, names: tuple[str, ...]) -> dict[str, inspect.Signature]:
    """Collect the real signatures of a builder module's exports.

    :param module: The module the names live on
    :param names: The module's ``__all__``

    :return: Exported name -> its signature, for every export that has one
    """
    return {
        name: signature
        for name in names
        if callable(obj := getattr(module, name)) and (signature := _signature_of(obj)) is not None
    }


# The sequence API (``eq1_pulse.builder``) and the unused, experimental schedule API
# (``eq1_pulse.builder.experimental``) give the same names (``play``, ``build_schedule``
# in one, not the other, but e.g. ``play`` in both) different signatures. A snippet's
# calls must bind against whichever API it is actually demonstrating.
BUILDER_SIGNATURES = _signatures_of(builder, builder.__all__)
EXPERIMENTAL_SIGNATURES = _signatures_of(experimental_builder, experimental_builder.__all__)


def _extract_python_blocks(text: str) -> list[tuple[int, str]]:
    """Pull every ``.. code-block:: python`` body out of some ReST text.

    :param text: The ReST source to scan

    :return: ``(line number, dedented code)`` for each block found
    """
    lines = text.split("\n")
    blocks: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        match = CODE_BLOCK_RE.match(lines[index])
        if not match:
            index += 1
            continue

        indent = len(match.group(1))
        index += 1
        # skip the directive's own options and the blank line after them
        while index < len(lines) and (not lines[index].strip() or lines[index].lstrip().startswith(":")):
            index += 1

        start = index
        body: list[str] = []
        while index < len(lines):
            line = lines[index]
            if line.strip() and (len(line) - len(line.lstrip())) <= indent:
                break
            body.append(line)
            index += 1

        while body and not body[-1].strip():
            body.pop()
        if body:
            margin = min(len(line) - len(line.lstrip()) for line in body if line.strip())
            blocks.append((start + 1, "\n".join(line[margin:] for line in body)))

    return blocks


def _docstring_blocks(path: Path) -> list[tuple[int, str]]:
    """Pull the ReST code blocks out of every docstring in a Python module.

    :param path: The module to scan

    :return: ``(line number, dedented code)`` for each block found
    """
    module = ast.parse(path.read_text())
    blocks: list[tuple[int, str]] = []
    for node in ast.walk(module):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if docstring := ast.get_docstring(node):
            lineno = getattr(node, "lineno", 1)
            blocks.extend((lineno, code) for _, code in _extract_python_blocks(docstring))
    return blocks


def _is_pseudo_code(code: str) -> bool:
    """Check whether a snippet is illustrative rather than runnable.

    Signature displays and elided bodies are a legitimate documentation idiom; they are
    not expected to bind against the real signatures.

    :param code: The snippet to classify

    :return: :obj:`True` if the snippet is not meant to be valid, complete Python
    """
    if "..." in code or "# operations" in code:
        return True
    # a multi-line signature display, with the keyword-only marker on its own line
    if re.search(r"^\s*\*,\s*$", code, re.M):
        return True
    # a one-line signature display, e.g. `wait(*channels, duration, **schedule_params)`
    body = [line for line in code.strip().split("\n") if line.strip() and not line.lstrip().startswith("#")]
    return len(body) == 1 and "*" in body[0] and re.fullmatch(r"[\w.]+\(.*\)", body[0].strip()) is not None


def _called_name_and_signature(
    func: ast.expr, signatures: dict[str, inspect.Signature]
) -> tuple[str, inspect.Signature] | None:
    """Resolve a call's callee to a name and its real signature.

    Handles both bare calls (``play(...)``), checked against ``signatures``, and
    module-qualified calls (``experimental.play(...)``), which always demonstrate the
    experimental API and so are checked against :data:`EXPERIMENTAL_SIGNATURES`
    regardless of which ``signatures`` map the snippet is otherwise being checked against.

    :param func: The ``func`` expression of an ``ast.Call`` node
    :param signatures: Exported name -> real signature, for the API the snippet demonstrates

    :return: The resolved name and its signature, or :obj:`None` if it doesn't match a known export
    """
    if isinstance(func, ast.Name):
        if (signature := signatures.get(func.id)) is not None:
            return func.id, signature
        return None
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "experimental":
        if (signature := EXPERIMENTAL_SIGNATURES.get(func.attr)) is not None:
            return func.attr, signature
        return None
    return None


def _mismatches(code: str, signatures: dict[str, inspect.Signature] = BUILDER_SIGNATURES) -> list[str]:
    """Bind every builder call in a snippet against the real signature.

    :param code: The snippet to check
    :param signatures: Exported name -> real signature, for the API the snippet demonstrates

    :return: A description of each call that could not be bound
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return [] if _is_pseudo_code(code) else [f"SyntaxError: {error.msg}"]

    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        resolved = _called_name_and_signature(node.func, signatures)
        if resolved is None:
            continue
        name, signature = resolved
        # a starred argument hides the real arity, so it cannot be bound here
        if any(isinstance(arg, ast.Starred) for arg in node.args) or any(kw.arg is None for kw in node.keywords):
            continue

        try:
            signature.bind(*[None] * len(node.args), **{kw.arg: None for kw in node.keywords if kw.arg})
        except TypeError as error:
            problems.append(f"line {node.lineno}: {name}(): {error}")

    return problems


DOC_FILES = sorted(DOC_ROOT.rglob("*.rst")) if DOC_ROOT.is_dir() else []
SOURCE_FILES = sorted((SRC_ROOT / "eq1_pulse" / "builder").rglob("*.py"))


@pytest.mark.parametrize("path", DOC_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_documentation_snippets_match_the_api(path: Path):
    """Test that ReST snippets call builder functions with valid arguments."""
    failures = [
        f"{path.relative_to(REPO_ROOT)}:{lineno}: {problem}"
        for lineno, code in _extract_python_blocks(path.read_text())
        if not _is_pseudo_code(code)
        for problem in _mismatches(code)
    ]
    assert not failures, "documentation does not match the builder API:\n" + "\n".join(failures)


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_docstring_snippets_match_the_api(path: Path):
    """Test that docstring snippets call builder functions with valid arguments."""
    signatures = EXPERIMENTAL_SIGNATURES if EXPERIMENTAL_ROOT in path.parents else BUILDER_SIGNATURES
    failures = [
        f"{path.relative_to(REPO_ROOT)}:{lineno}: {problem}"
        for lineno, code in _docstring_blocks(path)
        if not _is_pseudo_code(code)
        for problem in _mismatches(code, signatures)
    ]
    assert not failures, "docstrings do not match the builder API:\n" + "\n".join(failures)
