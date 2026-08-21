# ruff: noqa: D100, D107
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal

from pydantic import (
    BeforeValidator,
    ConfigDict,
    Discriminator,
    PlainSerializer,
    TypeAdapter,
    ValidationError,
    WithJsonSchema,
)

from .base_models import LeanModel as _LeanModel
from .basic_types import Amplitude, Duration, Frequency, Magnitude, Phase
from .complex import complex_from_tuple
from .identifier_str import FullyQualifiedIdentifier
from .nd_array import NumpyArray, NumpyComplexArray1D, NumpyFloatArray1D
from .reference_types import ExternalRef, ExtRefDict, PulseRef, SymbolRef, VariableRef, VarRefDict

if TYPE_CHECKING:
    from .basic_types import AmplitudeLike, DurationLike, FrequencyLike, MagnitudeLike, PhaseLike
    from .reference_types import PulseRefLike, SymbolRefLike, VariableRefLike

__all__ = (
    "ArbitrarySampledPulse",
    "ExternalParamScalarValue",
    "ExternalParamValue",
    "ExternalParamValueLike",
    "ExternalPulse",
    "PulseParamScalarValue",
    "PulseParamValue",
    "PulseParamValueLike",
    "PulseType",
    "SinePulse",
    "SquarePulse",
)


class PulseBase(_LeanModel):
    """Base class for all pulse types."""

    pulse_type: Any  # str
    """The type discriminator for pulse types."""
    duration: Duration | SymbolRef
    """The duration of the pulse."""
    amplitude: Amplitude | SymbolRef
    """The amplitude of the pulse."""

    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            duration: DurationLike | SymbolRefLike,
            amplitude: AmplitudeLike | SymbolRefLike,
            **data,
        ): ...


class SquarePulse(PulseBase):
    """Square pulse with optional rise and fall times.

    If rise and fall times are specified, the pulse will
    have linear ramps at the beginning and end.

    These ramps shorten the flat top duration accordingly.
    """

    pulse_type: Literal["square"] = "square"
    """The type discriminator, always "square"."""
    rise_time: Duration | SymbolRef | None = None
    """The rise time of the pulse. It's also included in the total duration."""
    fall_time: Duration | SymbolRef | None = None
    """The fall time of the pulse. It's also included in the total duration."""

    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            duration: DurationLike | SymbolRefLike,
            amplitude: AmplitudeLike | SymbolRefLike,
            rise_time: DurationLike | SymbolRefLike | None = None,
            fall_time: DurationLike | SymbolRefLike | None = None,
            **data,
        ): ...


class SinePulse(PulseBase):
    """Sine wave pulse with optional frequency sweep."""

    pulse_type: Literal["sine"] = "sine"
    """The type discriminator, always "sine"."""
    frequency: Frequency | SymbolRef
    """The frequency of the sine wave."""
    to_frequency: Frequency | SymbolRef | None = None
    """The target frequency for frequency sweeps."""

    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            duration: DurationLike | SymbolRefLike,
            amplitude: AmplitudeLike | SymbolRefLike,
            frequency: FrequencyLike | SymbolRefLike,
            to_frequency: FrequencyLike | SymbolRefLike | None = None,
            **data,
        ): ...


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
    duration: Duration | SymbolRef
    """The duration of the pulse."""
    amplitude: Amplitude | SymbolRef
    """The reference amplitude of the pulse. This is usually the peak amplitude."""
    params: dict[str, ExternalParamValue] | None = None
    """Additional parameters to pass to the pulse function."""

    if TYPE_CHECKING:

        def __init__(
            self,
            function: FullyQualifiedIdentifier,
            *,
            duration: DurationLike | SymbolRefLike,
            amplitude: AmplitudeLike | SymbolRefLike,
            params: dict[str, ExternalParamValueLike] | None = None,
        ): ...

    else:

        def __init__(self, /, function, **data):
            super().__init__(function=function, **data)


