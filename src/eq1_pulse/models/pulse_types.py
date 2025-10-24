# ruff: noqa: D100, D101, D107
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import ConfigDict, Discriminator

from .base_models import LeanModel
from .basic_types import Amplitude, Duration, Frequency
from .identifier_str import FullyQualifiedIdentifier
from .nd_array import NumpyArray, NumpyComplexArray1D, NumpyFloatArray1D
from .reference_types import VariableRef, VarRefDict

if TYPE_CHECKING:
    from .basic_types import AmplitudeLike, DurationLike, FrequencyLike
    from .reference_types import VariableRefLike

__all__ = ("ArbitrarySampledPulse", "ExternalPulse", "PulseType", "SinePulse", "SquarePulse")


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


type PulseParamScalarValue = float | int | complex | str
"""Scalar parameter value for arbitrary pulses."""
type PulseParamValue = Amplitude | Duration | Frequency | VariableRef | PulseParamScalarValue
"""Dimensional or scalar parameter value for arbitrary pulses."""
type PulseParamValueLike = (
    AmplitudeLike | DurationLike | FrequencyLike | VariableRef | VarRefDict | PulseParamScalarValue
)
"""Acceptable input types for dimensional or scalar parameter values for arbitrary pulses."""


class ExternalPulse(PulseBase):
    """Pulse type that references an externally defined pulse function.

    The amplitude refers to the reference amplitude of the pulse, which is usually the peak amplitude.
    The duration refers to the total duration of the pulse.

    The pulse function is expected to be defined elsewhere, such as in a pulse library or a hardware definition.
    """

    pulse_type: Literal["external"] = "external"
    """The type discriminator for external pulses. It is always "external"."""
    function: FullyQualifiedIdentifier
    """The name of the externally defined pulse function to use."""
    duration: Duration | VariableRef
    """The duration of the pulse."""
    amplitude: Amplitude | VariableRef
    """The reference amplitude of the pulse. This is usually the peak amplitude."""
    params: dict[str, PulseParamValue] | None = None
    """Additional parameters to pass to the pulse function."""

    if TYPE_CHECKING:

        def __init__(
            self,
            function: FullyQualifiedIdentifier,
            *,
            duration: DurationLike | VariableRefLike,
            amplitude: AmplitudeLike | VariableRefLike,
            params: dict[str, PulseParamValueLike] | None = None,
        ): ...

    else:

        def __init__(self, /, function, **data):
            super().__init__(function=function, **data)


class ArbitrarySampledPulse(PulseBase):
    """Pulse type that uses arbitrary sampled waveform data.

    The amplitude refers to the reference amplitude of the pulse, which is usually the peak amplitude.
    The duration refers to the total duration of the pulse.
    The samples (complex or real) are expected to be normalized between -1 and 1, and will be scaled by the amplitude.
    The samples are uniformly distributed over the duration of the pulse, with interpolation applied as needed.
    """

    pulse_type: Literal["arbitrary"] = "arbitrary"
    """The type discriminator for arbitrary sampled pulses. It is always "arbitrary"."""
    samples: NumpyFloatArray1D | NumpyComplexArray1D
    """The normalized samples of the pulse waveform."""
    interpolation: str | None = None
    """The interpolation method to use when resampling the waveform. Defaults to :obj:`None`."""
    time_points: NumpyFloatArray1D | None = None
    """The time points of the samples in time.

    The range will be scaled to the duration of the pulse during resampling.
    If :obj:`None`, samples are assumed to be uniformly distributed over the duration."""

    if TYPE_CHECKING:

        def __init__(
            self,
            samples: list[float] | list[complex] | NumpyArray | VariableRefLike,
            *,
            duration: DurationLike | VariableRefLike,
            amplitude: AmplitudeLike | VariableRefLike,
            interpolation: str | None = None,
            time_points: list[float] | NumpyArray | None = None,
        ): ...

    else:

        def __init__(self, /, samples, **data):
            super().__init__(samples=samples, **data)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


type PulseType = Annotated[SquarePulse | SinePulse | ExternalPulse | ArbitrarySampledPulse, Discriminator("pulse_type")]
"""All the supported pulse types, discriminated by the "pulse_type" field."""
