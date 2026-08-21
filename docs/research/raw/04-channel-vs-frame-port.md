# Raw Perplexity result — 04: Flat `channel` vs OpenPulse `port` + `frame`

> Model: `sonar-reasoning-pro` (reason, high search context). Query: what a flat-channel
> abstraction loses vs OpenPulse's port/frame split; quantify-scheduler's `(port, clock)` pair;
> comparison with Braket, LabOne Q, Qibolab, old Qiskit Pulse; recommendation for a portable
> JSON IR.
>
> Citation URL list truncated to primary sources at the end.

---

## Bottom line

A flat `channel` identifier is adequate only if it means **"one independently phase-coherent
signal stream"**, not merely **"one physical connector."** It conflates at least three different
resources:

1. a physical I/O path (`port`);
2. an independently timed and phase-tracked carrier (`frame` or oscillator);
3. a scheduling/serialization constraint.

That conflation is lossy when several carriers share one I/O path, or when one carrier must
retain state across separately defined calibrations.

OpenPulse makes the distinction explicit: a `frame` is attached to one `port`, has mutable
`frequency` and `phase`, and carries an implicit `time` cursor advanced by `play`, `capture`,
`delay`, and `barrier`.

---

## 1. What a flat channel loses

| Lost distinction                      | Concrete consequence                                                                                       |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Physical path versus carrier          | Cannot say two logical signals use the same DAC/ADC connector while having different carrier frequencies.  |
| Carrier identity versus waveform identity | Cannot preserve an oscillator/frame's accumulated phase independently of the pulse being played.        |
| Per-frame time cursor                 | Cannot naturally express two timelines on one port.                                                        |
| Persistent state                      | Cannot identify the same phase/frequency state across separate calibration invocations unless reconstructed externally. |
| Concurrent signal composition         | Cannot represent two independent plays that overlap on one port and must be mixed or summed by the backend. |

A flat model can simulate some of these by manufacturing many channel names —
`q0_readout_5.1GHz`, `q1_readout_5.2GHz`, and so on — but then the shared physical-port
relationship is no longer in the IR. It has become an undocumented convention in the channel
names or hardware configuration.

### Concrete cases

| Case                                                     | OpenPulse expression                                                                                                                                                                       | What the flat model cannot express directly                                                                                                                                    |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **(a) Frequency-multiplexed readout**                    | Several frames such as `r0_frame`, `r1_frame`, `r2_frame` can all be attached to one ADC/DAC `port`, each with its own resonator frequency. Multiple frames per port are explicitly permitted, subject to backend hardware limits. | A single `channel` normally denotes one stream. It cannot state "these three logical readout signals share `adc0` but have independent carrier frequencies, phase state, and capture timing." Separate flat channels hide the sharing; one flat channel loses the frequency/frame distinction. |
| **(b) Independent `01` and `12` phase tracking**         | Two frames can share a drive port but represent different transitions: `frame_ge = newframe(d0, f01, 0)` and `frame_ef = newframe(d0, f12, 0)`. `shift_phase(frame_ge, θ)` changes only the `01` frame. OpenPulse phase and frequency are properties of the frame, not the port. | A channel-level `shift_phase(channel, θ)` has ambiguous scope. If the channel is the shared drive line, it incorrectly shifts both transitions; if separate channels are invented, the shared-line relation is lost. |
| **(c) Frame reuse/persistence across `defcal` invocations** | A frame declared in a global `cal` block can be referenced by multiple `defcal` bodies. Its state is retained: modifications made through one use can affect later uses of the same frame.  | A flat channel usually supplies only a name and perhaps static configuration. It does not identify a persistent mutable phase accumulator. Recreating a channel at each export or `defcal` call risks resetting phase or assigning a fresh cursor. |
| **(d) Two frame plays on one port that must be summed**  | Two independent frame tracks can target the same port. Their envelopes may be combined explicitly with OpenPulse `sum(wf1, wf2)` (pointwise addition); alternatively, a backend can schedule two carrier streams and sum in its signal path. | A single flat channel does not distinguish "two independent producers of one physical output" from "two conflicting users of one serialized channel." It cannot carry the composition requirement — sum, mix, reject overlap, or allocate separate hardware NCOs — without an additional multi-track or mixer abstraction. |

### Important qualification about case (d)

OpenPulse does **not** universally guarantee unlimited simultaneous frames on a port. The
specification leaves the number of frames per port to the hardware/backend. Therefore, the
portable meaning should be: "These are independent frame signals targeting the same physical
port, with an explicit composition policy."

```json
{"port": "dac0", "composition": "sum", "tracks": ["frame_ge", "frame_ef"]}
```

or it might be compiled into a single pre-mixed waveform. The IR should not silently assume
that every backend can perform dynamic multi-frame summation.

---

