# ruff: noqa: D100, D107
from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal

from pydantic import BeforeValidator, Discriminator, PlainSerializer, TypeAdapter, ValidationError

from .base_models import LeanModel
from .basic_types import Amplitude, Duration, Frequency, Magnitude, OpBase, Phase, Threshold, Voltage
from .identifier_str import ExternalSymbolStr, IdentifierStr
from .pulse_types import PulseType
from .reference_types import SymbolRef, VariableRef

if TYPE_CHECKING:
    from .basic_types import (
        AmplitudeLike,
        DurationLike,
        FrequencyLike,
        MagnitudeLike,
        PhaseLike,
        ThresholdLike,
        VoltageLike,
    )
    from .reference_types import SymbolRefLike, VariableRefLike

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


_SYMBOL_VALUE_DIMENSIONAL_TYPES: Final = (Amplitude, Duration, Frequency, Phase, Magnitude, Voltage, Threshold)
_SYMBOL_VALUE_DIMENSIONAL_TYPE_ADAPTERS: Final = tuple(TypeAdapter(t) for t in _SYMBOL_VALUE_DIMENSIONAL_TYPES)


def _coerce_symbol_value_string(value: Any) -> Any:
    """Coerce a unit-suffixed string to its typed dimensional quantity, if it matches one.

    :data:`SymbolValue` has no plain :obj:`str` member, unlike
    :data:`~.pulse_types.ExternalParamValue`, so an unmatched string is left as-is here and fails
    validation against the rest of the union, rather than being kept as :obj:`str`.

    :param value: Raw input for a :data:`SymbolValue`

    :return: The parsed dimensional quantity if *value* is a matching unit-suffixed string,
        otherwise *value* unchanged
    """
    if not isinstance(value, str):
        return value
    for adapter in _SYMBOL_VALUE_DIMENSIONAL_TYPE_ADAPTERS:
        try:
            return adapter.validate_python(value)
        except ValidationError:
            continue
    return value


type SymbolValue = Annotated[
    Amplitude | Duration | Frequency | Phase | Magnitude | Voltage | Threshold | bool | int | float | complex,
    BeforeValidator(_coerce_symbol_value_string),
]
"""The value of a declared symbol (a parameter default or external constant): dimensional, boolean,
or plain numeric.

Unit-suffixed strings are coerced to their typed dimensional quantity the same way as in
:data:`~.pulse_types.ExternalParamValue`: ``"10us"`` becomes a :class:`~.basic_types.Duration`,
``"100mV"`` an :class:`~.basic_types.Amplitude` (tried before :class:`~.basic_types.Voltage`,
:class:`~.basic_types.Threshold` and :class:`~.basic_types.Magnitude`, since all four accept the
same ``V``/``mV`` suffixes), and so on.
"""

type SymbolValueLike = (
    AmplitudeLike
    | DurationLike
    | FrequencyLike
    | PhaseLike
    | MagnitudeLike
    | VoltageLike
    | ThresholdLike
    | bool
    | int
    | float
    | complex
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
    threshold: Threshold | SymbolRef
    """The threshold value for discrimination."""
    rotation: Phase | SymbolRef = Phase(0)
    """Phase rotation to apply before discrimination."""
    compare: Annotated[ComparisonMode, PlainSerializer(str)] = ComparisonMode.GreaterEqual
    """The comparison mode to use."""
    project: Annotated[ComplexToRealProjectionMode, PlainSerializer(str)] = ComplexToRealProjectionMode.RealPart
    """The projection mode for complex to real conversion."""

    if TYPE_CHECKING:

        def __init__(
            self,
            /,
            *,
            target: VariableRefLike,
            source: VariableRefLike,
            threshold: ThresholdLike | SymbolRefLike,
            rotation: PhaseLike | SymbolRefLike = 0,
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
    mode: Annotated[StoreMode, PlainSerializer(str)]
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
    VariableDecl | ParameterDecl | ExternalDecl | PulseDecl | Discriminate | Store, Discriminator("op_type")
]
"""Data operation type.

This is a closed set of data operations that can be used in a sequence of operations.
All data operation types have a common discriminator field `op_type` (inherited from `OpBase`)
that is used to distinguish between them.
"""
