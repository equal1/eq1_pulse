"""Check a :class:`~eq1_pulse.models.arguments.ProgramArguments` against the program it invokes.

§0 of the parameter sweeps plan makes a promise the IR cannot keep on its own: a stored program
invoked with *the wrong* ranges is still a valid program. Two failures matter enough to catch, and
neither is visible to a model validator, because an invocation is not part of the document being
validated:

* a sweep declared in ``mV`` supplied in ``V`` -- both are numbers, the program runs 1000x off and
  looks fine;
* arguments that do not match the program's declared nesting -- a missing sweep, a group supplied
  with unequal lengths, a name that is not swept, or a level in the wrong place.

:func:`check_arguments` walks a program's declarations and its loop nesting, derives the sweep
structure plan §7 defines -- unconsumed sweeps in declaration order, then consumed sweeps in
``for_`` nesting order -- and reports every disagreement it finds rather than raising on the first.
A user with three mistakes learns all three in one run.

**Advisory, and in** :mod:`~eq1_pulse.utilities` **rather than** :mod:`~eq1_pulse.models`. The
payload is data the IR owns (:class:`~eq1_pulse.models.arguments.ProgramArguments`, task T7), but
matching one against a particular program is analysis no field validator can perform -- it needs
both the program and the arguments in scope at once. Nothing calls this automatically, and it
imports nothing from :mod:`~eq1_pulse.builder`.

**Units are compared as strings, never converted.** ``"mV" != "V"`` is a finding; deciding the two
are 1000 apart is not this function's business and contradicts #6. An argument that states no unit
is accepted as being in the declared one -- that is not a finding.
"""

from __future__ import annotations

from collections.abc import Iterable, Sized
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ..models.arguments import ProgramArguments, QualifiedSweepValue
from ..models.data_ops import ParameterDecl
from ..models.expressions import ExprBase, sweep_names_in
from ..models.sequence import Conditional, Iteration, OpSequence, Repetition
from ..models.sweeps import SweepDecl, SweepGroup

if TYPE_CHECKING:
    from ..models.arguments import SweepArgument
    from ..models.sweeps import SweepSpec

__all__ = ("Finding", "check_arguments")


@dataclass(frozen=True)
class Finding:
    """One problem :func:`check_arguments` found matching a payload to a program.

    :ivar category: A short slug grouping the finding -- ``"name-coverage"``, ``"unit"``,
        ``"nesting"``, ``"group"``, ``"shape"`` or ``"limits"``.
    :ivar message: A human-readable description naming the declaration and what is wrong. Nesting
        findings name *both* what the payload asserted and what the program says.
    """

    category: str
    message: str

    def __str__(self) -> str:
        """Render the finding as ``[category] message``."""
        return f"[{self.category}] {self.message}"


@dataclass
class _Declarations:
    """What a walk of the program found: the sweep and parameter declarations, and the loop levels.

    :ivar sweep_specs: Every declared sweep by name, group members included -- the body carrying
        ``unit``, ``shape``, ``default`` and ``limits``.
    :ivar sweep_levels: One entry per declaration in *declaration order*: a singleton for a
        :class:`~eq1_pulse.models.sweeps.SweepDecl`, the full member set for a
        :class:`~eq1_pulse.models.sweeps.SweepGroup`.
    :ivar parameters: Every declared parameter by name.
    :ivar consuming_levels: The sweeps each ``for_`` consumes, in nesting (pre-order) order, with
        loops that consume nothing left out. A zipped loop over a group is one entry of several
        names.
    """

    sweep_specs: dict[str, SweepSpec] = field(default_factory=dict)
    sweep_levels: list[frozenset[str]] = field(default_factory=list)
    parameters: dict[str, ParameterDecl] = field(default_factory=dict)
    consuming_levels: list[frozenset[str]] = field(default_factory=list)


def _consumed_by(iteration: Iteration) -> frozenset[str]:
    """Return the sweep names *iteration* consumes: every sweep its ``items`` trees read.

    The same rule the builder applies in :func:`eq1_pulse.builder._sweeps._consume_sweeps` --
    :func:`~eq1_pulse.models.expressions.sweep_names_in` over each item that is an expression, so an
    inline transform consumes its bases exactly as a bare reference does, and index iteration
    (``indices(len_(sweep("vg")))``) consumes nothing, since a
    :class:`~eq1_pulse.models.expressions.LenExpr` reads no sweep through itself.

    :param iteration: The loop operation to inspect
    :return: The names it consumes, possibly empty
    """
    items = iteration.items if isinstance(iteration.items, list) else [iteration.items]
    names: set[str] = set()
    for item in items:
        if isinstance(item, ExprBase):
            names |= sweep_names_in(item)
    return frozenset(names)