class ArbitrarySampledPulse(PulseBase):
    """Pulse type that uses arbitrary sampled waveform data.

    The amplitude refers to the reference amplitude of the pulse, which is usually the peak amplitude.
    The duration refers to the total duration of the pulse.
    The samples (complex or real) are expected to be normalized between -1 and 1, and will be scaled by the amplitude.
    The samples are distributed over the duration of the pulse (uniformly or according to custom `time_points`),
    with interpolation applied as needed.
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
            duration: DurationLike | SymbolRefLike,
            amplitude: AmplitudeLike | SymbolRefLike,
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


type ExternalParamScalarValue = bool | float | int | complex_from_tuple | str
"""Scalar parameter value for externally defined pulses and blocks.

:obj:`complex` is represented as :data:`~.complex.complex_from_tuple` (a ``(real, imag)`` pair)
rather than a bare :obj:`complex`: :class:`complex`'s native JSON form is a string, which would
otherwise be indistinguishable from a plain :obj:`str` value in :data:`ExternalParamValue`.
"""


def _wrap_tagged_variable_ref(value: Any) -> Any:
    """Recognize the tagged-dict encoding of a :class:`~.reference_types.VariableRef`.

    :param value: Raw input for an :data:`ExternalParamValue`

    :return: The equivalent :class:`~.reference_types.VariableRef` constructor argument if
        ``value`` is the tagged form (``{"var_ref": name}``), otherwise ``value`` unchanged
    """
    if isinstance(value, Mapping) and set(value) == {"var_ref"}:
        return {"var": value["var_ref"]}
    return value


def _unwrap_tagged_variable_ref(value: VariableRef) -> dict[str, str]:
    """Serialize a :class:`~.reference_types.VariableRef` as a tagged dict.

    :param value: The reference to serialize

    :return: ``{"var_ref": name}``
    """
    return {"var_ref": value.var}


def _wrap_tagged_pulse_ref(value: Any) -> Any:
    """Recognize the tagged-dict encoding of a :class:`~.reference_types.PulseRef`.

    :param value: Raw input for an :data:`ExternalParamValue`

    :return: The equivalent :class:`~.reference_types.PulseRef` constructor argument if
        ``value`` is the tagged form (``{"pulse_ref": name}``), otherwise ``value`` unchanged
    """
    if isinstance(value, Mapping) and set(value) == {"pulse_ref"}:
        return {"pulse_name": value["pulse_ref"]}
    return value


def _unwrap_tagged_pulse_ref(value: PulseRef) -> dict[str, str]:
    """Serialize a :class:`~.reference_types.PulseRef` as a tagged dict.

    :param value: The reference to serialize

    :return: ``{"pulse_ref": name}``
    """
    return {"pulse_ref": value.pulse_name}


type _TaggedVariableRef = Annotated[
    VariableRef,
    BeforeValidator(_wrap_tagged_variable_ref),
    PlainSerializer(_unwrap_tagged_variable_ref, return_type=dict[str, str]),
    WithJsonSchema({"type": "object", "properties": {"var_ref": {"type": "string"}}, "required": ["var_ref"]}),
]
"""A :class:`~.reference_types.VariableRef`, tagged as ``{"var_ref": name}``.

