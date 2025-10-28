# ruff: noqa: D100, D101, D107
from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Discriminator, PlainSerializer

from .basic_types import OpBase, Phase, Threshold
from .identifier_str import IdentifierStr
from .pulse_types import PulseType
from .reference_types import VariableRef

if TYPE_CHECKING:
    from .basic_types import PhaseLike, ThresholdLike
    from .reference_types import VariableRefLike

__all__ = (
    "ComparisonMode",
    "ComplexToRealProjectionMode",
    "DataOp",
    "Discriminate",
    "PulseDecl",
    "Store",
    "StoreMode",
    "VariableDecl",
)


class DataOpBase(OpBase):
    if TYPE_CHECKING:

        def __init__(*args, **data):
            super().__init__(*args, **data)  # type: ignore[misc]


type VariableDTypeType = Literal["bool", "int", "float", "complex"]


class VariableDecl(DataOpBase):
    """Variable declaration operation.

    Variables must be declared before they can be referred to.

    Variable declarations are scoped to the surrounding context and its children.
    """

    op_type: Literal["var_decl"] = "var_decl"
    """The operation type discriminator for variable declaration operations. It is always "var_decl"."""

    name: IdentifierStr
    """Name of the variable. Must be a valid identifier."""
    dtype: VariableDTypeType
    """Data type of the variable."""
    shape: tuple[int, ...] | None = None
    """Shape of the variable. Must be a tuple of integers."""
    unit: str | None = None
    """Unit of the variable. This is a string that represents the unit of measurement for the variable.
    This must be defined and be consistent with the parameter types of the operations that use this variable.
    The unit can take dynamic values if not specified here, for instance when used with iteration operations.
    """

    def __init__(self, name: str, **data):
        super().__init__(name=name, **data)


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
    GreaterEqual = ">="
    Greater = ">"
    LessEqual = "<="
    Less = "<"


class ComplexToRealProjectionMode(StrEnum):
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
    op_type: Literal["discriminate"] = "discriminate"
    target: VariableRef
    source: VariableRef
    threshold: Threshold
    rotation: Phase = Phase(0)
    compare: Annotated[ComparisonMode, PlainSerializer(str)] = ComparisonMode.GreaterEqual
    project: Annotated[ComplexToRealProjectionMode, PlainSerializer(str)] = ComplexToRealProjectionMode.RealPart

    if TYPE_CHECKING:

        def __init__(
            self,
            /,
            *,
            target: VariableRefLike,
            source: VariableRefLike,
            threshold: ThresholdLike,
            rotation: PhaseLike = 0,
            compare: ComparisonModeLike = ComparisonMode.GreaterEqual,
            project: ComplexToRealProjectionModeLike = ComplexToRealProjectionMode.RealPart,
            **data,
        ): ...


class StoreMode(StrEnum):
    Last = "last"
    Average = "average"
    Count = "count"
    Trace = "trace"


type StoreModeLiteral = Literal["last", "average", "count", "trace"]
type StoreModeLike = StoreMode | StoreModeLiteral


class Store(DataOpBase):
    op_type: Literal["store"] = "store"
    key: str
    source: VariableRef
    mode: Annotated[StoreMode, PlainSerializer(str)]

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


DataOp = Annotated[VariableDecl | PulseDecl | Discriminate | Store, Discriminator("op_type")]
"""Data operation type.

This is a closed set of data operations that can be used in a sequence of operations.
All data operation types have a common discriminator field `op_type` (inherited from `OpBase`)
that is used to distinguish between them.
"""