def _gather(sequence: OpSequence, found: _Declarations) -> None:
    """Walk *sequence* pre-order, recording declarations and consuming loops into *found*.

    Scoping is not reconstructed -- a program from the builder has no colliding names, and this is
    advisory. Declaration order is pre-order position; loop nesting order is the order the loops
    are entered, so an outer loop precedes the loops in its body.

    :param sequence: The operation sequence to walk
    :param found: The accumulator to fill
    """
    for item in sequence.items:
        if isinstance(item, OpSequence):
            _gather(item, found)
        elif isinstance(item, SweepDecl):
            found.sweep_specs[item.name] = item
            found.sweep_levels.append(frozenset({item.name}))
        elif isinstance(item, SweepGroup):
            members = frozenset(spec.name for spec in item.sweeps)
            for spec in item.sweeps:
                found.sweep_specs[spec.name] = spec
            found.sweep_levels.append(members)
        elif isinstance(item, ParameterDecl):
            found.parameters[item.name] = item
        elif isinstance(item, Iteration):
            consumed = _consumed_by(item)
            if consumed:
                found.consuming_levels.append(consumed)
            _gather(item.body, found)
        elif isinstance(item, Repetition | Conditional):
            _gather(item.body, found)


def _program_structure(found: _Declarations) -> list[frozenset[str]]:
    """Derive the program's sweep nesting per plan §7.

    Unconsumed sweeps first, in declaration order and one level each (a group is one level); then
    the consumed sweeps, in ``for_`` nesting order.

    :param found: The declarations and loops from :func:`_gather`
    :return: The levels, outermost first
    """
    consumed_names: set[str] = set()
    for level in found.consuming_levels:
        consumed_names |= level

    structure: list[frozenset[str]] = [level for level in found.sweep_levels if not (level & consumed_names)]
    structure.extend(found.consuming_levels)
    return structure


def _fmt_level(level: Iterable[str]) -> str:
    """Format one nesting level as ``{a, b}`` with names sorted.

    :param level: The sweep names in the level
    :return: The formatted level
    """
    return "{" + ", ".join(sorted(level)) + "}"


def _fmt_structure(levels: Iterable[Iterable[str]]) -> str:
    """Format a whole nesting structure as ``[{a}, {b, c}]``.

    :param levels: The levels, outermost first
    :return: The formatted structure
    """
    return "[" + ", ".join(_fmt_level(level) for level in levels) + "]"


def _unit_of(value: SweepArgument) -> str | None:
    """Return the unit a supplied sweep value states, or :obj:`None` if it states none.

    :param value: One entry of a supplied level
    :return: The unit key of a :class:`~eq1_pulse.models.arguments.QualifiedSweepValue`, else
        :obj:`None`
    """
    if isinstance(value, QualifiedSweepValue):
        return next(iter(value.root))
    return None


def _inner(value: SweepArgument) -> object:
    """Return the bare sweep value a level entry carries, unwrapping the unit key if there is one.

    :param value: One entry of a supplied level
    :return: The :class:`~eq1_pulse.models.basic_types.LinSpace`,
        :class:`~eq1_pulse.models.basic_types.Range` or array underneath
    """
    if isinstance(value, QualifiedSweepValue):
        return value.root[next(iter(value.root))]
    return value


def _length_of(value: SweepArgument) -> int | None:
    """Return how many items a supplied sweep value has, or :obj:`None` if that is not knowable.

    :class:`~eq1_pulse.models.basic_types.LinSpace`, :class:`~eq1_pulse.models.basic_types.Range`
    and an array are all :class:`~collections.abc.Sized`.

    :param value: One entry of a supplied level
    :return: The item count, or :obj:`None`
    """
    inner = _inner(value)
    return len(inner) if isinstance(inner, Sized) else None


def _endpoints_of(value: SweepArgument) -> tuple[float, float] | None:
    """Return the smallest and largest value a supplied sweep spans, or :obj:`None`.

    Reads ``start``/``stop`` off a :class:`~eq1_pulse.models.basic_types.LinSpace` or
    :class:`~eq1_pulse.models.basic_types.Range`, and the min/max off an array. Only real values
    have endpoints to bound; a complex or non-numeric sweep returns :obj:`None`.

    :param value: One entry of a supplied level
    :return: ``(low, high)``, or :obj:`None` if the span is not a pair of real numbers
    """
    inner = _inner(value)
    start = getattr(inner, "start", None)
    stop = getattr(inner, "stop", None)
    if isinstance(start, int | float) and isinstance(stop, int | float):
        return (float(min(start, stop)), float(max(start, stop)))
    if not isinstance(inner, Iterable):
        return None
    try:
        values = [float(item) for item in inner]
    except (TypeError, ValueError):
        return None
    return (min(values), max(values)) if values else None


