"""Builder-side coercion: the single place the string, dict, and zero grammars are read.

Each ``as_*`` function takes the corresponding ``*Like`` union and returns the concrete model.
This is now the only place most of those forms are read at all: since the type-system-robustness
work (issue #10) the models validate the canonical object form and nothing else, and the string
and zero spellings survive as *constructor* arguments -- which is what these functions use.

None of these functions touch the context stack except :func:`as_symbol_ref`, which keeps the
declaration checks that already lived on this logic before it moved here, and
:func:`as_channel_ref`, which applies the same check to an externally supplied channel name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..models.base_models import WrappedValueModel
from ..models.basic_types import Amplitude, Angle, Duration, Frequency, Magnitude, Phase, Threshold, Time, Voltage
from ..models.reference_types import ChannelRef, ExternalRef, PulseRef, VariableRef
from ._state import _check_external_declared, _check_variable_declared, _is_variable_declared

if TYPE_CHECKING:
    from ..models.basic_types import AmplitudeLike, DurationLike, FrequencyLike, MagnitudeLike, PhaseLike, ThresholdLike
    from ..models.data_ops import SymbolValue, SymbolValueLike
    from ..models.reference_types import ChannelRefLike, ChannelTarget, PulseRefLike, SymbolRef, SymbolRefLike

__all__ = (
    "as_amplitude",
    "as_channel_ref",
    "as_duration",
    "as_frequency",
    "as_magnitude",
    "as_phase",
    "as_pulse_ref",
    "as_quantity",
    "as_symbol_ref",
    "as_symbol_value",
    "as_threshold",
)


def as_quantity[QuantityT: WrappedValueModel](quantity: type[QuantityT], value: Any) -> QuantityT:
    """Coerce an authoring form of *quantity* to *quantity* itself.

    The authoring forms are the quantity constructor's: a ``"<number><unit>"`` string, the literal
    ``0``, a ``{unit: number}`` dict, or an already-built quantity. Only the dict is a wire form;
    reading the rest is what this module exists for.

    :param quantity: The quantity type to coerce to.
    :param value: The value in any of *quantity*'s authoring forms.
    :return: *value* unchanged if it is already a *quantity*, otherwise the *quantity* it denotes.
    :raises ValueError: If *value* is not one of the authoring forms.
    """
    return value if isinstance(value, quantity) else quantity(value)


def as_duration(value: DurationLike) -> Duration:
    """Coerce a duration-like value (string, dict, the literal ``0``, or :class:`Duration`) to a :class:`Duration`."""
    return as_quantity(Duration, value)


def as_frequency(value: FrequencyLike) -> Frequency:
    """Coerce a frequency-like value to a :class:`Frequency`."""
    return as_quantity(Frequency, value)


def as_phase(value: PhaseLike) -> Phase:
    """Coerce a phase-like value to a :class:`Phase`."""
    return as_quantity(Phase, value)


def as_amplitude(value: AmplitudeLike) -> Amplitude:
    """Coerce an amplitude-like value to an :class:`Amplitude`."""
    return as_quantity(Amplitude, value)


def as_magnitude(value: MagnitudeLike) -> Magnitude:
    """Coerce a magnitude-like value to a :class:`Magnitude`."""
    return as_quantity(Magnitude, value)


def as_threshold(value: ThresholdLike) -> Threshold:
    """Coerce a threshold-like value to a :class:`Threshold`."""
    return as_quantity(Threshold, value)


def as_symbol_value(value: SymbolValueLike) -> SymbolValue:
    """Coerce an authoring form of a declared symbol's value to its concrete :data:`SymbolValue`.

    Every authoring form but the unit-suffixed string is already a wire form :data:`SymbolValue`
    validates directly -- dicts, bools, ints, floats, complex/list/tuple pairs, and already-built
    dimensional quantities reach pydantic untouched. A string is read against each dimension in
    turn, the same way :meth:`WrappedValueModel.parse` reads it for a single quantity.

    :param value: The value in any of :data:`SymbolValueLike`'s authoring forms.
    :return: *value* unchanged, unless it is a unit-suffixed string, in which case the dimensional
        quantity it denotes.
    :raises ValueError: If *value* is a string that does not end in any known unit.
    """
    if not isinstance(value, str):
        return cast("SymbolValue", value)

    for quantity in (Time, Voltage, Frequency, Angle):
        try:
            return quantity.parse(value)
        except ValueError:
            continue

    raise ValueError(f"{value!r} is not a number followed by one of the known units")


def as_channel_ref(value: ChannelRefLike) -> ChannelTarget:
    """Coerce a channel-like value to the :obj:`ChannelTarget` it denotes.

    A bare name -- the canonical wire form of a channel -- becomes a :class:`ChannelRef`. The
    ``{"ext": ...}`` forms become an :class:`ExternalRef`, for a channel whose name the calibration
    store owns; like every other external symbol it must have been declared, and this is where that
    is checked.

    :param value: A channel name, a :class:`ChannelRef`, or either external form.
    :return: The :class:`ChannelRef` or :class:`ExternalRef` *value* denotes.
    :raises RuntimeError: If an external channel names an undeclared external symbol.
    :raises TypeError: If *value* is not one of the channel forms.
    """
    if isinstance(value, ChannelRef | str):
        return value if isinstance(value, ChannelRef) else ChannelRef(value)

    if isinstance(value, ExternalRef):
        _check_external_declared(value.ext)
        return value

    if isinstance(value, dict) and "ext" in value:
        ext_ref = ExternalRef(**value)
        _check_external_declared(ext_ref.ext)
        return ext_ref

    raise TypeError(f"{value!r} is not a channel name, a ChannelRef, or an external channel reference")


def as_pulse_ref(value: str | PulseRefLike) -> PulseRef:
    """Coerce a pulse-reference-like value (name string, dict, or :class:`PulseRef`) to a :class:`PulseRef`.

    The bare name is a builder convenience: :class:`PulseRef`'s wire form is ``{"pulse_name": ...}``
    and nothing else.
    """
    if isinstance(value, PulseRef):
        return value
    return PulseRef(value) if isinstance(value, str) else PulseRef(**value)


def as_symbol_ref(value: str | SymbolRefLike, *, param_name: str, context: str) -> SymbolRef:
    """Convert a reference-shaped value to its checked, concrete :obj:`SymbolRef`.

    Accepts an identifier-shaped string (treated as a variable name), a ``{"var": ...}`` or
    ``{"ext": ...}`` dict, or an already-built :class:`VariableRef`/:class:`ExternalRef`, and
    verifies the referenced variable or external symbol has been declared.

    This is the single place that recognition and declaration-checking logic lives; callers that
    decide *whether* a value is reference-shaped (:func:`_validate_or_pass_through` and
    :func:`_validate_explicit_variable_ref` in ``builder/_factories.py``) delegate to this function
    once they have made that decision, rather than duplicating it.

    :param value: A reference-shaped value
    :param param_name: Name of the parameter being validated (for error messages)
    :param context: Context/function name where validation occurs (for error messages)

    :return: The validated :class:`VariableRef` or :class:`ExternalRef`

    :raises RuntimeError: If the reference names an undeclared variable or external symbol
    :raises TypeError: If *value* is not actually reference-shaped
    """
    if isinstance(value, VariableRef):
        _check_variable_declared(value.var)
        return value

    if isinstance(value, ExternalRef):
        _check_external_declared(value.ext)
        return value

    if isinstance(value, dict):
        if "var" in value:
            var_ref = VariableRef(**value)
            _check_variable_declared(var_ref.var)
            return var_ref
        if "ext" in value:
            ext_ref = ExternalRef(**value)
            _check_external_declared(ext_ref.ext)
            return ext_ref
        raise TypeError(f"{value!r} is not a symbol reference dict (missing a 'var'/'ext' key)")

    if isinstance(value, str) and value.isidentifier():
        if not _is_variable_declared(value):
            raise RuntimeError(
                f"Parameter '{param_name}' in {context} references undeclared variable '{value}'. "
                f"Use var_decl('{value}', dtype, ...) before referencing this variable."
            )
        return VariableRef(value)

    raise TypeError(f"{value!r} is not a symbol reference")