Used only within :data:`ExternalParamValue`: a bare :class:`~.reference_types.VariableRef`
serializes as a plain string identical in shape to :obj:`str`, so it would not survive a JSON
round-trip through a union that also accepts :obj:`str`.
"""

type _TaggedPulseRef = Annotated[
    PulseRef,
    BeforeValidator(_wrap_tagged_pulse_ref),
    PlainSerializer(_unwrap_tagged_pulse_ref, return_type=dict[str, str]),
    WithJsonSchema({"type": "object", "properties": {"pulse_ref": {"type": "string"}}, "required": ["pulse_ref"]}),
]
"""A :class:`~.reference_types.PulseRef`, tagged as ``{"pulse_ref": name}``, for the same reason
as :data:`_TaggedVariableRef`.
"""

_DIMENSIONAL_TYPE_ADAPTERS: Final = tuple(
    TypeAdapter(dimensional_type) for dimensional_type in (Amplitude, Duration, Frequency, Phase, Magnitude)
)


def _coerce_dimensional_string(value: Any) -> Any:
    """Coerce a unit-suffixed string to its typed dimensional quantity, if it matches one.

    Because :data:`ExternalParamValue` also accepts a bare :obj:`str`, Pydantic's default
    "smart" union resolution always prefers the exact :obj:`str` match over the dimensional
    types that merely *accept* a unit-suffixed string. This runs before that resolution and
    tries each dimensional type's own validator in turn (in the order the union declares them),
    leaving ``value`` as a plain string only if none of them accept it.

    :param value: Raw input for an :data:`ExternalParamValue`

    :return: The parsed dimensional quantity if ``value`` is a matching unit-suffixed string,
        otherwise ``value`` unchanged
    """
    if not isinstance(value, str):
        return value
    for adapter in _DIMENSIONAL_TYPE_ADAPTERS:
        try:
            return adapter.validate_python(value)
        except ValidationError:
            continue
    return value


type ExternalParamValue = Annotated[
    Amplitude
    | Duration
    | Frequency
    | Phase
    | Magnitude
    | _TaggedVariableRef
    | _TaggedPulseRef
    | ExternalRef
    | PulseType
    | ExternalParamScalarValue,
    BeforeValidator(_coerce_dimensional_string),
]
"""Dimensional, reference, or scalar parameter value for externally defined pulses and blocks.

Unit-suffixed strings are coerced to their typed dimensional quantity: ``"10us"`` becomes a
:class:`~.basic_types.Duration`, ``"100mV"`` an :class:`~.basic_types.Amplitude` (tried before
:class:`~.basic_types.Magnitude`, since both accept the same ``V``/``mV`` suffixes), ``"5GHz"``
a :class:`~.basic_types.Frequency`, and so on. A string that matches none of them (e.g. ``"foo"``)
is kept as plain :obj:`str`.

:class:`~.reference_types.VariableRef` and :class:`~.reference_types.PulseRef` are represented as
tagged dicts (``{"var_ref": name}`` / ``{"pulse_ref": name}``) rather than the bare string they
would otherwise serialize as, so they round-trip through JSON as their own type instead of
degrading to :obj:`str`. :class:`~.reference_types.ExternalRef` needs no such tagging: it already
serializes to its wrapped ``{"ext": name}`` form (see :attr:`~.reference_types.Reference._serializes_bare`),
which is distinguishable from a plain string on its own. Construct any of these explicitly to get a
typed reference; a bare string is always kept as :obj:`str`, since an arbitrary identifier string is
otherwise indistinguishable from one.
"""
type ExternalParamValueLike = (
    AmplitudeLike
    | DurationLike
    | FrequencyLike
    | PhaseLike
    | MagnitudeLike
    | VariableRef
    | VarRefDict
    | PulseRefLike
    | ExternalRef
    | ExtRefDict
    | PulseType
    | ExternalParamScalarValue
)
"""Acceptable input types for :data:`ExternalParamValue`."""


type PulseParamScalarValue = ExternalParamScalarValue
"""Deprecated alias of :data:`ExternalParamScalarValue`, retained for backwards compatibility.

This widens the previous ``float | int | complex | str`` definition to also accept :obj:`bool`.
"""
type PulseParamValue = ExternalParamValue
"""Deprecated alias of :data:`ExternalParamValue`, retained for backwards compatibility.

This widens the previous pulse-only union to also accept :class:`~.basic_types.Phase`,
:class:`~.basic_types.Magnitude`, :class:`~.reference_types.PulseRef`, :data:`PulseType`, and
:obj:`bool`.
"""
type PulseParamValueLike = ExternalParamValueLike
"""Deprecated alias of :data:`ExternalParamValueLike`, retained for backwards compatibility."""