## 2. Quantify Scheduler: the `port` + `clock` pair

Quantify Scheduler's closest equivalent to an OpenPulse frame is a **port-clock pair**,
conventionally written `(port, clock)`. Quantify deliberately separates physical position from
frequency-space identity. Its documentation states that pulses are applied to a `port` at a
frequency specified by a `clock`; both are represented as strings.

### Exact API symbols and semantics

| Quantify symbol           | Type/API form                                                            | Semantics                                                                                                            |
| ------------------------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| `port`                    | `str` pulse/acquisition field, e.g. `"q0:mw"`                            | Logical or physical output/input location. It identifies *where* the operation is applied. Not itself the carrier frequency. |
| `clock`                   | `str` pulse/acquisition field, e.g. `"q0.ge"`                            | Name of the frequency/phase resource used to modulate the operation. The name should identify the *purpose* of the clock, not necessarily encode its numeric frequency. |
| `ClockResource`           | `quantify_scheduler.resources.ClockResource(name, freq, phase=0)`        | A physical/modulation clock with frequency `freq` in Hz and starting phase `phase` in **degrees**.                    |
| `BasebandClockResource`   | `quantify_scheduler.resources.BasebandClockResource(name)`               | Special global clock identity for unmodulated real-valued baseband operation. Documented identity is `cl0.baseband`.  |
| Port-clock key            | usually `"portclock"` or a `(port, clock)` combination in backend config | The hardware compiler maps each pair to a sequencer, mixer, NCO, latency correction, distortion correction, etc.      |

```python
from quantify_scheduler import Schedule
from quantify_scheduler.resources import ClockResource
from quantify_scheduler.operations.pulse_library import SquarePulse

sched = Schedule("example")
sched.add_resource(ClockResource(name="q0.ge", freq=5.0e9, phase=0))  # phase in degrees
sched.add(SquarePulse(amp=0.1, duration=40e-9, port="q0:mw", clock="q0.ge"))
```

Quantify's Qblox documentation explicitly requires the `port` and `clock` combination to be
unique for each configured port-clock resource/sequencer.

### Frequency and baseband behavior

A zero-frequency clock is interpreted as baseband in the scheduler's model; the pulse is assumed
real-valued. For an explicitly named baseband resource, `BasebandClockResource(name="cl0.baseband")`
identifies a virtual unmodulated clock. Conceptually similar to an OpenPulse frame whose carrier
frequency is zero, but not the same object model: `BasebandClockResource` is a special resource
identity rather than a stateful frame instance.

### How phase is tracked

```python
from quantify_scheduler.operations.pulse_library import (
    ShiftClockPhase, ResetClockPhase, SetClockFrequency,
)

sched.add(ShiftClockPhase(phase_shift=45, clock="q0.ge"))  # degrees
sched.add(ResetClockPhase(clock="q0.ge"))
sched.add(SetClockFrequency(clock="q0.ge", frequency=5.1e9))
```

### Difference from an OpenPulse frame

| Property            | OpenPulse `frame`                  | Quantify `(port, clock)`                                     |
| ------------------- | ---------------------------------- | ------------------------------------------------------------ |
| Physical destination| `frame.port`                       | `port: str`                                                  |
| Carrier frequency   | `frame.frequency`                  | `ClockResource.freq`                                         |
| Initial phase       | `frame.phase`                      | `ClockResource.phase`                                        |
| Mutable phase       | `set_phase`, `shift_phase`         | `ResetClockPhase`, `ShiftClockPhase`                         |
| Mutable frequency   | `set_frequency`, `shift_frequency` | `SetClockFrequency`                                          |
| Timing cursor       | Implicit per-frame `.time`         | Schedule/operation timing, not a first-class per-clock cursor |
| Persistent identity | Named frame object/reference       | Named clock resource, backend-dependent state semantics      |
| Capture target      | A frame can provide capture timing | Acquisition uses port/clock resources and scheduler timing   |

Quantify's pair is the right conceptual decomposition, but it is not a perfect semantic
replacement for an OpenPulse frame. OpenPulse makes the frame's time cursor part of the language
semantics; Quantify normally schedules operations in a schedule timeline and uses the clock
primarily for modulation/resource identity.

---

## 3. Comparison with other APIs

