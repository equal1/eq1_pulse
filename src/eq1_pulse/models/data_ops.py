# ruff: noqa: D100, D107
from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal

import numpy as np
from pydantic import Discriminator, Tag

from .base_models import LeanModel
from .basic_types import (
    COMPLEX_VOLTAGE_TAG,
    Angle,
    ComplexVoltage,
    Frequency,
    OpBase,
    OperationDiscriminator,
    Phase,
    Threshold,
    Time,
    Voltage,
    dimension_tag_of,
    dimension_tag_of_unit_mapping,
    dimension_unit_tag_map,
)
from .complex import complex_from_tuple
from .identifier_str import ExternalSymbolStr, IdentifierStr
from .pulse_types import PulseType
from .reference_types import VariableRef

if TYPE_CHECKING:
    from .basic_types import (
        AngleLike,
        ComplexVoltageLike,
        FrequencyLike,
        PhaseLike,
        ThresholdLike,
        TimeLike,
        VoltageLike,
    )
    from .expressions import ValueRefLike
    from .reference_types import VariableRefLike

__all__ = (
    "ComparisonMode",
    "ComplexToRealProjectionMode",
    "DataOp",
    "Discriminate",
    "ExternalDecl",
    "ParameterDecl",
    "PulseDecl",
    "Store",
    "StoreMode",
    "SymbolValue",
    "SymbolValueLike",
    "ValueLimits",
    "VariableDecl",
)


class DataOpBase(OpBase):
    """Base class for all data operations."""

    if TYPE_CHECKING:

        def __init__(*args, **data):
            super().__init__(*args, **data)  # type: ignore[misc]


type VariableDTypeType = Literal["bool", "int", "float", "complex"]


_SYMBOL_VALUE_UNIT_TAGS: Final = dimension_unit_tag_map()
"""Unit key -> dimension tag (``"time"``, ``"voltage"``, ``"frequency"`` or ``"angle"``), read from
the shared unit registry."""


def _symbol_value_tag(value: Any) -> str | None:
    """Return the tag *value* is spelled with, or :obj:`None` to report an unknown tag.

    :param value: Raw input for a :data:`SymbolValue`
    """
    if isinstance(value, Mapping):
        return dimension_tag_of_unit_mapping(value, _SYMBOL_VALUE_UNIT_TAGS)
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, complex | list | tuple | np.complexfloating):
        return "complex"
    if isinstance(value, np.ndarray) and value.shape == (2,) and issubclass(value.dtype.type, np.integer | np.floating):
        return "complex"
    return dimension_tag_of(value)


type SymbolValue = Annotated[
    Annotated[Time, Tag("time")]
    | Annotated[Voltage, Tag("voltage")]
    | Annotated[ComplexVoltage, Tag(COMPLEX_VOLTAGE_TAG)]
    | Annotated[Frequency, Tag("frequency")]
    | Annotated[Angle, Tag("angle")]
    | Annotated[bool, Tag("bool")]
    | Annotated[int, Tag("int")]
    | Annotated[float, Tag("float")]
    | Annotated[complex_from_tuple, Tag("complex")],
    Discriminator(_symbol_value_tag),
]
"""The value of a declared symbol (a parameter default or external constant): dimensional, boolean,
or plain numeric.

Lists one type per dimension -- :class:`~.basic_types.Time`, :class:`~.basic_types.Voltage`,
:class:`~.basic_types.ComplexVoltage`, :class:`~.basic_types.Frequency`, :class:`~.basic_types.Angle`
-- rather than per refinement: :class:`~.basic_types.Duration`, :class:`~.basic_types.Amplitude`,
:class:`~.basic_types.Threshold`, :class:`~.basic_types.Magnitude` and :class:`~.basic_types.Phase`
are indistinguishable on the wire from their base dimension, so listing them here would make
resolution depend on declaration order.

The two voltage dimensions share their unit keys, so they are told apart by the shape of the value:
``{"mV": 100}`` is a :class:`~.basic_types.Voltage` and ``{"mV": [1, 2]}`` a
:class:`~.basic_types.ComplexVoltage`. A real-valued :class:`~.basic_types.Amplitude` therefore
narrows to :class:`~.basic_types.Voltage` on the way back in, the same narrowing
:class:`~.basic_types.Duration` gets, and for the same reason: on the wire the two are one document.

Unlike :data:`~.pulse_types.ExternalParamValue`, there is no plain :obj:`str` member: a unit-suffixed
string is not a wire form for either union any more, so it is rejected here rather than kept as-is.
"""

