"""Base models for control flow operations."""

from collections.abc import Iterable
from typing import Annotated, Literal, Self

from pydantic import (
    ConfigDict,
    Field,
    RootModel,
    model_validator,
)

from .basic_types import LinSpace, OpBase, Range
from .nd_array import NumpyComplexArray1D, NumpyFloatArray1D, NumpyIntArray1D
from .reference_types import SymbolRef, VariableRef

__all__ = "ConditionalBase", "IterationBase", "RepetitionBase"


class SequenceBase[ItemT](RootModel[list[ItemT]]):
    """Base class for a sequence of items, whose wire form is the JSON array itself.

    A nested sequence is recognised by *being* an array, not by carrying an ``items`` key, so
    sequences compose with the operation types they sit beside without either having to be
    disambiguated from the other.

    :ivar items: List of operation sequence items
    """

    root: list[ItemT]
    """The operation sequence items."""

    @property
    def items(self) -> list[ItemT]:
        """The operation sequence items.

        The list itself, not a copy: appending to it appends to the sequence, which is how the
        builder grows the sequence it is filling.
        """
        return self.root

    def __len__(self):
        return len(self.root)

    def __getitem__(self, key: int) -> ItemT:
        return self.root[key]

    def __init__(self, items: Iterable[ItemT] = (), /, **data):
        """Initialize a sequence with its items.

        :param items: An iterable of sequence items, positional-only; empty by default.
        :param data: Never passed by a caller. ``items`` being positional-only makes a keyword
            argument here wire data instead: pydantic routes a *mapping* input through a custom
            ``__init__`` even on a root model, and a mapping is not a sequence's wire form, so it
            goes to root validation to be reported as the error it is.
        """
        if data:
            super().__init__(**data)
        else:
            super().__init__(list(items))


class RepetitionBase[BodyT](OpBase):
    """Represents an abstract repeated sequence of operations.

    :ivar op_type: Operation type, always "repeat"
    :ivar count: Number of times to repeat the sequence
    :ivar body: The sequence of operations to repeat

    To be extended with field to contain the operations.
    """

    op_type: Literal["repeat"] = "repeat"
    """The type discriminator, always "repeat"."""
    count: Annotated[int, Field(ge=0)] | SymbolRef
    """Number of times to repeat the sequence.

    The literal branch keeps its ``ge=0`` constraint; there is nothing to constrain on the symbol
    branch, which is the "declare, never enforce" split every other symbol value follows.
    """
    body: BodyT
    """The sequence of operations to repeat."""


type NumpyIterableArray = NumpyIntArray1D | NumpyFloatArray1D | NumpyComplexArray1D
type IterableSequence = LinSpace | Range | list[str] | NumpyIterableArray


class IterationBase[BodyT](OpBase):
    """Base class for iteration over a sequence of operations.

    :ivar op_type: Operation type, always "for"
    :ivar var: The variable reference for the iterated value.
    :ivar items: The linear space, range or array over which to iterate.
    :ivar body: The sequence of operations to execute in each iteration
    """

    op_type: Literal["for"] = "for"
    """The discriminator field for the operation type. Always "for"."""
    var: list[VariableRef] | VariableRef
    """The variable reference(s) for the iterated value(s).

    It can be a single variable reference or a list of variable references
    when iterating over multiple variables simultaneously.
    """
    items: list[IterableSequence] | IterableSequence
    """The linear space, range, array or list of arrays over which to iterate.

    It can be a single iterable or a list of iterables when iterating
    over multiple variables simultaneously.
    """

    body: BodyT
    """The sequence of operations to execute in each iteration."""

    # We need to allow arbitrary types because of the NumpyArray.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def _validate_vars_vs_items(self) -> Self:
        if isinstance(self.var, list):
            if not isinstance(self.items, list) or all(isinstance(item, str) for item in self.items):
                raise ValueError("Both 'var' and 'items' must be lists or both must be single values.")
            if len(self.var) != len(self.items):
                raise ValueError("Both 'var' and 'items' must have the same length.")
            lengths = [len(item) for item in self.items]
            if not all(length == lengths[0] for length in lengths[1:]):
                raise ValueError("All 'items' must have the same length.")
        else:
            if isinstance(self.items, list) and not all(isinstance(item, str) for item in self.items):
                raise ValueError("Both 'var' and 'items' must be lists or both must be single values.")
        return self


class ConditionalBase[BodyT](OpBase):
    """Base class for conditional sequence of operations.

    :ivar op_type: Operation type, always "if"
    :ivar var: The variable reference for the condition.
    :ivar body: The sequence of operations to execute if the condition is met
    """

    op_type: Literal["if"] = "if"
    """The type discriminator, always "if"."""
    var: SymbolRef
    """The variable reference for the condition."""
    body: BodyT
    """The sequence of operations to execute if the condition is met."""