| System/API                | Physical resource                                                    | Carrier/frequency object                                                                 | Phase semantics                                                                          | Time granularity / cursor                                | Model classification                       |
| ------------------------- | -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------ |
| **AWS Braket Pulse**      | `Port(name, dt=...)`; port string identifies the connector, `dt` is the minimum sample-time increment | `Frame(frame_id=..., port=..., frequency=..., phase=...)`; fields `frame.port`, `frame.frequency`, `frame.phase` | Frame-level `set_phase(frame, ...)`, `shift_phase(frame, ...)`; analogous frequency ops in `PulseSequence` | Frame acts as a clock whose time advances when used     | Explicit frame/port model, very close to OpenPulse |
| **Zurich LabOne Q**       | Logical signal lines, mapped through a `DeviceSetup` to physical instrument channels | `SignalCalibration.oscillator` (modulation frequency + mode); `local_oscillator` (center frequency) | `Oscillator(frequency=..., modulation_type=...)`; `play()` supports `increment_oscillator_phase`, `set_oscillator_phase`; `reset_oscillator_phase` | Experiment sections and signal-line timing, not an exposed frame cursor | Explicit logical-signal plus oscillator/calibration model |
| **LabOne Q hardware osc** | Physical channel/signal line selected by calibration                  | `Oscillator(..., modulation_type=ModulationType.HARDWARE)` — continuously running digital oscillator on the instrument | Phase is instrument oscillator state; resets and increments explicit                     | Hardware-dependent execution timing                      | Persistent hardware NCO-like resource      |
| **LabOne Q software osc** | Same logical signal line                                              | `Oscillator(..., modulation_type=ModulationType.SOFTWARE)` — carrier written point-by-point into waveforms | Phase compiled into waveform data                                                        | Waveform/sample based                                    | Carrier is not a separately addressable runtime hardware oscillator |
| **Qibolab**               | `Channel` objects connect qubit operations to instrument ports; platform-wide IDs, may be shared among qubits | Frequency commonly a channel configuration or `Pulse.frequency`; an LO can be associated with a channel | Pulses expose `relative_phase`; channel/pulse config supplies frequency and phase        | `Pulse` carries `start`, duration, frequency, phase, amplitude; `PulseSequence` contains `(channel_id, pulse)` tuples | More channel-oriented; frequency/phase are pulse/channel parameters rather than a persistent frame |
| **Old Qiskit Pulse**      | Flat typed channels: `DriveChannel(i)`, `MeasureChannel(i)`, `ControlChannel(i)`, receive-only `AcquireChannel(i)` | Frequency/phase were mutable properties of transmit channels via `SetFrequency`, `ShiftFrequency`, `ShiftPhase` | Channel-level phase accumulator (enabling virtual-Z), but no explicit frame object       | Integer sample timing via backend `dt`; channel scheduling | Flat typed-channel model                   |

### AWS Braket specifically

```python
from braket.pulse import Frame, Port

port0 = Port("channel_0", dt=1e-9)
readout_frame = Frame(frame_id="r0_measure", port=port0, frequency=5e9, phase=0)
```

Braket's documentation describes a frame as both a clock and a stateful carrier, and a port as
the connector abstraction with its own sample interval.

### Zurich LabOne Q specifically

```python
from laboneq.dsl.calibration import SignalCalibration, Oscillator
from laboneq.dsl.enums import ModulationType

cal = SignalCalibration(
    oscillator=Oscillator(uid="q0_ge_osc", frequency=100e6,
                          modulation_type=ModulationType.HARDWARE),
)
# or software modulation with an explicit LO:
cal = SignalCalibration(
    oscillator=Oscillator(uid="q0_ge_osc", frequency=100e6,
                          modulation_type=ModulationType.SOFTWARE),
    local_oscillator=Oscillator(uid="q0_ge_lo", frequency=5.0e9),
)
```

Richer than a flat channel, although oscillator ownership and sharing are expressed through
calibration and instrument constraints rather than an OpenPulse-like `frame.port` field.

### Old Qiskit Pulse specifically

`DriveChannel`, `MeasureChannel`, and `ControlChannel` were transmit channels; `AcquireChannel`
was receive-only. Instructions: `Play`, `SetFrequency`, `ShiftFrequency`, `ShiftPhase`, `Acquire`.
The major limitation is that frequency and phase state belonged to the flat transmit channel. A
`DriveChannel(0)` therefore behaves much more like a single default *frame* attached to a signal
line than like a physical *port* capable of hosting multiple independent frames.

---

## 4. Recommendation for a portable JSON pulse IR

### Recommended model

Use **explicit frames internally**, while allowing a convenient channel-oriented shorthand.

```json
{
  "ports": {
    "dac0": {"direction": "output", "dt": 1e-09},
    "adc0": {"direction": "input",  "dt": 1e-09}
  },
  "frames": {
    "q0_ge": {"port": "dac0", "frequency_hz": 5000000000.0, "phase_rad": 0.0},
    "q0_ef": {"port": "dac0", "frequency_hz": 4700000000.0, "phase_rad": 0.0},
    "q0_ro": {"port": "adc0", "frequency_hz": 6500000000.0, "phase_rad": 0.0}
  },
  "operations": [
    {"op": "play",        "frame": "q0_ge", "waveform": "x90"},
    {"op": "shift_phase", "frame": "q0_ge", "phase_rad": 1.5707963267948966}
  ]
}
```

