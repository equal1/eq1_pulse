"""Program arguments: the values a caller supplies to invoke a stored program.

A pulse program declares parameters and sweeps; :class:`ProgramArguments` is what a caller passes
to run it. It is a first-class artifact -- a model, published in the schema -- so a stored
experiment *and* the arguments it was run with are both validated (plan §16, §9 Q18).

The payload has two parts, kept deliberately apart:

``parameters``
    a scalar per declared parameter, spelled exactly as :data:`~.data_ops.SymbolValue` -- the same
    ``{"mV": 100}`` unit wrapper a parameter default already uses.

``sweeps``
    a list of *levels*, outermost first. A level with one entry supplies a single sweep; a level
    with several supplies a group. The nesting the caller believes in is therefore visible in the
    shape of the document, and ``check_arguments()`` compares that assertion against the program's
    actual structure (plan §7, §16 check 3) -- it is not a second source of truth.

The two are separate fields because ``{"mV": [1, 2]}`` is a :class:`~.basic_types.ComplexVoltage`
under :data:`~.data_ops.SymbolValue` and a two-item array sweep under :data:`SweepArgument`; one
combined field could not tell them apart without a declaration to consult, which a standalone model
does not have. Separating them makes "supplied a sweep where a parameter was declared" a validation
error rather than a checker finding.

This module validates only the payload's own shape -- one known unit key per qualified value, every
level non-empty, no name repeated across levels. Whether a given payload *fits* a given program is
``check_arguments()``' job (plan §16, T8); nothing here consults a program, and no ``externals``
mapping appears, because those are resolved by the framework rather than supplied (plan §9).

It imports :mod:`~.basic_types`, :mod:`~.data_ops` and :mod:`~.sweeps`, and nothing imports it
back -- a leaf, like :mod:`~.sweeps`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, Self

from pydantic import ConfigDict, Field, RootModel, model_validator

from .base_models import LeanModel
from .basic_types import dimension_tag_of_unit_mapping, dimension_unit_tag_map
from .data_ops import SymbolValue
from .identifier_str import IdentifierStr
from .sweeps import SweepValue

if TYPE_CHECKING:
    from .data_ops import SymbolValueLike
    from .sweeps import SweepValueLike

__all__ = (
    "ProgramArguments",
    "QualifiedSweepValue",
    "SweepArgument",
    "SweepLevel",
)


_UNIT_TAGS: Final = dimension_unit_tag_map()
"""Unit key -> dimension tag, read from the shared unit registry -- the same map
:data:`~.data_ops.SymbolValue`'s discriminator uses. A key absent from it is not a known unit."""


class QualifiedSweepValue(RootModel[Any]):
    """A sweep value tagged with the unit it is expressed in: ``{"mV": {...}}``.

    The list-valued lift of the ``{"mV": 100}`` wrapper :data:`~.data_ops.SymbolValue` already uses
    for a scalar quantity. Exactly one key, and it must be a known unit -- checked with
    :func:`~.basic_types.dimension_tag_of_unit_mapping`, the same reader
    :data:`~.data_ops.SymbolValue` discriminates with, so a new unit needs no change here.

    A supplied value with *no* unit is the bare :data:`~.sweeps.SweepValue`, not this -- see
    :data:`SweepArgument`.
    """

    # numpy arrays reach `root` through `SweepValue`, and pydantic must be told they are welcome.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    root: dict[str, SweepValue]

    @model_validator(mode="after")
    def _validate_single_known_unit(self) -> Self:
        """Check that the wrapper carries exactly one key and that it names a known unit.

        :return: This value, unchanged.
        :raises ValueError: If the mapping has other than one key, or its key is not a known unit.
        """
        if len(self.root) != 1:
            raise ValueError(f"a unit-qualified sweep value has exactly one key, got {sorted(self.root)!r}")
        if dimension_tag_of_unit_mapping(self.root, _UNIT_TAGS) is None:
            raise ValueError(f"{next(iter(self.root))!r} is not a known unit")
        return self

    if TYPE_CHECKING:

        def __init__(self, root: dict[str, SweepValueLike], /) -> None: ...  # noqa: D107


type SweepArgument = SweepValue | QualifiedSweepValue
"""One sweep's supplied value: a bare :data:`~.sweeps.SweepValue`, or one wrapped in its unit.

An unwrapped value is taken to be in the declared unit; a :class:`QualifiedSweepValue` states its
unit, and ``check_arguments()`` compares it to the declaration as a string -- never converting.
"""


type SweepLevel = dict[IdentifierStr, SweepArgument]
"""One level of sweep nesting, outermost first. More than one entry means those sweeps are a group."""


class ProgramArguments(LeanModel):
    """What a caller supplies to invoke a stored program.

    ``parameters`` is a scalar per declared parameter; ``sweeps`` is a list of nesting levels,
    outermost first, in which a one-entry level supplies a single sweep and a multi-entry level
    supplies a group. The two are separate fields on purpose (see the module docstring).

    Only the payload's own shape is validated here: every level is non-empty and no sweep name is
    supplied in two levels. Matching a payload against a particular program -- name coverage, unit
    agreement, nesting agreement -- is ``check_arguments()`` in :mod:`~.utilities`, which is where
    a program is in scope (plan §16, §9 Q16).
    """

    # numpy arrays reach `sweeps` through `SweepValue`, and pydantic must be told they are welcome.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    parameters: dict[IdentifierStr, SymbolValue] = Field(default_factory=dict)
    """A scalar for each declared parameter, spelled as :data:`~.data_ops.SymbolValue` -- the same
    ``{"mV": 100}`` wrapper a :attr:`~.data_ops.ParameterDecl.default` uses."""
    sweeps: list[SweepLevel] = Field(default_factory=list)
    """The sweep values, as a list of levels outermost first. A one-entry level is a single sweep;
    a multi-entry level is a group. This is an *assertion* about the program's nesting, checked by
    ``check_arguments()`` against the program's actual structure (plan §7, §16 check 3), not a
    second source of truth."""

    @model_validator(mode="after")
    def _validate_levels(self) -> Self:
        """Check that every level is non-empty and no sweep name appears in two of them.

        Nothing here is checked against a program -- that is ``check_arguments()`` (plan §16).

        :return: These arguments, unchanged.
        :raises ValueError: If a level is empty, or a name is supplied in more than one level.
        """
        seen: set[str] = set()
        for index, level in enumerate(self.sweeps):
            if not level:
                raise ValueError(f"sweep level {index} is empty; every level names at least one sweep")
            for name in level:
                if name in seen:
                    raise ValueError(f"sweep {name!r} is supplied in more than one level")
                seen.add(name)
        return self

    if TYPE_CHECKING:

        def __init__(  # noqa: D107
            self,
            *,
            parameters: dict[str, SymbolValueLike] = ...,
            sweeps: list[dict[str, SweepValueLike | QualifiedSweepValue]] = ...,
            **data,
        ): ...
