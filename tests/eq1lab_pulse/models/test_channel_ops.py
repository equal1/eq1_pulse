from cmath import pi as π
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models.basic_types import Duration, Frequency, Magnitude, Phase
from eq1_pulse.models.channel_ops import (
    Barrier,
    ChannelOp,
    CompensateDC,
    DemodIntegration,
    FullIntegration,
    Play,
    Record,
    SetFrequency,
    SetPhase,
    ShiftFrequency,
    ShiftPhase,
    Trace,
    Wait,
)
from eq1_pulse.models.pulse_types import SquarePulse
from eq1_pulse.models.reference_types import ChannelRef, ExternalRef, VariableRef


def test_barrier_creation():
    barrier = Barrier(ChannelRef("ch1"), ChannelRef("ch2"))
    assert barrier.channels == [ChannelRef("ch1"), ChannelRef("ch2")]

    barrier = Barrier("ch1", "ch2")
    assert barrier.channels == [ChannelRef("ch1"), ChannelRef("ch2")]


def test_wait_operation():
    wait_op = Wait(channels=[ChannelRef("ch1"), ChannelRef("ch2")], duration=Duration(s=10e-9))
    assert wait_op.channels == [ChannelRef("ch1"), ChannelRef("ch2")]
    assert wait_op.duration == Duration(s=10e-9)

    wait_op = Wait(channels=["ch3", "ch4"], duration=Duration(s=15e-9))
    assert wait_op.channels == [ChannelRef("ch3"), ChannelRef("ch4")]
    assert wait_op.duration == Duration(s=15e-9)

    wait_op = Wait("ch1", "ch2", duration={"ns": 10})
    assert wait_op.channels == [ChannelRef("ch1"), ChannelRef("ch2")]
    assert wait_op.duration == Duration(s=10e-9)


def test_play_operation():
    pulse = SquarePulse(duration=Duration(s=20e-9), amplitude={"V": 0.5})
    play = Play(channel="ch1", pulse=pulse, scale_amp=1.0)
    assert play.channel.channel == "ch1"
    assert play.pulse == pulse
    assert play.scale_amp == 1.0


def test_record_operation():
    record = Record(channel="ch1", var="result", duration=Duration(s=100e-9), integration=FullIntegration())
    assert record.channel.channel == "ch1"
    assert record.var.var == "result"
    assert record.integration.integration_type == "full"


def test_demod_integration():
    demod = DemodIntegration(phase=Phase(deg=90), scale_cos=1, scale_sin=-1)
    assert demod.phase == Phase(deg=90)
    assert demod.scale_cos == 1
    assert demod.scale_sin == -1


def test_set_frequency():
    set_freq = SetFrequency(channel="ch1", frequency=Frequency(Hz=5e6))
    assert set_freq.channel.channel == "ch1"
    assert set_freq.frequency == Frequency(Hz=5e6)


def test_shift_frequency():
    shift_freq = ShiftFrequency(channel="ch1", frequency=Frequency(Hz=5e6))
    assert shift_freq.channel.channel == "ch1"
    assert shift_freq.frequency == Frequency(Hz=5e6)


def test_barrier_json_serialization():
    barrier = Barrier("ch1", "ch2")
    barrier_json = barrier.model_dump_json()
    barrier_loaded = Barrier.model_validate_json(barrier_json)
    assert barrier_loaded == barrier


def test_wait_json_serialization():
    wait = Wait("ch1", "ch2", duration=Duration(s=10e-9))
    wait_json = wait.model_dump_json()
    wait_loaded = Wait.model_validate_json(wait_json)
    assert wait_loaded == wait


def test_invalid_play_validation():
    with pytest.raises(ValidationError):
        Play(channel="ch1", pulse=None)  # type: ignore[arg-type]


def test_trace_operation():
    trace = Trace(channel="ch1", var="trace_data", duration=Duration(s=1e-6), integration=DemodIntegration())
    assert trace.channel.channel == "ch1"
    assert trace.var.var == "trace_data"
    assert isinstance(trace.integration, DemodIntegration)