type SymbolValueLike = (
    TimeLike | VoltageLike | ComplexVoltageLike | FrequencyLike | AngleLike | bool | int | float | complex
)
"""Acceptable input types for :data:`SymbolValue`."""


class ValueLimits(LeanModel):
    """Declared bounds on a symbol's value.

    These bounds are carried on the declaration and never enforced by eq1_pulse itself: eq1_pulse
    does not perform unit conversion, so checking a bound would require the outside framework's
    cooperation anyway. This model exists so a bound can be expressed and travel with the program.
    """

    minimum: SymbolValue | None = None
    """The smallest value the symbol may take, or :obj:`None` if unbounded below."""
    maximum: SymbolValue | None = None
    """The largest value the symbol may take, or :obj:`None` if unbounded above."""
    allowed: list[SymbolValue] | None = None
    """The set of values the symbol may take, or :obj:`None` if not restricted to a fixed set."""

    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            minimum: SymbolValueLike | None = None,
            maximum: SymbolValueLike | None = None,
            allowed: list[SymbolValueLike] | None = None,
            **data,
        ): ...


class SymbolDeclBase(DataOpBase):
    """Shared shape for declarations of a named symbol: a variable, a parameter, or an external constant."""

    if TYPE_CHECKING:

        def __init__(*args, **data):
            super().__init__(*args, **data)  # type: ignore[misc]

    dtype: VariableDTypeType
    """Data type of the symbol."""
    shape: tuple[int, ...] | None = None
    """Shape of the symbol. Must be a tuple of integers."""
    unit: str | None = None
    """Unit of the symbol. This is a string that represents the unit of measurement for the symbol.
    This must be defined and be consistent with the parameter types of the operations that use this symbol.
    The unit can take dynamic values if not specified here, for instance when used with iteration operations.
    """


class VariableDecl(SymbolDeclBase):
    """Variable declaration operation.

    Variables must be declared before they can be referred to.

    Variable declarations are scoped to the surrounding context and its children.
    """

    op_type: Literal["var_decl"] = "var_decl"
    """The operation type discriminator for variable declaration operations. It is always "var_decl"."""

    name: IdentifierStr
    """Name of the variable. Must be a valid identifier."""

    def __init__(self, name: str, **data):
        super().__init__(name=name, **data)


class ParameterDecl(SymbolDeclBase):
    """Parameter declaration operation.

    A parameter is a symbol whose value is supplied by the caller when the program is submitted,
    rather than computed inside the program. Everything else about it is a variable: it is
    referenced with ``var()``, it obeys the same lexical scoping, and it may be read anywhere a
    variable may be read. ``default`` makes it optional at submission time.

    Parameter declarations are scoped to the surrounding context and its children.
    """

    op_type: Literal["param_decl"] = "param_decl"
    """The operation type discriminator for parameter declaration operations. It is always "param_decl"."""

    name: IdentifierStr
    """Name of the parameter. Must be a valid identifier."""
    default: SymbolValue | None = None
    """The value used if none is supplied at submission time, or :obj:`None` if the parameter is required."""
    limits: ValueLimits | None = None
    """Declared bounds on the parameter's value, or :obj:`None` if unbounded."""

    if TYPE_CHECKING:

        def __init__(
            self,
            name: str,
            *,
            dtype: VariableDTypeType,
            shape: tuple[int, ...] | None = None,
            unit: str | None = None,
            default: SymbolValueLike | None = None,
            limits: ValueLimits | None = None,
            **data,
        ): ...


class ExternalDecl(SymbolDeclBase):
    """External constant declaration operation.

    An external constant is a symbol resolved outside the program: its value is looked up per
    submission in a calibration store by name, rather than supplied directly by the caller. It is
    referenced with ``ext()``.

    External declarations are scoped to the surrounding context and its children.
    """

    op_type: Literal["extern_decl"] = "extern_decl"
    """The operation type discriminator for external declaration operations. It is always "extern_decl"."""

    name: ExternalSymbolStr
    """Name of the external symbol."""
    default: SymbolValue | None = None
    """The value used if none is resolved at submission time, or :obj:`None` if resolution is required."""
    limits: ValueLimits | None = None
    """Declared bounds on the external symbol's value, or :obj:`None` if unbounded."""

    if TYPE_CHECKING:

        def __init__(
            self,
            name: str,
            *,
            dtype: VariableDTypeType,
            shape: tuple[int, ...] | None = None,
            unit: str | None = None,
            default: SymbolValueLike | None = None,
            limits: ValueLimits | None = None,
            **data,
        ): ...


