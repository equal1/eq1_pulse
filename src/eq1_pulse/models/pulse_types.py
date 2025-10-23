# ruff: noqa: D100 D101 D102 D105, D107
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import Discriminator

from .basic_types import Amplitude, Duration, Frequency, LeanModel
from .reference_types import VariableRef

if TYPE_CHECKING:
    from .basic_types import AmplitudeLike, DurationLike, FrequencyLike
    from .reference_types import VariableRefLike

__all__ = ("PulseType", "SinePulse", "SquarePulse")


class PulseBase(LeanModel):
    pulse_type: Any  # str
    duration: Duration | VariableRef
    amplitude: Amplitude | VariableRef

    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            duration: DurationLike | VariableRefLike,
            amplitude: AmplitudeLike | VariableRefLike,
            **data,
        ): ...


class SquarePulse(PulseBase):
    pulse_type: Literal["square"] = "square"
    rise_time: Duration | VariableRef | None = None
    fall_time: Duration | VariableRef | None = None

    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            duration: DurationLike | VariableRefLike,
            amplitude: AmplitudeLike | VariableRefLike,
            rise_time: DurationLike | VariableRefLike | None = None,
            fall_time: DurationLike | VariableRefLike | None = None,
            **data,
        ): ...


class SinePulse(PulseBase):
    pulse_type: Literal["sine"] = "sine"
    frequency: Frequency | VariableRef
    to_frequency: Frequency | VariableRef | None = None

    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            duration: DurationLike | VariableRefLike,
            amplitude: AmplitudeLike | VariableRefLike,
            frequency: FrequencyLike | VariableRefLike,
            to_frequency: FrequencyLike | VariableRefLike | None = None,
            **data,
        ): ...


type PulseType = Annotated[SquarePulse | SinePulse, Discriminator("pulse_type")]
"""All the supported pulse types, discriminated by the "pulse_type" field."""