def _scalar_and_unit(bound: object) -> tuple[float, str | None] | None:
    """Reduce a declared :data:`~eq1_pulse.models.data_ops.SymbolValue` bound to a number and a unit.

    :param bound: A ``limits.minimum`` / ``limits.maximum`` value: a plain number, or a wrapped
        quantity whose wire form is ``{unit: number}``
    :return: ``(number, unit_or_None)``, or :obj:`None` if it is not a real scalar
    """
    if isinstance(bound, bool):
        return None
    if isinstance(bound, int | float):
        return (float(bound), None)
    if isinstance(bound, BaseModel):
        dumped = bound.model_dump()
        if isinstance(dumped, dict) and len(dumped) == 1:
            unit, number = next(iter(dumped.items()))
            if isinstance(number, int | float) and not isinstance(number, bool):
                return (float(number), str(unit))
    return None


def _check_name_coverage(found: _Declarations, arguments: ProgramArguments) -> list[Finding]:
    """Check that every required declaration is supplied and every argument names a declaration.

    :param found: The program's declarations
    :param arguments: The payload
    :return: One finding per uncovered declaration or unknown argument
    """
    findings: list[Finding] = []

    supplied_sweeps = {name for level in arguments.sweeps for name in level}
    for name in sorted(supplied_sweeps - set(found.sweep_specs)):
        findings.append(
            Finding("name-coverage", f"the arguments supply sweep {name!r}, which the program does not declare")
        )
    for name, spec in sorted(found.sweep_specs.items()):
        if spec.default is None and name not in supplied_sweeps:
            findings.append(Finding("name-coverage", f"sweep {name!r} is declared without a default but not supplied"))

    for name in sorted(set(arguments.parameters) - set(found.parameters)):
        findings.append(
            Finding("name-coverage", f"the arguments supply parameter {name!r}, which the program does not declare")
        )
    for name, decl in sorted(found.parameters.items()):
        if decl.default is None and name not in arguments.parameters:
            findings.append(
                Finding("name-coverage", f"parameter {name!r} is declared without a default but not supplied")
            )

    return findings


def _check_units(found: _Declarations, arguments: ProgramArguments) -> list[Finding]:
    """Check that a stated unit equals the declared one, as strings, never converting.

    :param found: The program's declarations
    :param arguments: The payload
    :return: One finding per unit disagreement
    """
    findings: list[Finding] = []
    for level in arguments.sweeps:
        for name, value in level.items():
            spec = found.sweep_specs.get(name)
            if spec is None:
                continue
            stated = _unit_of(value)
            if stated is None:
                continue
            if spec.unit is None:
                findings.append(
                    Finding("unit", f"sweep {name!r} is declared without a unit but supplied in {stated!r}")
                )
            elif stated != spec.unit:
                findings.append(
                    Finding(
                        "unit",
                        f"sweep {name!r} is declared in {spec.unit!r} but supplied in {stated!r}; "
                        "units are compared, never converted",
                    )
                )
    return findings


def _check_nesting(found: _Declarations, arguments: ProgramArguments) -> list[Finding]:
    """Check the supplied levels against the program's structure, position by position.

    :param found: The program's declarations
    :param arguments: The payload
    :return: A single finding for a level-count mismatch, or one per level in the wrong place --
        each naming both what the payload asserted and what the program says
    """
    structure = _program_structure(found)
    supplied = [frozenset(level) for level in arguments.sweeps]

    if len(structure) != len(supplied):
        return [
            Finding(
                "nesting",
                f"the program has {len(structure)} sweep level(s) {_fmt_structure(structure)}, "
                f"but the arguments supply {len(supplied)} {_fmt_structure(supplied)}",
            )
        ]

    findings: list[Finding] = []
    for index, (want, got) in enumerate(zip(structure, supplied, strict=True)):
        if want != got:
            findings.append(
                Finding(
                    "nesting",
                    f"sweep level {index}: the arguments assert {_fmt_level(got)}, "
                    f"but the program says {_fmt_level(want)}",
                )
            )
    return findings


