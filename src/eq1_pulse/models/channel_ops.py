"""Channel operations models.

These models define various operations that can be performed on channels,
including playing pulses, waiting, setting frequencies and phases,
and recording data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal, overload

from pydantic import Discriminator

from .base_models import LeanModel
from .basic_types import Duration, Frequency, Magnitude, OpBase, Phase
from .pulse_types import PulseType
from .reference_types import ChannelRef, PulseRef, VariableRef

if TYPE_CHECKING:
    from .basic_types import DurationLike, FrequencyLike, MagnitudeLike, PhaseLike
    from .reference_types import ChannelRefLike, PulseRefLike, VariableRefLike

__all__ = (
    "Barrier",
    "ChannelOpBase",
    "CompensateDC",
    "DemodIntegration",
    "FullIntegration",
    "IntegrationType",
    "Play",
    "Record",
    "SetFrequency",
    "SetPhase",
    "ShiftFrequency",
    "ShiftPhase",
    "Trace",
    "Wait",
)


class IntegrationType(LeanModel):
    """Base class for different types of integration operations."""

    integration_type: Any  # str
    """To be set to the discriminator value (literal) in subclasses."""


class FullIntegration(IntegrationType):
    """Full summation of measured values."""

    integration_type: Literal["full"] = "full"


class DemodIntegration(IntegrationType):
    """Demodulation integration of measured values.

    The demodulation operation will multiply the measured signal with
    the channels' output signal before integration.
    If scale_cos/scale_sin are specified they can be used to scale and "flip" the real/imaginary parts of the result.

    An optional phase may be applied to rotate the result.
    """

    integration_type: Literal["demod"] = "demod"
    phase: Phase | None = None
    scale_cos: float = 1
    scale_sin: float = 1


class ChannelOpBase(OpBase):
    """Base class for operations involving a single channel."""

    channel: ChannelRef

    def __init__(self, channel: ChannelRefLike, **data):  # noqa: D107
        super().__init__(channel=channel, **data)  # type: ignore[call-arg]


class Play(ChannelOpBase):
    """Play a pulse on a channel."""

    op_type: Literal["play"] = "play"
    """The operation type discriminator, always set to "play"."""

    pulse: PulseType | PulseRef
    """The pulse to be played on the channel."""

    scale_amp: float | complex | VariableRef | None = None
    """Optional amplitude scaling factor for the pulse."""

    cond: VariableRef | None = None
    """Optional condition variable to control whether the pulse is played."""

    def __init__(self, channel: ChannelRefLike, pulse: PulseType | PulseRefLike, **data):  # noqa: D107
        super().__init__(channel=channel, pulse=pulse, **data)


class ChannelsOpBase(OpBase):
    """Base class for operations involving multiple channels."""

    channels: list[ChannelRef]
    """The channels involved in the operation."""

    def __init__(self, *channels: ChannelRefLike, **data):
        """Initialize with channels."""
        if not channels:
            super().__init__(**data)
        else:
            super().__init__(channels=list(channels), **data)  # type: ignore[call-arg]


class Barrier(ChannelsOpBase):
    """Synchronize channels.

    The barrier operation causes channels to wait until all channels have reached the barrier.
    """

    op_type: Literal["barrier"] = "barrier"

    if TYPE_CHECKING:

        @overload
        def __init__(self, /, *, channels: list[ChannelRefLike], **data): ...

        @overload
        def __init__(self, /, *channels: ChannelRefLike, **data): ...

        def __init__(self, *args, **data): ...  # noqa: D107


class Wait(ChannelsOpBase):
    """Add wait of duration on channel(s).

    The wait operations are scheduled to start as soon as possible on each channel.

    The relative timing between channels is not guaranteed.
    """

    op_type: Literal["wait"] = "wait"
    duration: Duration

    if TYPE_CHECKING:

        @overload
        def __init__(self, /, *, channels: list[ChannelRefLike], duration: Duration | dict[str, float], **data): ...

        @overload
        def __init__(self, /, *channels: ChannelRefLike, duration: Duration | dict[str, float], **data): ...

        def __init__(self, *args, **data): ...  # noqa: D107


class SetFrequency(ChannelOpBase):
    """Set the frequency of a channel."""

    op_type: Literal["set_frequency"] = "set_frequency"
    """The operation type discriminator, always set to "set_frequency"."""

    frequency: Frequency | VariableRef

    def __init__(self, channel: ChannelRefLike, frequency: FrequencyLike | VariableRefLike, **data):  # noqa: D107
        super().__init__(channel=channel, frequency=frequency, **data)


class ShiftFrequency(ChannelOpBase):
    """Add a frequency shift to the channel frequency."""

    op_type: Literal["shift_frequency"] = "shift_frequency"
    """The operation type discriminator, always set to "shift_frequency"."""
    frequency: Frequency | VariableRef

    def __init__(self, /, channel: ChannelRefLike, frequency: FrequencyLike | VariableRefLike, **data):  # noqa: D107
        super().__init__(channel=channel, frequency=frequency, **data)


class SetPhase(ChannelOpBase):
    """Set the phase of a channel."""

    op_type: Literal["set_phase"] = "set_phase"
    phase: Phase | VariableRef

    def __init__(self, /, channel: ChannelRefLike, phase: PhaseLike | VariableRefLike, **data):  # noqa: D107
        super().__init__(channel=channel, phase=phase, **data)


class ShiftPhase(ChannelOpBase):
    """Add a phase shift to the channel phase."""

    op_type: Literal["shift_phase"] = "shift_phase"
    phase: Phase | VariableRef

    def __init__(self, /, channel: ChannelRefLike, phase: PhaseLike | VariableRefLike, **data):  # noqa: D107
        super().__init__(channel=channel, phase=phase, **data)


class Record(ChannelOpBase):
    """Acquire scalar data from the channel with integration.

    The integration type can be either "full" or "demod".
    Full integration is a simple accumulation of the signal.
    Demod integration is a complex multiplication of the signal with the channel's
    frequency and phase followed by accumulation.

    The result of the integration is saved into a scalar (complex) variable.

    Further processing may be applied to the result, such as projection to real/imaginary parts,
    see :class:`Discriminate`.
    """

    op_type: Literal["record"] = "record"
    var: VariableRef
    duration: Duration
    integration: FullIntegration | DemodIntegration
    time_of_flight: Duration | None = None

    if TYPE_CHECKING:

        def __init__(  # noqa: D107
            self,
            /,
            channel: ChannelRefLike,
            *,
            var: VariableRefLike,
            duration: Duration | dict[str, float],
            integration: FullIntegration | DemodIntegration = ...,
            time_of_flight: Duration | dict[str, float] | None = None,
            **data,
        ): ...


class Trace(ChannelOpBase):
    """Acquire trace data from the channel with integration.

    Similar to :class:`Record`, but the result is saved into an array variable,
    and it essentially a repeated, continuous record operation.

    The duration is the total time of the trace, the number of records
    is determined by the length of the array variable.

    Further processing may be applied to the result, such as projection to real/imaginary parts,
    see :class:`Discriminate`.
    """

    op_type: Literal["trace"] = "trace"
    var: VariableRef
    duration: Duration
    integration: FullIntegration | DemodIntegration | None = None
    time_of_flight: Duration | None = None

    if TYPE_CHECKING:

        def __init__(  # noqa: D107
            self,
            /,
            channel: ChannelRefLike,
            *,
            var: VariableRef | str,
            duration: Duration | dict[str, float],
            integration: FullIntegration | DemodIntegration = ...,
            time_of_flight: Duration | dict[str, float] | None = None,
            **data,
        ): ...


class CompensateDC(ChannelOpBase):
    """Apply DC offset compensation to the channel.

    A square wave of specified duration is played on the channel. The amplitude of the wave is calculated to
    result in a zero average value when integrated over the duration since the laste reset.

    If ``null``/:obj:`None` duration is specified, the accumulated value is reset to zero, without
    playing a compensation pulse.

    If ``max_amp`` is specified, the amplitude of the compensation pulse is limited to that value.
    If the amplitude is calculated to be higher, the pulse area is subtracted from the accumulated value,
    leaving the possibility to compensate the rest in the following operations.

    If ``rise_time`` and ``fall_time`` are specified, they define the duration of linear ramps
    at the beginning and end of the compensation pulse. The ramps are included in the area calculation.
    The rise and fall times are also included in the total duration of the compensation pulse.
    """

    op_type: Literal["dc_comp"] = "dc_comp"
    duration: Duration | VariableRef | None
    """If :obj:`None`, reset channel-accumulated value without playing anything."""

    max_amp: Magnitude | None = None

    rise_time: Duration | VariableRef | None = None
    fall_time: Duration | VariableRef | None = None

    if TYPE_CHECKING:

        def __init__(  # noqa: D107
            self,
            /,
            channel: ChannelRefLike,
            *,
            duration: DurationLike | VariableRefLike | None,
            max_amp: MagnitudeLike | None = None,
            **data,
        ): ...


type ChannelOp = Annotated[
    Play | Wait | Barrier | SetFrequency | ShiftFrequency | SetPhase | ShiftPhase | Record | Trace | CompensateDC,
    Discriminator("op_type"),
]
"""Channel operation type.

This is a closed set of channel operations that can be used in a sequence.
All operations have a discriminator field ``op_type`` that is used to distinguish between them.
 """
