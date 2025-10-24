"""Base models for control flow operations."""

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, Literal, Self, overload

from pydantic import (
    ConfigDict,
    Field,
    model_serializer,
    model_validator,
)

from .base_models import NoExtrasModel
from .basic_types import LinSpace, OpBase, Range
from .nd_array import NumpyComplexArray1D, NumpyFloatArray1D, NumpyIntArray1D
from .reference_types import VariableRef

__all__ = "ConditionalBase", "IterationBase", "RepetitionBase"


class SequenceBase[ItemT](NoExtrasModel):
    """Base class for sequence of items that can be serialized as a list.

    This class represents an ordered collection of operation sequence items that
    will be serialized as a list when converted to JSON or other formats.

    :ivar items: List of operation sequence items
    """

    items: list[ItemT]

    def __len__(self):
        return len(self.items)

    def __getitem__(self, key: int) -> ItemT:
        return self.items[key]

    @overload
    def __init__(self, items: Iterable[ItemT], **data): ...

    @overload
    def __init__(self, **data): ...

    def __init__(self, *args, **data):
        """Initialize a seuence with sequence items.

        :param items: An iterable of operation sequence items
        :param data: Additional keyword arguments for Model initialization
        """
        match len(args):
            case 0:
                pass
            case 1:
                if "items" in data:
                    raise TypeError("duplicate argument 'items'")
                data["items"] = list(args[0])
            case n:
                raise TypeError(f"Expected 0 or 1 positional arguments, got {n}")

        super().__init__(**data)

    @model_validator(mode="before")
    @classmethod
    def _wrap_validator(cls, data: Any) -> Any:
        if isinstance(data, Mapping):
            # This artifact is required to allow recursive containment of sequences within sequences.
            if "items" not in data:
                # The pydantic engine will enter here to try to validate other data
                # as a sequence. It will fail and continue to match other types.
                # Caveat: if alternative types have an "items" field, they will be accepted here instead.
                raise ValueError("items field is required")
            return data
        if isinstance(data, list):
            return {"items": data}

        raise ValueError("Invalid data type")

    @model_serializer
    def _wrap_serializer(self) -> Any:
        return self.items

    if TYPE_CHECKING:

        def model_dump(  # type: ignore[override]
            self,
            *,
            mode="python",
            include=None,
            exclude=None,
            context=None,
            by_alias=False,
            exclude_unset=False,
            exclude_defaults=False,
            exclude_none=False,
            round_trip=False,
            warnings=True,
            serialize_as_any=False,
        ) -> list[dict[str, Any]]: ...


class RepetitionBase[BodyT](OpBase):
    """Represents an abstract repeated sequence of operations.

    :ivar op_type: Operation type, always "repeat"
    :ivar count: Number of times to repeat the sequence
    :ivar body: The sequence of operations to repeat

    To be extended with field to contain the operations.
    """

    op_type: Literal["repeat"] = "repeat"
    count: int = Field(ge=0)
    body: BodyT


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
    var: VariableRef
    body: BodyT
