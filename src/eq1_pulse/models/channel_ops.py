"""Channel operations models.

These models define various operations that can be performed on channels,
including playing pulses, waiting, setting frequencies and phases,
and recording data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal, overload

from .base_models import LeanModel
from .basic_types import Duration, Frequency, Magnitude, OpBase, OperationDiscriminator, Phase
from .pulse_types import PulseType
from .reference_types import ChannelTarget, PulseRef, VariableRef, VarName

if TYPE_CHECKING:
    from .basic_types import DurationLike, FrequencyLike, MagnitudeLike, PhaseLike
    from .expressions import ValueRefLike
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
    """The type discriminator for integration types."""


class FullIntegration(IntegrationType):
    """Full summation of measured values."""

    integration_type: Literal["full"] = "full"
    """The type discriminator, always "full"."""


class DemodIntegration(IntegrationType):
    """Demodulation integration of measured values.

    The demodulation operation will multiply the measured signal with
    the channels' output signal before integration.
    If scale_cos/scale_sin are specified they can be used to scale and "flip" the real/imaginary parts of the result.

    An optional phase may be applied to rotate the result.
    """

    integration_type: Literal["demod"] = "demod"
    """The type discriminator, always "demod"."""
    phase: Phase | ValueRef | None = None
    """Optional phase rotation to apply to the result."""
    scale_cos: float | ValueRef = 1
    """Scaling factor for the real (cosine) part."""
    scale_sin: float | ValueRef = 1
    """Scaling factor for the imaginary (sine) part."""


class ChannelOpBase(OpBase):
    """Base class for operations involving a single channel."""

    channel: ChannelTarget
    """The channel on which the operation is performed."""

    def __init__(self, channel: ChannelRefLike, **data):  # noqa: D107
        super().__init__(channel=channel, **data)  # type: ignore[call-arg]


class Play(ChannelOpBase):
    """Play a pulse on a channel."""

    op_type: Literal["play"] = "play"
    """The operation type discriminator, always set to "play"."""

    pulse: PulseType | PulseRef
    """The pulse to be played on the channel."""

    scale_amp: float | complex | ValueRef | None = None
    """Optional amplitude scaling factor for the pulse."""

    cond: ValueRef | None = None
    """Optional condition variable to control whether the pulse is played."""

    def __init__(self, channel: ChannelRefLike, pulse: PulseType | PulseRefLike, **data):  # noqa: D107
        super().__init__(channel=channel, pulse=pulse, **data)


class ChannelsOpBase(OpBase):
    """Base class for operations involving multiple channels."""

    channels: list[ChannelTarget]
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
    """The type discriminator, always "barrier"."""

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

    ``Wait`` is the more primitive counterpart of OpenQASM's multi-resource ``delay``, which
    conflates a barrier with a delay. The composite decomposes exactly:

    .. code-block:: text

        import:   delay[d] a, b;   ->   barrier(a, b) ; wait(a, b, d)
        export:   wait(a, b, d)    ->   delay[d] a;  delay[d] b;

    The import identity holds because after ``barrier(a, b)`` both channels' cursors are equal, so
    an independent per-channel wait lands both ends at ``max(...) + d`` -- precisely the OpenQASM
    semantics. The export identity holds because a single-resource ``delay`` advances only its own
    cursor.
    """

    op_type: Literal["wait"] = "wait"
    """The type discriminator, always "wait"."""
    duration: Duration | ValueRef
    """The duration to wait."""

    if TYPE_CHECKING:

        @overload
        def __init__(
            self, /, *, channels: list[ChannelRefLike], duration: Duration | dict[str, float] | ValueRefLike, **data
        ): ...

        @overload
        def __init__(
            self, /, *channels: ChannelRefLike, duration: Duration | dict[str, float] | ValueRefLike, **data
        ): ...

        def __init__(self, *args, **data): ...  # noqa: D107


class SetFrequency(ChannelOpBase):
    """Set the frequency of a channel."""

    op_type: Literal["set_frequency"] = "set_frequency"
    """The operation type discriminator, always set to "set_frequency"."""

    frequency: Frequency | ValueRef
    """The frequency to set."""

    def __init__(self, channel: ChannelRefLike, frequency: FrequencyLike | ValueRefLike, **data):  # noqa: D107
        super().__init__(channel=channel, frequency=frequency, **data)


