# ruff: noqa: D100, D107
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal

import numpy as np
from pydantic import (
    ConfigDict,
    Discriminator,
    Tag,
)

from .base_models import LeanModel as _LeanModel
from .basic_types import (
    COMPLEX_VOLTAGE_TAG,
    Amplitude,
    Angle,
    ComplexVoltage,
    Duration,
    Frequency,
    Time,
    Voltage,
    dimension_tag_of,
    dimension_tag_of_unit_mapping,
    dimension_unit_tag_map,
)
from .complex import complex_from_tuple
from .identifier_str import FullyQualifiedIdentifier
from .nd_array import NumpyArray, NumpyComplexArray1D, NumpyFloatArray1D
from .reference_types import ExternalRef, ExtRefDict, PulseRef, SymbolRef, VariableRef

if TYPE_CHECKING:
    from .basic_types import AngleLike, ComplexVoltageLike, FrequencyLike, TimeLike, VoltageLike
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
            duration: Duration | dict[str, float] | SymbolRefLike,
            amplitude: Amplitude | dict[str, float | complex] | SymbolRefLike,
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
            duration: Duration | dict[str, float] | SymbolRefLike,
            amplitude: Amplitude | dict[str, float | complex] | SymbolRefLike,
            rise_time: Duration | dict[str, float] | SymbolRefLike | None = None,
            fall_time: Duration | dict[str, float] | SymbolRefLike | None = None,
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
            duration: Duration | dict[str, float] | SymbolRefLike,
            amplitude: Amplitude | dict[str, float | complex] | SymbolRefLike,
            frequency: Frequency | dict[str, float] | SymbolRefLike,
            to_frequency: Frequency | dict[str, float] | SymbolRefLike | None = None,
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
            duration: Duration | dict[str, float] | SymbolRefLike,
            amplitude: Amplitude | dict[str, float | complex] | SymbolRefLike,
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
            duration: Duration | dict[str, float] | SymbolRefLike,
            amplitude: Amplitude | dict[str, float | complex] | SymbolRefLike,
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


_EXTERNAL_PARAM_UNIT_TAGS: Final = dimension_unit_tag_map()
"""Unit key -> dimension tag (``"time"``, ``"voltage"``, ``"frequency"`` or ``"angle"``), read from
the shared unit registry."""

_EXTERNAL_PARAM_REFERENCE_TAGS: Final[dict[type, str]] = {
    VariableRef: "var",
    PulseRef: "pulse_name",
    ExternalRef: "ext",
}
"""Reference type -> the sole key its wire object carries."""

_EXTERNAL_PARAM_PULSE_TAG: Final = "pulse_type"


def _external_param_value_tag(value: Any) -> str | None:
    """Return the tag *value* is spelled with, or :obj:`None` to report an unknown tag.

    :param value: Raw input for an :data:`ExternalParamValue`
    """
    if isinstance(value, Mapping):
        if _EXTERNAL_PARAM_PULSE_TAG in value:
            return _EXTERNAL_PARAM_PULSE_TAG
        if len(value) == 1:
            key: str = next(iter(value))
            if key in _EXTERNAL_PARAM_UNIT_TAGS:
                return dimension_tag_of_unit_mapping(value, _EXTERNAL_PARAM_UNIT_TAGS)
            if key in _EXTERNAL_PARAM_REFERENCE_TAGS.values():
                return key
        return None
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "str"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, complex | list | tuple | np.complexfloating):
        return "complex"
    if isinstance(value, np.ndarray) and value.shape == (2,) and issubclass(value.dtype.type, np.integer | np.floating):
        return "complex"
    if isinstance(value, PulseBase):
        return _EXTERNAL_PARAM_PULSE_TAG
    for reference, tag in _EXTERNAL_PARAM_REFERENCE_TAGS.items():
        if isinstance(value, reference):
            return tag
    return dimension_tag_of(value)


type ExternalParamValue = Annotated[
    Annotated[Time, Tag("time")]
    | Annotated[Voltage, Tag("voltage")]
    | Annotated[ComplexVoltage, Tag(COMPLEX_VOLTAGE_TAG)]
    | Annotated[Frequency, Tag("frequency")]
    | Annotated[Angle, Tag("angle")]
    | Annotated[VariableRef, Tag("var")]
    | Annotated[PulseRef, Tag("pulse_name")]
    | Annotated[ExternalRef, Tag("ext")]
    | Annotated[PulseType, Tag(_EXTERNAL_PARAM_PULSE_TAG)]
    | Annotated[bool, Tag("bool")]
    | Annotated[int, Tag("int")]
    | Annotated[float, Tag("float")]
    | Annotated[complex_from_tuple, Tag("complex")]
    | Annotated[str, Tag("str")],
    Discriminator(_external_param_value_tag),
]
"""Dimensional, reference, or scalar parameter value for externally defined pulses and blocks.

Lists one type per dimension -- :class:`~.basic_types.Time`, :class:`~.basic_types.Voltage`,
:class:`~.basic_types.ComplexVoltage`, :class:`~.basic_types.Frequency`, :class:`~.basic_types.Angle`
-- rather than per refinement, the same narrowing :data:`~.data_ops.SymbolValue` makes and for the
same reason (issue #10): :class:`~.basic_types.Duration`, :class:`~.basic_types.Amplitude`,
:class:`~.basic_types.Threshold`, :class:`~.basic_types.Magnitude` and :class:`~.basic_types.Phase`
are indistinguishable on the wire from their base dimension. The two voltage dimensions share their
unit keys and are told apart by the shape of the value, exactly as in
:data:`~.data_ops.SymbolValue`.

Every reference here is its own tagged object -- ``{"var": name}``, ``{"pulse_name": name}``,
``{"ext": name}`` -- so each round-trips through JSON as its own type with nothing in this module
to tag it.

Unlike :data:`~.data_ops.SymbolValue`, this union keeps a plain :obj:`str` member: a bare string is
now *only* ever a string, since it is opaque data passed to an external program rather than an
authored quantity. It is never coerced to a dimensional type, however unit-suffixed it looks.
"""
type ExternalParamValueLike = (
    TimeLike
    | VoltageLike
    | ComplexVoltageLike
    | FrequencyLike
    | AngleLike
    | VariableRefLike
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

This widens the previous pulse-only union to also accept :class:`~.basic_types.Angle`,
:class:`~.basic_types.Voltage`, :class:`~.reference_types.PulseRef`, :data:`PulseType`, and
:obj:`bool`.
"""
type PulseParamValueLike = ExternalParamValueLike
"""Deprecated alias of :data:`ExternalParamValueLike`, retained for backwards compatibility."""
