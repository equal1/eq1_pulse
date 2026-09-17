"""Context-free builder helpers.

Pulse factories, the ``phase``/``var``/``channel``/``pulse_ref`` constructors, and the
variable-reference validation helpers. None of these touch the context stack beyond
checking that a referenced variable has been declared, so they are shared unchanged
between the sequence builder (:mod:`eq1_pulse.builder.core`) and the schedule builder
(:mod:`eq1_pulse.builder.experimental.schedule`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Literal, overload

from eq1_pulse.models import Phase

from ..models.basic_types import LinSpace, Range
from ..models.channel_ops import DemodIntegration, FullIntegration
from ..models.control_flow import Indices
from ..models.expressions import (
    BinaryExpr,
    CallExpr,
    CompareExpr,
    ExprBase,
    IndexExpr,
    LenExpr,
    LogicalExpr,
    NotExpr,
    SymbolExpr,
    UnaryExpr,
)
from ..models.pulse_types import (
    ArbitrarySampledPulse,
    DigitalTriggerPulse,
    ExternalPulse,
    SinePulse,
    SquarePulse,
    StepPulse,
)
from ..models.reference_types import ChannelRef, ExternalRef, PulseRef, VariableRef
from ._coerce import as_amplitude, as_duration, as_frequency, as_phase, as_symbol_ref
from ._expressions import Expr
from ._state import _check_external_declared, _check_pulse_declared, _check_variable_declared
from ._sweeps import _check_sweep_reads

if TYPE_CHECKING:
    from ..models.basic_types import AmplitudeLike, DurationLike, FrequencyLike, PhaseLike
    from ..models.expressions import Expression, ValueRef
    from ..models.reference_types import SymbolRef, SymbolRefLike, VariableRefLike
    from ._expressions import ExprLike

# ============================================================================
# Basic model builders
# ============================================================================


@overload
def phase(_0: Literal[0], /) -> Phase: ...


@overload
def phase(_s: str, /) -> Phase: ...


@overload
def phase(*, deg: float) -> Phase: ...


@overload
def phase(*, rad: float) -> Phase: ...


@overload
def phase(*, turns: float) -> Phase: ...


@overload
def phase(*, half_turns: float) -> Phase: ...


def phase(*args, **kwargs) -> Phase:
    """Construct a phase object.

    :param deg: Phase in degrees
    :param rad: Phase in radians
    :param turns: Phase in turns
    :param half_turns: Phase in half-turns
    :param _0: The literal zero
    :param _s: The string representation (value + unit) only as positional
    :return: The constructed phase object
        Use the result to matrix-multiply (`@`)
    """
    match len(args):
        case 0:
            if not len(kwargs):
                raise TypeError("not enough arguments")
            return Phase(**kwargs)
        case 1:
            if len(kwargs):
                raise TypeError("keyword arguments cannot follow positional argument")
            return Phase(*args)
        case _:
            raise TypeError("at most one positional argument is allowed")


def _validate_variable_ref(var_ref: str | VariableRefLike) -> VariableRef:
    """Validate a variable reference and convert to VariableRef object.

    :param var_ref: Variable reference (string, dict, or VariableRef)

    :return: Validated VariableRef object

    :raises RuntimeError: If variable has not been declared
    """
    # Convert to VariableRef if needed
    if isinstance(var_ref, str):
        var_ref = VariableRef(var_ref)
    elif isinstance(var_ref, dict):
        var_ref = VariableRef(**var_ref)
    elif isinstance(var_ref, VariableRef):
        pass
    else:
        raise TypeError(f"Unexpected value passed into variable reference: {var_ref!r}")

    # Check if variable is declared
    _check_variable_declared(var_ref.var)

    # Return validated VariableRef
    return var_ref


def _check_expression_leaves(node: Expression) -> None:
    """Walk an expression tree and check that every leaf it reads is declared.

    The only new traversal this plan adds: every other validation helper here checks a single
    reference, but an :class:`~.expressions.Expression` can bury references arbitrarily deep, so it
    needs its own walk rather than reusing :func:`_check_variable_declared` /
    :func:`_check_external_declared` directly.

    :class:`~.expressions.SweepExpr` leaves are checked too, by
    :func:`~eq1_pulse.builder._sweeps._check_sweep_reads`, which also enforces that the sweeps any
    one expression reads advance together.

    :param node: The expression tree to walk.

    :raises RuntimeError: If a leaf names an undeclared variable, external symbol or sweep, or if
        one expression reads sweeps that are not in lock-step.
    """
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, SymbolExpr):
            symbol = current.symbol
            if isinstance(symbol, VariableRef):
                _check_variable_declared(symbol.var)
            else:
                _check_external_declared(symbol.ext)
        elif isinstance(current, UnaryExpr | NotExpr):
            stack.append(current.rhs)
        elif isinstance(current, BinaryExpr | CompareExpr | LogicalExpr):
            stack.append(current.lhs)
            stack.append(current.rhs)
        elif isinstance(current, CallExpr):
            stack.extend(current.args)
        elif isinstance(current, IndexExpr):
            # Rank-0 nodes still hold symbols: `sweep("vg")[var("i")]` reads `i`.
            stack.append(current.operand)
            stack.extend(current.indices)
        elif isinstance(current, LenExpr):
            stack.append(current.operand)

    _check_sweep_reads(node)


def _validate_or_pass_through[T](
    value: T | SymbolRef | ExprLike,
    *,
    param_name: str,
    context: str,
) -> T | ValueRef:
    """Validate a parameter that can be a variable/external reference or literal value.

    - If value is :obj:`None`: pass through
    - If value is :class:`VariableRef`: validate it's declared, pass through
    - If value is :class:`ExternalRef`: validate it's declared, pass through
    - If value is dict with ``"var"`` key: convert to :class:`VariableRef` and validate
    - If value is dict with ``"ext"`` key: convert to :class:`ExternalRef` and validate
    - If value is dict without ``"var"``/``"ext"`` key: pass through unchanged
    - If value is string AND identifier: treat as variable, validate, return :class:`VariableRef`
    - If value is string AND not identifier: pass through (e.g., ``"10us"``)
    - If value is :class:`~eq1_pulse.builder._expressions.Expr`: unwrap, check its leaves are
      declared, return the :data:`~.expressions.Expression`
    - If value is a bare :data:`~.expressions.Expression` model: check its leaves are declared,
      pass through unchanged -- a user deserializing a fragment should not have to re-wrap it
    - Otherwise: pass through unchanged (for model validation)

    This handles parameters like ``duration="10us"`` vs ``duration="my_var"`` vs ``duration=var("my_var")``.

    An identifier-like string is always treated as a variable, never an external symbol -- an
    external symbol must be spelled out explicitly with :func:`ext` or a ``{"ext": ...}`` dict.

    The reference-shaped branches delegate their conversion and declaration-check to
    :func:`~eq1_pulse.builder._coerce.as_symbol_ref`; this function's own job is only to decide
    whether *value* is reference-shaped in the first place.

    :param value: Parameter value
    :param param_name: Name of the parameter being validated (for error messages)
    :param context: Context/function name where validation occurs (for error messages)

    :return: :class:`VariableRef`/:class:`ExternalRef`/:data:`~.expressions.Expression` if a
        reference or expression, else unchanged value

    :raises RuntimeError: If a reference names an undeclared variable or external symbol, or an
        expression contains one
    """
    if value is None:
        return None  # type: ignore[return-value]

    if isinstance(value, Expr):
        node = value.unwrap()
        _check_expression_leaves(node)
        return node

    if isinstance(value, ExprBase):
        _check_expression_leaves(value)  # type: ignore[arg-type]
        return value

    if isinstance(value, VariableRef | ExternalRef):
        return as_symbol_ref(value, param_name=param_name, context=context)  # type: ignore[arg-type]

    if isinstance(value, dict):
        if "var" in value or "ext" in value:
            return as_symbol_ref(value, param_name=param_name, context=context)  # type: ignore[arg-type]
        # Dict without "var"/"ext" key - pass through (e.g., {"ns": 100})
        return value  # type: ignore[return-value]

    if isinstance(value, str) and value.isidentifier():
        return as_symbol_ref(value, param_name=param_name, context=context)  # type: ignore[arg-type]

    return value


def _coerce_or_ref[T](
    value: T | str | SymbolRefLike | ExprLike | None,
    *,
    coerce: Callable[[Any], T],
    param_name: str,
    context: str,
) -> T | ValueRef | None:
    """Resolve a parameter to a concrete model, a checked symbol reference, or an expression.

    Delegates reference/expression-recognition to :func:`_validate_or_pass_through`; whatever it
    leaves untouched (a literal, not a reference or expression) is handed to *coerce* -- one of the
    ``as_*`` functions in :mod:`eq1_pulse.builder._coerce` -- to read its string/dict/zero grammar
    into the canonical model. An :data:`~.expressions.Expression` must be recognized here too, or it
    falls through to *coerce* and is silently mishandled rather than failing to type-check.

    :param value: Parameter value
    :param coerce: Function turning a non-reference, non-expression value into the canonical model
    :param param_name: Name of the parameter being validated (for error messages)
    :param context: Context/function name where validation occurs (for error messages)

    :return: The canonical model, a :class:`VariableRef`/:class:`ExternalRef`, an
        :data:`~.expressions.Expression`, or :obj:`None`

    :raises RuntimeError: If a reference names an undeclared variable or external symbol, or an
        expression contains one
    """
    resolved = _validate_or_pass_through(value, param_name=param_name, context=context)
    if resolved is None or isinstance(resolved, VariableRef | ExternalRef | ExprBase):
        return resolved
    return coerce(resolved)


def _validate_explicit_variable_ref[T](value: T | ExprLike, *, param_name: str) -> T | ValueRef:
    """Validate only *explicit* references and expressions, passing everything else through.

    Unlike :func:`_validate_or_pass_through`, an identifier-like string is **not**
    treated as a variable reference. Use this for free-form values where a bare
    string is more likely to be a literal than a variable name; callers wanting a
    variable there must say so with :func:`var` or a ``{"var": ...}`` dict, and callers
    wanting an external symbol must say so with :func:`ext` or a ``{"ext": ...}`` dict. A
    bare string is never promoted to an :class:`ExternalRef`.

    :param value: Parameter value
    :param param_name: Name of the parameter being validated (for error messages)

    :return: :class:`VariableRef`/:class:`ExternalRef`/:data:`~.expressions.Expression` if
        explicitly one, else the value unchanged

    :raises RuntimeError: If an explicit reference names an undeclared variable or external symbol,
        or an expression contains one
    """
    if isinstance(value, Expr):
        node = value.unwrap()
        _check_expression_leaves(node)
        return node

    if isinstance(value, ExprBase):
        _check_expression_leaves(value)  # type: ignore[arg-type]
        return value

    if isinstance(value, VariableRef | ExternalRef):
        return as_symbol_ref(value, param_name=param_name, context="")  # type: ignore[arg-type]

    if isinstance(value, dict) and ("var" in value or "ext" in value):
        return as_symbol_ref(value, param_name=param_name, context="")  # type: ignore[arg-type]

    return value


# ============================================================================
# Pulse creation helpers
# ============================================================================


def square_pulse(
    *,
    duration: DurationLike | SymbolRefLike | ExprLike,
    amplitude: AmplitudeLike | SymbolRefLike | ExprLike,
    rise_time: DurationLike | SymbolRefLike | ExprLike | None = None,
    fall_time: DurationLike | SymbolRefLike | ExprLike | None = None,
) -> SquarePulse:
    """Create a square pulse.

    :param duration: Pulse duration
    :param amplitude: Pulse amplitude
    :param rise_time: Optional rise time
    :param fall_time: Optional fall time

    :return: Square pulse definition

    Examples

    .. code-block:: python

        from eq1_pulse.builder import square_pulse

        pulse = square_pulse(duration="10us", amplitude="100mV")
    """
    duration = _coerce_or_ref(duration, coerce=as_duration, param_name="duration", context="square_pulse()")  # type: ignore[assignment]
    amplitude = _coerce_or_ref(amplitude, coerce=as_amplitude, param_name="amplitude", context="square_pulse()")  # type: ignore[assignment]
    rise_time = _coerce_or_ref(rise_time, coerce=as_duration, param_name="rise_time", context="square_pulse()")
    fall_time = _coerce_or_ref(fall_time, coerce=as_duration, param_name="fall_time", context="square_pulse()")

    return SquarePulse(
        duration=duration,  # type: ignore[arg-type]
        amplitude=amplitude,  # type: ignore[arg-type]
        rise_time=rise_time,  # type: ignore[arg-type]
        fall_time=fall_time,  # type: ignore[arg-type]
    )


def step_pulse(
    *,
    duration: DurationLike | SymbolRefLike | ExprLike,
    amplitude: AmplitudeLike | SymbolRefLike | ExprLike,
) -> StepPulse:
    """Create a step pulse.

    The amplitude is reached instantaneously at the start and **persists** past the end of the
    pulse, becoming the channel's new base level. ``duration`` is how long the step occupies the
    channel, not how long the level lasts -- see :class:`~eq1_pulse.models.StepPulse` for the full
    semantics.

    :param duration: Time the step occupies the channel
    :param amplitude: Amplitude the channel steps to, and remains at

    :return: Step pulse definition

    Examples

    .. code-block:: python

        from eq1_pulse.builder import step_pulse

        pulse = step_pulse(duration="1us", amplitude="150mV")
    """
    duration = _coerce_or_ref(duration, coerce=as_duration, param_name="duration", context="step_pulse()")  # type: ignore[assignment]
    amplitude = _coerce_or_ref(amplitude, coerce=as_amplitude, param_name="amplitude", context="step_pulse()")  # type: ignore[assignment]

    return StepPulse(
        duration=duration,  # type: ignore[arg-type]
        amplitude=amplitude,  # type: ignore[arg-type]
    )


def trigger_pulse(
    *,
    duration: DurationLike | SymbolRefLike | ExprLike,
) -> DigitalTriggerPulse:
    """Create a digital trigger pulse.

    Sets a digital trigger line high for ``duration``, then returns it low. Played with
    :func:`~eq1_pulse.builder.play` on a digital output channel; carries no amplitude.

    :param duration: Time the trigger line is held high

    :return: Digital trigger pulse definition

    Examples

    .. code-block:: python

        from eq1_pulse.builder import trigger_pulse

        pulse = trigger_pulse(duration="100ns")
    """
    duration = _coerce_or_ref(duration, coerce=as_duration, param_name="duration", context="trigger_pulse()")  # type: ignore[assignment]

    return DigitalTriggerPulse(duration=duration)  # type: ignore[arg-type]


def sine_pulse(
    *,
    duration: DurationLike | SymbolRefLike | ExprLike,
    amplitude: AmplitudeLike | SymbolRefLike | ExprLike,
    frequency: FrequencyLike | SymbolRefLike | ExprLike,
    to_frequency: FrequencyLike | SymbolRefLike | ExprLike | None = None,
) -> SinePulse:
    """Create a sine pulse.

    :param duration: Pulse duration
    :param amplitude: Pulse amplitude
    :param frequency: Start frequency
    :param to_frequency: Optional end frequency for chirp

    :return: Sine pulse definition

    Examples

    .. code-block:: python

        from eq1_pulse.builder import sine_pulse

        pulse = sine_pulse(duration="20us", amplitude="50mV", frequency="5GHz")

        # Chirped sine pulse
        chirp = sine_pulse(
            duration="50us",
            amplitude="30mV",
            frequency="4.5GHz",
            to_frequency="5.5GHz"
        )
    """
    duration = _coerce_or_ref(duration, coerce=as_duration, param_name="duration", context="sine_pulse()")  # type: ignore[assignment]
    amplitude = _coerce_or_ref(amplitude, coerce=as_amplitude, param_name="amplitude", context="sine_pulse()")  # type: ignore[assignment]
    frequency = _coerce_or_ref(frequency, coerce=as_frequency, param_name="frequency", context="sine_pulse()")  # type: ignore[assignment]
    to_frequency = _coerce_or_ref(to_frequency, coerce=as_frequency, param_name="to_frequency", context="sine_pulse()")

    return SinePulse(
        duration=duration,  # type: ignore[arg-type]
        amplitude=amplitude,  # type: ignore[arg-type]
        frequency=frequency,  # type: ignore[arg-type]
        to_frequency=to_frequency,  # type: ignore[arg-type]
    )


def external_pulse(
    function: str,
    *,
    duration: DurationLike | SymbolRefLike | ExprLike,
    amplitude: AmplitudeLike | SymbolRefLike | ExprLike,
    params: dict[str, Any] | None = None,
) -> ExternalPulse:
    """Create an external pulse reference.

    References a pulse shape defined in an external function. The function
    should accept duration, amplitude, and any additional params, and return
    normalized waveform samples.

    :param function: Fully qualified function name (e.g., "my_lib.gaussian")
    :param duration: Pulse duration
    :param amplitude: Pulse amplitude (scale factor)
    :param params: Additional parameters passed to the pulse function

    :return: External pulse definition

    Examples

    .. code-block:: python

        from eq1_pulse.builder import external_pulse

        # Reference a Gaussian pulse from an external library
        pulse = external_pulse(
            "pulses.gaussian",
            duration="100ns",
            amplitude="80mV",
            params={"sigma": "20ns"}
        )

        # DRAG pulse with parameters
        drag = external_pulse(
            "pulses.drag",
            duration="50ns",
            amplitude="100mV",
            params={"beta": 0.5, "sigma": "10ns"}
        )
    """
    duration = _coerce_or_ref(duration, coerce=as_duration, param_name="duration", context="external_pulse()")  # type: ignore[assignment]
    amplitude = _coerce_or_ref(amplitude, coerce=as_amplitude, param_name="amplitude", context="external_pulse()")  # type: ignore[assignment]

    # Validate top-level params dict values (if params provided).
    #
    # Unlike the typed scalar parameters above, params carries arbitrary values for
    # the external function, so a bare identifier-like string is far more likely to
    # be a literal ("hann", "cubic", "gaussian") than a variable name. Only explicit
    # variable references are validated here; everything else passes through.
    if params is not None:
        params = {
            key: _validate_explicit_variable_ref(value, param_name=f"params['{key}']") for key, value in params.items()
        }

    return ExternalPulse(
        function=function,
        duration=duration,  # type: ignore[arg-type]
        amplitude=amplitude,  # type: ignore[arg-type]
        params=params,  # type: ignore[arg-type]
    )


def arbitrary_pulse(
    samples: list[float] | list[complex],
    *,
    duration: DurationLike | SymbolRefLike | ExprLike,
    amplitude: AmplitudeLike | SymbolRefLike | ExprLike,
    interpolation: str | None = None,
    time_points: list[float] | None = None,
) -> ArbitrarySampledPulse:
    """Create an arbitrary sampled pulse from explicit samples.

    Defines a pulse shape using explicitly provided sample points. Samples
    should be normalized (peak value of 1.0), and will be scaled by amplitude.

    :param samples: Normalized waveform samples (real or complex)
    :param duration: Total pulse duration
    :param amplitude: Pulse amplitude (scale factor for samples)
    :param interpolation: Interpolation method (e.g., "linear", "cubic")
    :param time_points: Optional time points for samples (normalized 0-1)

    :return: Arbitrary pulse definition

    Examples

    .. code-block:: python

        from eq1_pulse.builder import arbitrary_pulse

        # Simple triangle pulse
        triangle = arbitrary_pulse(
            samples=[0.0, 0.5, 1.0, 0.5, 0.0],
            duration="100ns",
            amplitude="50mV"
        )

        # Complex IQ pulse with explicit time points
        iq_samples = [0.0+0.0j, 0.5+0.3j, 1.0+0.0j, 0.5-0.3j, 0.0+0.0j]
        iq_pulse = arbitrary_pulse(
            samples=iq_samples,
            duration="80ns",
            amplitude="75mV",
            time_points=[0.0, 0.25, 0.5, 0.75, 1.0],
            interpolation="cubic"
        )
    """
    duration = _coerce_or_ref(duration, coerce=as_duration, param_name="duration", context="arbitrary_pulse()")  # type: ignore[assignment]
    amplitude = _coerce_or_ref(amplitude, coerce=as_amplitude, param_name="amplitude", context="arbitrary_pulse()")  # type: ignore[assignment]

    return ArbitrarySampledPulse(
        samples=samples,
        duration=duration,  # type: ignore[arg-type]
        amplitude=amplitude,  # type: ignore[arg-type]
        interpolation=interpolation,
        time_points=time_points,
    )


# ============================================================================
# Integration helpers
# ============================================================================


def full_integration() -> FullIntegration:
    """Create a full integration configuration.

    Full integration performs a simple accumulation of the measured signal
    over the acquisition window.

    :return: Full integration configuration object

    Examples

    .. code-block:: python

        from eq1_pulse.builder import full_integration, record

        # Use full integration for recording
        record("readout", var="result", duration="1us", integration=full_integration())
    """
    return FullIntegration()


def demod_integration(
    *,
    phase: PhaseLike | SymbolRefLike | ExprLike | None = None,
    scale_cos: float | str | SymbolRefLike | ExprLike = 1.0,
    scale_sin: float | str | SymbolRefLike | ExprLike = 1.0,
) -> DemodIntegration:
    """Create a demodulation integration configuration.

    Demodulation integration multiplies the measured signal with the channel's
    output signal (at the channel's frequency and phase) before integration.
    This is useful for extracting the in-phase and quadrature components.

    :param phase: Optional phase rotation to apply to the result, or a variable/external reference
    :param scale_cos: Scaling factor for the real (cosine) part, or a variable/external reference (default: 1.0)
    :param scale_sin: Scaling factor for the imaginary (sine) part, or a variable/external reference (default: 1.0)

    :return: Demodulation integration configuration object

    Examples

    .. code-block:: python

        from eq1_pulse.builder import demod_integration, record

        # Basic demodulation
        record("readout", var="result", duration="1us",
               integration=demod_integration())

        # With phase rotation
        record("readout", var="result", duration="1us",
               integration=demod_integration(phase="45deg"))

        # With scaling (e.g., to flip sign of imaginary part)
        record("readout", var="result", duration="1us",
               integration=demod_integration(scale_cos=1.0, scale_sin=-1.0))
    """
    validated_phase = _coerce_or_ref(phase, coerce=as_phase, param_name="phase", context="demod_integration()")
    validated_scale_cos = _validate_or_pass_through(scale_cos, param_name="scale_cos", context="demod_integration()")
    validated_scale_sin = _validate_or_pass_through(scale_sin, param_name="scale_sin", context="demod_integration()")

    return DemodIntegration(
        phase=validated_phase,  # type: ignore[arg-type]
        scale_cos=validated_scale_cos,  # type: ignore[arg-type]
        scale_sin=validated_scale_sin,  # type: ignore[arg-type]
    )


# ============================================================================
# Reference helpers
# ============================================================================


def var(name: str) -> VariableRef:
    """Create a variable reference.

    :param name: Variable name

    :return: Variable reference

    :raises RuntimeError: If variable has not been declared in current or parent contexts

    Examples

    .. code-block:: python

        from eq1_pulse.builder import var

        freq_var = var("frequency")
    """
    _check_variable_declared(name)
    return VariableRef(var=name)


def ext(name: str) -> ExternalRef:
    """Create an external symbol reference.

    :param name: External symbol name, e.g. ``"q0.f01"``

    :return: External symbol reference

    :raises RuntimeError: If the external symbol has not been declared in current or parent contexts

    Examples

    .. code-block:: python

        from eq1_pulse.builder import ext

        f01 = ext("q0.f01")
    """
    _check_external_declared(name)
    return ExternalRef(ext=name)


def channel(name: str) -> ChannelRef:
    """Create a channel reference.

    :param name: Channel name

    :return: Channel reference

    Examples

    .. code-block:: python

        from eq1_pulse.builder import channel

        ch = channel("qubit_1")
    """
    return ChannelRef(name)


def pulse_ref(name: str) -> PulseRef:
    """Create a pulse reference.

    :param name: Pulse name

    :return: Pulse reference

    Examples

    .. code-block:: python

        from eq1_pulse.builder import pulse_ref

        p = pulse_ref("pi_pulse")
    """
    _check_pulse_declared(name)

    return PulseRef(pulse_name=name)


type IterableLike = Iterable[Any] | Range | LinSpace | Indices | ExprLike
"""What a ``for_()`` accepts as one of the things it iterates.

The builder-side mirror of :data:`~.control_flow.IterableSequence`: the concrete sequences the
model has always taken, plus the two this plan added -- a sweep or any transform of one (an
:class:`~eq1_pulse.builder._expressions.Expr` or a bare expression node), and :func:`indices`.
"""


def indices(count: int | str | SymbolRefLike | ExprLike) -> Indices:
    """Build the positions ``0 .. count-1``, for a ``for_`` that binds an index rather than an item.

    ``for_``'s other iterable form. Pairing it with :func:`~eq1_pulse.builder._expressions.len_`
    -- ``indices(len_(sweep("vg")))`` -- iterates the positions of a sweep whose length is not
    known until the program is invoked, and the body reaches each item with ``sweep("vg")[var("i")]``.

    Binding the item is what is wanted almost always; the position is needed when an item and its
    own index appear in one expression, or to reach a fixed item of the scan.

    :param count: How many positions to iterate: a literal, a declared variable or external symbol,
        or an expression such as ``len_(sweep("vg"))``

    :return: The :class:`~eq1_pulse.models.control_flow.Indices` to hand to ``for_``

    :raises RuntimeError: If *count* references an undeclared variable, external symbol or sweep

    Examples

    .. code-block:: python

        from eq1_pulse.builder import *

        with build_sequence():
            sweep_decl("vg", "float", unit="mV")
            var_decl("i", "int")
            with for_("i", indices(len_(sweep("vg")))):
                play("gate", step_pulse(duration="40ns", amplitude=sweep("vg")[var("i")]))
    """
    return Indices(count=_validate_or_pass_through(count, param_name="count", context="indices()"))  # type: ignore[arg-type]


def _validate_iteration_item(item: Any) -> Any:
    """Resolve one ``for_()`` item to something :data:`~.control_flow.IterableSequence` accepts.

    An :class:`~eq1_pulse.builder._expressions.Expr` is unwrapped -- the model takes the expression
    node, not the builder's wrapper -- and any expression, wrapped or bare, has its leaves checked
    the way every other widened value site does. Everything else is handed to
    :func:`_convert_range_to_model`, which converts a Python :class:`range` and passes the rest
    through untouched.

    :param item: One iterable as the caller wrote it

    :return: The item in the form the iteration model accepts

    :raises RuntimeError: If the item is an expression referencing an undeclared symbol or sweep,
        or reading sweeps that are not in lock-step
    """
    if isinstance(item, Expr):
        node = item.unwrap()
        _check_expression_leaves(node)
        return node

    if isinstance(item, ExprBase):
        _check_expression_leaves(item)  # type: ignore[arg-type]
        return item

    return _convert_range_to_model(item)


def _convert_range_to_model(iterable: Any) -> Range | list[Any] | Any:
    """Convert Python range objects to Range model or list.

    This function handles the semantic differences between Python's built-in range
    and the eq1_pulse Range model:

    - Python range excludes the stop point, Range includes it
    - Python range can be empty if step has wrong direction, Range adjusts step sign
    - Range requires step to divide the distance evenly

    :param iterable: An iterable, potentially a Python range object

    :return: Range model, list, or the original iterable unchanged

    Conversion rules:

    - Empty range → :class:`ValueError` (a loop that can never run is a typo, not intent)
    - Single-element range → single-element list
    - Multi-element range → Range model (if valid) or list

    :raises ValueError: If the range yields no elements

    Examples

    .. code-block:: python

        _convert_range_to_model(range(0, 10, 2))  # Range(start=0, stop=8, step=2)
        _convert_range_to_model(range(10, 0, 2))  # ValueError (wrong step direction)
        _convert_range_to_model(range(5, 6))      # [5] (single element)
    """
    # Only process Python range objects
    if not isinstance(iterable, range):
        return iterable

    # Convert to list to get actual elements
    range_list = list(iterable)

    # An empty range (wrong step direction, or step larger than the span) would build
    # a loop body that can never execute. Say so rather than emitting it silently.
    if len(range_list) == 0:
        raise ValueError(
            f"{iterable!r} is empty, so the loop body would never execute. "
            "Check the sign of the step and the order of start/stop."
        )

    # Handle single-element range
    if len(range_list) == 1:
        return range_list

    # Multi-element range: convert to Range model
    # Range includes the stop point, so we use the last element as stop
    start = range_list[0]
    stop = range_list[-1]
    step = iterable.step

    # Create Range with adjusted stop point to include the last element
    try:
        return Range(start=start, stop=stop, step=step)
    except ValueError:
        # If Range validation fails (step doesn't divide evenly), fall back to list
        return range_list
