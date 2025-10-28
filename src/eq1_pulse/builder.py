"""Builder interface for constructing pulse sequences and schedules.

This module provides a fluent builder API for creating pulse sequences and schedules
using context managers and function calls. The builder interface simplifies the
creation of complex pulse programs through:

- Global context for building models
- Context managers for sequences, schedules, iterations, and conditionals
- Function calls for operations like playing pulses, recording, and barriers
- Token-based references for relative positioning in schedules
- Shorthand functions for common pulse types
- Measure function for simultaneous play + record operations

Examples

.. code-block:: python

    from eq1_pulse.builder import build

    # Building a sequence
    with build.sequence() as seq:
        build.play("ch1", build.square(duration="10us", amplitude="100mV"))
        build.wait("ch1", "5us")
        build.play("ch1", build.sine(duration="20us", amplitude="50mV", frequency="5GHz"))

    # Building a schedule with relative positioning
    with build.schedule() as sched:
        op1 = build.play("ch1", build.square(duration="10us", amplitude="100mV"))
        op2 = build.play("ch2", build.square(duration="10us", amplitude="100mV"),
                        ref_op=op1, ref_pt="start", rel_time="5us")

    # Using control flow
    with build.sequence() as seq:
        with build.repeat(10):
            build.play("qubit", build.square(duration="50ns", amplitude="100mV"))
            build.measure("qubit", "readout", duration="1us")

        with build.for_loop("i", range(0, 100, 10)):
            build.set_frequency("qubit", build.var("i"))
            build.play("qubit", build.square(duration="100ns", amplitude="50mV"))
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal, TypedDict, Unpack

from .models.basic_types import LinSpace, Range
from .models.channel_ops import (
    Barrier,
    DemodIntegration,
    FullIntegration,
    IntegrationType,
    Play,
    Record,
    SetFrequency,
    SetPhase,
    ShiftFrequency,
    ShiftPhase,
    Wait,
)
from .models.data_ops import Discriminate, Store, VariableDecl
from .models.pulse_types import ArbitrarySampledPulse, ExternalPulse, PulseType, SinePulse, SquarePulse
from .models.reference_types import ChannelRef, PulseRef, VariableRef
from .models.schedule import (
    SchedConditional,
    SchedIteration,
    SchedRepetition,
    Schedule,
    ScheduledOperation,
)
from .models.sequence import Conditional, Iteration, OpSequence, Repetition

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from .models.basic_types import AmplitudeLike, DurationLike, FrequencyLike, PhaseLike, ThresholdLike
    from .models.data_ops import ComparisonModeLike, ComplexToRealProjectionModeLike
    from .models.reference_types import ChannelRefLike, PulseRefLike, VariableRefLike
    from .models.schedule import RefPtLike, RelTimeLike

__all__ = ("Builder", "ScheduleParams", "build", "resolve_schedule_params")


class ScheduleParams(TypedDict, total=False):
    """Type definition for schedule parameters used in builder operations.

    :param name: Optional name for the operation
    :param rel_time: Relative time from the reference point
    :param ref_op: Name of or token for the reference operation
    :param ref_pt: Reference point on the reference operation
    :param ref_pt_new: Reference point on the new operation
    """

    name: str | None
    rel_time: RelTimeLike | None
    ref_op: str | OperationToken | None
    ref_pt: RefPtLike | None
    ref_pt_new: RefPtLike | None


def resolve_schedule_params(params: ScheduleParams) -> dict[str, Any]:
    """Resolve operation tokens in schedule parameters to operation names.

    This utility function processes schedule parameters and converts any
    :class:`OperationToken` references in the ``ref_op`` field to their
    corresponding operation names (strings).

    :param params: Schedule parameters potentially containing operation tokens

    :return: Resolved parameters with tokens replaced by operation names

    Examples

    .. code-block:: python

        # With token
        token = build.play("ch1", pulse)
        params = {"ref_op": token, "ref_pt": "end"}
        resolved = resolve_schedule_params(params)
        # resolved["ref_op"] is now the string name

        # Without token (already a string)
        params = {"ref_op": "op_1", "ref_pt": "end"}
        resolved = resolve_schedule_params(params)
        # resolved["ref_op"] remains "op_1"
    """
    resolved: dict[str, Any] = dict(params)

    # Resolve operation token to name
    if "ref_op" in resolved and isinstance(resolved["ref_op"], OperationToken):
        resolved["ref_op"] = resolved["ref_op"].name

    # Remove rel_time if it's 0 (will use default None)
    if "rel_time" in resolved and resolved["rel_time"] == 0:
        del resolved["rel_time"]

    return resolved


class OperationToken:
    """Token representing a scheduled operation for reference in relative positioning.

    :param name: The name assigned to the operation
    :param operation: The scheduled operation this token refers to
    """

    def __init__(self, name: str, operation: ScheduledOperation):
        """Initialize an operation token."""
        self.name = name
        self.operation = operation

    def __str__(self) -> str:
        """Return the operation name."""
        return self.name


class Builder:
    """Builder class for constructing pulse sequences and schedules.

    This class provides a fluent API for building pulse programs. Use the global
    :obj:`build` instance for convenience.

    :ivar _context_stack: Stack of active building contexts
    :ivar _op_counter: Counter for generating unique operation names
    """

    def __init__(self):
        """Initialize the builder."""
        self._context_stack: list[
            OpSequence
            | Schedule
            | Repetition
            | Iteration
            | Conditional
            | SchedRepetition
            | SchedIteration
            | SchedConditional
        ] = []
        self._op_counter = 0

    def _generate_op_name(self) -> str:
        """Generate a unique operation name.

        :return: Unique operation name
        """
        self._op_counter += 1
        return f"op_{self._op_counter}"

    def _current_context(self) -> Any:
        """Get the current building context.

        :return: The current sequence or schedule being built

        :raises RuntimeError: If no context is active
        """
        if not self._context_stack:
            raise RuntimeError("No active building context. Use sequence() or schedule() context manager first.")
        return self._context_stack[-1]

    def _add_to_sequence(self, operation: Any) -> None:
        """Add an operation to the current sequence context.

        :param operation: The operation to add

        :raises RuntimeError: If current context is not a sequence
        """
        context = self._current_context()
        if isinstance(context, Repetition | Iteration | Conditional):
            context.body.items.append(operation)
        elif isinstance(context, OpSequence):
            context.items.append(operation)
        else:
            raise RuntimeError(f"Cannot add sequence operation to {type(context).__name__} context")

    def _add_to_schedule(self, operation: Any, **schedule_params: Unpack[ScheduleParams]) -> OperationToken:
        """Add an operation to the current schedule context.

        :param operation: The operation to add
        :param schedule_params: Additional scheduling parameters

        :return: Token for referencing this operation

        :raises RuntimeError: If current context is not a schedule
        """
        context = self._current_context()
        if not isinstance(context, Schedule):
            raise RuntimeError(f"Cannot add scheduled operation to {type(context).__name__} context")

        # Resolve any operation tokens to names
        resolved_params = resolve_schedule_params(schedule_params)  # type: ignore[arg-type]

        # Generate operation name if not provided
        if "name" not in resolved_params:
            resolved_params["name"] = self._generate_op_name()

        sched_op = ScheduledOperation(op=operation, **resolved_params)  # type: ignore[arg-type]
        context.items.append(sched_op)
        return OperationToken(resolved_params["name"], sched_op)

    @contextmanager
    def sequence(self) -> Iterator[OpSequence]:
        """Context manager for building an operation sequence.

        :yield: The operation sequence being built

        Examples

        .. code-block:: python

            with build.sequence() as seq:
                build.play("ch1", build.square(duration="10us", amplitude="100mV"))
                build.wait("ch1", "5us")
        """
        seq = OpSequence(items=[])
        self._context_stack.append(seq)
        try:
            yield seq
        finally:
            self._context_stack.pop()

    @contextmanager
    def schedule(self) -> Iterator[Schedule]:
        """Context manager for building a schedule.

        :yield: The schedule being built

        Examples

        .. code-block:: python

            with build.schedule() as sched:
                op1 = build.play("ch1", build.square(duration="10us", amplitude="100mV"))
                op2 = build.play("ch2", build.square(duration="10us", amplitude="100mV"),
                                ref_op=op1, ref_pt="start", rel_time="5us")
        """
        sched = Schedule(items=[])
        self._context_stack.append(sched)
        try:
            yield sched
        finally:
            self._context_stack.pop()

    @contextmanager
    def repeat(self, count: int) -> Iterator[Repetition]:
        """Context manager for building a repetition block.

        :param count: Number of times to repeat

        :yield: The repetition being built

        Examples

        .. code-block:: python

            with build.sequence():
                with build.repeat(10):
                    build.play("qubit", build.square(duration="50ns", amplitude="100mV"))
        """
        body = OpSequence(items=[])
        rep = Repetition(count=count, body=body)

        # Add to parent context if it exists
        if self._context_stack:
            parent = self._current_context()
            if isinstance(parent, OpSequence):
                parent.items.append(rep)
            elif isinstance(parent, Repetition | Iteration | Conditional):
                parent.body.items.append(rep)
            elif isinstance(parent, Schedule):
                # For schedules, we need SchedRepetition not Repetition
                sched_rep = SchedRepetition(count=count, body=Schedule(items=[]))
                parent.items.append(ScheduledOperation(op=sched_rep))
                self._context_stack.append(sched_rep)
                try:
                    yield sched_rep  # type: ignore[misc]
                finally:
                    self._context_stack.pop()
                return

        self._context_stack.append(rep)
        try:
            yield rep
        finally:
            self._context_stack.pop()

    def var_decl(
        self,
        name: str,
        dtype: Literal["bool", "int", "float", "complex"],
        *,
        shape: tuple[int, ...] | None = None,
        unit: str | None = None,
    ) -> None:
        """Declare a variable for use in the current context.

        Variables should be declared before they are used in iterations or conditionals.
        The declaration specifies the variable's data type, optional shape (for arrays),
        and optional unit for dimensional consistency.

        :param name: Name of the variable (must be a valid identifier)
        :param dtype: Data type of the variable ("bool", "int", "float", or "complex")
        :param shape: Optional shape for array variables (e.g., (10,) for 1D array)
        :param unit: Optional unit string (e.g., "mV", "ns", "GHz") for the variable

        Examples

        .. code-block:: python

            with build.sequence():
                # Declare a float variable for amplitude with unit
                build.var_decl("amp", "float", unit="mV")

                # Declare an integer variable for iteration
                build.var_decl("count", "int")

                # Declare a complex array variable
                build.var_decl("iq_data", "complex", shape=(100,))
        """
        var_decl = VariableDecl(name=name, dtype=dtype, shape=shape, unit=unit)
        self._add_to_sequence(var_decl)

    @contextmanager
    def for_loop(
        self,
        var: VariableRefLike | list[VariableRefLike],
        items: Iterable[Any] | Range | LinSpace,
    ) -> Iterator[Iteration]:
        """Context manager for building an iteration (for loop).

        :param var: Variable reference(s) for the loop variable(s)
        :param items: Range, LinSpace, or iterable to iterate over

        :yield: The iteration being built

        Examples

        .. code-block:: python

            with build.sequence():
                with build.for_loop("i", range(0, 100, 10)):
                    build.set_frequency("qubit", build.var("i"))
        """
        body = OpSequence(items=[])
        iter_obj = Iteration(var=var, items=items, body=body)

        # Add to parent context if it exists
        if self._context_stack:
            parent = self._current_context()
            if isinstance(parent, OpSequence):
                parent.items.append(iter_obj)
            elif isinstance(parent, Repetition | Iteration | Conditional):
                parent.body.items.append(iter_obj)
            elif isinstance(parent, Schedule):
                # For schedules, we need SchedIteration not Iteration
                sched_iter = SchedIteration(var=var, items=items, body=Schedule(items=[]))
                parent.items.append(ScheduledOperation(op=sched_iter))
                self._context_stack.append(sched_iter)
                try:
                    yield sched_iter  # type: ignore[misc]
                finally:
                    self._context_stack.pop()
                return

        self._context_stack.append(iter_obj)
        try:
            yield iter_obj
        finally:
            self._context_stack.pop()

    @contextmanager
    def if_condition(self, var: VariableRefLike) -> Iterator[Conditional]:
        """Context manager for building a conditional block.

        :param var: Variable reference for the condition

        :yield: The conditional being built

        Examples

        .. code-block:: python

            with build.sequence():
                with build.if_condition("result"):
                    build.play("qubit", build.square(duration="50ns", amplitude="100mV"))
        """
        body = OpSequence(items=[])
        cond = Conditional(var=var, body=body)

        # Add to parent context if it exists
        if self._context_stack:
            parent = self._current_context()
            if isinstance(parent, OpSequence):
                parent.items.append(cond)
            elif isinstance(parent, Repetition | Iteration | Conditional):
                parent.body.items.append(cond)
            elif isinstance(parent, Schedule):
                # For schedules, we need SchedConditional not Conditional
                sched_cond = SchedConditional(var=var, body=Schedule(items=[]))
                parent.items.append(ScheduledOperation(op=sched_cond))
                self._context_stack.append(sched_cond)
                try:
                    yield sched_cond  # type: ignore[misc]
                finally:
                    self._context_stack.pop()
                return

        self._context_stack.append(cond)
        try:
            yield cond
        finally:
            self._context_stack.pop()

    @contextmanager
    def measure_if(
        self,
        drive_channel: ChannelRefLike,
        readout_channel: ChannelRefLike,
        raw_var: VariableRefLike,
        result_var: VariableRefLike,
        *,
        threshold: ThresholdLike,
        duration: DurationLike,
        amplitude: AmplitudeLike,
        integration: IntegrationType | Literal["full", "demod"] = "full",
        phase: PhaseLike | None = None,
        scale_cos: float = 1.0,
        scale_sin: float = 1.0,
        rotation: PhaseLike = 0,
        compare: ComparisonModeLike = ">=",
        project: ComplexToRealProjectionModeLike = "real",
        **schedule_params: Unpack[ScheduleParams],
    ) -> Iterator[Conditional]:
        """Measure, discriminate, and create a conditional block in one call.

        This is a convenience context manager that combines :meth:`measure_and_discriminate`
        with :meth:`if_condition`. It performs a measurement, discriminates the result,
        and opens a conditional block that executes if the discrimination result is true.

        :param drive_channel: Channel to play measurement pulse on
        :param readout_channel: Channel to record from
        :param raw_var: Variable to store the raw measurement result
        :param result_var: Variable to store the discriminated binary result
        :param threshold: Threshold value for discrimination
        :param duration: Measurement duration
        :param amplitude: Measurement pulse amplitude
        :param integration: Integration type for recording
        :param phase: Phase for demod integration
        :param scale_cos: Cosine scaling for demod integration
        :param scale_sin: Sine scaling for demod integration
        :param rotation: Phase rotation for discrimination
        :param compare: Comparison operator for discrimination
        :param project: Complex-to-real projection mode for discrimination
        :param schedule_params: Additional scheduling parameters (for schedules)

        :yield: The conditional being built

        Examples

        .. code-block:: python

            with build.sequence():
                # Measure, discriminate, and execute conditionally
                with build.measure_if(
                    "drive", "readout", "raw", "state", "0.5mV",
                    duration="1us", amplitude="50mV"
                ):
                    # This block executes if state is true
                    build.play("qubit", build.square(duration="50ns", amplitude="100mV"))
        """
        # Perform measurement and discrimination
        self.measure_and_discriminate(
            drive_channel,
            readout_channel,
            raw_var,
            result_var,
            threshold=threshold,
            duration=duration,
            amplitude=amplitude,
            integration=integration,
            phase=phase,
            scale_cos=scale_cos,
            scale_sin=scale_sin,
            rotation=rotation,
            compare=compare,
            project=project,
            **schedule_params,
        )

        # Open conditional block using the discriminated result
        with self.if_condition(result_var) as cond:
            yield cond

    # ============================================================================
    # Pulse creation helpers
    # ============================================================================

    def square(
        self,
        *,
        duration: DurationLike,
        amplitude: AmplitudeLike,
        rise_time: DurationLike | None = None,
        fall_time: DurationLike | None = None,
    ) -> SquarePulse:
        """Create a square pulse.

        :param duration: Pulse duration
        :param amplitude: Pulse amplitude
        :param rise_time: Optional rise time
        :param fall_time: Optional fall time

        :return: Square pulse definition

        Examples

        .. code-block:: python

            pulse = build.square(duration="10us", amplitude="100mV")
        """
        return SquarePulse(
            duration=duration,
            amplitude=amplitude,
            rise_time=rise_time,
            fall_time=fall_time,
        )

    def sine(
        self,
        *,
        duration: DurationLike,
        amplitude: AmplitudeLike,
        frequency: FrequencyLike,
        to_frequency: FrequencyLike | None = None,
    ) -> SinePulse:
        """Create a sine pulse.

        :param duration: Pulse duration
        :param amplitude: Pulse amplitude
        :param frequency: Start frequency
        :param to_frequency: Optional end frequency for chirp

        :return: Sine pulse definition

        Examples

        .. code-block:: python

            pulse = build.sine(duration="20us", amplitude="50mV", frequency="5GHz")
        """
        return SinePulse(
            duration=duration,
            amplitude=amplitude,
            frequency=frequency,
            to_frequency=to_frequency,
        )

    def external_pulse(
        self,
        function: str,
        *,
        duration: DurationLike,
        amplitude: AmplitudeLike,
        params: dict[str, Any] | None = None,
    ) -> ExternalPulse:
        """Create an external pulse reference.

        :param function: Fully qualified function name
        :param duration: Pulse duration
        :param amplitude: Pulse amplitude
        :param params: Additional parameters for the pulse function

        :return: External pulse definition

        Examples

        .. code-block:: python

            pulse = build.external_pulse("my_lib.gaussian", duration="10us", amplitude="100mV")
        """
        return ExternalPulse(
            function=function,
            duration=duration,
            amplitude=amplitude,
            params=params,
        )

    def arbitrary_pulse(
        self,
        samples: list[float] | list[complex],
        *,
        duration: DurationLike,
        amplitude: AmplitudeLike,
        interpolation: str | None = None,
        time_points: list[float] | None = None,
    ) -> ArbitrarySampledPulse:
        """Create an arbitrary sampled pulse.

        :param samples: Normalized waveform samples
        :param duration: Pulse duration
        :param amplitude: Pulse amplitude
        :param interpolation: Interpolation method
        :param time_points: Time points for samples

        :return: Arbitrary pulse definition

        Examples

        .. code-block:: python

            pulse = build.arbitrary_pulse([0, 1, 1, 0], duration="10us", amplitude="100mV")
        """
        return ArbitrarySampledPulse(
            samples=samples,
            duration=duration,
            amplitude=amplitude,
            interpolation=interpolation,
            time_points=time_points,
        )

    # ============================================================================
    # Reference helpers
    # ============================================================================

    def var(self, name: str) -> VariableRef:
        """Create a variable reference.

        :param name: Variable name

        :return: Variable reference

        Examples

        .. code-block:: python

            freq_var = build.var("frequency")
        """
        return VariableRef(var=name)

    def channel(self, name: str) -> ChannelRef:
        """Create a channel reference.

        :param name: Channel name

        :return: Channel reference

        Examples

        .. code-block:: python

            ch = build.channel("qubit_1")
        """
        return ChannelRef(channel=name)

    def pulse_ref(self, name: str) -> PulseRef:
        """Create a pulse reference.

        :param name: Pulse name

        :return: Pulse reference

        Examples

        .. code-block:: python

            p = build.pulse_ref("pi_pulse")
        """
        return PulseRef(pulse_name=name)

    # ============================================================================
    # Channel operations
    # ============================================================================

    def play(
        self,
        channel: ChannelRefLike,
        pulse: PulseType | PulseRefLike,
        *,
        scale_amp: float | complex | VariableRef | None = None,
        cond: VariableRefLike | None = None,
        **schedule_params: Unpack[ScheduleParams],
    ) -> OperationToken | None:
        """Play a pulse on a channel.

        :param channel: Channel to play on
        :param pulse: Pulse to play
        :param scale_amp: Optional amplitude scaling
        :param cond: Optional condition variable
        :param schedule_params: Additional scheduling parameters (for schedules)

        :return: Operation token if in schedule context, :obj:`None` if in sequence context

        Examples

        .. code-block:: python

            # In sequence
            build.play("ch1", build.square(duration="10us", amplitude="100mV"))

            # In schedule with positioning
            op = build.play("ch1", build.square(duration="10us", amplitude="100mV"),
                          ref_op=previous_op, ref_pt="end")
        """
        op = Play(channel=channel, pulse=pulse, scale_amp=scale_amp, cond=cond)

        context = self._current_context()
        if isinstance(context, Schedule):
            return self._add_to_schedule(op, **schedule_params)
        else:
            self._add_to_sequence(op)
            return None

    def wait(
        self,
        *channels: ChannelRefLike,
        duration: DurationLike,
        **schedule_params: Unpack[ScheduleParams],
    ) -> OperationToken | None:
        """Add wait operation on channel(s).

        :param channels: Channels to wait on
        :param duration: Wait duration
        :param schedule_params: Additional scheduling parameters (for schedules)

        :return: Operation token if in schedule context, :obj:`None` if in sequence context

        Examples

        .. code-block:: python

            build.wait("ch1", duration="5us")
            build.wait("ch1", "ch2", duration="10us")
        """
        op = Wait(*channels, duration=duration)  # type: ignore[arg-type]

        context = self._current_context()
        if isinstance(context, Schedule):
            return self._add_to_schedule(op, **schedule_params)
        else:
            self._add_to_sequence(op)
            return None

    def barrier(
        self,
        *channels: ChannelRefLike,
        **schedule_params: Unpack[ScheduleParams],
    ) -> OperationToken | None:
        """Add barrier (synchronization) on channel(s).

        :param channels: Channels to synchronize
        :param schedule_params: Additional scheduling parameters (for schedules)

        :return: Operation token if in schedule context, :obj:`None` if in sequence context

        Examples

        .. code-block:: python

            build.barrier("ch1", "ch2", "ch3")
        """
        op = Barrier(*channels)

        context = self._current_context()
        if isinstance(context, Schedule):
            return self._add_to_schedule(op, **schedule_params)
        else:
            self._add_to_sequence(op)
            return None

    def set_frequency(
        self,
        channel: ChannelRefLike,
        frequency: FrequencyLike | VariableRefLike,
        **schedule_params: Unpack[ScheduleParams],
    ) -> OperationToken | None:
        """Set channel frequency.

        :param channel: Channel to set frequency on
        :param frequency: Frequency to set
        :param schedule_params: Additional scheduling parameters (for schedules)

        :return: Operation token if in schedule context, :obj:`None` if in sequence context

        Examples

        .. code-block:: python

            build.set_frequency("qubit", "5GHz")
        """
        op = SetFrequency(channel=channel, frequency=frequency)

        context = self._current_context()
        if isinstance(context, Schedule):
            return self._add_to_schedule(op, **schedule_params)
        else:
            self._add_to_sequence(op)
            return None

    def shift_frequency(
        self,
        channel: ChannelRefLike,
        frequency: FrequencyLike | VariableRefLike,
        **schedule_params: Unpack[ScheduleParams],
    ) -> OperationToken | None:
        """Shift channel frequency.

        :param channel: Channel to shift frequency on
        :param frequency: Frequency shift amount
        :param schedule_params: Additional scheduling parameters (for schedules)

        :return: Operation token if in schedule context, :obj:`None` if in sequence context

        Examples

        .. code-block:: python

            build.shift_frequency("qubit", "100MHz")
        """
        op = ShiftFrequency(channel=channel, frequency=frequency)

        context = self._current_context()
        if isinstance(context, Schedule):
            return self._add_to_schedule(op, **schedule_params)
        else:
            self._add_to_sequence(op)
            return None

    def set_phase(
        self,
        channel: ChannelRefLike,
        phase: PhaseLike | VariableRefLike,
        **schedule_params: Unpack[ScheduleParams],
    ) -> OperationToken | None:
        """Set channel phase.

        :param channel: Channel to set phase on
        :param phase: Phase to set
        :param schedule_params: Additional scheduling parameters (for schedules)

        :return: Operation token if in schedule context, :obj:`None` if in sequence context

        Examples

        .. code-block:: python

            build.set_phase("qubit", "90deg")
        """
        op = SetPhase(channel=channel, phase=phase)

        context = self._current_context()
        if isinstance(context, Schedule):
            return self._add_to_schedule(op, **schedule_params)
        else:
            self._add_to_sequence(op)
            return None

    def shift_phase(
        self,
        channel: ChannelRefLike,
        phase: PhaseLike | VariableRefLike,
        **schedule_params: Unpack[ScheduleParams],
    ) -> OperationToken | None:
        """Shift channel phase.

        :param channel: Channel to shift phase on
        :param phase: Phase shift amount
        :param schedule_params: Additional scheduling parameters (for schedules)

        :return: Operation token if in schedule context, :obj:`None` if in sequence context

        Examples

        .. code-block:: python

            build.shift_phase("qubit", "45deg")
        """
        op = ShiftPhase(channel=channel, phase=phase)

        context = self._current_context()
        if isinstance(context, Schedule):
            return self._add_to_schedule(op, **schedule_params)
        else:
            self._add_to_sequence(op)
            return None

    def record(
        self,
        channel: ChannelRefLike,
        var: VariableRefLike,
        *,
        duration: DurationLike,
        integration: IntegrationType | Literal["full", "demod"] = "full",
        phase: PhaseLike | None = None,
        scale_cos: float = 1.0,
        scale_sin: float = 1.0,
        **schedule_params: Unpack[ScheduleParams],
    ) -> OperationToken | None:
        """Record (acquire) data from a channel.

        :param channel: Channel to record from
        :param var: Variable to store the result
        :param duration: Recording duration
        :param integration: Integration type ("full" or "demod")
        :param phase: Phase for demod integration
        :param scale_cos: Cosine scaling for demod integration
        :param scale_sin: Sine scaling for demod integration
        :param schedule_params: Additional scheduling parameters (for schedules)

        :return: Operation token if in schedule context, :obj:`None` if in sequence context

        Examples

        .. code-block:: python

            build.record("readout", "result", duration="1us", integration="demod")
        """
        # Handle integration type
        if isinstance(integration, str):
            if integration == "full":
                integration_obj: IntegrationType = FullIntegration()
            elif integration == "demod":
                integration_obj = DemodIntegration(phase=phase, scale_cos=scale_cos, scale_sin=scale_sin)  # type: ignore[arg-type]
            else:
                raise ValueError(f"Invalid integration type: {integration}")
        else:
            integration_obj = integration

        op = Record(channel=channel, var=var, duration=duration, integration=integration_obj)  # type: ignore[arg-type]

        context = self._current_context()
        if isinstance(context, Schedule):
            return self._add_to_schedule(op, **schedule_params)
        else:
            self._add_to_sequence(op)
            return None

    def discriminate(
        self,
        target: VariableRefLike,
        source: VariableRefLike,
        threshold: ThresholdLike,
        *,
        rotation: PhaseLike = 0,
        compare: ComparisonModeLike = ">=",
        project: ComplexToRealProjectionModeLike = "real",
        **schedule_params: Unpack[ScheduleParams],
    ) -> OperationToken | None:
        """Discriminate a measurement result to a binary outcome.

        This operation applies a rotation, projects complex data to real, and compares
        against a threshold to produce a boolean result.

        :param target: Variable to store the discrimination result (boolean)
        :param source: Source variable containing the measurement data
        :param threshold: Threshold value for comparison
        :param rotation: Phase rotation to apply before projection (default: 0)
        :param compare: Comparison operator (default: ">=")
        :param project: Complex-to-real projection mode (default: "real")
        :param schedule_params: Additional scheduling parameters (for schedules)

        :return: Operation token if in schedule context, :obj:`None` if in sequence context

        Examples

        .. code-block:: python

            # Simple discrimination with default parameters
            build.discriminate("bit", "measurement", threshold=0.5)

            # With rotation and different comparison
            build.discriminate("bit", "measurement", threshold=0.5,
                             rotation="45deg", compare=">", project="abs")
        """
        op = Discriminate(
            target=target,
            source=source,
            threshold=threshold,
            rotation=rotation,  # type: ignore[arg-type]
            compare=compare,  # type: ignore[arg-type]
            project=project,  # type: ignore[arg-type]
        )

        context = self._current_context()
        if isinstance(context, Schedule):
            return self._add_to_schedule(op, **schedule_params)
        else:
            self._add_to_sequence(op)
            return None

    def store(
        self,
        key: str,
        source: VariableRefLike,
        *,
        mode: Literal["last", "average", "count", "trace"] = "last",
        **schedule_params: Unpack[ScheduleParams],
    ) -> OperationToken | None:
        """Store a variable value for later retrieval.

        This operation stores the value of a variable to persistent storage
        for analysis after the pulse program completes. Different storage modes
        allow for averaging, counting, or trace capture.

        :param key: Storage key for retrieving the data
        :param source: Source variable to store
        :param mode: Storage mode - how to aggregate multiple values
        :param schedule_params: Additional scheduling parameters (for schedules)

        :return: Operation token if in schedule context, :obj:`None` if in sequence context

        Examples

        .. code-block:: python

            # Store single measurement
            build.store("result", "measurement", mode="last")

            # Average multiple measurements
            with build.for_loop("i", range(100)):
                build.measure("drive", "readout", "m", duration="1us", amplitude="50mV")
                build.store("avg_result", "m", mode="average")
        """
        op = Store(key=key, source=source, mode=mode)  # type: ignore[arg-type]

        context = self._current_context()
        if isinstance(context, Schedule):
            return self._add_to_schedule(op, **schedule_params)
        else:
            self._add_to_sequence(op)
            return None

    def measure(
        self,
        drive_channel: ChannelRefLike,
        readout_channel: ChannelRefLike,
        result_var: VariableRefLike,
        *,
        duration: DurationLike,
        amplitude: AmplitudeLike,
        integration: IntegrationType | Literal["full", "demod"] = "full",
        phase: PhaseLike | None = None,
        scale_cos: float = 1.0,
        scale_sin: float = 1.0,
        **schedule_params: Unpack[ScheduleParams],
    ) -> OperationToken | None:
        """Perform a measurement (simultaneous play + record).

        This is a convenience function that creates a square pulse play operation
        and a record operation that execute simultaneously.

        :param drive_channel: Channel to play measurement pulse on
        :param readout_channel: Channel to record from
        :param result_var: Variable to store the measurement result
        :param duration: Measurement duration
        :param amplitude: Measurement pulse amplitude
        :param integration: Integration type for recording
        :param phase: Phase for demod integration
        :param scale_cos: Cosine scaling for demod integration
        :param scale_sin: Sine scaling for demod integration
        :param schedule_params: Additional scheduling parameters (for schedules)

        :return: Operation token if in schedule context, :obj:`None` if in sequence context

        Examples

        .. code-block:: python

            build.measure("qubit", "readout", "result",
                         duration="1us", amplitude="50mV", integration="demod")
        """
        # Create measurement pulse
        meas_pulse = self.square(duration=duration, amplitude=amplitude)

        context = self._current_context()

        if isinstance(context, Schedule):
            # In schedule: create both operations with same timing
            play_token = self.play(drive_channel, meas_pulse, **schedule_params)

            # Record starts at the same time as play
            record_params = schedule_params.copy()
            if play_token:
                record_params["ref_op"] = play_token.name
                record_params["ref_pt"] = "start"
                record_params["ref_pt_new"] = "start"
                record_params["rel_time"] = 0

            return self.record(
                readout_channel,
                result_var,
                duration=duration,
                integration=integration,
                phase=phase,
                scale_cos=scale_cos,
                scale_sin=scale_sin,
                **record_params,
            )
        else:
            # In sequence: add operations sequentially
            # Note: In a true measurement, play and record should be simultaneous
            # This requires the backend to handle the timing correctly
            self.play(drive_channel, meas_pulse)
            self.record(
                readout_channel,
                result_var,
                duration=duration,
                integration=integration,
                phase=phase,
                scale_cos=scale_cos,
                scale_sin=scale_sin,
            )
            return None

    def measure_and_discriminate(
        self,
        drive_channel: ChannelRefLike,
        readout_channel: ChannelRefLike,
        raw_var: VariableRefLike,
        result_var: VariableRefLike,
        *,
        threshold: ThresholdLike,
        duration: DurationLike,
        amplitude: AmplitudeLike,
        integration: IntegrationType | Literal["full", "demod"] = "full",
        phase: PhaseLike | None = None,
        scale_cos: float = 1.0,
        scale_sin: float = 1.0,
        rotation: PhaseLike = 0,
        compare: ComparisonModeLike = ">=",
        project: ComplexToRealProjectionModeLike = "real",
        **schedule_params: Unpack[ScheduleParams],
    ) -> OperationToken | None:
        """Perform measurement and discrimination in one call.

        This is a convenience function that combines :meth:`measure` and
        :meth:`discriminate` operations. It performs a measurement, stores
        the raw result, discriminates it to a binary outcome, and returns
        a token for the discrimination operation.

        :param drive_channel: Channel to play measurement pulse on
        :param readout_channel: Channel to record from
        :param raw_var: Variable to store the raw measurement result
        :param result_var: Variable to store the discriminated binary result
        :param threshold: Threshold value for discrimination
        :param duration: Measurement duration
        :param amplitude: Measurement pulse amplitude
        :param integration: Integration type for recording
        :param phase: Phase for demod integration
        :param scale_cos: Cosine scaling for demod integration
        :param scale_sin: Sine scaling for demod integration
        :param rotation: Phase rotation for discrimination
        :param compare: Comparison operator for discrimination
        :param project: Complex-to-real projection mode for discrimination
        :param schedule_params: Additional scheduling parameters (for schedules)

        :return: Operation token if in schedule context, :obj:`None` if in sequence context

        Examples

        .. code-block:: python

            # Measure and discriminate in one call
            build.measure_and_discriminate(
                "drive", "readout", "raw_data", "qubit_state", "0.5mV",
                duration="1us", amplitude="50mV"
            )

            # Then use the result in a conditional
            with build.if_condition("qubit_state"):
                build.play("qubit", build.square(duration="50ns", amplitude="100mV"))
        """
        # Perform measurement
        self.measure(
            drive_channel,
            readout_channel,
            raw_var,
            duration=duration,
            amplitude=amplitude,
            integration=integration,
            phase=phase,
            scale_cos=scale_cos,
            scale_sin=scale_sin,
            **schedule_params,
        )

        # Discriminate the result
        return self.discriminate(
            target=result_var,
            source=raw_var,
            threshold=threshold,
            rotation=rotation,
            compare=compare,
            project=project,
            **schedule_params,
        )


# Global builder instance for convenience
build = Builder()