def _check_groups(arguments: ProgramArguments) -> list[Finding]:
    """Check that every entry in a multi-entry level has the same length.

    A level is a group precisely because its members advance on one index, so unequal lengths are
    the failure it exists to prevent. Entries whose length is not knowable yet are skipped.

    :param arguments: The payload
    :return: One finding per group with unequal supplied lengths
    """
    findings: list[Finding] = []
    for index, level in enumerate(arguments.sweeps):
        if len(level) < 2:
            continue
        lengths = {name: length for name, value in level.items() if (length := _length_of(value)) is not None}
        if len(set(lengths.values())) > 1:
            spelled = ", ".join(f"{name}={length}" for name, length in sorted(lengths.items()))
            findings.append(
                Finding("group", f"sweep level {index} is a group, but its entries have unequal lengths: {spelled}")
            )
    return findings


def _check_shape_and_limits(found: _Declarations, arguments: ProgramArguments) -> list[Finding]:
    """Check a supplied value against its declaration's ``shape`` and ``limits``.

    ``shape`` pins an exact item count. ``limits`` bounds each item; the supplied endpoints must lie
    within ``minimum``/``maximum``, and a bound stated in a different unit than the value is skipped
    rather than converted.

    :param found: The program's declarations
    :param arguments: The payload
    :return: One finding per shape or limit violation
    """
    findings: list[Finding] = []
    for level in arguments.sweeps:
        for name, value in level.items():
            spec = found.sweep_specs.get(name)
            if spec is None:
                continue

            if spec.shape is not None and len(spec.shape) == 1:
                length = _length_of(value)
                if length is not None and length != spec.shape[0]:
                    findings.append(
                        Finding(
                            "shape",
                            f"sweep {name!r} declares shape {tuple(spec.shape)} "
                            f"({spec.shape[0]} items) but the supplied value has {length}",
                        )
                    )

            if spec.limits is not None:
                findings.extend(_limit_findings(name, spec, value))
    return findings


def _limit_findings(name: str, spec: SweepSpec, value: SweepArgument) -> list[Finding]:
    """Return findings for *value* falling outside *spec*'s declared ``minimum`` / ``maximum``.

    :param name: The sweep's name, for the message
    :param spec: Its declaration, whose ``limits`` is not :obj:`None`
    :param value: The supplied value
    :return: A finding per breached bound, empty if the value fits or cannot be compared
    """
    assert spec.limits is not None
    span = _endpoints_of(value)
    if span is None:
        return []
    low, high = span
    value_unit = _unit_of(value) or spec.unit

    findings: list[Finding] = []
    lower = _scalar_and_unit(spec.limits.minimum) if spec.limits.minimum is not None else None
    if lower is not None and (lower[1] is None or lower[1] == value_unit) and low < lower[0]:
        findings.append(Finding("limits", f"sweep {name!r} spans down to {low} but its declared minimum is {lower[0]}"))
    upper = _scalar_and_unit(spec.limits.maximum) if spec.limits.maximum is not None else None
    if upper is not None and (upper[1] is None or upper[1] == value_unit) and high > upper[0]:
        findings.append(Finding("limits", f"sweep {name!r} spans up to {high} but its declared maximum is {upper[0]}"))
    return findings


def check_arguments(program: OpSequence, arguments: ProgramArguments) -> list[Finding]:
    """Check that *arguments* fit *program*, returning every disagreement found.

    Runs the five checks of plan §16 -- name coverage, unit agreement, nesting agreement, group
    agreement, shape and limits -- and collects their findings rather than raising on the first. An
    empty list means the arguments fit.

    Nesting is derived per plan §7: the program's sweep levels are its unconsumed sweeps in
    declaration order followed by its consumed sweeps in ``for_`` nesting order, and the payload's
    ``sweeps`` list is an assertion about that, checked position by position. A disagreement names
    both sides, which is how a stored invocation catches a program that has drifted since it was
    written.

    Units are compared as strings and never converted: ``"mV"`` supplied for a ``"V"`` declaration
    is a finding. A value that states no unit is taken to be in the declared one.

    :param program: The pulse program, as built by :func:`~eq1_pulse.builder.build_sequence`
    :param arguments: The invocation payload to check against it
    :return: The findings, most-fundamental first (coverage, then units, nesting, groups, shape and
        limits); empty when the arguments fit
    """
    found = _Declarations()
    _gather(program, found)

    return [
        *_check_name_coverage(found, arguments),
        *_check_units(found, arguments),
        *_check_nesting(found, arguments),
        *_check_groups(arguments),
        *_check_shape_and_limits(found, arguments),
    ]