class PulseDecl(DataOpBase):
    """Pulse declaration operation.

    Pulses must be declared before they can be referred to.
    Pulse declarations are scoped to the surrounding context and its children.
    """

    op_type: Literal["pulse_decl"] = "pulse_decl"
    """The operation type discriminator for pulse declaration operations. It is always "pulse_decl"."""
    name: str
    """Name of the pulse. Must be a valid identifier."""
    pulse: PulseType
    """The pulse definition."""

    def __init__(self, name: str, **data):
        super().__init__(name=name, **data)


class ComparisonMode(StrEnum):
    """Comparison modes for discrimination operations."""

    GreaterEqual = ">="
    Greater = ">"
    LessEqual = "<="
    Less = "<"


class ComplexToRealProjectionMode(StrEnum):
    """Projection modes for converting complex values to real values."""

    RealPart = "real"
    ImaginaryPart = "imag"
    Magnitude = "abs"
    Phase = "phase"


if TYPE_CHECKING:
    ComparisonModeLiteral = Literal["<", "<=", ">", ">="]
    ComparisonModeLike = ComparisonMode | ComparisonModeLiteral
    ComplexToRealProjectionModeLiteral = Literal["real", "imag", "abs", "phase"]
    ComplexToRealProjectionModeLike = ComplexToRealProjectionMode | ComplexToRealProjectionModeLiteral


class Discriminate(DataOpBase):
    """Discriminate operation to convert complex data to boolean based on threshold comparison."""

    op_type: Literal["discriminate"] = "discriminate"
    """The type discriminator, always "discriminate"."""
    target: VariableRef
    """The target variable to store the discrimination result."""
    source: VariableRef
    """The source variable containing the data to discriminate."""
    threshold: Threshold | ValueRef
    """The threshold value for discrimination."""
    rotation: Phase | ValueRef = Phase(0)
    """Phase rotation to apply before discrimination."""
    compare: ComparisonMode = ComparisonMode.GreaterEqual
    """The comparison mode to use."""
    project: ComplexToRealProjectionMode = ComplexToRealProjectionMode.RealPart
    """The projection mode for complex to real conversion."""

    if TYPE_CHECKING:

        def __init__(
            self,
            /,
            *,
            target: VariableRefLike,
            source: VariableRefLike,
            threshold: ThresholdLike | ValueRefLike,
            rotation: PhaseLike | ValueRefLike = 0,
            compare: ComparisonModeLike = ComparisonMode.GreaterEqual,
            project: ComplexToRealProjectionModeLike = ComplexToRealProjectionMode.RealPart,
            **data,
        ): ...


class StoreMode(StrEnum):
    """Storage modes for storing variable data."""

    Last = "last"
    Average = "average"
    Count = "count"
    Trace = "trace"


type StoreModeLiteral = Literal["last", "average", "count", "trace"]
type StoreModeLike = StoreMode | StoreModeLiteral


class Store(DataOpBase):
    """Store operation to save variable data for later retrieval."""

    op_type: Literal["store"] = "store"
    """The type discriminator, always "store"."""
    key: str
    """The key to identify the stored data."""
    source: VariableRef
    """The source variable to store."""
    mode: StoreMode
    """The storage mode to use."""

    if TYPE_CHECKING:

        def __init__(
            self,
            /,
            *,
            key: str,
            source: VariableRefLike,
            mode: StoreModeLike,
            **data,
        ): ...


DataOp = Annotated[
    VariableDecl | ParameterDecl | ExternalDecl | PulseDecl | Discriminate | Store, OperationDiscriminator()
]
"""Data operation type.

This is a closed set of data operations that can be used in a sequence of operations.
Each one is spelled as the single-key object ``{op_type: payload}`` -- ``{"var_decl": {...}}`` --
and :class:`~.basic_types.OperationDiscriminator` selects the member by that sole key.
"""

# Deferred: `expressions` imports `SymbolValue` from this module, so importing it back at module
# top would be a real cycle rather than a forward reference. By the time this runs, `expressions`
# has already defined `ValueRef`/`ValueRefLike` (see its own bottom-of-module comment), so this
# succeeds regardless of which of the two modules is imported first.
from .expressions import ValueRef  # noqa: E402

Discriminate.model_rebuild()