def test_compensate_dc():
    comp = CompensateDC(channel="ch1", duration=Duration(s=50e-9), max_amp=Magnitude(V=0.5))
    assert comp.channel.channel == "ch1"
    assert isinstance(comp.duration, Duration)
    assert comp.duration.ns == 50
    assert isinstance(comp.max_amp, Magnitude)
    assert comp.max_amp.V == 0.5

    # Test reset case
    reset_comp = CompensateDC(channel="ch1", duration=None)
    assert reset_comp.duration is None


def test_compensate_dc_alt():
    comp = CompensateDC("ch1", duration={"ns": 50}, max_amp={"V": 0.5})
    assert comp.channel.channel == "ch1"
    assert isinstance(comp.duration, Duration)
    assert comp.duration.ns == 50
    assert isinstance(comp.max_amp, Magnitude)
    assert comp.max_amp.V == 0.5

    # Test reset case
    reset_comp = CompensateDC(channel="ch1", duration=None)
    assert reset_comp.duration is None


def test_compensate_dc_var():
    comp = CompensateDC("ch1", duration={"var": "dur"}, max_amp={"V": 0.5})
    assert comp.channel.channel == "ch1"
    assert isinstance(comp.duration, VariableRef)
    assert comp.duration.var == "dur"
    assert isinstance(comp.max_amp, Magnitude)
    assert comp.max_amp.V == 0.5


def test_phase_operations():
    set_phase = SetPhase(channel="ch1", phase=Phase(rad=0.25 * π))
    assert set_phase.channel.channel == "ch1"
    assert set_phase.phase == Phase(rad=0.25 * π)

    shift_phase = ShiftPhase(channel="ch1", phase=Phase(rad=0.1 * π))
    assert shift_phase.channel.channel == "ch1"
    assert shift_phase.phase == Phase(rad=0.1 * π)


def test_record_with_demod_validation():
    record_dict = {
        "channel": "ch1",
        "var": "result",
        "duration": {"s": 100e-9},
        "integration": {"integration_type": "demod", "phase": {"deg": 45}},
        "op_type": "record",
    }
    record: Any = TypeAdapter(ChannelOp).validate_python(record_dict)
    assert isinstance(record, Record)
    assert isinstance(record.integration, DemodIntegration)
    assert record.integration.phase == Phase(deg=45)


def test_record_with_demod_serialization():
    original = Record(
        channel="ch1", var="result", duration=Duration(s=100e-9), integration=DemodIntegration(phase=Phase(deg=45))
    )
    serialized = original.model_dump_json()
    deserialized: Any = TypeAdapter(ChannelOp).validate_json(serialized)
    assert isinstance(deserialized, Record)
    assert deserialized == original


def test_trace_with_full_integration():
    trace = Trace(channel="ch1", var="trace_data", duration=Duration(s=1e-6), integration=FullIntegration())
    assert trace.channel.channel == "ch1"
    assert isinstance(trace.integration, FullIntegration)
    assert trace.integration.integration_type == "full"


def test_trace_with_full_integration_validation():
    trace_dict = {
        "channel": "ch1",
        "var": "trace_data",
        "duration": {"s": 1e-6},
        "integration": {"integration_type": "full"},
        "op_type": "trace",
    }
    trace: Any = TypeAdapter(ChannelOp).validate_python(trace_dict)
    assert isinstance(trace, Trace)
    assert isinstance(trace.integration, FullIntegration)


def test_trace_with_full_integration_serialization():
    original = Trace(channel="ch1", var="trace_data", duration=Duration(s=1e-6), integration=FullIntegration())
    serialized = original.model_dump_json()
    deserialized: Any = TypeAdapter(ChannelOp).validate_json(serialized)
    assert isinstance(deserialized, Trace)
    assert deserialized == original


def test_wait_duration_accepts_external_ref():
    wait_op = Wait("ch1", "ch2", duration=ExternalRef(ext="q0.dur"))
    assert isinstance(wait_op.duration, ExternalRef)
    assert wait_op.duration.ext == "q0.dur"


def test_play_cond_and_scale_amp_accept_external_ref():
    pulse = SquarePulse(duration=Duration(s=20e-9), amplitude={"V": 0.5})
    play = Play(channel="ch1", pulse=pulse, scale_amp=ExternalRef(ext="q0.scale"), cond=ExternalRef(ext="q0.cond"))
    assert isinstance(play.scale_amp, ExternalRef)
    assert isinstance(play.cond, ExternalRef)


