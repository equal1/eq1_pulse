"""External block model.

An :class:`ExternalBlock` is an opaque, channel-reserving operation whose contents are not
described by this IR. See the class docstring for its full semantics.
"""

# ruff: noqa: D107
from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Self

from pydantic import model_validator

from .basic_types import Duration, OpBase
from .identifier_str import FullyQualifiedIdentifier
from .pulse_types import ExternalParamValue
from .reference_types import ChannelTarget, SymbolRef, VariableRef

if TYPE_CHECKING:
    from .basic_types import DurationLike
    from .pulse_types import ExternalParamValueLike
    from .reference_types import ChannelRefLike, SymbolRefLike, VariableRefLike

__all__ = ("ExternalBlock",)


class ExternalBlock(OpBase):
    """An opaque, channel-reserving block of externally defined contents.

    It is simultaneously: the way to reference an externally defined program (a calibrated gate, a
    vendor routine, a hand-written OpenPulse ``defcal``); the scoping construct needed to *consume*
    OpenQASM ``box``; and the mechanism that makes a multi-channel operation atomic against the
    surrounding scheduler.

    Semantics:

    1. **Reservation.** The block occupies every channel in :attr:`channels` for its whole extent.
       No operation elsewhere in the program may be scheduled on any of those channels within that
       extent.
    2. **Synchronisation.** Entry and exit are synchronisation points across :attr:`channels`: the
       block starts at the latest availability of all of them and all of them become free
       simultaneously at its end. (Same rule as OpenQASM ``box`` resource participation and
       ``defcal`` entry alignment.)
    3. **Non-interference.** Channels *not* listed are unaffected and may be driven concurrently.
    4. **Opacity / optimisation barrier.** Contents are not described by this IR. Operations may
       not be moved into or out of the block. Nothing may be assumed about what happens on the
       reserved channels inside it.
    5. **Timed vs flex.**

       - ``duration=D`` -- hard total-duration constraint. It is an error if the referenced
         program's natural duration exceeds ``D``. Slack placement inside the block is the
         program's business.
       - ``duration=None`` -- flex. Duration is the referenced program's natural duration,
         resolved by whatever holds the program definitions. Directly analogous to OpenQASM's
         untimed ``box`` and to ``durationof``.
    6. **Empty** :attr:`program`. ``program=None`` with a :attr:`duration` is a pure reservation --
       "these channels are busy for this long, do not touch them." Useful for modelling externally
       driven intervals.

    Regarding :attr:`params`:

    4. If ``duration=None`` (flex) **and** any :attr:`params` value is a :class:`~.reference_types.VariableRef`
       whose value is only known at run time, the block's duration is not resolvable at compile
       time. OpenQASM has the same rule for ``defcal``: the body must have a definite duration
       regardless of its parameters. Either the external program guarantees a parameter-independent
       duration, or the block must carry an explicit :attr:`duration`. This is enforced as a
       validation rule with a clear error, not a runtime surprise.
    5. The IR does not know the referenced program's signature -- opacity is the point. Arity and
       type checking of :attr:`params`/:attr:`results`/:attr:`channels` belongs to whatever resolves
       :attr:`program`. The IR validates only what it can see: that :attr:`results` variables are
       declared, that :attr:`channels` values are valid channel targets -- a channel name, or an
       :class:`~.reference_types.ExternalRef` when the calibration store owns the name -- and
       rule 4 above.
    """

    op_type: Literal["external_block"] = "external_block"
    """The type discriminator, always "external_block"."""

    program: FullyQualifiedIdentifier | None = None
    """Reference to an externally defined program supplying the contents.

    Spelled as a fully-qualified identifier for consistency with
    :attr:`~.pulse_types.ExternalPulse.function`.
    """

    channels: dict[str, ChannelTarget]
    """Channels claimed by the block, keyed by the role each plays in the referenced program.

    The reservation set is exactly ``channels.values()``.
    """

    params: dict[str, ExternalParamValue] | None = None
    """Input arguments passed to the referenced program."""

    results: dict[str, VariableRef] | None = None
    """Output bindings: variables the referenced program writes into."""

    duration: Duration | SymbolRef | None = None
    """Total duration.

    :obj:`None` means *flex*: the duration is whatever the referenced program naturally takes,
    and must be resolved before execution.
    """

    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            program: FullyQualifiedIdentifier | None = None,
            channels: dict[str, ChannelRefLike],
            params: dict[str, ExternalParamValueLike] | None = None,
            results: dict[str, VariableRefLike] | None = None,
            duration: DurationLike | SymbolRefLike | None = None,
            **data,
        ): ...

    @model_validator(mode="after")
    def _validate_flex_duration_params(self) -> Self:
        if self.duration is None and self.params is not None:
            for name, value in self.params.items():
                if isinstance(value, VariableRef):
                    raise ValueError(
                        f"external_block: flex duration (duration=None) combined with a runtime-variable "
                        f"parameter {name!r} is unresolvable. Either supply an explicit duration=..., "
                        f"or pass a compile-time value for {name!r}."
                    )
        return self