Export to OpenPulse is then direct:

```text
port dac0;
frame q0_ge = newframe(dac0, 5.0e9, 0.0);
frame q0_ef = newframe(dac0, 4.7e9, 0.0);
play(q0_ge, x90);
shift_phase(q0_ge, pi/2);
```

### Tradeoff table

| Design                                          | Advantages                                                                                                        | Costs / failure modes                                                                                                                                                        |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Flat channels only; resolve to frames at export** | Small schema; easy for simple hardware; resembles old Qiskit Pulse and basic Qibolab usage; users need not understand NCO/frame identity. | Exporter must infer frequency, phase lifetime, timing cursor, sharing, and composition. May silently reset phase between `defcal` calls or merge signals that should remain independent. Round-tripping OpenPulse is lossy. |
| **Explicit `port` + `frame`**                   | Faithfully represents OpenPulse; naturally supports multiplexing, independent transition phases, persistent state, capture frames, per-frame timing. | More objects and references; backend validation needed because hardware may limit frame count per port or disallow concurrent frames.                                          |
| **Single object with embedded frequency/phase** | Convenient JSON and close to a pulse "channel."                                                                    | Ambiguous whether frequency/phase are persistent resource state or per-play overrides; cannot cleanly represent two persistent carriers on one port.                            |
| **Hybrid port + clock/frame designation**       | Retains a simple operation syntax while preserving decomposition; closely resembles Quantify's `(port, clock)`.     | Requires explicit rules for whether the clock has a cursor, whether phase is persistent, and how frame identity maps to OpenPulse.                                              |

### Best middle ground

Use a required physical `port` plus an optional named `clock`/`frame`:

```json
{"op": "play", "port": "dac0", "clock": "q0.ge", "waveform": "x90"}
```

```json
{"clocks": {"q0.ge": {"frequency_hz": 5000000000.0, "phase_rad": 0.0, "persistent": true}}}
```

Rules:

| Rule             | Recommendation                                                                          |
| ---------------- | --------------------------------------------------------------------------------------- |
| `port`           | Always identify the physical I/O resource.                                              |
| `clock`/`frame`  | Identify an independently phase/frequency-tracked signal.                               |
| Omitted clock    | Permit only as shorthand for a default frame/clock supplied by hardware configuration.  |
| Persistent state | Make it explicit; do not infer persistence from a string name alone.                    |
| Timing           | Store either a frame cursor or an explicit schedule time, and define the conversion rule.|
| Shared port      | Permit multiple clocks/frames to reference one port.                                    |
| Composition      | Require an explicit policy: `sum`, `serialize`, `reject_overlap`, or `backend_defined`. |
| Export           | Generate one OpenPulse `frame` per persistent IR frame, not one frame per pulse.        |
| Hardware config  | Use it for physical mapping and capabilities, not to reconstruct semantic information the source IR omitted. |

### Final recommendation

For an IR that must export reliably to OpenPulse, **model frames explicitly**. Keep flat
channels only as a user-facing shorthand or compatibility view. The practical compromise is:

```text
operation target = (port, optional named clock/frame)
```

with the named clock/frame carrying frequency, phase, persistence, and — if the IR needs
OpenPulse-equivalent behavior — an independent timing cursor. This gives the compactness of
Quantify's `port` + `clock` pair while retaining enough information to export correctly to
OpenPulse, Braket `Frame`/`Port`, LabOne Q oscillators, and simpler flat-channel backends.

---

## Primary citations

- https://openqasm.com/versions/3.0/language/openpulse.html
- https://openqasm.com/language/openpulse.html
- https://arxiv.org/pdf/2104.14722
- https://openqasm.com/language/pulses.html
- https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/resources/index.html
- https://quantify-os.org/docs/quantify-scheduler/dev/user/user_guide.html
- https://quantify-os.org/docs/quantify-scheduler/v0.28.1/autoapi/quantify_scheduler/operations/pulse_library/index.html
- https://docs.aws.amazon.com/braket/latest/developerguide/braket-pulse-control.html
- https://amazon-braket-sdk-python.readthedocs.io/en/stable/_apidoc/braket.pulse.pulse_sequence.html
- https://docs.zhinst.com/labone_q_user_manual/core/reference/dsl/calibration.html
- https://docs.zhinst.com/labone_q_user_manual/core/functionality_and_concepts/03_sections_pulses/concepts/06_pulses_amplitude_and_phase.html
- https://qibo.science/qibolab/stable/main-documentation/qibolab.html
- https://docs.quantum.ibm.com/api/qiskit/0.19/qiskit.pulse.channels
- https://github.com/openqasm/openqasm/issues/577 — `extern port` / `extern frame`