class ShiftFrequency(ChannelOpBase):
    """Add a frequency shift to the channel frequency."""

    op_type: Literal["shift_frequency"] = "shift_frequency"
    """The operation type discriminator, always set to "shift_frequency"."""
    frequency: Frequency | ValueRef
    """The frequency shift to apply."""

    def __init__(self, /, channel: ChannelRefLike, frequency: FrequencyLike | ValueRefLike, **data):  # noqa: D107
        super().__init__(channel=channel, frequency=frequency, **data)


class SetPhase(ChannelOpBase):
    """Set the phase of a channel."""

    op_type: Literal["set_phase"] = "set_phase"
    """The type discriminator, always "set_phase"."""
    phase: Phase | ValueRef
    """The phase to set."""

    def __init__(self, /, channel: ChannelRefLike, phase: PhaseLike | ValueRefLike, **data):  # noqa: D107
        super().__init__(channel=channel, phase=phase, **data)


class ShiftPhase(ChannelOpBase):
    """Add a phase shift to the channel phase."""

    op_type: Literal["shift_phase"] = "shift_phase"
    """The type discriminator, always "shift_phase"."""
    phase: Phase | ValueRef
    """The phase shift to apply."""

    def __init__(self, /, channel: ChannelRefLike, phase: PhaseLike | ValueRefLike, **data):  # noqa: D107
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
    """The type discriminator, always "record"."""
    var: VarName
    """The variable to store the acquisition result."""
    duration: Duration | ValueRef
    """The duration of the acquisition."""
    integration: FullIntegration | DemodIntegration
    """The integration method to use."""
    time_of_flight: Duration | ValueRef | None = None
    """Optional delay before starting acquisition."""

    if TYPE_CHECKING:

        def __init__(  # noqa: D107
            self,
            /,
            channel: ChannelRefLike,
            *,
            var: VariableRefLike,
            duration: DurationLike | ValueRefLike,
            integration: FullIntegration | DemodIntegration = ...,
            time_of_flight: DurationLike | ValueRefLike | None = None,
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
    """The type discriminator, always "trace"."""
    var: VarName
    """The array variable to store the trace data."""
    duration: Duration | ValueRef
    """The total duration of the trace acquisition."""
    integration: FullIntegration | DemodIntegration | None = None
    """The integration method to use."""
    time_of_flight: Duration | ValueRef | None = None
    """Optional delay before starting acquisition."""

    if TYPE_CHECKING:

        def __init__(  # noqa: D107
            self,
            /,
            channel: ChannelRefLike,
            *,
            var: VariableRef | str,
            duration: DurationLike | ValueRefLike,
            integration: FullIntegration | DemodIntegration = ...,
            time_of_flight: DurationLike | ValueRefLike | None = None,
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
    """The type discriminator, always "dc_comp"."""
    duration: Duration | ValueRef | None
    """If :obj:`None`, reset channel-accumulated value without playing anything."""

    max_amp: Magnitude | ValueRef | None = None
    """Maximum amplitude limit for the compensation pulse."""

    rise_time: Duration | ValueRef | None = None
    """Duration of the rising edge ramp."""
    fall_time: Duration | ValueRef | None = None
    """Duration of the falling edge ramp."""

    if TYPE_CHECKING:

        def __init__(  # noqa: D107
            self,
            /,
            channel: ChannelRefLike,
            *,
            duration: DurationLike | ValueRefLike | None,
            max_amp: MagnitudeLike | ValueRefLike | None = None,
            **data,
        ): ...


type ChannelOp = Annotated[
    Play | Wait | Barrier | SetFrequency | ShiftFrequency | SetPhase | ShiftPhase | Record | Trace | CompensateDC,
    OperationDiscriminator(),
]
"""Channel operation type.

This is a closed set of channel operations that can be used in a sequence.
Each one is spelled as the single-key object ``{op_type: payload}`` -- ``{"play": {...}}`` -- and
:class:`~.basic_types.OperationDiscriminator` selects the member by that sole key.
"""

# Deferred: this module is reachable (via `pulse_types`) before `expressions` has finished defining
# `ValueRef`, so importing it at the top would recurse back through that edge. By the time this
# runs, every class above is already defined, so the rebuild below is all that is left to resolve.
from .expressions import ValueRef  # noqa: E402

DemodIntegration.model_rebuild()
Play.model_rebuild()
Wait.model_rebuild()
SetFrequency.model_rebuild()
ShiftFrequency.model_rebuild()
SetPhase.model_rebuild()
ShiftPhase.model_rebuild()
Record.model_rebuild()
Trace.model_rebuild()
CompensateDC.model_rebuild()