def test_set_frequency_accepts_external_ref():
    set_freq = SetFrequency(channel="ch1", frequency=ExternalRef(ext="q0.freq"))
    assert isinstance(set_freq.frequency, ExternalRef)


def test_phase_operations_accept_external_ref():
    set_phase = SetPhase(channel="ch1", phase=ExternalRef(ext="q0.phase"))
    assert isinstance(set_phase.phase, ExternalRef)


def test_record_duration_accepts_external_ref():
    record = Record(channel="ch1", var="result", duration=ExternalRef(ext="q0.dur"), integration=FullIntegration())
    assert isinstance(record.duration, ExternalRef)


def test_compensate_dc_accepts_external_ref():
    comp = CompensateDC("ch1", duration=ExternalRef(ext="q0.dur"))
    assert isinstance(comp.duration, ExternalRef)


def test_record_var_rejects_external_ref():
    with pytest.raises(ValidationError):
        Record(
            channel="ch1",
            var=ExternalRef(ext="q0"),  # type: ignore[arg-type]
            duration=Duration(s=100e-9),
            integration=FullIntegration(),
        )


def test_trace_var_rejects_external_ref():
    with pytest.raises(ValidationError):
        Trace(channel="ch1", var=ExternalRef(ext="q0"), duration=Duration(s=1e-6))  # type: ignore[arg-type]


def test_record_time_of_flight_accepts_variable_and_external_ref():
    record = Record(
        channel="ch1",
        var="result",
        duration=Duration(s=100e-9),
        integration=FullIntegration(),
        time_of_flight=VariableRef("tof"),
    )
    assert isinstance(record.time_of_flight, VariableRef)

    record = Record(
        channel="ch1",
        var="result",
        duration=Duration(s=100e-9),
        integration=FullIntegration(),
        time_of_flight=ExternalRef(ext="q0.tof"),
    )
    assert isinstance(record.time_of_flight, ExternalRef)

    # Still accepts its literal form.
    record = Record(
        channel="ch1",
        var="result",
        duration=Duration(s=100e-9),
        integration=FullIntegration(),
        time_of_flight=Duration(ns=20),
    )
    assert isinstance(record.time_of_flight, Duration)


def test_trace_time_of_flight_accepts_variable_and_external_ref():
    trace = Trace(channel="ch1", var="trace_data", duration=Duration(s=1e-6), time_of_flight=VariableRef("tof"))
    assert isinstance(trace.time_of_flight, VariableRef)

    trace = Trace(channel="ch1", var="trace_data", duration=Duration(s=1e-6), time_of_flight=ExternalRef(ext="q0.tof"))
    assert isinstance(trace.time_of_flight, ExternalRef)


def test_compensate_dc_max_amp_accepts_variable_and_external_ref():
    comp = CompensateDC("ch1", duration=Duration(s=50e-9), max_amp=VariableRef("amp"))
    assert isinstance(comp.max_amp, VariableRef)

    comp = CompensateDC("ch1", duration=Duration(s=50e-9), max_amp=ExternalRef(ext="q0.max_amp"))
    assert isinstance(comp.max_amp, ExternalRef)

    # Still accepts its literal form.
    comp = CompensateDC("ch1", duration=Duration(s=50e-9), max_amp=Magnitude(V=0.5))
    assert isinstance(comp.max_amp, Magnitude)


def test_demod_integration_phase_accepts_variable_and_external_ref():
    demod = DemodIntegration(phase=VariableRef("phi"))
    assert isinstance(demod.phase, VariableRef)

    demod = DemodIntegration(phase=ExternalRef(ext="q0.phase"))
    assert isinstance(demod.phase, ExternalRef)


def test_demod_integration_scale_cos_sin_accept_variable_and_external_ref():
    demod = DemodIntegration(scale_cos=VariableRef("sc"), scale_sin=ExternalRef(ext="q0.ss"))
    assert isinstance(demod.scale_cos, VariableRef)
    assert isinstance(demod.scale_sin, ExternalRef)


def test_demod_integration_scale_cos_sin_default_still_elided():
    """Widening scale_cos/scale_sin to accept a SymbolRef must not perturb LeanModel's default elision."""
    demod = DemodIntegration()
    assert demod.model_dump() == {"integration_type": "demod"}
